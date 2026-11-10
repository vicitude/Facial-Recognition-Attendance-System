# SPEC-001 · 签到/签退人员管理系统(原版,已被子 spec 取代)

> **状态**: 已被 01-foundation / 02-service / 03-ui / 04-test 4 份子 spec 取代
> **保留原因**: 决策溯源;`decisions/001-v1-init-workspace.md` 引用本文件
> **拆分时间**: 2026-08-24
> **拆分人**: agent (响应用户要求)
>
> 本文件不应再修改;若需变更,请先修改对应子 spec 并在 `_INDEX.md` 追加变更说明。

---

## 0. 文档头与元数据

- **文件路径**: `/specs/attendance/_LEGACY.md` (原 `/specs/attendance/spec.md`)
- **拆分前版本**: v1.0.0
- **拆分后子 spec**:
  - [SPEC-001-A 基础层](01-foundation/spec.md) — 覆盖原 §3.1 ConfigService / §3.2 Database / §3.7 AuthUtils / §4.5 Models / §6.2 utils 异常
  - [SPEC-001-B 业务服务层](02-service/spec.md) — 覆盖原 §3.3 EmployeeService / §3.4 ScheduleService / §3.5 CheckService / §3.6 AdminService / §5.1 决策表
  - [SPEC-001-C UI 层](03-ui/spec.md) — 覆盖原 §3.8 UI 事件契约 / §5.2 状态机
  - [SPEC-001-D 测试与验证](04-test/spec.md) — 覆盖原 §7 覆盖矩阵 / §8 非功能

---

## 1. 术语表

> 已并入各子 spec §1 术语表,本节不再展开。

| 术语 | 迁移至 |
|---|---|
| 管理员 / Admin | A §1 / B §1 / D §1 |
| 班次 / Schedule | A §1 / B §1 |
| 员工 / Employee | A §1 / B §1 |
| 打卡记录 / CheckRecord | A §1 / B §1 |
| CheckType 枚举 | A §1 / B §1 |
| 异常类层级 | A §1 |

---

## 2. 用户故事

> 已按 Gherkin 拆分至各子 spec,不再保留总集。

---

## 3. 服务层 API

> 已拆分至 A §3 (ConfigService / Database / AuthUtils) 与 B §3 (EmployeeService / ScheduleService / CheckService / AdminService) 与 C §3 (UI 事件契约)。

---

## 4. 数据模型

> 字段定义已拆分至 A §4 (JSON Schema + 字段映射表),引用其即可。

---

## 5. 业务规则

> 决策表已拆分至 B §5;UI 状态机已拆分至 C §5。

---

## 6. 错误处理

> 错误码字典完整保留于 A §6 + B §6 + C §6 (按子 spec 适用部分);汇总于 C §6.7(引用)。

---

## 7. 测试用例覆盖矩阵(汇总)

| TC ID | 子 Spec | 类型 |
|---|---|---|
| TC-ATT-001 | D §7 | 集成 |
| TC-ATT-002 | D §7 | 集成 |
| TC-ATT-003 | D §7 | 集成 |
| TC-ATT-004 | D §7 | 集成 |
| TC-ATT-005 | D §7 | 集成 |
| TC-ATT-006 | D §7 | 集成 |
| TC-ATT-007 | D §7 | 集成 |
| TC-ATT-008 | D §7 | 集成 |
| TC-ATT-009 | D §7 | 集成 |
| TC-ATT-010 | D §7 | 集成 |
| TC-ATT-011 | D §7 | 集成 |
| TC-ATT-012 | D §7 | 集成 |
| TC-ATT-013 | D §7 | 集成 |
| TC-ATT-014 | D §7 | 集成 |
| TC-ATT-015 | B §7 | 单元 |
| TC-ATT-016 | B §7 | 单元 |
| TC-ATT-017 | B §7 | 单元 |
| TC-ATT-018 | B §7 | 单元 |
| TC-ATT-019 | C §7 | UI 烟测 |
| TC-ATT-020 | B §7 | 单元 |
| TC-ATT-021 | B §7 | 单元 |
| TC-ATT-022 | D §7 | 集成 |
| TC-ATT-023 | A §7 | 集成 |
| TC-ATT-024 | A §7 | 单元 |
| TC-ATT-025 | A §7 | 单元 |

---

## 8. 非功能性需求

> 已拆分至 A §8 / B §8 / C §8 / D §8;汇总于 D §8(引用)。

---

## 9. 假设、约束与变更日志

### 9.1 假设

> 已拆分至 A §9.1 / B §9.1 / C §9.1;完整版在 A §9.1。

### 9.2 约束

> 已拆分至 A §9.2 / B §9.2 / C §9.2;完整版在 A §9.2。

### 9.3 变更日志

| 日期 | 版本 | 变更说明 | 关联 Commit |
|------|------|----------|-------------|
| 2026-08-24 | v1.0.0 | 初始版本, 覆盖登录/人员管理/实时签到/打卡查询 4 大功能 | (待提交) |
| 2026-08-24 | v1.0.0 → 拆分 | 按用户要求拆分为 4 份子 spec (A 基础 / B 服务 / C UI / D 测试) | (待提交) |
