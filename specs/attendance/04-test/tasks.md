# 任务拆解: SPEC-001-D 测试与验证（集成 + 端到端）

> 与 `specs/attendance/04-test/spec.md` v1.0.0 配套。
> **范围**: 11 个 TC（4 集成 + 7 端到端）, 严格不动 `tests/conftest.py`, 复用 `attendance_db`。
> **依赖**: SPEC-001-A + SPEC-001-B + SPEC-001-C 已闭环（决策 002 / 003 / 004）。

---

## T-501 编写 tests/test_integration.py（4 个集成 TC）

- **依赖**: SPEC-001-A + SPEC-001-B 已闭环
- **前置**: `tests/conftest.py` 6 个 fixture 已稳定（`_db_session` / `_patch_argv` / `_per_test_reset` / `sample_schedule` / `face_image` / `sample_employees`）, 不修改
- **产出物**: `tests/test_integration.py` 含 4 个测试函数 + 1 个文件内 fixture:

  **文件内 fixture**（仅供本文件 TC 使用, 不进 conftest）:
  - `default_admin() -> Admin`: 调 `AdminService.ensure_default("admin", "admin123")` 1 次, 返回 admin 实例。D03 用。

  **测试函数**（4 个, 命名严格遵循 `test_TC_ATT_D{NN}_<description>`）:
  - `test_TC_ATT_D01_service_chain_schedule_employee_check`
  - `test_TC_ATT_D02_delete_cascade_constraint`
  - `test_TC_ATT_D03_admin_change_password`
  - `test_TC_ATT_D04_list_records_date_range`

- **TC 详细产出**:

  | TC | 关键操作 | 关键断言 |
  |----|----------|----------|
  | D01 | `sample_schedule` + `face_image` → `EmployeeService.create("200001", "集成A", ...)` → `CheckService.create_record("200001", "check_in")` → `CheckService.create_record("200001", "check_out")` | `CheckRecord.select().where(employee_id="200001").count() == 2`; 2 条 check_type 分别为 "check_in" / "check_out" |
  | D02 | 建 employee "200002" + 1 条 check_in → `EmployeeService.delete("200002")` 应抛 `EmployeeHasRecords` → 清 CheckRecord → 再 delete 应成功 | 第一次 delete 抛 `EmployeeHasRecords`; 第二次 delete 后 `Employee.select().where(employee_id="200002").exists() == False` |
  | D03 | `default_admin` fixture → `authenticate("admin", "admin123")` 成功 → 取 `admin.id` → `change_password(admin.id, "admin123", "newpass456")` → 旧密码 `authenticate` 抛 `AuthFailed` → 新密码 `authenticate` 成功 | 3 个断言全过 |
  | D04 | 建 employee "200004" + 3 条 CheckRecord（昨天 check_in + 昨天 check_out + 今天 check_in）→ `CheckService.list_records(date_from=昨天, date_to=今天)` → 返回 3 条按 check_timestamp 降序; 再调 date_from > date_to 抛 `DateRangeInvalid` | list 返回长度 == 3; 顺序降序; 反向范围抛 `DateRangeInvalid` |

- **关联**: spec §2.1 Gherkin 4 场景 + §3.1 复用 fixture + §5.1 时序 + §7 矩阵 D01~D04
- **覆盖**: SPEC-001-D 集成 4 个 TC（REQ-D-01~REQ-D-04）
- **完成后**: 跑 `pytest tests/test_integration.py -v --tb=short` 应 4/4 PASSED

---

## T-502 编写 tests/test_e2e.py（7 个端到端 TC）

- **依赖**: T-501 完成 + SPEC-001-C 已闭环
- **前置**:
  - T-501 跑通（4 个集成 TC 全绿）
  - 跑测试时前置 `QT_QPA_PLATFORM=offscreen` 环境变量（spec §3.4）
  - `tests/conftest.py` 不修改
- **产出物**: `tests/test_e2e.py` 含 7 个测试函数 + 1 个文件内 fixture + 1 个 Mock 类:

  **文件内 fixture**:
  - `logged_in_main_window(qtbot, monkeypatch) -> MainWindow`:
    - 调 `AdminService.ensure_default("admin", "admin123")`
    - 调 `AdminService.authenticate("admin", "admin123")` 取 admin
    - `monkeypatch.setattr(attendance.db, "close_db", lambda: None)` 计数（mock, 避免真关连接）
    - `monkeypatch.setattr(QtWidgets.QApplication, "quit", lambda: None)` 计数
    - 创建 `MainWindow(admin)`, yield
    - teardown: `main.closeEvent(QtGui.QCloseEvent())` 释放资源

  **Mock 类**:
  - `_FakeCaptureOk`（与 C 阶段 2 同款, 4 个方法: `__init__` / `isOpened` / `read` / `release`, 代码见 spec §3.3）

  **测试函数**（7 个）:
  - `test_TC_ATT_D05_attendance_ui_importable`
  - `test_TC_ATT_D06_login_enters_main_window`
  - `test_TC_ATT_D07_e2e_add_employee_check_record`
  - `test_TC_ATT_D08_mainwindow_close_releases_camera`
  - `test_TC_ATT_D09_menu_exit_calls_close_db`
  - `test_TC_ATT_D10_camera_open_close_cycle`
  - `test_TC_ATT_D11_attendance_ui_main_signature`

- **TC 详细产出**:

  | TC | 关键操作 | 关键断言 | 关键 mock |
  |----|----------|----------|-----------|
  | D05 | `importlib.import_module("attendance_ui")` | 模块加载无 ImportError; `main` 是 callable; `inspect.signature(main)` 参数数 == 0; 不含 VAR_POSITIONAL; 不含 VAR_KEYWORD | 无 |
  | D06 | `default_admin` + 创建 `LoginDialog` + 直接调 `_on_login_clicked` 走成功路径（admin/admin123 已 seed） | `dlg.admin` 是 `Admin` 实例; `dlg.admin.username == "admin"`; `MainWindow(dlg.admin).tabs.count() == 3`; statusBar 消息含 "admin" | 无 |
  | D07 | `logged_in_main_window` + mock `recognition.recognition` + mock `get_name.rec` + mock `CheckConfirmDialog.exec_` 为 `fake_exec`; 切换 EmployeesTab → mock `EmployeeDialog.exec_` 为 fake_exec 填 "200007"/"集成B" → `btn_add.click()` → 切换 CheckInTab → `checkin_tab._do_recognition(zero_frame)` → 切换 RecordsTab → `_refresh_table()` | Employee 新增 1 行; CheckRecord 新增 1 条 check_in; RecordsTab 表格显示 1 行 | `recognition.recognition` / `get_name.rec` / `CheckConfirmDialog.exec_` / `EmployeeDialog.exec_` |
  | D08 | `logged_in_main_window` + mock `CheckInTab._camera = _FakeCaptureOk()` + mock `CheckInTab._timer = MagicMock()`; 调 `main.closeEvent(QtGui.QCloseEvent())` | `_close_camera` 被调 1 次（用 mock 计数器验证）; `checkin_tab._camera is None`; `checkin_tab._timer is None` | `_FakeCaptureOk` |
  | D09 | `logged_in_main_window` + 触发 `main.action_exit.triggered`（或调 `_on_exit` 槽函数, 取实际代码命名） | `close_db` 被调 1 次; `QApplication.quit` 被调 1 次 | `attendance.db.close_db` / `QApplication.quit` |
  | D10 | `monkeypatch.setattr(cv2, "VideoCapture", _FakeCaptureOk)`; 循环 3 次 `checkin_tab._open_camera()` + `checkin_tab._close_camera()`; 每次断言 `_camera is None` 与 `_timer is None or not _timer.isActive()` | 第 1/2/3 次循环后 `_camera is None`; `_timer` 不活跃 | `cv2.VideoCapture` |
  | D11 | `inspect.signature(attendance_ui.main)` | 参数数 == 0; 无 `*args`; 无 `**kwargs` | 无 |

- **关联**: spec §2.2 Gherkin 7 场景 + §3.1 复用 fixture + §3.2 文件内 fixture + §3.3 Mock 契约 + §5.4 时序约定 + §7 矩阵 D05~D11
- **覆盖**: SPEC-001-D 端到端 7 个 TC（REQ-D-05~REQ-D-11）
- **完成后**: 跑 `QT_QPA_PLATFORM=offscreen pytest tests/test_e2e.py -v --tb=short` 应 7/7 PASSED

---

## T-503 跑 D 层 + CI 验证 + 闭环决策

- **依赖**: T-501 + T-502 全部完成
- **前置**: 4 集成 + 7 端到端 TC 在单跑下全绿
- **产出物**:

  **1. 跑全量 D 层 + 收集命令**（G-01, G-02, G-03 验收）:
  ```bash
  # G-01: 11/11 PASSED
  $env:QT_QPA_PLATFORM="offscreen"; pytest tests/test_integration.py tests/test_e2e.py -v --tb=short -p no:cacheprovider
  # 期望: 11 passed in <60s

  # G-02: 11 个 TC 函数
  pytest --collect-only -q | grep -c "test_TC_ATT_D"
  # 期望: 11

  # G-03: < 60 秒
  time pytest tests/test_integration.py tests/test_e2e.py -q
  # 期望: real < 60s
  ```

  **2. 跑 flake 检查**（G-04 验收）:
  ```bash
  for i in 1 2 3; do
    QT_QPA_PLATFORM=offscreen pytest tests/test_integration.py tests/test_e2e.py -q || exit 1
  done
  # 期望: 3 次全 RC 0
  ```

  **3. 跑全量 A+B+C+D 回归**（47 TC, 验收 0 回归）:
  ```bash
  QT_QPA_PLATFORM=offscreen pytest tests/ -v --tb=short
  # 期望: 47 passed (A=0 + B=18 + C=18 + D=11)
  ```

  **4. 写闭环决策**:
  - 新建 `decisions/005-v1-test-shipped.md`, 摘要含"闭环: 排期清单 #001"
  - 在 `decisions/_INDEX.md` 末尾追加 005 行
  - 从 `BACKLOG.md` 清除 #001 排期项（不再保留闭环记录在 BACKLOG）
  - 在 `AGENTS.md` §6 踩坑教训章节追加本次实际遇到的坑（若有, 编号 L-004 起）
  - 在 `AGENTS.md` §10 变更日志追加一行（2026-08-24 D 层闭环）
  - 在 `AGENTS.md` §2 当前入口追加 tests/test_integration.py + test_e2e.py

- **关联**: spec §0 G-01~G-07 + §3.4 pytest 命令 + §3.5 不允许项 + §7 矩阵 + §8 非功能需求
- **覆盖**: 全部 11 个 D 层 TC + 0 回归

---

## 任务依赖图

```text
A 闭环 (decision 002) ─┐
B 闭环 (decision 003) ─┼──> T-501 ──┐
C 闭环 (decision 004) ─┘            │
                                    ├──> T-503 (闭环决策)
                        T-501 完成 ──┤
                                    │
                        T-502 ──────┘
                          │
                          └─ T-502 依赖 T-501 完成 (避免 T-501 失败时浪费 T-502 工作)
```

## 排期

| 阶段 | 任务 | 工时（单人时） |
|------|------|----------------|
| 集成测试 | T-501 | 1.0 |
| 端到端测试 | T-502 | 1.5 |
| 验证 + 闭环 | T-503 | 0.5 |
| **合计** | — | **3.0** |

## 配套产物清单

| 路径 | 状态 | 来源 |
|------|------|------|
| `tests/test_integration.py` | T-501 新建 | 本 spec |
| `tests/test_e2e.py` | T-502 新建 | 本 spec |
| `tests/conftest.py` | **不动** | 已有 6 fixture |
| `decisions/005-v1-test-shipped.md` | T-503 新建 | 本 spec 闭环后写 |
| `decisions/_INDEX.md` | T-503 追加 005 行 | 索引维护 |
| `BACKLOG.md` | T-503 清除 #001 | 闭环后清除 |
| `AGENTS.md` §2/§6/§10 | T-503 追加 | 红线/踩坑/变更日志维护 |
