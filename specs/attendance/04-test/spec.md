# SPEC-001-D: 测试与验证（集成 + 端到端）

> **规范状态**: 已批准
> **版本**: v1.0.0
> **拆分自**: SPEC-001 v1.0.0（见 `specs/attendance/_LEGACY.md`）
> **依赖**: SPEC-001-A + SPEC-001-B + SPEC-001-C 全部已闭环（决策 002 / 003 / 004）
> **代码包路径**: `tests/test_integration.py`、`tests/test_e2e.py`
> **最后修改**: 2026-08-24

---

## 0. 文档头与元数据

- **文件路径**: `/specs/attendance/04-test/spec.md`
- **关联代码路径**:
  - 测试入口: `tests/test_integration.py`（4 个集成 TC，D01~D04）
  - 测试入口: `tests/test_e2e.py`（7 个端到端 TC，D05~D11）
  - 复用 conftest: `tests/conftest.py`（6 个 fixture 严格不动，详见 §3.1）
  - 被测代码: `attendance/services.py`（B 层闭环产物，不修改）、`attendance/ui_*.py` + `attendance_ui.py`（C 层闭环产物，不修改）
- **CI 门禁规则**（必须全部满足才允许 D 层闭环）:
  - G-01 `pytest tests/test_integration.py tests/test_e2e.py -v --tb=short` 退出码 0，11/11 PASSED
  - G-02 `pytest --collect-only -q | grep -c "test_TC_ATT_D"` 输出 11
  - G-03 完整 D 层耗时 < 60 秒（`time pytest tests/test_integration.py tests/test_e2e.py -q`）
  - G-04 连续 3 次跑 0 flake（`for i in 1 2 3; do pytest ...; done` 全 RC 0）
  - G-05 启动命令前置 `QT_QPA_PLATFORM=offscreen` 环境变量
  - G-06 D 层不新增 conftest fixture（违反即 spec 越界）
  - G-07 本文件修改时，`test_integration.py` + `test_e2e.py` + `tasks.md` + `checklist.md` 必须同步修改

---

## 1. 术语表与统一语言

| 术语 | 英文名 | 类型 | 定义 | 代码映射 | 数据库映射 | 示例 |
|------|--------|------|------|----------|------------|------|
| 测试用例 | Test Case | 名词 | 一个 pytest 函数, 命名 `test_TC_ATT_D{NN}_<description>` | `def test_TC_ATT_D01_xxx():` | — | `test_TC_ATT_D07_e2e_add_employee_check_record` |
| 集成测试 | Integration Test | 测试类型 | 跨 Service 协作, 不涉及 UI | `tests/test_integration.py` | 复用 `attendance_db` | D01~D04 |
| 端到端测试 | End-to-End Test | 测试类型 | 完整流程, 涉及 UI + Service | `tests/test_e2e.py` | 复用 `attendance_db` | D05~D11 |
| 测试夹具 | Fixture | pytest 概念 | setup / teardown, 分 session/function scope | `@pytest.fixture` | — | `_db_session` (session) / `sample_schedule` (function) |
| 测试替身 | Mock | 测试概念 | 替代真实依赖的对象 | `monkeypatch.setattr` | — | `_FakeCaptureOk` |
| 复用 conftest fixture | SharedFixture | 资源 | `tests/conftest.py` 已定义的 6 个 fixture | 严格不动 | — | `_db_session` / `_patch_argv` / `_per_test_reset` / `sample_schedule` / `face_image` / `sample_employees` |
| D 层文件内 fixture | LocalFixture | 资源 | 仅在 D 层 2 个测试文件内定义, 不进 conftest | `default_admin` / `logged_in_main_window` | — | `default_admin` |
| 默认管理员 | Default Admin | 测试数据 | username=admin / password=admin123, sha256 哈希 | `AdminService.ensure_default` | `admins` 表 | `username="admin"` |
| 种子班次 | Seed Schedule | 测试数据 | init_db 预置的 1 个 Schedule, name="测试班次" | init_db 自动 seed | `schedules` 表 | `name="测试班次"` |
| 临时人脸照片 | face_image | 测试数据 | tmp_path 下 2 字节 .jpg + monkeypatch 放宽 path | `conftest.face_image` | `employees.face_image_path` | `tmp_path/100001.jpg` |
| 登录属性读 | dlg.admin | API 模式 | 登录成功后 `LoginDialog.admin` 是 `Admin` 实例 | `ui_login.LoginDialog.admin` | — | `isinstance(dlg.admin, Admin)` |
| Tab 切换 | `tabs.setCurrentWidget` | API 模式 | QTabWidget 标准 API, 用于 e2e 跳转 | `MainWindow.tabs` | — | `main.tabs.setCurrentWidget(main.employees_tab)` |
| 识别直接调 | `_do_recognition(frame)` | 测试技巧 | 跳过 `QTimer` 30ms 真实触发 | `ui_checkin.CheckInTab._do_recognition` | — | `tab._do_recognition(np.zeros(...))` |
| 关闭事件直接调 | `closeEvent(QCloseEvent())` | 测试技巧 | 绕开 `QT_QPA_PLATFORM=offscreen` 下 `close()` 不触发 `closeEvent` 的坑 | `MainWindow.closeEvent` | — | `main.closeEvent(QtGui.QCloseEvent())` |

**一致性保障**:
- 任何代码中出现的 TC 编号, 必须与本文 §7 覆盖矩阵逐字一致
- 任何测试函数名, 必须以 `test_TC_ATT_D` 前缀开头, 编号 D01~D11 与本文一一对应
- D 层不新增 conftest fixture, 违反 = spec 越界, 不允许 D 层闭环

---

## 2. 用户故事与验收场景（Gherkin）

### 2.1 集成场景（Service 协作）

```gherkin
功能: 业务服务层全链路打通
  作为 开发者
  我需要 跨 Service 协作
  以便 保证 Schedule→Employee→CheckRecord 数据流正确

  场景: TC-ATT-D01 service_chain_schedule_employee_check
    假设 attendance_db 已 init_db, Schedule 含种子班次
    当 调 ScheduleService.list_all() 取 schedule
    且 调 EmployeeService.create(employee_id="200001", name="集成A", face_image_path=face_image, schedule_id=schedule.id)
    且 调 CheckService.create_record(employee_id="200001", check_type="check_in")
    且 调 CheckService.create_record(employee_id="200001", check_type="check_out")
    那么 CheckRecord.select().where(employee_id="200001").count() == 2
    且 2 条记录 check_type 分别为 "check_in" / "check_out"
    且 Employee.select().where(employee_id="200001").get().name == "集成A"

功能: 删除约束级联
  作为 开发者
  我需要 验证删除员工的级联约束
  以便 保证数据完整性

  场景: TC-ATT-D02 delete_cascade_constraint
    假设 Employee "200002" 存在, 且有 1 条 CheckRecord
    当 调 EmployeeService.delete("200002")
    那么 抛 EmployeeHasRecords (AttendanceError 子类, 错误码 "EMPLOYEE_HAS_RECORDS")
    且 Employee "200002" 仍存在
    当 调 CheckRecord.delete().where(employee_id="200002").execute()
    且 调 EmployeeService.delete("200002")
    那么 Employee "200002" 不再存在

功能: 管理员改密
  作为 开发者
  我需要 验证密码修改流程
  以便 保证 AdminService.change_password 行为正确

  场景: TC-ATT-D03 admin_change_password
    假设 已调 AdminService.ensure_default("admin", "admin123")
    当 调 AdminService.authenticate("admin", "admin123") 应成功, 返回 admin
    且 记 admin.id = aid
    且 调 AdminService.change_password(aid, "admin123", "newpass456")
    那么 调 AdminService.authenticate("admin", "admin123") 抛 AuthFailed
    且 调 AdminService.authenticate("admin", "newpass456") 成功, 返回 admin

功能: 跨天记录查询
  作为 开发者
  我需要 验证跨天日期范围查询
  以便 保证 CheckService.list_records 行为正确

  场景: TC-ATT-D04 list_records_date_range
    假设 Employee "200004" 存在
    且 CheckRecord 已有 3 条: 昨天 check_in, 昨天 check_out, 今天 check_in
    当 调 CheckService.list_records(date_from=昨天, date_to=今天)
    那么 返回列表长度 == 3
    且 列表按 check_time 降序排列
    且 date_from > date_to 时抛 DateRangeInvalid
```

### 2.2 端到端场景（UI + Service）

```gherkin
功能: 系统入口可导入
  作为 开发者
  我需要 attendance_ui 可被 import
  以便 验证入口模块签名稳定

  场景: TC-ATT-D05 attendance_ui_importable
    假设 QT_QPA_PLATFORM=offscreen 环境变量已设
    当 用 importlib.import_module("attendance_ui") 加载模块
    那么 加载无 ImportError
    且 attendance_ui.main 是 callable
    且 attendance_ui.main 接受 0 个位置参数
    且 attendance_ui.main 接受 0 个关键字参数

功能: 登录进入主窗口
  作为 管理员
  我需要 用默认账号登录
  以便 进入主窗口

  场景: TC-ATT-D06 login_enters_main_window
    假设 已调 AdminService.ensure_default("admin", "admin123")
    当 创建 LoginDialog
    且 Mock LoginDialog._on_login_clicked 走成功路径 (等同于输入 admin/admin123 后点登录)
    那么 dlg.admin 是 Admin 实例
    且 dlg.admin.username == "admin"
    且 创建 MainWindow(dlg.admin) 成功
    且 MainWindow.tabs.count() == 3
    且 statusBar 当前消息文本 含 "admin"

功能: 完整业务流（增员 → 模拟识别 → 打卡 → 查记录）
  作为 管理员
  我需要 走完一遍完整流程
  以便 验证整个系统端到端跑通

  场景: TC-ATT-D07 e2e_add_employee_check_record
    假设 管理员已登录, MainWindow 已显示
    且 已 mock recognition.recognition 返回 [[0,0,100,100,0.99,0,"face"]]
    且 已 mock get_name.rec 返回 "D07-001"
    且 已 mock CheckConfirmDialog.exec_ 为 fake_exec (内部调 _confirm("check_in") 后返回 Accepted)
    当 切换到 EmployeesTab
    且 Mock EmployeeDialog.exec_ 为 fake_exec (内部填 employee_id="D07-001" name="集成B" schedule_id=sample_schedule.id 后 accept)
    且 调 EmployeesTab.btn_add.click() (触发 _on_add)
    那么 Employees 表格新增 1 行 (工号 D07-001)
    且 DB Employee.select().where(employee_id="D07-001").exists() == True
    当 切换到 CheckInTab
    且 调 checkin_tab._do_recognition(zero_frame) (跳过 QTimer)
    那么 CheckRecord 新增 1 条 (employee_id="D07-001", check_type="check_in", check_date=今天)
    当 切换到 RecordsTab
    且 调 RecordsTab._refresh_table()
    那么 表格显示 1 行 (工号 D07-001, 姓名 集成B, 类型 签到)

功能: 主窗口资源释放
  作为 管理员
  我需要 关闭主窗口
  以便 资源得到正确释放

  场景: TC-ATT-D08 mainwindow_close_releases_camera
    假设 MainWindow 已创建, CheckInTab._camera 已被设置 (mock 为 _FakeCaptureOk)
    且 CheckInTab._timer 已被设置 (mock 为 QTimer 实例)
    当 调 mainwindow.closeEvent(QtGui.QCloseEvent())
    那么 CheckInTab._close_camera 应被调用 1 次
    且 CheckInTab._camera 应为 None
    且 CheckInTab._timer 应为 None

功能: 菜单退出
  作为 管理员
  我需要 点菜单"文件>退出"
  以便 安全退出系统

  场景: TC-ATT-D09 menu_exit_calls_close_db
    假设 MainWindow 已创建
    且 Mock close_db 计数 (monkeypatch attendance.db.close_db)
    且 Mock QApplication.quit 计数
    当 触发 action_exit.triggered
    那么 close_db 应被调用 1 次
    且 QApplication.quit 应被调用 1 次

功能: 相机资源循环
  作为 开发者
  我需要 验证 _open_camera / _close_camera 循环
  以便 保证无资源泄漏

  场景: TC-ATT-D10 camera_open_close_cycle
    假设 cv2.VideoCapture 已被 mock 为 _FakeCaptureOk
    当 循环 3 次:
      且 调 checkin_tab._open_camera()
      且 调 checkin_tab._close_camera()
    那么 第 1/2/3 次 _close_camera 后 checkin_tab._camera 都为 None
    且 第 1/2/3 次 _close_camera 后 checkin_tab._timer 都为 None 或不活跃

功能: 入口函数签名
  作为 开发者
  我需要 attendance_ui.main 签名稳定
  以便 集成脚本可调用

  场景: TC-ATT-D11 attendance_ui_main_signature
    假设 QT_QPA_PLATFORM=offscreen 环境变量已设
    当 用 inspect.signature(attendance_ui.main) 取签名
    那么 签名参数数量 == 0
    且 签名不含 VAR_POSITIONAL (*args)
    且 签名不含 VAR_KEYWORD (**kwargs)
```

---

## 3. 测试入口契约（Pytest Invocation）

### 3.1 复用 conftest fixture（严格不动）

| Fixture 名 | 作用域 | autouse | 来源 | D 层用法 |
|------------|--------|---------|------|----------|
| `_db_session` | session | 是 | conftest.py L28-34 | D01~D11 全部依赖（自动 init_db + close_db） |
| `_patch_argv` | function | 是 | conftest.py L37-49 | D05~D11 依赖（自动绕开 recognition.py argparse） |
| `_per_test_reset` | function | 是 | conftest.py L57-71 | D01~D11 全部依赖（自动清 CheckRecord/Employee/Admin, 保证 Schedule） |
| `sample_schedule` | function | 否 | conftest.py L79-82 | D01, D02, D07 显式调用 |
| `face_image` | function | 否 | conftest.py L85-99 | D01, D02, D07 显式调用（.jpg 临时文件 + 放宽 path） |
| `sample_employees` | function | 否 | conftest.py L102-119 | D 层不主动用（D 层用自己创建的固定 employee_id, 不与 sample 撞） |

**红线**: D 层严禁新增 conftest.py fixture, 违反 = spec 越界, 不允许 D 层闭环。

### 3.2 D 层文件内 fixture（D 文件内自管, 不进 conftest）

| Fixture 名 | 所在文件 | 作用域 | 工厂方法签名 | 作用 | 复用 TC |
|------------|----------|--------|---------------|------|---------|
| `default_admin` | test_integration.py | function | `def default_admin() -> Admin` | 调 `AdminService.ensure_default("admin", "admin123")` 1 次, 返回 admin 实例 | D03 |
| `logged_in_main_window` | test_e2e.py | function | `def logged_in_main_window(qtbot, monkeypatch) -> MainWindow` | 调 ensure_default + authenticate + MainWindow(admin); 自动 mock QApplication.quit 计数; 返回 main 实例 | D06, D07, D08, D09 |
| `_FakeCaptureOk` (类) | test_e2e.py | — | `class _FakeCaptureOk:` 见 §3.4 | D10 模拟可用相机 | D10 |

**D 层文件内 fixture 注入规则**:
- 不放 conftest.py（违反 G-06）
- 不与 conftest.py 现有 fixture 重名（避免覆盖）
- 仅供同文件 TC 使用, 不跨文件引用

### 3.3 Mock 对象契约

**`_FakeCaptureOk`**（D08, D10 用, 与 C 阶段 2 同款）:

```python
class _FakeCaptureOk:
    def __init__(self, *args, **kwargs):
        self._opened = True
    def isOpened(self) -> bool:
        return self._opened
    def read(self) -> tuple:
        import numpy as np
        return True, np.zeros((480, 640, 3), dtype=np.uint8)
    def release(self) -> None:
        self._opened = False
```

**D07 端到端识别 mock 链**:

| Mock 目标 | 替换值 | monkeypatch 路径 | 行为 |
|-----------|--------|------------------|------|
| `recognition.recognition` | `lambda frame: [[0, 0, 100, 100, 0.99, 0, "face"]]` | `monkeypatch.setattr("recognition.recognition", lambda frame: [[0, 0, 100, 100, 0.99, 0, "face"]])` | 返回 1 个检测框 |
| `get_name.rec` | `lambda frame, box: "D07-001"` | `monkeypatch.setattr("get_name.rec", lambda frame, box: "D07-001")` | 返回 employee_id 字符串 |
| `CheckConfirmDialog.exec_` | `fake_exec` (内部调 `_confirm("check_in")` 后返回 `Accepted`) | `monkeypatch.setattr(CheckConfirmDialog, "exec_", fake_exec)` | 走通"签到"路径 |

**`fake_exec` 实现**（D07 用）:

```python
def fake_exec(self_dialog):
    # self_dialog 是 CheckConfirmDialog 实例
    # _confirm 在 CheckConfirmDialog 内, 通过 dlg._confirm("check_in") 调用
    self_dialog._confirm("check_in")
    return QtWidgets.QDialog.Accepted
```

### 3.4 Pytest 命令契约

```bash
# 单跑 D 层 (CI 主用, 启动命令前置 offscreen 环境变量)
$env:QT_QPA_PLATFORM="offscreen"; pytest tests/test_integration.py tests/test_e2e.py -v --tb=short -p no:cacheprovider

# 收集用例数量 (G-02 验收)
pytest --collect-only -q | grep -c "test_TC_ATT_D"
# 期望: 11

# 性能验收 (G-03)
time pytest tests/test_integration.py tests/test_e2e.py -q
# 期望: real < 60s

# Flake 验收 (G-04)
for i in 1 2 3; do pytest tests/test_integration.py tests/test_e2e.py -q || exit 1; done
# 期望: 3 次全 RC 0

# 全量 (A + B + C + D, A 层 0 自动化, 实际跑 B+C+D = 47 TC)
QT_QPA_PLATFORM=offscreen pytest tests/ -v --tb=short
```

### 3.5 Pytest 不允许项（CI 红线）

- ❌ `pytest-xdist` 并行跑（会破坏 `_per_test_reset` 数据库隔离, 必 fail）
- ❌ `--ff` / `-x` 跳测（CI 必须跑完全部 11 个）
- ❌ 跳过 D01~D11 任何一个（CI 门禁 G-01 失败）
- ❌ 跑超 60 秒（G-03 门禁失败）
- ❌ 不设 `QT_QPA_PLATFORM=offscreen`（D05~D11 涉及 Qt 初始化, 无 offscreen 必 fail）
- ❌ 修改 `tests/conftest.py` 新增 fixture（G-06 红线）
- ❌ `unittest.mock.patch` 装饰器（与 C 层风格不一致, 用 monkeypatch）

---

## 4. 测试数据模型

D 层不新增数据模型, 全部复用 B 层（`attendance/models.py`）的 4 个 Model:

| Model | D 层用法 | 关键字段 |
|-------|----------|----------|
| `Admin` | D03 改密, D05~D11 登录 | `id`, `username`, `password_hash` |
| `Schedule` | D01, D02, D07 取 schedule_id | `id`, `name="测试班次"`, `work_start`, `work_end` |
| `Employee` | D01 建员工, D02 删除约束, D07 增员 | `id`, `employee_id`, `name`, `face_image_path`, `schedule_id`, `is_active` |
| `CheckRecord` | D01 打卡, D02 级联, D04 跨天查询, D07 端到端 | `id`, `employee_id`, `check_type`, `check_date`, `check_time` |

**TC 内固定值约定**（避免与 conftest.sample_employees 撞 ID）:
- D01 用 `employee_id="D01-001"`
- D02 用 `employee_id="D02-001"`
- D03 不创建 Employee（仅操作 Admin）
- D04 用 `employee_id="D04-001"`
- D07 用 `employee_id="D07-001"`
- D08, D09, D10 不创建 Employee（仅操作 MainWindow / CheckInTab）
- D11 不创建任何数据

---

## 5. 行为规则

### 5.1 setup / teardown 时序

| 阶段 | 行为 | 来源 |
|------|------|------|
| 测试 session 启动 | `init_db(config)` 建库 + seed 1 个 Schedule | `_db_session` (session, autouse) |
| 测试 session 结束 | `close_db()` 关连接 | `_db_session` (yield 后) |
| 每个 TC 前 | `CheckRecord.delete(); Employee.delete(); Admin.delete()` | `_per_test_reset` (function, autouse) |
| 每个 TC 前 | Schedule 不存在时重建种子 (`name="测试班次"`) | `_per_test_reset` |
| 每个 TC 前 | `sys.argv = [script_name]`（绕开 recognition.py argparse） | `_patch_argv` (function, autouse) |
| TC 函数体 | 直接操作 + `monkeypatch.setattr` 打桩 | TC 自身 |
| 每个 TC 后 | `monkeypatch` 自动还原所有 `setattr` | pytest 内置 |
| 每个 TC 后 | `sys.argv = original` 还原 | `_patch_argv` try/finally |

### 5.2 数据库隔离规则

- 复用 `attendance_db`（与 B/C 层同库, 不另建 `_test` 库）
- 每 TC 前 `_per_test_reset` 清表, 保留 `Schedule`（init_db seed）
- TC 内创建的数据用固定 `employee_id`（`D01-001` / `D02-001` / `D04-001` / `D07-001`）, 便于断言
- TC 结束后不主动 `drop table`（避免破坏 seed 状态影响下一个 TC）

### 5.3 Mock 隔离规则

- 全部用 `monkeypatch.setattr`（pytest 内置 fixture）
- TC 结束 monkeypatch 自动还原, 不需要手动 teardown
- 严禁 `unittest.mock.patch` 装饰器（与 C 层风格一致）
- D10 中 `cv2.VideoCapture` 用 monkeypatch 替换; D11 静态 import 验证, 不打桩

### 5.4 时序约定（避免 QTimer 30ms 真实触发）

- D05~D11 端到端测试**不**主动调 `app.processEvents()` 在循环里
- D07 模拟识别时**直接**调 `checkin_tab._do_recognition(frame)`, 跳过 `QTimer`
- D07 模拟"签到确认"时 monkeypatch `CheckConfirmDialog.exec_` 为 `fake_exec`
- D08 模拟"关闭主窗口"时**直接**调 `mainwindow.closeEvent(QtGui.QCloseEvent())`（与 C04 同思路, 绕开 offscreen 平台 `close()` 不触发 `closeEvent` 的坑, AGENTS.md §6 L-003）

---

## 6. 错误处理

### 6.1 D 层不主动测的错误码（B/C 层已覆盖）

| 错误源 | 覆盖位置 |
|--------|----------|
| 14 个 `AttendanceError` 子类（如 `AuthFailed` / `EmployeeHasRecords` / `DateRangeReversed` 等） | B 层 18 个 TC（test_services.py） |
| C 层 UI 错误码（`AUTH_FAILED` / `EMPLOYEE_ID_INVALID` 等） | C 层 18 个 TC（test_ui_*.py 4 文件） |

### 6.2 D 层要触发的错误码

| TC | 触发的异常类 | 触发条件 |
|----|-------------|----------|
| D02 | `EmployeeHasRecords`（`AttendanceError` 子类） | `EmployeeService.delete` 在有 CheckRecord 时 |
| D04 | `DateRangeInvalid`（`AttendanceError` 子类） | `CheckService.list_records` date_from > date_to |

**D 层 TC 失败模式处理**:

| 失败模式 | 处理 |
|----------|------|
| TC 内部 `assert` 失败 | pytest 自动报 AssertionError, `--tb=short` 输出 |
| 整体 > 60s | CI 门禁 G-03 失败, 标"性能不达标" |
| 连续 3 次有 flake | 标"不稳定", 阻塞 D 层闭环 |
| MySQL 不可达 | `_db_session` 抛 `DBConnectFailed`, 整个 tests/ 全部 skip |

---

## 7. 测试用例与覆盖矩阵

| 需求来源 | 需求 ID | 类型 | TC ID | 自动化状态 | TC 函数名 | 文件 |
|----------|---------|------|-------|------------|-----------|------|
| §2.1 全链路 | REQ-D-01 | 集成 | TC-ATT-D01 | 已自动化 | `test_TC_ATT_D01_service_chain_schedule_employee_check` | tests/test_integration.py |
| §2.1 级联约束 | REQ-D-02 | 集成 | TC-ATT-D02 | 已自动化 | `test_TC_ATT_D02_delete_cascade_constraint` | tests/test_integration.py |
| §2.1 改密 | REQ-D-03 | 集成 | TC-ATT-D03 | 已自动化 | `test_TC_ATT_D03_admin_change_password` | tests/test_integration.py |
| §2.1 跨天 | REQ-D-04 | 集成 | TC-ATT-D04 | 已自动化 | `test_TC_ATT_D04_list_records_date_range` | tests/test_integration.py |
| §2.2 入口可导入 | REQ-D-05 | 端到端 | TC-ATT-D05 | 已自动化 | `test_TC_ATT_D05_attendance_ui_importable` | tests/test_e2e.py |
| §2.2 登录 | REQ-D-06 | 端到端 | TC-ATT-D06 | 已自动化 | `test_TC_ATT_D06_login_enters_main_window` | tests/test_e2e.py |
| §2.2 完整流程 | REQ-D-07 | 端到端 | TC-ATT-D07 | 已自动化 | `test_TC_ATT_D07_e2e_add_employee_check_record` | tests/test_e2e.py |
| §2.2 关闭资源 | REQ-D-08 | 端到端 | TC-ATT-D08 | 已自动化 | `test_TC_ATT_D08_mainwindow_close_releases_camera` | tests/test_e2e.py |
| §2.2 菜单退出 | REQ-D-09 | 端到端 | TC-ATT-D09 | 已自动化 | `test_TC_ATT_D09_menu_exit_calls_close_db` | tests/test_e2e.py |
| §2.2 相机循环 | REQ-D-10 | 端到端 | TC-ATT-D10 | 已自动化 | `test_TC_ATT_D10_camera_open_close_cycle` | tests/test_e2e.py |
| §2.2 入口签名 | REQ-D-11 | 端到端 | TC-ATT-D11 | 已自动化 | `test_TC_ATT_D11_attendance_ui_main_signature` | tests/test_e2e.py |

**总计**: 11 个 TC（4 集成 + 7 端到端）, 0 个未自动化, 0 个跳过。

### 7.1 全项目测试矩阵汇总

| 来源 | 数量 | 测试文件 | 决策 |
|------|------|----------|------|
| SPEC-001-A 基础层 | 0 自动化（沿用 002 决策的 smoke test） | — | decisions/002-v1-foundation-shipped.md |
| SPEC-001-B 服务层 | 18 | tests/test_services.py | decisions/003-v1-service-shipped.md |
| SPEC-001-C UI 层 | 18 | tests/test_ui_login.py / checkin.py / employees.py / records.py | decisions/004-v1-ui-shipped.md |
| SPEC-001-D 测试层 | 11 | tests/test_integration.py (4) + test_e2e.py (7) | 本 spec（D 层闭环后写 decision 005） |
| **合计自动化** | **47** | — | — |

---

## 8. 非功能性需求

| 类别 | 具体要求 | 验证方法 |
|------|----------|----------|
| 性能 | D 层 11 TC 整体耗时 < 60 秒 | G-03 `time pytest tests/test_integration.py tests/test_e2e.py -q` 记录 < 60 |
| 稳定性 | 连续 3 次跑 0 flake | G-04 `for i in 1 2 3; do pytest ... -q; done` 全 RC 0 |
| 可重现性 | 同一 MySQL 实例, 同一 conftest, 任意两次跑结果完全一致 | 两次跑输出 diff 为空 |
| 隔离性 | 一 TC 失败不影响其他 TC（因 `_per_test_reset` + `_db_session` 隔离） | 故意让 D03 失败, 跑 D04 仍通过 |
| 可观测性 | TC 失败时打印 traceback + fixture 状态 | pytest 默认 `--tb=short` |
| 入口可导入 | `attendance_ui.py` 可被 `importlib.import_module` 加载, 无 ImportError | D05 |
| 入口签名 | `attendance_ui.main()` 接受 0 个位置参数 + 0 个关键字参数 + 不含 VAR_POSITIONAL + 不含 VAR_KEYWORD | D11 `inspect.signature` |
| 不依赖真实相机 | D08/D10 用 `_FakeCaptureOk` mock `cv2.VideoCapture` | 代码中无 `cv2.VideoCapture(0)` 真实调用 |
| 不依赖真实模型推理 | D07 mock `recognition.recognition` + `get_name.rec` | 代码中无真实 `recognition()` / `rec()` 调用 |

---

## 9. 假设、约束与变更日志

### 9.1 假设

- A1. MySQL `127.0.0.1:3306` 可用, root 凭证与 `attendance_config.ini` 一致
- A2. opencv4 环境已装 `pytest==8.4.2` + `pytest-qt==4.5.0`（C 阶段已完成）
- A3. 训练权重 `runs/detect/train/weights/best.pt` 存在（UI 启动会触发 `import recognition` 加载模型, 即使 mock 也需要 import 成功）
- A4. B 层 4 个 Service + 14 个异常类签名已稳定（decision 003 闭环）
- A5. C 层 6 个 UI 模块 + 1 个根入口签名已稳定（decision 004 闭环）
- A6. `tests/conftest.py` 6 个 fixture 已稳定, D 层不修改（用户拍板决策）
- A7. `attendance/services.py` 与 `attendance/ui_*.py` 已稳定, D 层不修改（红线）
- A8. `attendance_config.ini` 已含正确 MySQL root 凭证（用户已确认）
- A9. A 层 0 自动化测试被接受（用户拍板, 沿用 002 决策的 smoke test 9 项手测）

### 9.2 约束

- C1. 不测试真实相机（D08/D10 用 `_FakeCaptureOk` mock）
- C2. 不测试真实模型推理（D07 mock `recognition.recognition` + `get_name.rec`）
- C3. 不重复 B/C 层 36 个已测路径（D 层只补跨层集成 + UI 端到端）
- C4. 不修改 `tests/conftest.py` 已有 fixture（用户拍板, G-06 红线）
- C5. 不修改 `attendance/services.py`（B 层闭环, 红线）
- C6. 不修改 `attendance/ui_*.py` + `attendance_ui.py`（C 层闭环, 红线）
- C7. 不修改 `recognition.py` / `get_name.py` / `ui.py` / `mydata.yaml` / 训练权重（AGENTS.md §5 红线）
- C8. D 层 11 个 TC 必须 100% 通过 + 0 flake 才允许 D 层闭环
- C9. 跑测试必须前置 `QT_QPA_PLATFORM=offscreen` 环境变量, 否则 D05~D11 fail
- C10. 严禁 `pytest-xdist` 并行 / `--ff` / `-x` 跳测（破坏数据库隔离）

### 9.3 变更日志

| 日期 | 版本 | 变更说明 |
|------|------|----------|
| 2026-08-24 | v1.0.0 | 初始版本, 11 个 TC（4 集成 + 7 端到端）, D 层不修改 conftest, 不补 A 层 12 TC, 复用 attendance_db |

---

## 附录 A：15 题自检（spec-writing skill 落地前自检）

执行时间: 2026-08-24, 执行人: agent

### A.1 严格对齐（5 题）

- [x] Q1 字段名: ✅ TC ID 格式（`test_TC_ATT_D{NN}_<description>`）、fixture 名（`default_admin` / `logged_in_main_window` / `_FakeCaptureOk`）、错误类（`EmployeeHasRecords` / `DateRangeReversed`）与 §1 术语表 + §3.2 + §6.2 逐字一致
- [x] Q2 函数签名: ✅ §3.2 `default_admin() -> Admin` / `logged_in_main_window(qtbot, monkeypatch) -> MainWindow` / `_FakeCaptureOk.__init__(self, *args, **kwargs)` 全部明确参数与返回类型
- [x] Q3 枚举值: ✅ §4 TC 内固定 `employee_id` 值（`D01-001` / `D02-001` / `D04-001` / `D07-001`）与 §7 矩阵行逐字一致
- [x] Q4 测试用例 ID: ✅ §7 共 11 个 TC-ATT-D01~D11, tasks.md 全部覆盖, checklist.md 全部对应
- [x] Q5 默认值/校验器/错误码: ✅ §5.1 时序 8 阶段 + §5.2 数据库 4 规则 + §5.3 Mock 3 规则 + §5.4 时序 4 约定 + §6.2 错误码 2 条全部钉死

### A.2 细节遗漏（5 题）

- [x] Q6 10 段结构: ✅ §0-§9 齐全, 附录 A 自检
- [x] Q7 每段示例: ✅ §1 表格 / §2 Gherkin 11 场景 / §3 4 小节含 fixture 表 + pytest 命令 / §4 引用 + 固定值表 / §5 4 小节规则 / §6 错误码表 / §7 矩阵 + 汇总 / §8 9 项 / §9 假设 9 + 约束 10 + 变更日志
- [x] Q8 CI 门禁可执行: ✅ §0 G-01~G-07 共 7 条门禁全部可执行（pytest 命令 + grep + time + for 循环）
- [x] Q9 假设约束: ✅ §9.1 9 条假设 + §9.2 10 条约束
- [x] Q10 变更日志: ✅ §9.3 含 2026-08-24 / v1.0.0 / 初始版本摘要

### A.3 自由发挥空间（5 题）

- [x] Q11 黑名单模糊词: ✅ 全文检索"待定 / 暂定 / 可酌情 / TODO / TBD" 0 命中（除 _LEGACY.md 引用外）
- [x] Q12 Optional 触发条件: ✅ §3.2 fixture 函数签名明确返回类型（`-> Admin` / `-> MainWindow`）, §3.4 pytest 命令含前置 `QT_QPA_PLATFORM=offscreen` 触发条件
- [x] Q13 非功能需求验证方法: ✅ §8 9 项均配 `time pytest` / `for i in 1 2 3` / 代码搜索 等可执行验证方法
- [x] Q14 类比精确约束: ✅ §3.3 `_FakeCaptureOk` 完整代码, §3.3 `fake_exec` 完整代码, §3.4 4 个 pytest 命令完整字符串
- [x] Q15 实施必需动作声明: ✅ §0 G-01~G-07 7 条门禁 + §3.5 7 条不允许项 + §5.1~5.4 15 条运行时规则 全部钉死, 实施者无自由发挥空间

### 结论

- 总计 ✅: 15/15
- 总计 ❌: 0/15
- 进入实施阶段: **是**
