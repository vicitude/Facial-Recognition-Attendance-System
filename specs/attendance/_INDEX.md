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
| [SPEC-003 可配置班次与考勤规则](07-schedule-rules/spec.md) | 班次窗口、跨午夜、多班次绑定、签到签退、补签 | T-SCH-001 ~ T-SCH-010 | [spec](07-schedule-rules/spec.md) / [tasks](07-schedule-rules/tasks.md) / [checklist](07-schedule-rules/checklist.md) | [15+2题](07-schedule-rules/self-check.md) |
| [SPEC-004 多人识别与结果稳定化](08-multi-face-recognition/spec.md) | 多人逐框匹配、重叠框去重、未知/异常状态 | T-MFR-001 ~ T-MFR-005 | [spec](08-multi-face-recognition/spec.md) / [tasks](08-multi-face-recognition/tasks.md) / [checklist](08-multi-face-recognition/checklist.md) | [自检](08-multi-face-recognition/self-check.md) |
| [SPEC-005 Windows地点校验](09-location-validation/spec.md) | 允许地点、半径、坐标距离与越界拒绝 | T-LOC-001 ~ T-LOC-005 | [spec](09-location-validation/spec.md) / [tasks](09-location-validation/tasks.md) / [checklist](09-location-validation/checklist.md) | [自检](09-location-validation/self-check.md) |
| [SPEC-006 班次签到地点配置](09-location-validation/spec.md) | 班次地点配置、Windows 定位与签到前地点判定 | T-LOC-001 ~ T-LOC-011 | [spec](09-location-validation/spec.md) / [tasks](09-location-validation/tasks.md) / [checklist](09-location-validation/checklist.md) | 已闭环（实机验收待执行） |

## 融合活体研究

[SPEC-007 三次眨眼融合活体](10-fused-liveness/spec.md)：独立研究与自动化已实现，默认挑战现为三次眨眼。真人已有单轮现场通过反馈，纸照/手机静态照正式验收未完成。见[现场步骤](10-fused-liveness/field-validation.md)。

[SPEC-008 活体签到试运行接入](11-liveness-checkin/spec.md)：默认关闭管理员会话开关、逐人新验证、员工模板与本轮身份双门禁，活体通过后走原班次/地点确认。自动化实现完成，系统内实机与攻击验收待执行，见[试运行操作](11-liveness-checkin/trial-guide.md)。

[SPEC-009 统一CUDA/CPU推理设备](12-inference-device/spec.md)：保留opencv4并升级CUDA；FaceNet/MiniFASNet设备一致，真实CPU/CUDA及143项专项通过，验证后已删除独立GPU环境。详见[验证记录](../../docs/research/Unified-CUDA-environment.md)。

[SPEC-010 彩色光响应辅助活体检测](13-color-light-liveness/spec.md)：开发中的屏幕彩光研究/试运行方案；默认关闭，四周变色且中央显示预览，与三次眨眼互斥，不改正式数据库。自动化专项已完成，现场验收尚未执行。详见[三件套与状态机](13-color-light-liveness/tasks.md)。

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
