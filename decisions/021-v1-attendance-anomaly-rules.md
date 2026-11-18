# 决策 021：考勤异常规则阶段

## 状态
实现中；规则层与服务层聚焦回归已通过，完整 Qt 回归待补。

## 范围
在现有签到服务中增加重复打卡、签到签退顺序、班次迟到/早退判定，并将状态与异常原因保存到 `check_records`；不接入活体，不修改 `ui.py`、`recognition.py`、`get_name.py`。

## 实现
- `attendance/attendance_rules.py` 提供纯函数 `decide_check` 和不可变 `RuleDecision`。
- `CheckRecord` 新增 `status`、`anomaly_reason` 字段。
- `CheckService.create_record` 在写入前判定；非法顺序和重复打卡拒绝，迟到/早退允许写入异常状态。
- 记录界面增加状态、异常原因列。
- 数据库初始化通过 `SHOW COLUMNS` 后按缺失字段执行普通 `ALTER TABLE ADD COLUMN`，兼容不支持 `ADD COLUMN IF NOT EXISTS` 的 MySQL 版本。

## 验证
- `tests/test_attendance_rules.py`：2 passed。
- `tests/test_services.py`：21 passed。
- 完整测试与 Qt 离屏回归尚未宣称通过。
