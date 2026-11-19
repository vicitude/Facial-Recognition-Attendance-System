# SPEC-003 验收清单

> 版本：v1.0.0；所有条目必须有测试或可审计证据。

## 数据与迁移
- [ ] CHK-SCH-001 `schedules` 包含 `check_in_start`、`late_end`、`check_out_end`、`duplicate_policy`、`is_active`，旧记录可读取。
- [ ] CHK-SCH-002 `employee_schedules` 组合唯一，历史 Employee 单 schedule 数据可迁移为绑定关系。
- [ ] CHK-SCH-003 `check_records` 包含 `schedule_id`、`adjusted_by`，历史 `middle` 行保留。
- [ ] CHK-SCH-004 默认白班为 09:00–18:00，签到提前起点、迟到截止、最晚签退值明确写入 seed。

## 规则与服务
- [x] CHK-SCH-005 所有区间端点包含，边界测试全部通过。
- [x] CHK-SCH-006 跨午夜班次 22:00–次日06:00 的签到、签退周期判定通过。
- [ ] CHK-SCH-007 迟到截止后、最晚签退后、签到窗口前均拒绝。
- [x] CHK-SCH-008 重复签到和重复签退固定拒绝。
- [x] CHK-SCH-009 签到班次选择结果被签退复用。
- [ ] CHK-SCH-010 绑定重叠班次返回 `SCHEDULE_CONFLICT`，不写入部分绑定。
- [ ] CHK-SCH-011 早退取消不写记录，确认写 `early_leave`。
- [ ] CHK-SCH-012 管理员补签到/补签退写 `manual_adjusted` 且不要求原因。

## UI
- [ ] CHK-SCH-013 普通员工界面只提供签到、签退。
- [ ] CHK-SCH-014 多班次签到显示选择；单班次自动；无班次显示拒绝原因。
- [ ] CHK-SCH-015 管理员可新增、编辑、停用班次。
- [ ] CHK-SCH-016 员工多班次绑定提供冲突提示。
- [ ] CHK-SCH-017 记录页显示班次、状态、异常原因、补录标记。

## 回归与红线
- [ ] CHK-SCH-018 不修改 `ui.py`、`recognition.py`、`get_name.py`。
- [ ] CHK-SCH-019 不接入活体检测。
- [ ] CHK-SCH-020 不执行 drop/truncate/清空历史数据。
- [ ] CHK-SCH-021 聚焦测试、既有服务测试和可运行的 UI 契约测试通过；无法运行的 Qt 测试必须单独报告。
