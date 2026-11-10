# 验收清单: SPEC-002 管理员账户管理（改密 + 多管理员）

> 与 `specs/attendance/05-admin-features/spec.md` v1.0.0 + `tasks.md` 配套。
> **范围**: 11 个 TC（4 改密 UI + 3 管理员管理 UI + 2 B 层 Unit + 1 E2E）。
> **闭环后**: `decisions/007-v1-admin-features-shipped.md` + `_INDEX.md` 追加 007 行; `AGENTS.md` §2 / §6 / §10 追加。

---

## A. 文件存在

- [ ] **A-01** `attendance/utils.py` 新增 3 个异常类 `UsernameExists` / `LastAdminForbidden` / `SelfDeleteForbidden`, 均为 `AttendanceError` 子类 — 阻塞
- [ ] **A-02** `attendance/services.py` `AdminService` 类新增 3 个静态方法 `create` / `list_all` / `delete`, 既有 `authenticate` / `change_password` / `ensure_default` **未修改** — 阻塞
- [ ] **A-03** `attendance/ui_change_password.py` 新建, 含 `ChangePasswordDialog` 类 — 阻塞
- [ ] **A-04** `attendance/ui_admins.py` 新建, 含 `AdminsTab` + `AdminCreateDialog` 类 — 阻塞
- [ ] **A-05** `attendance/ui_main.py` L24 之后追加「账户」菜单 + 「修改密码」Action — 阻塞
- [ ] **A-06** `attendance/ui_main.py` L48 之后追加 `self.admins_tab = AdminsTab(self._admin)` + `self.tabs.addTab(self.admins_tab, "管理员管理")` — 阻塞
- [ ] **A-07** `tests/test_ui_change_password.py` 新建, 含 5 个 TC（`test_TC_ATT_E01` ~ `E05`）— 阻塞
- [ ] **A-08** `tests/test_ui_admins.py` 新建, 含 3 个 TC（`test_TC_ATT_E06` ~ `E08`）— 阻塞
- [ ] **A-09** `tests/test_services.py` 末尾追加 2 个 TC（`test_TC_ATT_E09` + `E10`）, 文件不新建 — 阻塞
- [ ] **A-10** `tests/test_e2e.py` 末尾追加 1 个 TC（`test_TC_ATT_E11_e2e_change_password_full_flow`）, 文件不新建 — 阻塞
- [ ] **A-11** `tests/conftest.py` 6 fixture（`_db_session` / `_patch_argv` / `_per_test_reset` / `sample_schedule` / `face_image` / `sample_employees`）**保持原样**（G-06 红线继承）— 阻塞

## B. 错误码覆盖（spec §6.1）

- [ ] **B-01** `USERNAME_EXISTS` 错误码被 E07/E10 触发（重复 username 创建）— 阻塞
- [ ] **B-02** `PASSWORD_TOO_SHORT` 错误码被 E03/E10 触发（新密码 < 6 位）— 阻塞
- [ ] **B-03** `AUTH_FAILED` 错误码被 E02 触发（旧密码错）— 阻塞
- [ ] **B-04** `LAST_ADMIN_FORBIDDEN` 错误码被 E08/E09 触发（删最后 1 个 admin）— 阻塞
- [ ] **B-05** `SELF_DELETE_FORBIDDEN` 错误码被 E09 触发（删自己）— 阻塞
- [ ] **B-06** `PASSWORD_MISMATCH` 错误码被 E04 触发（确认新密码 ≠ 新密码）— 阻塞
- [ ] **B-07** `ADMIN_NOT_FOUND` 错误码被 E09 触发（删不存在 admin_id）— 阻塞
- [ ] **B-08** `USERNAME_TOO_LONG` 错误码被 E10 触发（username 长度 > 50）— 阻塞
- [ ] **B-09** 8 个错误码弹窗标题与内容格式按 spec §6.1 表格逐字一致 — 阻塞

## C. UI 控件命名（spec §3.3）

- [ ] **C-01** `ChangePasswordDialog` 含 3 个 QLineEdit 对象名: `old_password_edit` / `new_password_edit` / `confirm_password_edit` — 阻塞
- [ ] **C-02** `ChangePasswordDialog` 含 2 个 QPushButton 对象名: `btn_confirm` / `btn_cancel` — 阻塞
- [ ] **C-03** `ChangePasswordDialog` 3 个 QLineEdit EchoMode == Password — 阻塞（TC-ATT-E01 断言）
- [ ] **C-04** `AdminsTab` 含 1 个 QTableView + 3 个 QPushButton: `btn_add` / `btn_delete` / `btn_refresh` — 阻塞
- [ ] **C-05** `AdminsTab` 表格 3 列: ID / 用户名 / 创建时间 — 阻塞
- [ ] **C-06** `AdminsTab` 自己行的「删除」按钮禁用 — 阻塞（TC-ATT-E06 断言）
- [ ] **C-07** `AdminCreateDialog` 含 2 个 QLineEdit: `username_edit` / `password_edit` + 2 个 QPushButton: `btn_save` / `btn_cancel` — 阻塞
- [ ] **C-08** `MainWindow` 「账户」菜单含 2 个 Action: `action_change_password` / `action_manage_admins` — 阻塞

## D. CI 门禁（spec §0 G-01~G-08）

- [ ] **D-01** **G-01**: `QT_QPA_PLATFORM=offscreen pytest tests/ -v --tb=short` 退出码 0, 输出 58 passed (A=0 自动化 + B=18 + C=18 + D=11 + E=11) — 阻塞
- [ ] **D-02** **G-02**: `pytest --collect-only -q | grep -c "test_TC_ATT_E"` 输出 11 — 阻塞
- [ ] **D-03** **G-03**: 连续 3 次跑 0 flake — 阻塞
- [ ] **D-04** **G-04**: 启动命令前置 `QT_QPA_PLATFORM=offscreen`（E11 e2e 需要）— 阻塞
- [ ] **D-05** **G-05**: `recognition.py` / `get_name.py` / `ui.py` 三个原文件哈希不变（`git diff` 输出为空）— 阻塞
- [ ] **D-06** **G-06**: `tests/conftest.py` 不修改（`git diff` 输出为空）— 阻塞
- [ ] **D-07** **G-07**: spec.md / tasks.md / checklist.md / 5 个代码文件 / 3 个测试文件五者之一修改时, 另八者同步更新 — 阻塞
- [ ] **D-08** **G-08**: 任务 1 弹窗卡死循环修复**不**在本 spec 范围, 闭环事实仅在 `decisions/006-v1-bugfix-checkin-warning-loop.md` — 反向验证

## E. 改密 UI 测试 5 个 TC（test_ui_change_password.py, E01~E05）

- [ ] **E-01** **TC-ATT-E01 change_password_success**: 旧密码="admin123" + 新密码="newpass456" + 确认匹配 → `AdminService.change_password` 真实调用 → dialog accept + statusBar 含"密码已修改, 下次登录生效" — 阻塞
- [ ] **E-02** **TC-ATT-E02 change_password_old_wrong**: 旧密码="wrong" → show_error AUTH_FAILED + dialog 保持 + statusBar 不更新 — 阻塞
- [ ] **E-03** **TC-ATT-E03 change_password_too_short**: 新密码="123" → show_error PASSWORD_TOO_SHORT + dialog 保持 — 阻塞
- [ ] **E-04** **TC-ATT-E04 change_password_mismatch**: 确认新密码="other789" ≠ 新密码 → show_error PASSWORD_MISMATCH + dialog 保持 — 阻塞
- [ ] **E-05** **TC-ATT-E05 change_password_cancel**: 点击取消 → dialog reject + statusBar 不更新 — 阻塞

## F. 管理员管理 UI 测试 3 个 TC（test_ui_admins.py, E06~E08）

- [ ] **F-01** **TC-ATT-E06 admins_tab_shows_list**: 切到 Tab 3, 表格显示 2 行 (admin + zhangsan), admin 行的「删除」按钮禁用 — 阻塞
- [ ] **F-02** **TC-ATT-E07 admins_create_ok**: mock `AdminCreateDialog.exec_` 填 username="200003" + password="pass123" → 走 `_on_save_clicked` 调 `AdminService.create` → 表格 +1 行 + admins 表 +1 行 + statusBar 反馈 — 阻塞
- [ ] **F-03** **TC-ATT-E08 admins_delete_last_forbidden**: 当前 admin 是最后 1 个 + 调 `_on_delete_clicked` + 确认弹窗走 mock 是 → 调 `AdminService.delete(self._admin.id, ...)` → 抛 LastAdminForbidden → show_error + 表格不变 — 阻塞

## G. B 层 Unit 测试 2 个 TC（test_services.py 末尾, E09~E10）

- [ ] **G-01** **TC-ATT-E09 admin_create_and_list_and_delete**: 8 个分支全过:
  - (1) create 新 admin 成功, 返回 Admin 实例, username/password_hash 正确
  - (2) create 重名 → 抛 UsernameExists
  - (3) create 短密码 "123" → 抛 PasswordTooShort
  - (4) list_all 返回 list, 含全部 admin
  - (5) delete 非最后 + 非自己 admin_id 成功, Admin.select().where(id=...).exists() == False
  - (6) delete 最后 1 个 admin_id → 抛 LastAdminForbidden
  - (7) delete 自己 admin_id (current_admin_id == admin_id) → 抛 SelfDeleteForbidden
  - (8) delete 不存在 admin_id (999999) → 抛 AdminNotFound
  - 阻塞
- [ ] **G-02** **TC-ATT-E10 admin_create_username_validation**: 7 个边界 case 全过:
  - (1) 空字符串 `""` → 成功 (不校验非空, 仅校验唯一)
  - (2) 纯空格 `"   "` → 成功
  - (3) 长度 1 `"a"` → 成功
  - (4) 长度 50 `"a" * 50` → 成功
  - (5) 长度 51 `"a" * 51` → 抛 InternalError (USERNAME_TOO_LONG, service 入口手动校验, 不依赖 MySQL strict mode)
  - (6) 含特殊字符 `"admin!@#"` → 成功 (允许)
  - (7) 含中文 `"管理员"` → 成功
  - 阻塞
- [ ] **G-03** `tests/test_services.py` 追加 2 TC 后总 TC 数 = 18 (旧) + 2 (新) = 20 个 — 阻塞
- [ ] **G-04** `pytest tests/test_services.py -v` 输出 20 passed — 阻塞

## H. E2E 测试 1 个 TC（test_e2e.py 末尾, E11）

- [ ] **H-01** **TC-ATT-E11 e2e_change_password_full_flow**:
  - `default_admin` fixture (复用 D03)
  - 触发 `main_window.action_change_password.triggered` 或 `findChild(QAction, "action_change_password").trigger()`
  - `ChangePasswordDialog` 弹窗, mock 走 `_on_confirm_clicked` 填 old="admin123" + new="newpass456" + confirm="newpass456" → accept
  - 关闭当前 MainWindow (`main.closeEvent(QtGui.QCloseEvent())`)
  - 重新创建 `LoginDialog` + 调 `_on_login_clicked` 走成功路径, 验证新密码 "newpass456" 成功 + `dlg.admin.username == "admin"`
  - 再调一次, 验证旧密码 "admin123" 抛 AuthFailed
  - 阻塞

## I. 静态检查

- [ ] **I-01** 业务层无 `raise Exception` (B 层红线, 验证: `grep -REn "raise Exception" attendance/ tests/` 输出 0) — 阻塞
- [ ] **I-02** 3 个新异常类名 (`UsernameExists` / `LastAdminForbidden` / `SelfDeleteForbidden`) 在 utils.py 中**仅**作为类定义出现, 不被业务代码 import 后重命名 — 阻塞
- [ ] **I-03** 严禁 `unittest.mock.patch` 装饰器 (验证: `grep -REn "unittest.mock.patch" tests/test_ui_change_password.py tests/test_ui_admins.py` 输出 0) — 阻塞
- [ ] **I-04** 严禁 `pytest-xdist` (验证: `grep -REn "pytest-xdist\|@pytest.mark.parallel" tests/` 输出 0) — 阻塞
- [ ] **I-05** `attendance/services.py` 中 `authenticate` / `change_password` / `ensure_default` 3 个旧方法 sha256 不变 (`git diff -U0 attendance/services.py | grep "^[+-]" | grep -v "^[+-]{3}" | wc -l` 应仅含新方法新增行) — 阻塞

## J. 隔离性 / 可重现性 / 资源释放

- [ ] **J-01** 一 TC 失败不影响其他 TC: 故意让 E02 失败, 跑 E03 仍通过 — 阻塞
- [ ] **J-02** 不依赖真实相机: E11 mock 全部, 代码中无 `cv2.VideoCapture(0)` 真实调用 — 阻塞
- [ ] **J-03** E11 改密后, 数据库 admins 表 password_hash 字段真的变了 (避免 mock 假阳性) — 阻塞
- [ ] **J-04** E11 改密后用旧密码登录抛 AuthFailed, 用新密码登录成功 — 阻塞 (与 H-01 重叠, 单独验证双向)

## K. 资源保护红线（AGENTS.md §5 + spec §9.2）

- [ ] **K-01** `recognition.py` 未修改 (`git diff recognition.py` 输出为空) — 阻塞
- [ ] **K-02** `get_name.py` 未修改 (`git diff get_name.py` 输出为空) — 阻塞
- [ ] **K-03** `ui.py` 未修改 (`git diff ui.py` 输出为空) — 阻塞
- [ ] **K-04** `mydata.yaml` 未修改 (`git diff mydata.yaml` 输出为空) — 阻塞
- [ ] **K-05** 训练权重 `runs/detect/train/weights/*.pt` 未修改 (`git diff runs/` 输出为空) — 阻塞
- [ ] **K-06** `attendance/services.py` 中 `authenticate` / `change_password` / `ensure_default` 3 个旧方法未修改 (仅追加 `create` / `list_all` / `delete` 3 个新方法) — 阻塞
- [ ] **K-07** `attendance/ui_login.py` 未修改 (LoginDialog 不变, 改密走新弹窗) — 阻塞
- [ ] **K-08** `attendance/ui_checkin.py` 未修改 (任务 1 修复已闭环, 走决策 006, 不在本 spec) — 阻塞
- [ ] **K-09** `tests/conftest.py` 未修改 (G-06 红线继承) — 阻塞
- [ ] **K-10** `attendance/ui_employees.py` + `attendance/ui_records.py` 未修改 (C 层闭环, 红线) — 阻塞

## L. 最终闭环

- [ ] **L-01** 全部阻塞项 (A~K) 通过后, 在 `decisions/007-v1-admin-features-shipped.md` 写入闭环决策, 摘要含 "闭环: SPEC-002 管理员账户管理" + 11/11 PASSED + 0 回归 + <90s + 0 flake — 阻塞
- [ ] **L-02** 在 `decisions/_INDEX.md` 末尾追加 007 行 (v1, admin, change-password, multi-admin, qt, 关键词) — 阻塞
- [ ] **L-03** 在 `AGENTS.md` §6 踩坑教训章节追加本次实际遇到的坑 (若有, 编号 L-007 起; 若无则跳过) — 阻塞
- [ ] **L-04** 在 `AGENTS.md` §10 变更日志追加一行 (2026-08-24 SPEC-002 闭环) — 阻塞
- [ ] **L-05** 在 `AGENTS.md` §2 当前入口追加 `attendance/ui_change_password.py` + `attendance/ui_admins.py` + `tests/test_ui_change_password.py` + `tests/test_ui_admins.py` — 阻塞
- [ ] **L-06** 任务 1 弹窗卡死循环修复**不**在本 spec 闭环, 仅在 `decisions/006-v1-bugfix-checkin-warning-loop.md` 体现 — 反向验证
