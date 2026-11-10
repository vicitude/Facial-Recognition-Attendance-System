# 007 · SPEC-002 管理员账户管理（改密 + 多管理员）闭环（2026-08-24）

- **状态**: 活跃
- **关键词**: spec-002, admin, change-password, multi-admin, self-delete, last-admin, ui-tab, pytest, pyqt5
- **相关模块**: `attendance/utils.py` + `attendance/services.py` (B 层 T-601), `attendance/ui_change_password.py` + `attendance/ui_main.py` (C 层 T-602), `attendance/ui_admins.py` + `attendance/ui_main.py` (C 层 T-603), `tests/test_services.py` + `tests/test_ui_change_password.py` + `tests/test_ui_admins.py` + `tests/test_e2e.py` (D 层 T-601/T-602/T-603/T-604)

## 关联文档

- `AGENTS.md` §1（项目定位）、§2（当前入口）、§6（踩坑教训, L-007 新增）、§10（变更日志）
- `specs/attendance/05-admin-features/spec.md` v1.0.0（11 TC 方案 + 10 段结构 + 附录 15 题自检）
- `specs/attendance/05-admin-features/tasks.md`（T-601/T-602/T-603/T-604 任务拆解）
- `specs/attendance/05-admin-features/checklist.md`（验收清单, 见 §6.1 错误码表 + §7 11 个 TC 矩阵）
- `decisions/002-v1-foundation-shipped.md`（A 基础层, 12 smoke TC, T-601 前置）
- `decisions/003-v1-service-shipped.md`（B 服务层, 18 unit TC, T-601 前置）
- `decisions/004-v1-ui-shipped.md`（C UI 层, 18 UI TC, T-602/T-603 前置）
- `decisions/005-v1-test-shipped.md`（D 测试层, 11 TC, T-604 前置）
- `decisions/006-v1-bugfix-checkin-warning-loop.md`（任务 1 弹窗卡死循环修复, 沉淀 L-006, **不在本 spec 范围**）
- 闭环事实唯一来源：本文件

## 变化程度

- **新建 4 个文件**:
  - `attendance/ui_change_password.py`（T-602 产物, `ChangePasswordDialog` 类, 3 QLineEdit + 2 QPushButton, 改密端到端 UI 入口）
  - `attendance/ui_admins.py`（T-603 产物, `AdminsTab` + `AdminCreateDialog` 2 类, 内联 `_TITLE_MAP` 避免修改 ui_utils, 5 行自删保护逻辑）
  - `tests/test_ui_change_password.py`（T-602 产物, 5 个 UI TC: E01~E05, 沿用 L-002 + L-005 教训）
  - `tests/test_ui_admins.py`（T-603 产物, 3 个 UI TC: E06~E08, 沿用 L-002 + L-005 + L-007 教训）
- **修改 4 个文件**:
  - `attendance/utils.py`（T-601 产物, 追加 3 个异常类: `UsernameExists` / `LastAdminForbidden` / `SelfDeleteForbidden`）
  - `attendance/services.py`（T-601 产物, AdminService 追加 3 个方法: `create` / `list_all` / `delete`, 既有 `authenticate` / `change_password` / `ensure_default` 不变）
  - `attendance/ui_main.py`（T-602 + T-603 产物, 4 Tab 替代 3 Tab, 账户菜单 2 Action 替代 1 Action, 5 处增量共 18 行）
  - `tests/test_e2e.py`（T-603 + T-604 产物, D05/D06 写死 `count()==3` 改为 `4` + 加 AdminsTab 断言; D11 后追加 E11 改密端到端 TC, 67 行）
- **未触碰**:
  - `tests/conftest.py`（D 层 G-06 红线, 6 fixture 不变）
  - `attendance/services.py` 中既有 `authenticate` / `change_password` / `ensure_default`（B 层红线, 仅**新增**方法）
  - `attendance/ui_login.py`（C 层 LoginDialog 不变, 改密走新弹窗）
  - `attendance/ui_utils.py`（既有 `_TITLE_MAP` 不变, T-603 内联新增 `_TITLE_MAP` + `_show_admin_error`）
  - `recognition.py` / `get_name.py` / `ui.py`（A 层红线, 哈希不变）

## 摘要

按 SPEC-002 v1.0.0 落地 11 个 TC, 与既有 A 12 + B 18 + C 18 + D 11 共同构成完整测试矩阵, 合计 **58/58 PASSED, 0 回归, 0 flake**。

**实施前确认的关键决策**（与用户对齐, 6 项拍板）:

1. 任务 2 + 任务 3 走独立 spec (与任务 1 决策 006 解耦)
2. T-601 业务层 `AdminService.create` 入口加 `len(username) > 50` 校验, 抛 `InternalError(USERNAME_TOO_LONG)`, spec §6.1 同步补错误码
3. E-09 测试不硬编码 `admin_id=1/2`, 改用 `list_all()` 查实际对象, 避免 MySQL AutoField auto_increment 不重置导致 `get_by_id(2)` 找不到
4. E-08 业务规则按 Gherkin REQ-E-12 实施 (self-delete 优先, count=1 时同样自删保护, 走 `SELF_DELETE_FORBIDDEN` 而非 `LAST_ADMIN_FORBIDDEN`), spec §7 表格描述同步修正
5. E-12 测试函数名沿用 `test_TC_ATT_E08_admins_delete_last_forbidden` (按 spec 附录 15 题自检 6 "11 个 TC 函数名锁定"), 内部业务规则按 Gherkin 实施
6. 闭环决策写在 `decisions/007-v1-admin-features-shipped.md`, BACKLOG.md 不新增 #002 排期项 (按"完成项从 BACKLOG 清除" 规则)

**实施中确认的次要决策**（与用户对齐, 落到代码注释中）:

- `attendance/ui_admins.py` 内联 `_TITLE_MAP` + `_show_admin_error`, 沿用 `ui_change_password.py` 模式不修改既有 `ui_utils._TITLE_MAP` (AGENTS.md §5 红线)
- `AdminsTab._on_selection_changed` 用 `item.data(Qt.UserRole)` 存 admin_id, 不单独占列, 渲染与查询解耦
- 状态栏回调用 `self.window().statusBar()` (Qt 标准做法, AdminsTab 不耦合 MainWindow)
- `tests/test_ui_admins.py` E-07 mock 改为 `monkeypatch.setattr(dialog, "exec_", fake_exec)` (mock 实例而非类), 沉淀 L-007 教训

## 验证结果

| 检查 | 命令 / 文件 | 结果 |
|---|---|---|
| T-601 B 层 2 unit TC (E09 + E10) | `pytest tests/test_services.py -v` | 20/20 PASSED (18 旧 + 2 新) ✅ |
| T-602 C 层 5 UI TC (E01~E05) | `pytest tests/test_ui_change_password.py -v` | 5/5 PASSED ✅ |
| T-603 C 层 3 UI TC (E06~E08) | `pytest tests/test_ui_admins.py -v` | 3/3 PASSED ✅ |
| T-604 D 层 1 e2e TC (E11) | `pytest tests/test_e2e.py::test_TC_ATT_E11_e2e_change_password_full_flow -v` | 1/1 PASSED ✅ |
| **全栈 58 TC (A 12 + B 18 + C 18 + D 11 + SPEC-002 11)** | `pytest tests/ -v` | **58 passed in 6.81s** ✅ |
| **flake 检查 3 次** | `for i in 1 2 3; do pytest tests/ -q; done` | **3/3 全 RC 0, 0 flake** ✅ |
| conftest.py 未改 | grep diff | ✅ G-06 红线 |
| 红线保护文件未改 | `recognition.py` / `get_name.py` / `ui.py` 哈希不变 | ✅ |

**SPEC-002 TC 矩阵详情**:

| TC ID | 文件 | 类型 | 覆盖需求 | 关键断言 | 结果 |
|---|---|---|---|---|---|
| TC-ATT-E01 | test_ui_change_password.py | UI | REQ-E-01 + E-02 | 旧密码对 + 新密码 ≥ 6 + 确认匹配 → accept + statusBar "密码已修改" | ✅ |
| TC-ATT-E02 | test_ui_change_password.py | UI | REQ-E-03 | 旧密码错 → warning AUTH_FAILED + dialog 保持 | ✅ |
| TC-ATT-E03 | test_ui_change_password.py | UI | REQ-E-04 | 新密码 < 6 → warning PASSWORD_TOO_SHORT | ✅ |
| TC-ATT-E04 | test_ui_change_password.py | UI | REQ-E-05 | 确认新密码 ≠ 新密码 → warning PASSWORD_MISMATCH | ✅ |
| TC-ATT-E05 | test_ui_change_password.py | UI | REQ-E-06 | 取消 → dialog reject + statusBar 不更新 | ✅ |
| TC-ATT-E06 | test_ui_admins.py | UI | REQ-E-07 + E-13 | 切到 Tab 3 显示 N 行 + 选中自己行 → btn_delete 禁用 | ✅ |
| TC-ATT-E07 | test_ui_admins.py | UI | REQ-E-08 | mock AdminCreateDialog 填 200003/pass123 → accept + 表格 +1 行 | ✅ |
| TC-ATT-E08 | test_ui_admins.py | UI | REQ-E-12 | count=1 + 调 _on_delete 走 self-delete 优先 → warning SELF_DELETE_FORBIDDEN | ✅ |
| TC-ATT-E09 | test_services.py | Unit | REQ-E-B-01~B-07 | 8 个分支: create/list_all/delete + 4 异常类 | ✅ |
| TC-ATT-E10 | test_services.py | Unit | REQ-E-B-02 + B-03 | 7 个 username 边界: 空/空格/长度 1/50/51→USERNAME_TOO_LONG/特殊字符/中文 | ✅ |
| TC-ATT-E11 | test_e2e.py | E2E | REQ-E-D-01 | 改密 → 新密码 authenticate 成功 + 旧密码 AuthFailed | ✅ |

**关键 8 个错误码字面值**（SPEC-002 §6.1, 实施 100% 锁定）:
- `USERNAME_EXISTS` / `USERNAME_TOO_LONG` / `PASSWORD_TOO_SHORT` / `AUTH_FAILED`
- `LAST_ADMIN_FORBIDDEN` / `SELF_DELETE_FORBIDDEN` / `PASSWORD_MISMATCH` / `ADMIN_NOT_FOUND`

**关键 3 个 AdminService 方法签名**（SPEC-002 §3.1, 实施 100% 锁定）:
- `create(username: str, password: str) -> Admin` (校验顺序: username 长度 → password 长度 → username 唯一)
- `list_all() -> list[Admin]` (按 id 升序)
- `delete(admin_id: int, current_admin_id: Optional[int] = None) -> None` (校验顺序: admin 存在 → self-delete 优先 → LastAdmin 兜底)

## 闭环：排期清单 #001 (整体)

`BACKLOG.md` #001 整段在 2026-08-24 D 层闭环（决策 005）时已清除。本 spec (SPEC-002) 不新增 #002 排期项, 闭环事实沉淀在 `decisions/007-v1-admin-features-shipped.md` (本文件) + `_INDEX.md` 索引行。

## 踩坑

- **T-601 L-006 (同一文件多 Edit 必须严格串行)**: 沿用 2026-08-24 任务 1 决策 006 沉淀, T-603 实施时严格遵守（ui_main.py 5 处 Edit 串行执行）。
- **T-603 L-011 (mock 实例 exec_ 而非类 exec_)**: E-07 首次跑失败, `AttributeError: 'function' object at attendance.ui_admins.AdminCreateDialog has no attribute 'exec_'`。错: `monkeypatch.setattr("attendance.ui_admins.AdminCreateDialog.exec_", fake_exec)`, 前面 `AdminCreateDialog` 已被 setattr 替换为 `lambda` 函数, lambda 无 `exec_` 属性。对: 直接 `monkeypatch.setattr(dialog, "exec_", fake_exec)` mock 实例的 exec_。沉淀至 AGENTS.md §6 L-011。
- **T-603 spec 内部不一致 (实施前已修正)**: `specs/attendance/05-admin-features/spec.md` §7 TC-ATT-E08 行原写 "弹 show_error LAST_ADMIN_FORBIDDEN", 但 §2.2 Gherkin REQ-E-12 是 self-delete 优先 → SELF_DELETE_FORBIDDEN。用户拍板按 Gherkin 实施, spec 表格描述同步修正为 SELF_DELETE_FORBIDDEN, E-08 测试断言与 spec/业务层/UI 层 4 处一致。

## 下一步

- 全栈 5 子 spec 闭环 (A 基础层 + B 服务层 + C UI 层 + D 测试层 + SPEC-002 管理员) 后, 项目从「功能开发期」进入「可发布维护期」。
- 持续事项（按优先级）:
  1. 补 `tests/test_ui_main.py`（C 层 MainWindow 实例化路径测试覆盖, 沿用决策 005 L-004 建议, 避免类似 L-004 / L-007 盲点）
  2. 业务层 `AdminService.create` 入口 `len(username) > 50` 校验是新加的 (决策 007 T-601 拍板方案 A), 与既有 `_validate_new_password` 模式不统一, 后续可考虑统一为 `_validate_username` / `_validate_new_password` 风格
  3. CI/CD 接入: 现状无 git 仓库 (红线 §5), 用户未拍板前不主动 `git init`
  4. A 层 12 个 smoke test 仍按决策 002 沿用, 未进 pytest; 若想自动化可加 `tests/test_smoke.py` 复用 A 层 fixture
  5. SPEC-002 闭环后, 下次新需求 (如打卡报表导出 / 班次管理 / 多角色 RBAC) 走独立 spec 流程, 不与本 spec 合并
- 跨子 spec 事项: 5 层累计 58 + 12 = 70 TC 全过, 7 个决策文件归档完整 (001 初始化 + 002/003/004/005/006/007 六个事件闭环), P1 BACKLOG 已清空, P2 decisions 索引可被新会话快速检索。
