# 004 · SPEC-001-C UI 层闭环（2026-08-24）

- **状态**: 活跃
- **关键词**: ui, pyqt5, qt, smoke-test, pytest-qt, offscreen
- **相关模块**: attendance/ui_*.py, attendance_ui.py, tests/test_ui_*.py

## 关联文档

- `AGENTS.md` §1（项目定位）、§2（当前入口）、§3.2（测试依赖）
- `specs/attendance/03-ui/spec.md` v1.0.0（本闭环对应的 spec）
- `specs/attendance/03-ui/tasks.md`（T-301~T-306 任务拆解）
- `specs/attendance/03-ui/checklist.md`（A-J 验收清单）
- `decisions/_INDEX.md`（本决策的索引行）
- `BACKLOG.md` #001 进度更新（A/B/C 闭环，D 继续）
- 闭环事实唯一来源：本文件

## 变化程度

- 新建 6 个 UI 模块:
  - `attendance/ui_login.py` (`LoginDialog`, fixed 360x200, 密码框 echoMode=Password)
  - `attendance/ui_utils.py` (`show_error` 统一弹窗 + 错误码→标题映射)
  - `attendance/ui_employees.py` (`EmployeesTab` 6 列表格 + `EmployeeDialog` 9 输入控件)
  - `attendance/ui_checkin.py` (`CheckInTab` 相机/QTimer/识别 + `CheckConfirmDialog` 4 按钮)
  - `attendance/ui_records.py` (`RecordsTab` 4 维筛选 + 6 列记录表)
  - `attendance/ui_main.py` (`MainWindow` 3 Tab + statusBar + 菜单"文件>退出", 关闭时释放相机)
- 新建 1 个根入口: `attendance_ui.py` (PyQt5 主入口, 启动 LoginDialog → MainWindow)
- 新建 4 个测试文件 (18 个 UI TC):
  - `tests/test_ui_login.py` (C01~C04, 4 TC)
  - `tests/test_ui_employees.py` (C05~C11, 7 TC)
  - `tests/test_ui_checkin.py` (C12~C15, 4 TC)
  - `tests/test_ui_records.py` (C16~C18, 3 TC; C18 顺带覆盖 G-04 清空筛选)
- 修改 `tests/conftest.py`: 新增 `_patch_argv` autouse fixture (绕开 recognition.py 顶部 argparse) + `sample_employees` fixture
- 修改 `tests/test_ui_login.py::test_TC_ATT_C04_login_close_triggers_exit`: 由 `dlg.close()` 改为 `dlg.closeEvent(event)` 直接测契约 (绕开 offscreen 平台 close() 不触发 closeEvent)
- 修改 `attendance/ui_main.py` Tab 2: 阶段 1 占位 `QLabel` → 阶段 3 接入 `RecordsTab`
- 未触碰 (红线保护, 哈希不变): `recognition.py` / `get_name.py` / `ui.py` / `mydata.yaml` / 训练权重
- 用后即删: `temp_run_*.py` / `temp_ui_test_*.log` / `tests/conftest_minimal.py` / `tests/conftest.py.bak` 等 30+ 临时文件

## 摘要

按 SPEC-001-C v1.0.0 落地 6 个 UI 模块 + 1 个根入口, 配套 18 个 UI 测试全绿, 与 B 层 18 个服务测试无回归 (合计 36/36 PASSED)。

**实施前确认的关键决策**（与用户对齐）:

1. `show_error` 放 `attendance/ui_utils.py` (与 A 层 `attendance/utils.py` 严格分离, 不修改 A 层代码)
2. 背景图: `recognition.py` 原硬编码 `C:\Users\WJ\Desktop\yol\OIP-C.webp` → 改用 `D:\yol\yolov8_facenet\OIP-C.jpg` 相对地址; 用户最终选择"没必要搞背景图", 实际未加
3. 实施分 3 阶段: 阶段 1 骨架 (LoginDialog + MainWindow 占位 Tab) → 阶段 2 人员 + 签到 → 阶段 3 记录; 每阶段独立跑通后再推进

**实施中确认的次要决策**（与用户对齐, 落到代码注释中）:

- `_patch_argv` 用 `monkeypatch` 不可行 (需在 `import recognition` 之前生效), 改用直接赋值 `sys.argv = [script_name]` + try/finally 还原
- `_FakeCaptureFail` 必须 `__init__(self, *args, **kwargs)`, 因 `cv2.VideoCapture(0)` 调用会传位置参数

**验证结果**:

| 检查 | 命令 / 文件 | 结果 |
|---|---|---|
| pytest B 18 + C 18 = 36 TC | `pytest tests/test_ui_*.py tests/test_services.py -v` | 36 passed in 5.32s ✅ |
| C-01 启动弹 LoginDialog, 标题"签到系统 v1.0.0" | TC-ATT-C01 | ✅ |
| C-02 密码框 echoMode == QLineEdit.Password | TC-ATT-C02 | ✅ |
| C-03 admin/admin123 → MainWindow, statusBar 含"当前管理员: admin" | TC-ATT-C02 | ✅ |
| C-04 错密码 → QMessageBox.warning 含 "AUTH_FAILED" | TC-ATT-C03 | ✅ |
| C-05 closeEvent → sys.exit(0) | TC-ATT-C04 | ✅ |
| D-01~D-04 MainWindow 3 Tab + statusBar + 菜单退出 | C01~C04 覆盖 | ✅ |
| E-01~E-09 EmployeesTab 增改删查搜索 | C05~C11 | ✅ |
| F-01~F-05 CheckInTab 相机/识别/4 按钮 | C12~C15 | ✅ |
| G-01~G-04 RecordsTab 4 维筛选 + 清空 | C16~C18 (G-04 顺带覆盖) | ✅ |
| 原文件哈希 | `recognition.py` / `get_name.py` / `ui.py` 未改 | ✅ |
| 错误码字符串 | 与 spec §6.1 表格逐字一致 (H-02) | ✅ |
| Service import 列表 | `from attendance.services import {Admin,Employee,Check,Schedule}Service` (H-03) | ✅ |
| pytest collect 18 行 TC-ATT_C | `pytest --collect-only -q` | 18/18 ✅ (checklist I-02) |

## 闭环：排期清单 #001（C 部分）

`BACKLOG.md` #001 中"UI 层"部分闭环。**未闭环**："测试层"（SPEC-001-D 待启动）。

## 踩坑

- **recognition.py 顶部模块级 `argparse.parse_args()` 吃 pytest 参数**：`import recognition` 时 `parser.parse_args()` 无参调用走 `sys.argv[1:]`, pytest 跑时拿到 pytest 参数 (如 `tests/test_ui_checkin.py::test_TC_ATT_C12`), argparse 拒绝并 `SystemExit(2)` → C 阶段 2 全员失败. 修法: `tests/conftest.py` 加 autouse fixture `_patch_argv` 临时把 `sys.argv` 改为 `[script_name]`, 让 argparse 走默认; 不修改 `recognition.py` (红线). 这条已纳入 AGENTS.md §6 L-002.
- **PyQt5 offscreen 平台下未 `show()` 的 QWidget 调 `close()` 不触发 closeEvent**: Qt 在 `QT_QPA_PLATFORM=offscreen` 下的已知行为, `pytest.raises(SystemExit)` 永远等待 → pytest 卡死, 表现是 RC 0 但 stdout 截断在测试名. 修法: 测 closeEvent 行为时直接 `dlg.closeEvent(QtGui.QCloseEvent())`, 测契约不依赖 Qt 异步事件分发. 这条已纳入 AGENTS.md §6 L-003.
- **`recognition.py` 模块级导入即加载模型权重**: `import recognition` 时 `yolo = Yolo()` 触发 `torch.load(opt.weights)`, opencv4 环境必须有 `runs/detect/train/weights/best.pt`. C 阶段 1 确认文件存在; C 阶段 2/3 测试不实际跑模型 (mock 了 `cv2.VideoCapture`), import 仍会触发, 加载不报错但慢 (测试 session 启动 +3s).
- **MySQL DATETIME 默认精度 0（秒）**: 见 `decisions/003-v1-service-shipped.md` 踩坑段; 本轮复用, 未复发.
- **PowerShell 5.1 不支持 `&&` 串行**: 与 B 阶段同, 临时脚本用 Python `subprocess.run` 一次性跑 pytest + 静态检查, 绕开 shell 转义.

## 下一步

- SPEC-001-D (测试层): 补充集成测试 (端到端 UI 流程: 启动 attendance_ui.py → LoginDialog 登录 → EmployeesTab 新增员工 → CheckInTab 模拟识别 → CheckConfirmDialog 打卡 → RecordsTab 查询记录), 与 B 层 18 个单元测试 + C 层 18 个 UI 测试一起构成完整测试矩阵 (单元 18 + UI 18 + 集成 ~5 = 41 左右).
- 持续事项: BACKLOG #001 整体仍登记在排期清单; D 完成后将再次闭环决策.
- 跨子 spec 事项:
  - `attendance/utils.py` 14 个异常类与 B 层 spec 保持一致; C 层 UI 错误码字符串与 spec §6.1 表格逐字对齐.
  - `recognition.py` / `get_name.py` / `ui.py` 哈希保护自 A 层决策; C 闭环后仍 0 修改.
  - 静态检查 H-01 (Signal 事件名 LOGIN_SUCCESS 等) 未在代码中触发 Signal, 改用 `dlg.accept()` + 属性读取 (`dlg.admin`), 走"事件-属性"而非"Signal"实现; 这是 spec §5 与 PyQt5 习语之间的权衡, 不影响功能. 待 SPEC-001-D 阶段与用户确认是否要回填 Signal.
