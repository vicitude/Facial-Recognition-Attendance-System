# 任务拆解: SPEC-002 管理员账户管理（改密 + 多管理员）

> 与 `specs/attendance/05-admin-features/spec.md` v1.0.0 配套。
> **范围**: 11 个 TC（4 改密 UI + 3 管理员管理 UI + 2 B 层 Unit + 1 E2E）。
> **依赖**: SPEC-001-A + SPEC-001-B + SPEC-001-C 全部已闭环（决策 002 / 003 / 004 / 005）。
> **前置**: 任务 1 弹窗卡死循环修复已闭环（决策 006 沉淀）, 不在本 tasks 范围。

---

## T-601 B 层 AdminService 新增 3 个方法 + 2 个 Unit TC

- **依赖**: SPEC-001-A + SPEC-001-B 已闭环
- **前置**: `attendance/utils.py` 已有 `AttendanceError` 基类 + `PasswordTooShort` / `AuthFailed` / `AdminNotFound` 异常
- **产出物**:

  **1. utils.py 新增 3 个异常类**（[spec §6.2](file:///d:/yol/yolov8_facenet/specs/attendance/05-admin-features/spec.md)）：
  - `class UsernameExists(AttendanceError)`
  - `class LastAdminForbidden(AttendanceError)`
  - `class SelfDeleteForbidden(AttendanceError)`

  **2. services.py AdminService 类追加 3 个静态方法**（[spec §3.1](file:///d:/yol/yolov8_facenet/specs/attendance/05-admin-features/spec.md)）:
  - `create(username: str, password: str) -> Admin` — 校验顺序: username 长度 (≤ 50, 超长抛 InternalError / USERNAME_TOO_LONG) → password 长度 (≥ 6, 抛 PasswordTooShort) → username 唯一 (抛 UsernameExists); DB 写失败转 InternalError
  - `list_all() -> list[Admin]` — 按 id 升序
  - `delete(admin_id: int, current_admin_id: Optional[int] = None) -> None` — 校验存在 + 至少 1 个 admin + 非自己, 抛 `AdminNotFound` / `LastAdminForbidden` / `SelfDeleteForbidden`

  **3. tests/test_services.py 追加 2 个 TC**（[spec §7](file:///d:/yol/yolov8_facenet/specs/attendance/05-admin-features/spec.md) TC-ATT-E09 + E10）:
  - `test_TC_ATT_E09_admin_create_and_list_and_delete` — 覆盖 create 成功 / 重名 / 短密码 / list_all / delete 成功 / 删最后 1 个 / 删自己 / 删不存在 8 个分支（不硬编码 admin_id=1/2, 改用 list_all() 查实际对象, 避免 MySQL AutoField auto_increment 不重置导致 get_by_id 失败）
  - `test_TC_ATT_E10_admin_create_username_validation` — 覆盖 username 边界（空字符串 / 纯空格 / 长度 1 / 长度 50 / 长度 51→USERNAME_TOO_LONG / 含特殊字符 / 含中文）7 个分支

- **关联**: spec §1 术语表 + §3.1 API 签名 + §4 数据模型 + §6.1 错误码 + §7 TC 矩阵
- **覆盖**: REQ-E-B-01 ~ B-08
- **完成后**: 跑 `pytest tests/test_services.py -v --tb=short` 应 18 + 2 = 20/20 PASSED

---

## T-602 C 层 ChangePasswordDialog + 5 个 UI TC

- **依赖**: T-601 完成
- **前置**: `AdminService.change_password` 已实现（SPEC-001-B 闭环）
- **产出物**:

  **1. attendance/ui_change_password.py 新建**, 含:
  - `class ChangePasswordDialog(QDialog)`:
    - `__init__(self, current_admin: Admin, parent=None)`: 构造 UI, 含 QLabel 标题 + 3 个 QLineEdit (旧密码 / 新密码 / 确认新密码, EchoMode.Password) + 2 个 QPushButton (确定 / 取消)
    - `_on_confirm_clicked(self)`: 校验非空 + 确认匹配, 调 `AdminService.change_password(self._current_admin.id, old, new)`, 成功 `self.accept()` + 状态栏回调, 失败 `show_error`
    - `_on_cancel_clicked(self)`: `self.reject()`

  **2. attendance/ui_main.py L24-26 修改** (L24 之后追加):
  - 「账户」菜单 + 「修改密码」Action, 触发 `ChangePasswordDialog(self._admin, self).exec_()`

  **3. tests/test_ui_change_password.py 新建**, 含 5 个 TC:
  - `test_TC_ATT_E01_change_password_success`
  - `test_TC_ATT_E02_change_password_old_wrong`
  - `test_TC_ATT_E03_change_password_too_short`
  - `test_TC_ATT_E04_change_password_mismatch`
  - `test_TC_ATT_E05_change_password_cancel`

- **关联**: spec §2.1 Gherkin 6 场景（E01+E06 合并 1 TC, E05+E06 拆 2 TC, 实际 5 TC）+ §3.3 事件契约 + §5 状态机 ChangePasswordDialog 节点
- **覆盖**: REQ-E-01 ~ E-06
- **完成后**: 跑 `pytest tests/test_ui_change_password.py -v --tb=short` 应 5/5 PASSED

---

## T-603 C 层 AdminsTab + AdminCreateDialog + 3 个 UI TC

- **依赖**: T-601 完成 + T-602 完成
- **前置**: `MainWindow._admin` 已注入（沿用 SPEC-001-C §5 T-305）+ `AdminService.create` / `delete` 已实现
- **产出物**:

  **1. attendance/ui_admins.py 新建**, 含:
  - `class AdminsTab(QWidget)`:
    - `__init__(self, current_admin: Admin, parent=None)`: 构造 UI, 工具栏 (新增 / 删除 / 刷新) + QTableView (3 列: ID / 用户名 / 创建时间)
    - `_refresh_table(self)`: 调 `AdminService.list_all()`, 渲染表格, 自己的行禁用「删除」按钮
    - `_on_create_clicked(self)`: 打开 `AdminCreateDialog(parent=self)`, 接受后调 `AdminService.create(...)` + `_refresh_table` + statusBar 回调
    - `_on_delete_clicked(self)`: 取选中行 `target_id`, 校验非自己, 调 `AdminService.delete(target_id, current_admin_id=self._current_admin.id)` + `_refresh_table` + statusBar
  - `class AdminCreateDialog(QDialog)`:
    - `__init__(self, parent=None)`: QLineEdit username + QLineEdit password (EchoMode.Password) + 2 个 QPushButton
    - `_on_save_clicked(self)`: 校验非空 + 校验长度, 调 `AdminService.create(username, password)`, 成功 `self.accept()`, 失败 `show_error`

  **2. attendance/ui_main.py L48-52 修改** (L48 之后追加):
  - `self.admins_tab = AdminsTab(self._admin)` (传入 current_admin 用于自删保护)
  - `self.tabs.addTab(self.admins_tab, "管理员管理")`

  **3. attendance/ui_main.py L24-26 追加第 2 个菜单项**:
  - 「账户 → 管理员管理」Action, 触发 `self.tabs.setCurrentWidget(self.admins_tab)`

  **4. tests/test_ui_admins.py 新建**, 含 3 个 TC:
  - `test_TC_ATT_E06_admins_tab_shows_list` — 切到 Tab 3 + 表格显示 N 行 + 自己行的删除按钮禁用
  - `test_TC_ATT_E07_admins_create_ok` — mock AdminCreateDialog.exec_ 填 "200003"/"pass123" → accept + 表格 +1 行 + admins 表 +1 行
  - `test_TC_ATT_E08_admins_delete_last_forbidden` — 当前 admin 是最后 1 个 + 调 _on_delete + 弹 show_error LAST_ADMIN_FORBIDDEN + 表格不变

- **关联**: spec §2.2 Gherkin 7 场景（E07+E08+E12 合并 3 TC, E13 与 E08 合并入 E06 自删 UI 保护）+ §3.3 事件契约 + §5 状态机 AdminsTab / AdminCreateDialog 节点
- **覆盖**: REQ-E-07 ~ E-13
- **完成后**: 跑 `pytest tests/test_ui_admins.py -v --tb=short` 应 3/3 PASSED

---

## T-604 D 层 1 个 E2E TC + 跑全栈 47 + 11 = 58 个 TC 验证 + 闭环决策 007

- **依赖**: T-601 + T-602 + T-603 全部完成
- **前置**: 4 改密 UI + 3 管理员管理 UI + 2 B 层 Unit + 1 E2E 全部单跑下全绿
- **产出物**:

  **1. tests/test_e2e.py 追加 1 个 TC**（[spec §7 TC-ATT-E11](file:///d:/yol/yolov8_facenet/specs/attendance/05-admin-features/spec.md)）:
  - `test_TC_ATT_E11_e2e_change_password_full_flow`:
    - `default_admin` fixture + `logged_in_main_window` (复用 D05~D11 既有 fixture)
    - 触发 `main_window.action_change_password.triggered` (或 `findChild(QAction, "action_change_password").trigger()`, 视实现)
    - ChangePasswordDialog 弹窗 (mock 走 `_on_confirm_clicked` 填合法值) → accept
    - 关闭当前 MainWindow, 重新创建 `LoginDialog` + 调 `_on_login_clicked` 走成功路径, 验证新密码 "newpass456" 成功
    - 再调一次, 验证旧密码 "admin123" 抛 AuthFailed

  **2. 跑全栈回归**:
  ```bash
  $env:QT_QPA_PLATFORM="offscreen"
  pytest tests/ -v --tb=short -p no:cacheprovider
  # 期望: 47 (旧) + 11 (本 spec) = 58 passed in <90s
  ```

  **3. 跑 flake 检查**:
  ```bash
  for i in 1 2 3; do
    QT_QPA_PLATFORM=offscreen pytest tests/ -q || exit 1
  done
  # 期望: 3 次全 RC 0
  ```

  **4. 写闭环决策 007**:
  - 新建 `decisions/007-v1-admin-features-shipped.md`, 摘要含 "闭环: SPEC-002 管理员账户管理 (改密 + 多管理员)" + 11/11 PASSED + 0 回归
  - 在 `decisions/_INDEX.md` 末尾追加 007 行
  - 在 `BACKLOG.md` 新建 #002 排期项并立即清除（按"完成项从 BACKLOG 清除" 规则, 但本 spec 不在 BACKLOG 排期项中, 故无需清除）
  - 在 `AGENTS.md` §6 踩坑教训章节追加本次实际遇到的坑（若有, 编号 L-007 起; 若无则跳过）
  - 在 `AGENTS.md` §10 变更日志追加一行（2026-08-24 SPEC-002 闭环）
  - 在 `AGENTS.md` §2 当前入口追加 `attendance/ui_change_password.py` + `attendance/ui_admins.py` + `tests/test_ui_change_password.py` + `tests/test_ui_admins.py`

- **关联**: spec §0 G-01~G-08 + §7 矩阵 E11 + §8 非功能需求
- **覆盖**: 11 个 SPEC-002 TC + 0 回归
- **完成后**: 跑 `QT_QPA_PLATFORM=offscreen pytest tests/ -v --tb=short` 应 58 passed in <90s

---

## 任务依赖图

```text
A 闭环 (002) ─┐
B 闭环 (003) ─┼──> T-601 (B 层 3 方法 + 2 Unit TC) ──┬──> T-602 (改密 UI + 5 UI TC) ──┐
C 闭环 (004) ─┤                                       │                                  │
D 闭环 (005) ─┘                                       └──> T-603 (AdminsTab + 3 UI TC) ──┤
                                                                                          ├──> T-604 (E2E + 回归 + 闭环)
                                                                                          │
                                                                                 T-601 ──┘
```

## 排期

| 阶段 | 任务 | 工时（单人时）|
|------|------|----------------|
| B 层 + 2 Unit | T-601 | 1.5 |
| C 层改密 | T-602 | 2.0 |
| C 层管理员管理 | T-603 | 2.5 |
| D 层 + 闭环 | T-604 | 1.0 |
| **合计** | — | **7.0** |

## 配套产物清单

| 路径 | 状态 | 来源 |
|------|------|------|
| `attendance/utils.py` | T-601 修改（追加 3 异常类）| 本 spec §6.2 |
| `attendance/services.py` | T-601 修改（追加 3 方法, 不动既有）| 本 spec §3.1 |
| `attendance/ui_change_password.py` | T-602 新建 | 本 spec §3.3 |
| `attendance/ui_admins.py` | T-603 新建 | 本 spec §3.3 |
| `attendance/ui_main.py` | T-602 + T-603 修改（追加 1 菜单项 + 1 Tab, 不动既有 3 Tab）| 本 spec §0 关联代码 |
| `tests/test_services.py` | T-601 追加 2 TC（不新建文件）| 本 spec §7 |
| `tests/test_ui_change_password.py` | T-602 新建 | 本 spec §7 |
| `tests/test_ui_admins.py` | T-603 新建 | 本 spec §7 |
| `tests/test_e2e.py` | T-604 追加 1 TC（不新建文件）| 本 spec §7 |
| `decisions/007-v1-admin-features-shipped.md` | T-604 新建 | 闭环决策 |
| `decisions/_INDEX.md` | T-604 追加 007 行 | 索引维护 |
| `AGENTS.md` §2 / §6 / §10 | T-604 追加 | 当前入口 / 踩坑 / 变更日志 |
