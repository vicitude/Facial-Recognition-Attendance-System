# Spec 索引: SPEC-001 签到/签退人员管理系统

> 4 份子 spec,各含 spec.md / tasks.md / checklist.md / self-check.md。
> 原 SPEC-001 v1.0.0 已被本组子 spec 取代,保留于 `_LEGACY.md` 备查。

## 子 Spec 一览

| 子 Spec | 范围 | 任务 | 三件套 | 自检 |
|---|---|---|---|---|
| [SPEC-001-A 基础层](01-foundation/spec.md) | 项目结构 + INI + utils + models + db | T-001 ~ T-104 | [spec](01-foundation/spec.md) / [tasks](01-foundation/tasks.md) / [checklist](01-foundation/checklist.md) | [15 题](01-foundation/self-check.md) |
| [SPEC-001-B 业务服务层](02-service/spec.md) | ScheduleService + EmployeeService + CheckService + AdminService | T-201 ~ T-204 | [spec](02-service/spec.md) / [tasks](02-service/tasks.md) / [checklist](02-service/checklist.md) | [15 题](02-service/self-check.md) |
| [SPEC-001-C UI 层](03-ui/spec.md) | Login + Main + Employees + CheckIn + Records + 入口 | T-301 ~ T-306 | [spec](03-ui/spec.md) / [tasks](03-ui/tasks.md) / [checklist](03-ui/checklist.md) | [15 题](03-ui/self-check.md) |
| [SPEC-001-D 测试与验证](04-test/spec.md) | 单元测试 + 集成测试 + CI 静态检查 | T-401 ~ T-404 | [spec](04-test/spec.md) / [tasks](04-test/tasks.md) / [checklist](04-test/checklist.md) | [15 题](04-test/self-check.md) |

## 实施顺序

```text
A (基础层) ──> B (服务层) ──> C (UI 层) ──> D (测试与验证)
```

每完成一份子 spec,在其 checklist 全部 ✅ 后,新建 `decisions/NNN-v1-XXX-shipped.md` 闭环该阶段;然后进入下一份。

## 跨子 Spec 引用

- A 的 utils.py 异常类被 B/C 全部 import: 见 B §0 / C §0
- A 的 ConfigService 加载结果被 B/C 全部消费: 见 B §0 / C §0
- A 的 peewee Models 被 B/C 全部消费: 见 B §0 / C §0
- D 的测试同时覆盖 A/B/C: 见 D §0
