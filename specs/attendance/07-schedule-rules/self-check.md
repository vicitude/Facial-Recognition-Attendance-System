# SPEC-003 落地前自检（15+2）

> 执行时间：2026-11-14；执行人：DSH coding agent。
> 结论仅覆盖文档门禁；代码实施必须继续遵守本文件及 `spec.md`。

## 6.1 严格对齐（5题）
- [x] Q1 字段名：Schedule、EmployeeSchedule、CheckRecord 字段已在 §1/§4/§5/§7 明确。
- [x] Q2 函数签名：§3 固化 ScheduleService、CheckService 五个服务契约签名。
- [x] Q3 枚举值：状态枚举与 `duplicate_policy="reject"` 已固定。
- [x] Q4 测试用例 ID：UT-SCH-001~006 已在 §7 与 tasks/checklist 绑定。
- [x] Q5 默认值/校验器/错误码：字段默认值、时间约束、错误码已写入 §4/§6。

## 6.2 细节遗漏（5题）
- [x] Q6 10段结构：§0 至 §9 全部存在。
- [x] Q7 每段示例：§1术语、§2 Gherkin、§3签名、§4白班字段、§5决策规则、§6错误码、§7测试行、§8验证方法、§9环境约束均有具体例子。
- [x] Q8 CI门禁：§0声明代码/测试同步与测试门禁；`tasks.md` T-SCH-010 固化回归任务。
- [x] Q9 假设约束：MySQL、时区、活体边界、旧 middle 数据保留已明确。
- [x] Q10 变更日志：§9记录 2026-11-14、v1.0.0 和变更摘要。

## 6.3 自由发挥空间（5题）
- [x] Q11 黑名单模糊词：已用脚本扫描 `spec.md`，无命中；`tasks.md` 与 `checklist.md` 也无模糊词。
- [x] Q12 Optional触发条件：`schedule_id=None` 仅在单班次自动选择前的服务入口使用；`confirmed_early_leave=False` 表示尚未确认早退；两者在 §3/§5 有行为说明。
- [x] Q13 非功能验证方法：§8 明确 pytest 规则测试、迁移前后历史读取验证。
- [x] Q14 类比约束：未使用“类似/参考”作为实施依据。
- [x] Q15 实施动作：模型迁移、多对多关系、跨午夜计算、UI选择、补签和回归均已在 tasks.md 与 checklist.md 固化。

## 6.4 Properties（2题）
- [x] Q16 关键行为已定义 P-SCH-01、P-SCH-02、P-SCH-03，并给出可判定行为。
- [x] Q17 Properties 已在 §5 回链到业务规则；UT-SCH-001、UT-SCH-004、UT-SCH-005 及 T-SCH-010 负责自动化装订，当前状态：规则、服务、班次 UI 与管理员补签契约测试已完成；完整 Qt 离屏回归仍受既有 `attendance/ui_utils.py:41 show_error` Windows access violation 阻塞。

## 结论
- 总计通过：17/17。
- 总计失败：0。
- 允许进入实施阶段：是。
- 说明：本文档门禁通过不代表功能已实现；实施完成前不得将 SPEC-003 标记为已实现。
