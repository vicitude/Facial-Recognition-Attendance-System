# 验收清单: SPEC-001-D 测试与验证（集成 + 端到端）

> 与 `specs/attendance/04-test/spec.md` v1.0.0 + `tasks.md` 配套。
> **范围**: 11 个 TC（4 集成 + 7 端到端）, `tests/conftest.py` 严格不动, 复用 `attendance_db`, A 层 0 自动化（沿用 002 决策手测）。
> **闭环后**: `decisions/005-v1-test-shipped.md` + `_INDEX.md` 追加 005 行; `BACKLOG.md` 清除 #001; `AGENTS.md` §6 / §10 追加。

---

## A. 文件存在

- [ ] **A-01** `tests/test_integration.py` 存在, 含 4 个测试函数（`test_TC_ATT_D01` ~ `test_TC_ATT_D04`）+ 1 个文件内 fixture `default_admin` — 阻塞
- [ ] **A-02** `tests/test_e2e.py` 存在, 含 7 个测试函数（`test_TC_ATT_D05` ~ `test_TC_ATT_D11`）+ 1 个文件内 fixture `logged_in_main_window` + 1 个 Mock 类 `_FakeCaptureOk` — 阻塞
- [ ] **A-03** `tests/conftest.py` 6 个 fixture（`_db_session` / `_patch_argv` / `_per_test_reset` / `sample_schedule` / `face_image` / `sample_employees`）**保持原样**（行数与文件未改）— 阻塞（G-06 红线）
- [ ] **A-04** `tests/test_foundation.py` **不存在**（A 层 0 自动化, 沿用 002 决策手测）— 反向验证

## B. D 层文件内 fixture 行为

- [ ] **B-01** `default_admin` 在 `tests/test_integration.py` 内定义, 作用域 function, 签名 `() -> Admin`, 调 `AdminService.ensure_default("admin", "admin123")` 1 次 — 阻塞
- [ ] **B-02** `logged_in_main_window` 在 `tests/test_e2e.py` 内定义, 作用域 function, 签名 `(qtbot, monkeypatch) -> MainWindow`, 调 ensure_default + authenticate + MainWindow(admin), mock close_db 与 QApplication.quit 计数 — 阻塞
- [ ] **B-03** `_FakeCaptureOk` 类在 `tests/test_e2e.py` 内定义, 4 个方法（`__init__(self, *args, **kwargs)` / `isOpened(self) -> bool` / `read(self) -> tuple` / `release(self) -> None`）— 阻塞
- [ ] **B-04** D 层 3 个文件内 fixture 严禁进 `tests/conftest.py`（grep 验证）— 阻塞（G-06 红线）

## C. CI 门禁（spec §0 G-01~G-07）

- [ ] **C-01** **G-01**: `$env:QT_QPA_PLATFORM="offscreen"; pytest tests/test_integration.py tests/test_e2e.py -v --tb=short -p no:cacheprovider` 退出码 0, 输出 11 passed — 阻塞
- [ ] **C-02** **G-02**: `pytest --collect-only -q | grep -c "test_TC_ATT_D"` 输出 11 — 阻塞
- [ ] **C-03** **G-03**: `time pytest tests/test_integration.py tests/test_e2e.py -q` 输出 real < 60s — 阻塞
- [ ] **C-04** **G-04**: `for i in 1 2 3; do QT_QPA_PLATFORM=offscreen pytest tests/test_integration.py tests/test_e2e.py -q; done` 3 次全 RC 0 — 阻塞（0 flake）
- [ ] **C-05** **G-05**: 启动命令前置 `QT_QPA_PLATFORM=offscreen`（不设则 D05~D11 fail）— 阻塞
- [ ] **C-06** **G-06**: `git diff tests/conftest.py` 输出为空（D 层不修改 conftest）— 阻塞（红线, 闭环前 git status 检查）
- [ ] **C-07** **G-07**: spec.md / tasks.md / checklist.md / test_integration.py / test_e2e.py 五者之一修改时, 另四者同步更新（人工 review）— 阻塞

## D. 集成测试 4 个 TC（test_integration.py, D01~D04）

- [ ] **D-01** **TC-ATT-D01 service_chain_schedule_employee_check**: 建 schedule + 建 employee "200001" + 2 条 CheckRecord (check_in / check_out), 断言 CheckRecord 数 == 2, 2 条 check_type 分别正确, Employee.name == "集成A" — 阻塞
- [ ] **D-02** **TC-ATT-D02 delete_cascade_constraint**: 有 CheckRecord 的 employee "200002" delete 抛 `EmployeeHasRecords`, employee 仍存在; 清 CheckRecord 后再 delete 成功, employee 不存在 — 阻塞
- [ ] **D-03** **TC-ATT-D03 admin_change_password**: ensure_default + 旧密码 auth 成功 + change_password(admin.id, "admin123", "newpass456") + 旧密码 auth 抛 `AuthFailed` + 新密码 auth 成功 — 阻塞
- [ ] **D-04** **TC-ATT-D04 list_records_date_range**: employee "200004" + 3 条 CheckRecord（昨天 check_in + 昨天 check_out + 今天 check_in）, list_records(date_from=昨天, date_to=今天) 返回 3 条降序; date_from > date_to 抛 `DateRangeInvalid` — 阻塞

## E. 端到端测试 7 个 TC（test_e2e.py, D05~D11）

- [ ] **E-01** **TC-ATT-D05 attendance_ui_importable**: `importlib.import_module("attendance_ui")` 无 ImportError; `main` 是 callable; `inspect.signature(main)` 参数数 == 0, 无 VAR_POSITIONAL, 无 VAR_KEYWORD — 阻塞
- [ ] **E-02** **TC-ATT-D06 login_enters_main_window**: default_admin + LoginDialog + 直接调 `_on_login_clicked` 走成功路径, `dlg.admin` 是 `Admin` 实例 + username=="admin" + MainWindow.tabs.count()==3 + statusBar 含 "admin" — 阻塞
- [ ] **E-03** **TC-ATT-D07 e2e_add_employee_check_record**: 4 步 mock + 增员 + 模拟识别 + 打卡 + 查记录, Employee 新增 1 行 + CheckRecord 新增 1 条 check_in + RecordsTab 表格显示 1 行 — 阻塞
- [ ] **E-04** **TC-ATT-D08 mainwindow_close_releases_camera**: mock `_FakeCaptureOk` 相机 + mock timer; 调 `main.closeEvent(QCloseEvent())`; `_close_camera` 被调 1 次 + `_camera is None` + `_timer is None` — 阻塞
- [ ] **E-05** **TC-ATT-D09 menu_exit_calls_close_db**: `logged_in_main_window` + 触发 `action_exit.triggered`; `close_db` 被调 1 次 + `QApplication.quit` 被调 1 次 — 阻塞
- [ ] **E-06** **TC-ATT-D10 camera_open_close_cycle**: monkeypatch `cv2.VideoCapture` 为 `_FakeCaptureOk`; 循环 3 次 `_open_camera` + `_close_camera`; 每次 `_camera is None` + `_timer` 不活跃 — 阻塞
- [ ] **E-07** **TC-ATT-D11 attendance_ui_main_signature**: `inspect.signature(attendance_ui.main)` 参数数 == 0, 无 `*args`, 无 `**kwargs` — 阻塞

## F. 错误码覆盖（spec §6.2）

- [ ] **F-01** `EmployeeHasRecords` 异常被 D02 触发 — 阻塞
- [ ] **F-02** `DateRangeReversed` 异常被 D04 触发 — 阻塞
- [ ] **F-03** `AuthFailed` 异常被 D03 触发（旧密码认证） — 阻塞
- [ ] **F-04** D 层不重复测 B/C 层 14 个 `AttendanceError` 子类 + UI 错误码（避免回归） — 反向验证

## G. 静态检查（spec §3.5 红线）

- [ ] **G-01** 业务层无 `raise Exception`（B 层已闭环, D 层不引入, 验证: `grep -REn "raise Exception" attendance/ tests/` 输出 0）— 阻塞
- [ ] **G-02** UI 层无 Service 字面量泄漏（验证: `grep -REn "['\"](check_in|check_out|middle)['\"]" attendance/ui_*.py tests/ | grep -v "VALID_TYPES\|check_type" | wc -l` 输出 0）— 阻塞
- [ ] **G-03** 严禁 `unittest.mock.patch` 装饰器（验证: `grep -REn "unittest.mock.patch" tests/test_integration.py tests/test_e2e.py` 输出 0）— 阻塞
- [ ] **G-04** 严禁 `pytest-xdist`（验证: `grep -REn "pytest-xdist\|@pytest.mark.parallel" tests/` 输出 0）— 阻塞
- [ ] **G-05** 严禁 `unittest.mock` 导入（验证: `grep -REn "^import unittest.mock\|^from unittest.mock" tests/test_integration.py tests/test_e2e.py` 输出 0）— 阻塞

## H. 整体回归（47 TC, A+B+C+D）

- [ ] **H-01** 全量回归: `QT_QPA_PLATFORM=offscreen pytest tests/ -v --tb=short` 输出 47 passed (A=0 + B=18 + C=18 + D=11) — 阻塞
- [ ] **H-02** B 层 18 TC 全绿（已在 decision 003 闭环, 回归无失败）— 阻塞
- [ ] **H-03** C 层 18 TC 全绿（已在 decision 004 闭环, 回归无失败）— 阻塞
- [ ] **H-04** D 层 11 TC 全绿（本次落地）— 阻塞
- [ ] **H-05** 全量耗时 < 90 秒（B+C+D 合计）— 阻塞

## I. 隔离性 / 可重现性 / 资源释放（spec §8）

- [ ] **I-01** 一 TC 失败不影响其他 TC: 故意让 D03 失败, 跑 D04 仍通过 — 阻塞
- [ ] **I-02** 不依赖真实相机: D08/D10 用 `_FakeCaptureOk` mock, 代码中无 `cv2.VideoCapture(0)` 真实调用 — 阻塞
- [ ] **I-03** 不依赖真实模型推理: D07 mock `recognition.recognition` + `get_name.rec`, 代码中无真实 `recognition()` / `rec()` 调用 — 阻塞
- [ ] **I-04** 入口可导入: `importlib.import_module("attendance_ui")` 无 ImportError — 阻塞（与 E-01 重叠, 单独验证 importlib 调用无 importlib.util.find_spec 替代）
- [ ] **I-05** 入口签名稳定: `inspect.signature(attendance_ui.main)` 参数数 == 0 — 阻塞（与 E-07 重叠, 单独跑）

## J. 资源保护红线（不修改范围, AGENTS.md §5 + spec §9.2）

- [ ] **J-01** `recognition.py` 未修改（`git diff recognition.py` 输出为空）— 阻塞
- [ ] **J-02** `get_name.py` 未修改（`git diff get_name.py` 输出为空）— 阻塞
- [ ] **J-03** `ui.py` 未修改（`git diff ui.py` 输出为空）— 阻塞
- [ ] **J-04** `mydata.yaml` 未修改（`git diff mydata.yaml` 输出为空）— 阻塞
- [ ] **J-05** 训练权重 `runs/detect/train/weights/*.pt` 未修改（`git diff runs/` 输出为空）— 阻塞
- [ ] **J-06** `attendance/services.py` 未修改（B 层闭环, 红线, `git diff attendance/services.py` 输出为空）— 阻塞
- [ ] **J-07** `attendance/ui_*.py` + `attendance_ui.py` 未修改（C 层闭环, 红线, `git diff attendance/ui_*.py attendance_ui.py` 输出为空）— 阻塞
- [ ] **J-08** `attendance/{config,db,models,utils}.py` 未修改（A 层闭环, 红线, `git diff attendance/__init__.py attendance/config.py attendance/db.py attendance/models.py attendance/utils.py` 输出为空）— 阻塞

## K. 最终闭环

- [ ] **K-01** 全部阻塞项（A~J）通过后, 在 `decisions/005-v1-test-shipped.md` 写入闭环决策, 摘要含"闭环: 排期清单 #001" + 11/11 PASSED + 0 flake + < 60s + 0 回归 — 阻塞
- [ ] **K-02** 在 `decisions/_INDEX.md` 末尾追加 005 行（v1, test, integration, e2e, pytest-qt, offscreen, 关键词）— 阻塞
- [ ] **K-03** 从 `BACKLOG.md` 清除 #001 排期项（决策文件是闭环事实唯一来源, BACKLOG 不保留闭环记录）— 阻塞
- [ ] **K-04** 在 `AGENTS.md` §6 踩坑教训章节追加本次实际遇到的坑（若有, 编号 L-004 起; 若无则跳过）— 阻塞
- [ ] **K-05** 在 `AGENTS.md` §10 变更日志追加一行（2026-08-24 D 层闭环）— 阻塞
- [ ] **K-06** 在 `AGENTS.md` §2 当前入口追加 `tests/test_integration.py` + `tests/test_e2e.py` — 阻塞

---

## 阻塞项合计

| 章节 | 阻塞项数 | 状态 |
|------|----------|------|
| A. 文件存在 | 4 | 待 T-501/T-502 |
| B. D 层文件内 fixture | 4 | 待 T-501/T-502 |
| C. CI 门禁（G-01~G-07） | 7 | 待 T-501/T-502/T-503 |
| D. 集成 4 TC | 4 | 待 T-501 |
| E. 端到端 7 TC | 7 | 待 T-502 |
| F. 错误码覆盖 | 4 | 待 T-501 |
| G. 静态检查 | 5 | 待 T-501/T-502 |
| H. 整体回归 | 5 | 待 T-503 |
| I. 隔离/可重现/资源 | 5 | 待 T-501/T-502/T-503 |
| J. 资源保护红线 | 8 | 待 T-503 验收 |
| K. 最终闭环 | 6 | 待 T-503 |
| **合计** | **59** | — |

## 验收后最终交付物

1. `tests/test_integration.py`（T-501 新建, 4 TC）
2. `tests/test_e2e.py`（T-502 新建, 7 TC）
3. `decisions/005-v1-test-shipped.md`（T-503 新建, 闭环决策）
4. `decisions/_INDEX.md`（T-503 追加 005 行）
5. `BACKLOG.md`（T-503 清除 #001）
6. `AGENTS.md` §2/§6/§10（T-503 追加维护）
