# SPEC-003: 可配置班次与考勤规则

> 状态：已批准；版本：v1.0.0
> 关联代码：`attendance/models.py`、`attendance/services.py`、`attendance/attendance_rules.py`、`attendance/ui_checkin.py`、`attendance/ui_employees.py`、`attendance/ui_records.py`、`attendance/db.py`
> 约束：不修改 `ui.py`、`recognition.py`、`get_name.py`；活体检测不作为本规范行为。

## 0. 文档头与元数据
本规范是班次、员工多班次绑定、签到签退和管理员补签的唯一行为契约。代码和测试修改必须同步更新本目录三件套。测试门禁：规则单元测试、服务层测试和相关 UI 契约测试必须通过；不得以未运行的完整 Qt 回归宣称完成。

## 1. 术语表与统一语言
|术语|英文名|类型|定义|代码映射|数据库映射|示例|
|---|---|---|---|---|---|---|
|班次|Schedule|聚合根|管理员配置的工作时间规则|`Schedule`|`schedules`|白班|
|签到窗口|CheckInWindow|值对象|提前签到区间，结束点等于上班时间|`check_in_start`|`schedules.check_in_start`|08:00–09:00|
|迟到窗口|LateWindow|值对象|上班时间至迟到截止时间，端点包含|`late_end`|`schedules.late_end`|09:00–12:00|
|签退窗口|CheckOutWindow|值对象|下班时间至最晚签退时间，端点包含|`check_out_end`|`schedules.check_out_end`|18:00–23:00|
|重复打卡|Duplicate|枚举状态|同一班次周期再次签到或签退|`duplicate`|`check_records.status`|拒绝|
|迟到|Late|枚举状态|在迟到窗口签到|`late`|`check_records.status`|09:30|
|早退|EarlyLeave|枚举状态|下班时间前确认签退|`early_leave`|`check_records.status`|17:30|
|管理员补签|AdminAdjusted|枚举状态|管理员直接写入签到或签退|`manual_adjusted`|`check_records.status`|补签到|

## 2. 用户故事与验收场景（Gherkin）
```gherkin
功能: 可配置班次考勤
  场景: 班次窗口判定
    假设 白班签到窗口为08:00-09:00，迟到窗口为09:00-12:00，签退窗口为18:00-23:00
    当 员工在08:00签到
    那么 记录状态为normal
    当 员工在09:00签到
    那么 记录状态为normal
    当 员工在09:01签到
    那么 记录状态为late
    当 员工在12:01签到
    那么 请求被拒绝
  场景: 早退确认
    假设 下班时间为18:00
    当 员工在17:30点击签退
    那么 系统提示时间未到下班时间
    当 员工确认
    那么 写入early_leave记录
    当 员工取消
    那么 不写入记录
  场景: 多班次冲突
    假设 员工已绑定09:00-18:00班次
    当 管理员绑定13:00-22:00班次
    那么 保存被拒绝并提示时间冲突
  场景: 管理员补签
    假设 当前用户为管理员
    当 管理员补签到员工100001
    那么 写入manual_adjusted签到记录
```

## 3. 服务接口契约
本项目为 PyQt5 本地应用，无 HTTP API。服务契约：`ScheduleService.create(name, work_start, work_end, check_in_start, late_end, check_out_end, duplicate_policy, is_active) -> Schedule`；`ScheduleService.update(schedule_id, ...) -> Schedule`；`ScheduleService.disable(schedule_id) -> Schedule`；`ScheduleService.bind_employee(employee_id, schedule_ids) -> EmployeeSchedule`；`CheckService.create_record(employee_id, check_type, schedule_id=None, confirmed_early_leave=False) -> CheckRecord`；`CheckService.admin_adjust(admin_id, employee_id, check_type, schedule_id) -> CheckRecord`。

## 4. 数据模型与校验规则
`Schedule` 必填字段：`name:str<=50`、`work_start:time`、`work_end:time`、`check_in_start:time`、`late_end:time`、`check_out_end:time`、`duplicate_policy:str="reject"`、`is_active:bool=True`。时间端点均按循环 24 小时计算：`check_in_start` 必须在上班时间之前，`late_end` 必须位于上班时间之后（可跨午夜），`check_out_end` 必须不早于下班时间；禁止零长度工作/签到窗口。员工绑定关系为 `employee_schedules(employee_id, schedule_id)`，唯一组合；同一员工的有效班次时间段不得重叠，跨午夜班次按拆分后的两个日历片段检测。`CheckRecord` 增加 `schedule_id`、`adjusted_by`，状态枚举为 `normal, late, early_leave, duplicate, invalid_sequence, too_early, too_late, no_schedule, manual_adjusted`。

## 5. 业务规则与状态流转
- 所有时间端点均包含。
- 早于签到窗口拒绝；签到窗口内为normal；迟到窗口内为late；迟到窗口结束后拒绝。
- 下班时间至最晚签退时间允许正常签退；下班前必须先确认，确认后写early_leave；未确认不写入。
- 同一员工同一班次周期只能签到一次、签退一次；重复策略固定为`reject`。
- 周期以签到窗口开始的日历日期为 check_date；跨午夜窗口按绝对 datetime 比较，秒与微秒不能截断。签退根据最近一次未签退的签到记录确定班次和周期，忽略界面传入的其他班次；超出最晚签退时间拒绝，不跨周期补签退。
- create_record 未传 schedule_id 时，签到仅在唯一有效绑定时自动选择；多班次必须选择，无班次拒绝。所有入口执行同样窗口规则，不存在旧调用绕过。服务锁定员工行并在事务内检查/写入，防止并发重复。
- 补签使用当前时间与班次周期，绕过时间窗口和早退确认，但不绕过在职、启用班次、重复和签到签退顺序检查；必须记录实际管理员 adjusted_by。历史 middle 允许查询但不允许新增。
- 时间窗口从 check_in_start 展开：0 < 上班偏移 <= 迟到截止偏移 < 下班偏移 <= 最晚签退偏移 < 24小时。班次绑定按工作区间闭端点检测相交；班次编辑后也必须重新验证所有已绑定员工，不允许引入冲突。
- 员工多班次时签到前选择班次；只有一个班次自动选择；签退沿用签到记录班次；无班次拒绝。
- 管理员可新增、编辑、停用班次，可直接补签到/补签退，不要求原因，记录状态为manual_adjusted。
- 新流程不产生middle，历史middle只读保留。

Properties：P-SCH-01 任意有效班次的签到时间若小于check_in_start则必拒绝；P-SCH-02 任意同员工同周期第二次同类型打卡必拒绝；P-SCH-03 任意绑定班次对时间段相交则绑定必拒绝。

## 6. 错误处理与日志
错误码：`SCHEDULE_TIME_INVALID`、`SCHEDULE_CONFLICT`、`NO_SCHEDULE`、`TOO_EARLY`、`TOO_LATE`、`DUPLICATE_CHECK`、`INVALID_SEQUENCE`、`EARLY_LEAVE_CONFIRM_REQUIRED`。服务层抛出既有 `InternalError` 或对应领域异常，日志记录 action、employee_id、schedule_id、check_type、status；不记录人脸原图、向量或活体数据。

## 7. 测试矩阵
|需求|测试ID|状态|
|---|---|---|
|窗口端点包含|UT-SCH-001|未自动化|
|迟到与超时|UT-SCH-002|未自动化|
|早退确认|UT-SCH-003|未自动化|
|重复拒绝|UT-SCH-004|未自动化|
|班次冲突|UT-SCH-005|未自动化|
|管理员补签|UT-SCH-006|未自动化|

## 8. 非功能需求
班次规则纯逻辑测试不依赖 Qt 或摄像头；规则判定单次调用耗时目标小于10ms，以 pytest 基准测试验证。数据库迁移不得删除已有记录，以测试迁移前后历史记录可读性验证。

## 9. 假设、约束与变更日志
假设 MySQL 与现有 Peewee 配置一致；跨午夜班次使用本地系统时区；普通员工只能签到/签退，活体检测仍独立研究且不接入放行。变更日志：2026-11-14 v1.0.0，依据用户确认固化班次窗口、跨午夜、多班次和补签规则。
