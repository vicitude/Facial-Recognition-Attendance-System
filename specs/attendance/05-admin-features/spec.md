# SPEC-002: 管理员账户管理（改密 + 多管理员）

> **规范状态**: 已批准
> **版本**: v1.0.0
> **拆分自**: SPEC-001-C v1.0.0 §2 登录流程 + §5 状态机未实现项
> **依赖**: SPEC-001-A + SPEC-001-B + SPEC-001-C 全部已闭环（决策 002 / 003 / 004 / 005）
> **代码包路径**: `attendance/services.py`（B 层新增）+ `attendance/ui_*.py`（C 层新增）+ `tests/test_services.py` + `tests/test_ui_*.py` + `tests/test_e2e.py`（D 层新增）
> **最后修改**: 2026-08-24
> **配套决策**: 任务 1 弹窗卡死循环修复走特批小补丁, 闭环事实沉淀到 `decisions/006-v1-bugfix-checkin-warning-loop.md`, **不在本 spec 范围**。

---

## 0. 文档头与元数据

- **文件路径**: `/specs/attendance/05-admin-features/spec.md`
- **关联代码路径**:
  - B 层 (services): `attendance/services.py` — `AdminService` 类新增 3 个静态方法 (`create` / `list_all` / `delete`)
  - B 层 (utils): `attendance/utils.py` — 新增 3 个异常类 (`UsernameExists` / `LastAdminForbidden` / `SelfDeleteForbidden`), 均为 `AttendanceError` 子类
  - C 层 (ui): `attendance/ui_change_password.py` — `ChangePasswordDialog` 类
  - C 层 (ui): `attendance/ui_admins.py` — `AdminsTab` 类 + `AdminCreateDialog` 类
  - C 层 (ui): `attendance/ui_main.py` — L24-26 追加 2 个菜单项「账户 → 修改密码 / 管理员管理」; L48-52 在 3 Tab 之后追加 Tab 3「管理员管理」
  - 消费: `AdminService` (B 层闭环) + `Admin` model (A 层闭环)
- **CI 门禁规则**:
  - G-01 `pytest tests/ -v --tb=short` 退出码 0, 输出 59 passed (A=12 smoke + B=18 + C=18 + D=11 + **本 spec 11** = 70, 其中 A 层 0 自动化沿用决策 002, 故 47 + 11 = 58, 实际 59 包含)
  - G-02 `pytest --collect-only -q | grep -c "test_TC_ATT_E"` 输出 11
  - G-03 连续 3 次跑 0 flake
  - G-04 启动命令前置 `QT_QPA_PLATFORM=offscreen`（D 层 e2e 需要）
  - G-05 严禁修改 `recognition.py` / `get_name.py` / `ui.py` 三个原文件（AGENTS.md §5 红线）
  - G-06 严禁修改 `tests/conftest.py` 已有 6 个 fixture（D 层 G-06 红线, 本 spec 不新增 conftest）
  - G-07 本文件修改时, `tasks.md` + `checklist.md` + 5 个代码文件 + 3 个测试文件必须同步更新
  - G-08 任务 1 弹窗卡死循环 bug 修复已闭环, 沉淀在 `decisions/006-v1-bugfix-checkin-warning-loop.md`, 本 spec 范围**不**重复

---

## 1. 术语表与统一语言

| 术语 | 英文名 | 类型 | 定义 | 代码映射 | 数据库映射 | 示例 |
|------|--------|------|------|----------|------------|------|
| 修改密码对话框 | ChangePasswordDialog | UI 组件 | 主窗口菜单触发, 弹窗改密 | `attendance.ui_change_password.ChangePasswordDialog` | — | — |
| 管理员管理 Tab | AdminsTab | UI 组件 | 第 4 Tab, 表格 + 增删 | `attendance.ui_admins.AdminsTab` | — | — |
| 创建管理员对话框 | AdminCreateDialog | UI 组件 | AdminsTab 新增按钮触发 | `attendance.ui_admins.AdminCreateDialog` | — | — |
| 多管理员 | MultiAdmin | 业务规则 | 系统中可存在 ≥1 个 admin 账号 | `Admin` 表行数 ≥ 1 | `admins` 表 | `count(*) >= 1` |
| 最后管理员保护 | LastAdminGuard | 业务规则 | 至少 1 个 admin 不可删, 锁死系统前自保 | `LastAdminForbidden` 异常 | `admins.count() > 1` | `delete(1)` when `count() == 1` |
| 自删保护 | SelfDeleteGuard | 业务规则 | 当前登录 admin 不可删自己, 防锁出 | `SelfDeleteForbidden` 异常 | `current_admin.id == target.id` | `delete(current.id)` |
| 用户名重复 | UsernameExists | 业务规则 | username 唯一约束 | `UsernameExists` 异常 | `admins.username UNIQUE` | `create("admin", ...)` when `admin` exists |
| 密码强度 | PasswordPolicy | 业务规则 | 长度 ≥ 6（沿用决策 002 `MIN_PASSWORD_LENGTH=6`）| `AdminService._validate_new_password` | — | `"123"` raises `PasswordTooShort` |
| 当前管理员上下文 | CurrentAdmin | UI 状态 | `MainWindow._admin` 属性, 改密/自删判断用 | `MainWindow._admin` | — | `self._admin.id` |
| 菜单结构 | MenuStructure | UI 设计 | 文件 / 账户 2 个顶级菜单 | `QMenuBar` | — | 「文件 → 退出」+ 「账户 → 修改密码 / 管理员管理」 |
| Tab 顺序 | TabOrder | UI 设计 | 实时签到 / 人员管理 / 打卡记录 / 管理员管理（Tab 3）| `QTabWidget.addTab` | — | `addTab(admins_tab, "管理员管理")` |
| 列表刷新触发 | RefreshTrigger | UI 模式 | 增删后自动 `_refresh_table()`, 无需手动刷新按钮 | `_refresh_table` | — | `after_create: self._refresh_table()` |
| 改密后状态提示 | PasswordChangedHint | UI 反馈 | statusBar 显示"密码已修改, 下次登录生效" | `MainWindow.statusBar().showMessage` | — | `statusBar 5s 自动消失` |

**一致性保障**:
- 所有异常类名 (`UsernameExists` / `LastAdminForbidden` / `SelfDeleteForbidden`) 必须与本文 §1 表格逐字一致, 且均为 `AttendanceError` 子类
- 所有 UI 类名 (`ChangePasswordDialog` / `AdminsTab` / `AdminCreateDialog`) 必须与本文 §1 表格逐字一致
- 所有错误码 (`USERNAME_EXISTS` / `PASSWORD_TOO_SHORT` / `LAST_ADMIN_FORBIDDEN` / `SELF_DELETE_FORBIDDEN`) 必须与本文 §6.1 表格逐字一致

---

## 2. 用户故事与验收场景（Gherkin）

### 2.1 改密场景

```gherkin
功能: 修改当前管理员密码
  作为 管理员
  我需要 改密 UI 入口
  以便 避免长期使用默认密码 admin123

  场景: REQ-E-01 打开改密弹窗
    假设 已登录 MainWindow, 当前管理员 username="admin"
    当 点击「账户 → 修改密码」菜单
    那么 弹 ChangePasswordDialog, 标题"修改密码"
    且 含 3 个 QLineEdit: 旧密码 / 新密码 / 确认新密码
    且 含 2 个 QPushButton: 确定 / 取消

  场景: REQ-E-02 改密成功
    假设 ChangePasswordDialog 已弹出
    当 填旧密码="admin123", 新密码="newpass456", 确认="newpass456", 点击确定
    那么 AdminService.change_password(self._admin.id, "admin123", "newpass456") 调用
    且 dialog close (accept)
    且 statusBar 显示"密码已修改, 下次登录生效"

  场景: REQ-E-03 旧密码错误
    假设 ChangePasswordDialog 已弹出
    当 填旧密码="wrong", 新密码="newpass456", 确认="newpass456", 点击确定
    那么 弹 QMessageBox.warning, 标题"修改失败", 内容"旧密码错误 (错误码: AUTH_FAILED)"
    且 dialog 仍保持
    且 statusBar 不更新

  场景: REQ-E-04 新密码 < 6 位
    假设 ChangePasswordDialog 已弹出
    当 填旧密码="admin123", 新密码="123", 确认="123", 点击确定
    那么 弹 QMessageBox.warning, 标题"修改失败", 内容含 "新密码长度 < 6 (错误码: PASSWORD_TOO_SHORT)"
    且 dialog 仍保持

  场景: REQ-E-05 确认新密码 ≠ 新密码
    假设 ChangePasswordDialog 已弹出
    当 填旧密码="admin123", 新密码="newpass456", 确认="other789", 点击确定
    那么 弹 QMessageBox.warning, 标题"修改失败", 内容"两次输入的新密码不一致 (错误码: PASSWORD_MISMATCH)"
    且 dialog 仍保持

  场景: REQ-E-06 取消改密
    假设 ChangePasswordDialog 已弹出
    当 点击取消
    那么 dialog close (reject)
    且 statusBar 不更新
```

### 2.2 管理员管理场景

```gherkin
功能: 管理员多账号管理
  作为 主管理员
  我需要 增删管理员 UI 入口
  以便 多人协作, 离职交接

  场景: REQ-E-07 进入管理员管理 Tab
    假设 已登录, admins 表有 2 行 (admin / zhangsan)
    当 点击 Tab 3「管理员管理」
    那么 表格显示 2 行, 列: ID / 用户名 / 创建时间
    且 第 1 行 username="admin", 不可删 (最后 1 个 admin 不允许自删保护)
    且 第 2 行 username="zhangsan", [删除] 按钮可见

  场景: REQ-E-08 创建新管理员
    假设 AdminsTab 已显示
    当 点击「新增」, 在 AdminCreateDialog 填 username="lisi", password="lisi123", 点击保存
    那么 AdminService.create("lisi", "lisi123") 调用
    且 dialog close
    且 表格新增 1 行, admins 表新增 1 行
    且 statusBar 显示"已创建管理员 lisi"

  场景: REQ-E-09 创建重复用户名
    假设 AdminCreateDialog 已弹出
    当 填 username="admin" (已存在), password="new123", 点击保存
    那么 弹 QMessageBox.warning, 标题"创建失败", 内容"用户名 admin 已存在 (错误码: USERNAME_EXISTS)"
    且 dialog 仍保持

  场景: REQ-E-10 创建密码 < 6 位
    假设 AdminCreateDialog 已弹出
    当 填 username="wangwu", password="123", 点击保存
    那么 弹 QMessageBox.warning, 标题"创建失败", 内容含 "新密码长度 < 6 (错误码: PASSWORD_TOO_SHORT)"

  场景: REQ-E-11 删除非自己非最后 admin
    假设 AdminsTab 已显示, 表格有 2 行 (admin id=1 / zhangsan id=2), 当前 admin id=1
    当 选中 zhangsan 行, 点击「删除」, 确认弹窗点"是"
    那么 AdminService.delete(admin_id=2) 调用
    且 表格该行消失, admins 表该行删除
    且 statusBar 显示"已删除管理员 zhangsan"

  场景: REQ-E-12 删除自己 (self-delete 优先, count=1 时同样自删保护)
    假设 AdminsTab 已显示, 表格仅 1 行 (admin id=1), 当前 admin id=1
    当 选中该行, 点击「删除」, 确认弹窗点"是"
    那么 AdminService.delete(admin_id=1, current_admin_id=1) 走 self-delete 优先校验
    且 抛 SelfDeleteForbidden (错误码: SELF_DELETE_FORBIDDEN)
    且 弹 QMessageBox.warning, 标题"删除失败", 内容"不能删除当前登录的管理员 1 (错误码: SELF_DELETE_FORBIDDEN)"
    且 表格该行仍存在

  场景: REQ-E-13 删除自己
    假设 AdminsTab 已显示, 表格 2 行 (admin id=1 / zhangsan id=2), 当前 admin id=1
    当 选中 admin 行 (自己), 「删除」按钮禁用 (不显示)
    或者
    当 (如果 UI 误启用) 调 AdminService.delete(admin_id=1) 直接抛 SelfDeleteForbidden
```

---

## 3. API 与 UI 事件契约

### 3.1 B 层 AdminService 新增方法签名

```python
# attendance/services.py AdminService 类追加

@staticmethod
def create(username: str, password: str) -> Admin:
    """创建新管理员。

    校验顺序: 1. username 长度 (InternalError / USERNAME_TOO_LONG, ≤ 50)
              2. password 长度 (PasswordTooShort, ≥ MIN_PASSWORD_LENGTH)
              3. username 唯一 (UsernameExists)
    DB 写失败转 InternalError.

    Raises:
        InternalError: username 长度 > 50 (USERNAME_TOO_LONG)
        PasswordTooShort: 密码长度 < MIN_PASSWORD_LENGTH (6)
        UsernameExists: username 已被注册
    """

@staticmethod
def list_all() -> list[Admin]:
    """列出所有管理员, 按 id 升序."""

@staticmethod
def delete(admin_id: int) -> None:
    """删除管理员。
    
    Raises:
        AdminNotFound: admin_id 不存在
        LastAdminForbidden: 系统中仅剩 1 个 admin
        SelfDeleteForbidden: 当前登录 admin 试图删自己
    """
```

### 3.2 错误码表（§6.1 完整版）

| 错误码 | 触发条件 | 抛异常 | UI 弹窗标题 | UI 弹窗内容 |
|--------|----------|--------|-------------|-------------|
| `USERNAME_EXISTS` | `Admin.select().where(username=...)` 命中 | `UsernameExists` | 创建失败 | "用户名 {username} 已存在 (错误码: USERNAME_EXISTS)" |
| `USERNAME_TOO_LONG` | `len(username) > 50` | `InternalError` (沿用 003) | 创建失败 | "username 长度 {len} > 50 (错误码: USERNAME_TOO_LONG)" |
| `PASSWORD_TOO_SHORT` | `len(password) < 6` | `PasswordTooShort` (沿用 003) | 修改失败 / 创建失败 | "新密码长度 < 6 (错误码: PASSWORD_TOO_SHORT)" |
| `AUTH_FAILED` | change_password 旧密码错 | `AuthFailed` (沿用 003) | 修改失败 | "旧密码错误 (错误码: AUTH_FAILED)" |
| `LAST_ADMIN_FORBIDDEN` | `admins.count() <= 1` 时 delete | `LastAdminForbidden` | 删除失败 | "系统至少保留 1 个管理员 (错误码: LAST_ADMIN_FORBIDDEN)" |
| `SELF_DELETE_FORBIDDEN` | `admin_id == current_admin.id` | `SelfDeleteForbidden` | 删除失败 | "不能删除当前登录的管理员 (错误码: SELF_DELETE_FORBIDDEN)" |
| `PASSWORD_MISMATCH` | 确认新密码 ≠ 新密码 | `ValueError` → 走 show_error | 修改失败 | "两次输入的新密码不一致 (错误码: PASSWORD_MISMATCH)" |
| `ADMIN_NOT_FOUND` | delete admin_id 不存在 | `AdminNotFound` (沿用 003) | 删除失败 | "管理员 {id} 不存在 (错误码: ADMIN_NOT_FOUND)" |

### 3.3 UI 事件契约

| UI 控件 | 事件 | 调用服务/方法 | 成功反馈 | 失败反馈 |
|---|---|---|---|---|
| MainWindow-账户→修改密码 | triggered | 创建 `ChangePasswordDialog(self._admin, self)` | dialog accept, statusBar 提示 | 旧密码错 / 新密码 < 6 / 不匹配 → QMessageBox.warning |
| ChangePasswordDialog-旧密码 | textChanged | 无 (内部状态) | - | - |
| ChangePasswordDialog-新密码 | textChanged | 无 (内部状态) | - | - |
| ChangePasswordDialog-确认新密码 | textChanged | 无 (内部状态) | - | - |
| ChangePasswordDialog-确定 | clicked | 校验匹配 + `AdminService.change_password(self._admin.id, old, new)` | accept + statusBar | show_error 对应错误码 |
| ChangePasswordDialog-取消 | clicked | reject() | - | - |
| MainWindow-Tab 切换 0→3 | currentChanged | 无 | - | - |
| AdminsTab-新增 | clicked | 打开 `AdminCreateDialog(parent=self)` | - | - |
| AdminsTab-删除 | clicked | 确认弹窗 + `AdminService.delete(target_id)` (target_id != self._admin.id 且 count>1) | 行消失 + statusBar | show_error LAST_ADMIN / SELF_DELETE / NOT_FOUND |
| AdminsTab-刷新 | clicked | `_refresh_table()` | - | - |
| AdminCreateDialog-保存 | clicked | 校验非空 + `AdminService.create(username, password)` | accept + 父窗口 _refresh | show_error USERNAME_EXISTS / PASSWORD_TOO_SHORT |
| AdminCreateDialog-取消 | clicked | reject() | - | - |

---

## 4. 数据模型与字段映射

> Admin model 已在 SPEC-001-A §4 定义, 本子 spec 不修改 model 字段, 仅新增 3 个 B 层方法。

| 业务字段 | Admin model 属性 | 数据库列 | AdminService.create 映射 |
|----------|------------------|----------|--------------------------|
| 用户名 | `Admin.username` | `admins.username VARCHAR(50) UNIQUE` | 校验唯一性 (抛 `UsernameExists`) |
| 密码 | `Admin.password_hash` | `admins.password_hash VARCHAR(64)` | `sha256_hex(password)` (沿用 003) |
| 长度校验 | — | — | `len(password) >= MIN_PASSWORD_LENGTH (6)` (抛 `PasswordTooShort`) |
| 创建时间 | `Admin.created_at` | `admins.created_at DATETIME` | `datetime.now()` |
| 更新时间 | `Admin.updated_at` | `admins.updated_at DATETIME` | `datetime.now()` |

**唯一约束**: `admins.username` UNIQUE, 重复时 peewee `IntegrityError` 触发, 转 `UsernameExists`。

---

## 5. UI 导航状态机（增量更新）

```yaml
stateMachine: AppNavigation
initial: LoginDialog
states:
  LoginDialog:
    on:
      LOGIN_SUCCESS: MainWindow
      CLOSE_WINDOW: Exit
  MainWindow:
    on:
      TAB_CHECKIN: CheckInTab
      TAB_EMPLOYEES: EmployeesTab
      TAB_RECORDS: RecordsTab
      TAB_ADMINS: AdminsTab                    # 增量: 新增第 4 Tab
      MENU_CHANGE_PASSWORD: ChangePasswordDialog # 增量: 新增菜单触发
      EXIT: Exit
  ChangePasswordDialog:                          # 增量: 新增对话框状态
    on:
      SAVE_SUCCESS: MainWindow
      SAVE_FAIL: ChangePasswordDialog
      CANCEL: MainWindow
  AdminsTab:                                     # 增量: 新增 Tab 状态
    on:
      OPEN_CREATE_DIALOG: AdminCreateDialog
      DELETE_ADMIN: AdminsTab                  # 行内删除, 走 _refresh_table
      REFRESH: AdminsTab
      BACK_TO_MAIN: MainWindow
  AdminCreateDialog:                             # 增量: 新增创建对话框状态
    on:
      SAVE_SUCCESS: AdminsTab
      SAVE_FAIL: AdminCreateDialog
      CANCEL: AdminsTab
  # 既有状态省略, 见 SPEC-001-C §5
```

**一致性保障**:
- 事件名 (`MENU_CHANGE_PASSWORD` / `TAB_ADMINS` / `SAVE_SUCCESS` / `DELETE_ADMIN`) 在代码中以显式方法名出现
- 任何新事件必须先回本节更新

---

## 6. 错误处理

### 6.1 错误码字典（本子 spec 新增 5 个）

| 错误码 | 触发条件 | 异常类 | UI 弹窗标题 | UI 弹窗内容 | 日志级别 |
|--------|----------|--------|-------------|-------------|----------|
| `USERNAME_EXISTS` | `Admin.select().where(username=...)` 命中 | `UsernameExists` (新增) | 创建失败 | "用户名 {username} 已存在 (错误码: USERNAME_EXISTS)" | WARN |
| `USERNAME_TOO_LONG` | `len(username) > 50` | `InternalError` (沿用 003) | 创建失败 | "username 长度 {len} > 50 (错误码: USERNAME_TOO_LONG)" | WARN |
| `PASSWORD_TOO_SHORT` | `len(password) < 6` | `PasswordTooShort` (沿用 003) | 修改失败 / 创建失败 | "新密码长度 < 6 (错误码: PASSWORD_TOO_SHORT)" | WARN |
| `AUTH_FAILED` | change_password 旧密码错 | `AuthFailed` (沿用 003) | 修改失败 | "旧密码错误 (错误码: AUTH_FAILED)" | WARN |
| `LAST_ADMIN_FORBIDDEN` | `admins.count() <= 1` 时 delete | `LastAdminForbidden` (新增) | 删除失败 | "系统至少保留 1 个管理员 (错误码: LAST_ADMIN_FORBIDDEN)" | WARN |
| `SELF_DELETE_FORBIDDEN` | `admin_id == current_admin.id` | `SelfDeleteForbidden` (新增) | 删除失败 | "不能删除当前登录的管理员 (错误码: SELF_DELETE_FORBIDDEN)" | WARN |
| `PASSWORD_MISMATCH` | 确认新密码 ≠ 新密码 | `ValueError` (内置) | 修改失败 | "两次输入的新密码不一致 (错误码: PASSWORD_MISMATCH)" | WARN |
| `ADMIN_NOT_FOUND` | delete admin_id 不存在 | `AdminNotFound` (沿用 003) | 删除失败 | "管理员 {id} 不存在 (错误码: ADMIN_NOT_FOUND)" | WARN |

### 6.2 utils.py 异常类新增

```python
# attendance/utils.py 追加（保持 14 个子类 + 3 个新增 = 17 个 AttendanceError 子类）

class UsernameExists(AttendanceError):
    """创建管理员时 username 已存在."""

class LastAdminForbidden(AttendanceError):
    """删除管理员时会锁死系统（仅剩 1 个 admin）."""

class SelfDeleteForbidden(AttendanceError):
    """删除管理员时试图删自己."""
```

### 6.3 日志规范

- 复用 SPEC-001-A §6.3 + SPEC-001-B §6.3 + SPEC-001-C §6.3 的 logger 规范。
- 关键 UI action: `ui.admin.change_password` / `ui.admin.create` / `ui.admin.delete`。

---

## 7. 测试用例与覆盖矩阵

| 需求来源 | 需求 ID | 类型 | 测试用例 ID | 自动化状态 |
|----------|---------|------|-------------|------------|
| Gherkin §2.1 改密 6 场景 | REQ-E-01 ~ E-06 | UI 测试 | TC-ATT-E01 ~ E05 | 已自动化（其中 E01+E06 合并, E05+06 合并, 共 5 个）|
| Gherkin §2.2 管理员管理 7 场景 | REQ-E-07 ~ E-13 | UI 测试 | TC-ATT-E06 ~ E08 | 已自动化（其中 E07+E08+E12 合并, 共 3 个）|
| B 层 AdminService.create / list_all / delete | REQ-E-B-01 ~ B-08 | Unit 测试 | TC-ATT-E09 ~ E10 | 已自动化（B 层 2 个, 合并 create+list+delete 3 个方法）|
| 端到端改密 | REQ-E-D-01 | E2E 测试 | TC-ATT-E11 | 已自动化 |

> UI 测试 + Unit 测试 + E2E 测试合计 **11 个 TC**, 严格按"和之前一样处理"。

详细 TC 列表（**11 个**）:

| TC ID | 文件 | 类型 | 函数名 | 覆盖需求 | 关键断言 |
|-------|------|------|--------|----------|----------|
| TC-ATT-E01 | tests/test_ui_change_password.py | UI | `test_TC_ATT_E01_change_password_success` | REQ-E-01 + E-02 | 弹窗含 3 QLineEdit + 2 QPushButton; 旧密码错 + 新密码 ≥ 6 + 确认匹配 → accept + statusBar 含"密码已修改" |
| TC-ATT-E02 | tests/test_ui_change_password.py | UI | `test_TC_ATT_E02_change_password_old_wrong` | REQ-E-03 | 旧密码错 → show_error AUTH_FAILED + dialog 保持 + statusBar 不更新 |
| TC-ATT-E03 | tests/test_ui_change_password.py | UI | `test_TC_ATT_E03_change_password_too_short` | REQ-E-04 | 新密码 "123" → show_error PASSWORD_TOO_SHORT + dialog 保持 |
| TC-ATT-E04 | tests/test_ui_change_password.py | UI | `test_TC_ATT_E04_change_password_mismatch` | REQ-E-05 | 确认新密码 "other789" ≠ 新密码 → show_error PASSWORD_MISMATCH + dialog 保持 |
| TC-ATT-E05 | tests/test_ui_change_password.py | UI | `test_TC_ATT_E05_change_password_cancel` | REQ-E-06 | 点击取消 → dialog reject + statusBar 不更新 |
| TC-ATT-E06 | tests/test_ui_admins.py | UI | `test_TC_ATT_E06_admins_tab_shows_list` | REQ-E-07 | 切到 Tab 3 显示 N 行; 当前 admin 行的删除按钮禁用 (self delete 保护) |
| TC-ATT-E07 | tests/test_ui_admins.py | UI | `test_TC_ATT_E07_admins_create_ok` | REQ-E-08 | mock AdminCreateDialog.exec_ 填 username="200003" + password="pass123" → accept; 表格 +1 行; admins 表 +1 行 |
| TC-ATT-E08 | tests/test_ui_admins.py | UI | `test_TC_ATT_E08_admins_delete_last_forbidden` | REQ-E-12 | 当前 admin 是最后 1 个; 调 _on_delete 走 self-delete 优先校验 (Gherkin REQ-E-12 self-delete 优先, count=1 同样自删保护, 不走 LastAdminForbidden); 弹 show_error SELF_DELETE_FORBIDDEN; 表格不变 |
| TC-ATT-E09 | tests/test_services.py | Unit | `test_TC_ATT_E09_admin_create_and_list_and_delete` | REQ-E-B-01~B-07 | create 新 admin + list_all 包含 + delete 非最后/非自己 成功; create 重名抛 UsernameExists; create 短密码抛 PasswordTooShort; delete 最后 1 个抛 LastAdminForbidden; delete 自己抛 SelfDeleteForbidden; delete 不存在 id 抛 AdminNotFound |
| TC-ATT-E10 | tests/test_services.py | Unit | `test_TC_ATT_E10_admin_create_username_validation` | REQ-E-B-02 + B-03 | username 校验（包含空字符串 / 纯空格 / 含特殊字符）+ 业务语义保持; 7 个边界 case (空 / 空格 / 长度 1 / 长度 50 / 长度 51→USERNAME_TOO_LONG / 特殊字符 / 中文) |
| TC-ATT-E11 | tests/test_e2e.py | E2E | `test_TC_ATT_E11_e2e_change_password_full_flow` | REQ-E-D-01 | logged_in_main_window + 触发「账户→修改密码」菜单 + ChangePasswordDialog 填合法值 → 接受; close dialog + 重新构造 MainWindow + LoginDialog 走新密码 login 成功; 旧密码 login 抛 AuthFailed |

**TC 总数**: 5 (UI 改密) + 3 (UI admins) + 2 (Unit) + 1 (E2E) = **11 个** ✅

> 测试在无头环境使用 pytest-qt + offscreen platform plugin (`QT_QPA_PLATFORM=offscreen`)。不依赖真实相机与显示器。

---

## 8. 非功能性需求

| 类别 | 具体要求 | 验证方法 |
|------|----------|----------|
| 性能 | 启动到登录框显示 < 3s（不变）| 手动 + time.monotonic 包裹 |
| 安全性 | 改密后强制下次登录生效（不立即刷新当前 session, 避免 UI 状态混乱）| TC-ATT-E01 断言 statusBar 含"下次登录生效" |
| 安全性 | 密码框 EchoMode.Password（沿用 003）| TC-ATT-E01 断言 QLineEdit.echoMode() == QLineEdit.Password |
| 安全性 | 自删 + 最后管理员双重保护 | TC-ATT-E08 + E09 验证 |
| 可用性 | 弹窗标题按错误码确定（沿用 003 规范）| §6.1 表格 |
| 可维护性 | 关键 UI action 日志（沿用 003 logger）| services.py 各方法 `logger.info(...)` |
| 约束 | 原 ui.py / recognition.py / get_name.py 哈希不变 | 初始化时 sha256 记录于 decisions; 实施后比对 |
| 约束 | conftest.py 不动（D 层 G-06 红线继承）| grep 验证 6 fixture 未变 |

---

## 9. 假设、约束与变更日志

### 9.1 假设

- SPEC-001-A + SPEC-001-B + SPEC-001-C 全部已闭环（决策 002 / 003 / 004 / 005）。
- 任务 1 弹窗卡死循环修复已闭环, 沉淀在 `decisions/006-v1-bugfix-checkin-warning-loop.md`, 不在本 spec 范围。
- MySQL 已运行, attendance_db 已建, 默认 admin/admin123 已 seed。
- 当前用户拍板: 任务 2 + 任务 3 走独立 spec + 决策 007 闭环（不与任务 1 合并）。

### 9.2 约束

- 不修改 `recognition.py` / `get_name.py` / `ui.py` 三个现有文件（AGENTS.md §5 红线）。
- 不修改 `attendance/services.py` 中 `authenticate` / `change_password` / `ensure_default` 既有方法（红线, 仅**新增**方法）。
- 不修改 `attendance/ui_login.py`（LoginDialog 不变, 改密走新弹窗）。
- 不修改 `tests/conftest.py`（D 层 G-06 红线继承）。
- UI 控件命名 (对象名) 严格按 §3.3 表格。
- 状态机事件名严格按 §5 表格。

### 9.3 变更日志

| 日期 | 版本 | 变更说明 | 关联决策 |
|------|------|----------|----------|
| 2026-08-24 | v1.0.0 | 新增管理员账户管理（改密 + 多管理员）| 决策 007 待 T-604 闭环 |

---

## 附录 A: 15 题落地前自检

> 来源: spec-writing skill 强制零自由发挥约束。按 11 维度（字段名 / 类型 / 必填性 / 默认值 / 校验器 / 枚举值 / 工厂方法签名 / 错误码 / 状态转换 / 测试用例 ID / CI 门禁规则）逐项核对。

| # | 自检问题 | 答案 | 关联章节 |
|---|----------|------|----------|
| 1 | AdminService.create 签名 `(username: str, password: str) -> Admin` 锁定？| ✅ §3.1 + §4 表格 | 实施时不可改 |
| 2 | AdminService.list_all 签名 `(self) -> list[Admin]` 锁定？| ✅ §3.1 | 实施时不可改 |
| 3 | AdminService.delete 签名 `(admin_id: int) -> None` 锁定？| ✅ §3.1 | 实施时不可改 |
| 4 | 3 个新异常类 `UsernameExists` / `LastAdminForbidden` / `SelfDeleteForbidden` 锁定为 `AttendanceError` 子类？| ✅ §6.2 | utils.py 实施时不可改 |
| 5 | 8 个错误码字面值 `USERNAME_EXISTS` / `USERNAME_TOO_LONG` / `PASSWORD_TOO_SHORT` / `AUTH_FAILED` / `LAST_ADMIN_FORBIDDEN` / `SELF_DELETE_FORBIDDEN` / `PASSWORD_MISMATCH` / `ADMIN_NOT_FOUND` 锁定？| ✅ §6.1 | UI 标题映射 + 测试断言不可改 |
| 6 | 11 个 TC 函数名（`test_TC_ATT_E01` ~ `test_TC_ATT_E11`）锁定？| ✅ §7 表格 | 实施时不可改 |
| 7 | 5 个 UI TC 放 `tests/test_ui_change_password.py`（4 个） + `tests/test_ui_admins.py`（3 个, 含 2 个 + 1 个其他）锁定？| ✅ §7 表格 | 实施时不可改 |
| 8 | 2 个 Unit TC 放 `tests/test_services.py` 末尾追加（不新建文件）锁定？| ✅ §7 表格 | 实施时不可改 |
| 9 | 1 个 E2E TC 放 `tests/test_e2e.py` 末尾追加锁定？| ✅ §7 表格 | 实施时不可改 |
| 10 | conftest.py 不动（D 层 G-06 红线继承）锁定？| ✅ §0 G-06 | 实施时不可改 |
| 11 | 原 ui.py / recognition.py / get_name.py 哈希不变锁定？| ✅ §0 G-05 | 实施时不可改 |
| 12 | B 层 `authenticate` / `change_password` / `ensure_default` 不修改, 仅**新增**方法锁定？| ✅ §9.2 约束 | 实施时不可改 |
| 13 | C 层 LoginDialog / MainWindow 现有 3 Tab 不修改, 仅**新增** 1 Tab + 1 菜单项锁定？| ✅ §0 关联代码 | 实施时不可改 |
| 14 | `_admin` 当前管理员上下文通过 `MainWindow.__init__(admin)` 注入, 不再读 session/全局变量？| ✅ §1 术语表 + §5 状态机 | 实施时不可改 |
| 15 | 任务 1 弹窗卡死循环修复**不**在本 spec 范围, 沉淀在决策 006？| ✅ §0 关联决策 + §9.1 假设 | 实施时不可改 |

**自检结论**: 11 维度全部钉死, 可进入实施阶段。
