# 005 · SPEC-001-D 测试层闭环（2026-08-24）

- **状态**: 活跃
- **关键词**: test, integration, e2e, pytest, pyqt5, offscreen
- **相关模块**: tests/test_integration.py, tests/test_e2e.py, attendance/ui_main.py (L17 修复)

## 关联文档

- `AGENTS.md` §1（项目定位）、§2（当前入口）、§3（真实验证命令）
- `specs/attendance/04-test/spec.md` v1.0.0（本闭环对应的 spec, 11 TC 方案 + 10 段结构）
- `specs/attendance/04-test/tasks.md`（T-501/T-502/T-503 任务拆解）
- `specs/attendance/04-test/checklist.md`（A-K 验收清单, 59 个阻塞项）
- `decisions/002-v1-foundation-shipped.md`（A 基础层闭环, 12 个 smoke TC）
- `decisions/003-v1-service-shipped.md`（B 服务层闭环, 18 个 unit TC）
- `decisions/004-v1-ui-shipped.md`（C UI 层闭环, 18 个 UI TC, 本闭环的 C 层前提）
- `BACKLOG.md` #001 整体闭环（最后一项 D 层, 本决策闭环后整行清除）
- 闭环事实唯一来源：本文件

## 变化程度

- 新建 2 个测试文件（11 个 TC）:
  - `tests/test_integration.py`（T-501 产物, 4 个集成 TC: D01~D04, 跨 Service 协作; 含 1 个文件内 fixture `default_admin`）
  - `tests/test_e2e.py`（T-502 产物, 7 个端到端 TC: D05~D11, 跨 3 Tab UI 协作; 含 4 个文件内 fixture `_offscreen_platform`/`app`/`default_admin`/`logged_in_main_window` + 1 个 Mock 类 `_FakeCaptureOk`）
- 修改 1 行: `attendance/ui_main.py` L17 追加 `from attendance.ui_records import RecordsTab`（C 层漏 import 修复, 用户拍板方案 A）
- 未触碰: `tests/conftest.py`（G-06 红线）/ `attendance/services.py`（B 层红线）/ `attendance/ui_employees.py` + `attendance/ui_checkin.py` + `attendance/ui_records.py`（C 层红线）/ `recognition.py` + `get_name.py` + `ui.py`（A 层红线, 哈希不变）

## 摘要

按 SPEC-001-D v1.0.0 落地 11 个跨层 TC, 与 B 层 18 个 unit + C 层 18 个 UI 共同构成完整测试矩阵, 合计 47/47 PASSED。

**实施前确认的关键决策**（与用户对齐, 4 项拍板）:

1. 重命名 04-test/ 统一（删旧 04-test/ 4 文件 + 04-testing/ 1 文件, 04-testing/ 现为空目录保留无害）
2. D 层独有 11 TC（A 12 + B 18 + C 18 = 48 已有 TC, D 层不重测, 总规模 47 + 12 smoke = 59）
3. A 层 0 自动化（沿用决策 002 smoke test, 复用决策 003/004 既有 36 TC）
4. conftest 不动（复用 6 个 fixture: _db_session / _patch_argv / _per_test_reset / sample_schedule / face_image / sample_employees）

**实施中确认的次要决策**（与用户对齐, 落到代码注释中）:

- `default_admin` fixture 复制到 test_integration.py + test_e2e.py 各自一份（不进 conftest, G-06 红线）
- `logged_in_main_window` fixture 跳过 LoginDialog, 直接 MainWindow(default_admin), 复用 C-02/C-05 已测组件
- D07 mock `EmployeeDialog.exec_` 改为内部调 `self._on_save()`, 保留 `EmployeeService.create` 真实调用
- D07 mock `CheckConfirmDialog.exec_` 改为内部调 `self._confirm("check_in")`, 保留 `CheckService.create_record` 真实调用

**实施中发现的 2 个 spec 错误**（已报告 + 修正）:

1. employee_id 命名 `D01-001` 等违反 `EmployeeService._validate_employee_id` 强制 `^\d{6}$`（[services.py:71-84](file:///d:/yol/yolov8_facenet/attendance/services.py#L71-L84)）→ 改 `200001/200002/200004/200007`（D07 用）, spec/tasks/checklist 7 处同步修正
2. 错误类名 `DateRangeReversed` 与实际 `DateRangeInvalid`（[utils.py:72-73](file:///d:/yol/yolov8_facenet/attendance/utils.py#L72-L73)）冲突 → 改 `DateRangeInvalid`, spec/tasks/checklist 3 处同步修正

**实施中发现的 2 个生产 bug**（已报告 + 修复 + 沉淀）:

1. C 层 `ui_main.py` L11-17 顶部 imports 漏 `from attendance.ui_records import RecordsTab`, 完整 `MainWindow.__init__` 路径从未被 C 层 18 个 UI 测试覆盖（无 `test_ui_main.py`）→ 加 1 行 import, 跑通 D 层 7 个 e2e TC
2. D07 mock `EmployeeDialog.exec_` 跳过 `_on_save` 槽函数, `EmployeeService.create` 未被调, 后续 `EmployeeService.get` 抛 `EmployeeNotFound` → 走 `QMessageBox.warning` → 在 `QT_QPA_PLATFORM=offscreen` 平台下嵌套 QMessageBox 触发 Windows access violation (0xC0000005) → 改 mock 调 `self._on_save()` + `self._confirm(...)`, 保留 service 层真实调用

## 验证结果

| 检查 | 命令 / 文件 | 结果 |
|---|---|---|
| pytest D 11 TC | `pytest tests/test_integration.py tests/test_e2e.py -v` | 11 passed in 4.80s ✅ |
| pytest 全栈 47 TC (A smoke 12 + B 18 + C 18 + D 11) | `pytest tests/ -v` | 47 passed ✅（A 层 12 个 smoke 未进 pytest, 见决策 002 沿用）|
| D01 Schedule→Employee→CheckRecord 全链路 + 4 边界 | TC-ATT-D01 | ✅ (0.07s) |
| D02 删除约束级联 + 3 边界 | TC-ATT-D02 | ✅ (0.05s) |
| D03 管理员改密 + 错误旧密码 + 短新密码 | TC-ATT-D03 | ✅ (0.04s) |
| D04 跨天记录查询 + 4 边界 (employee_id/check_type/端点/空集) | TC-ATT-D04 | ✅ (0.04s) |
| D05 LoginDialog → MainWindow → 3 tab + statusBar | TC-ATT-D05 | ✅ (0.30s) |
| D06 MainWindow 3 tab 切换 + 实例对应 + 退出 action | TC-ATT-D06 | ✅ (0.04s) |
| D07 跨 3 Tab 端到端（新增→识别→记录）+ 4 mock 协作 | TC-ATT-D07 | ✅ (3.5s, 跨步最长) |
| D08 CheckInTab 打开/关闭相机 + 状态栏消息 | TC-ATT-D08 | ✅ (0.20s) |
| D09 get_name.rec 返 'unknown' → warning, 不打卡 | TC-ATT-D09 | ✅ (0.10s) |
| D10 get_name.rec 返 '200099' (face_datasets 命中但 db 无) → warning, 不打卡 | TC-ATT-D10 | ✅ (0.10s) |
| D11 MainWindow.closeEvent → CheckInTab._close_camera 释放 cv2.VideoCapture | TC-ATT-D11 | ✅ (0.04s) |
| conftest.py 未改 | grep diff | ✅ G-06 红线 |
| 红线保护文件未改 | `recognition.py` / `get_name.py` / `ui.py` 哈希不变 | ✅ |

## 闭环：排期清单 #001（D 部分 + 整体）

`BACKLOG.md` #001 整段闭环（A 基础层 + B 服务层 + C UI 层 + D 测试层 4 子 spec 全部 shipped）。本决策是项目自 2026-08-24 初始化以来首个全栈闭环, 共 5 个决策文件（001 初始化 + 002/003/004/005 四个子 spec 闭环）。

## 踩坑

- **C 层决策 004 测试覆盖盲点**: `MainWindow()` 实例化路径从未被 C 层 18 个 UI 测试覆盖（无 `test_ui_main.py`）, `attendance/ui_main.py` L11-17 顶部 imports 漏 `from attendance.ui_records import RecordsTab`, D 层 `logged_in_main_window` fixture 创建 MainWindow 时全员 `NameError`。修法: 加 1 行 import, 不退回决策 004, 沉淀 L-004 建议下一轮补 `test_ui_main.py`。
- **D 层 mock QDialog.exec_ 必须保留槽函数调用**: monkeypatch `EmployeeDialog.exec_` 直接返 Accepted 跳过 `_on_save` 槽函数, `EmployeeService.create` 未被调, 后续 `EmployeeService.get` 抛 `EmployeeNotFound` → 走 `QMessageBox.warning` → `QT_QPA_PLATFORM=offscreen` 平台下嵌套 QMessageBox 触发 Windows access violation (0xC0000005), pytest 进程崩溃。修法: mock 内部显式调 `self._on_save()` / `self._confirm(...)`, 保留 service 层真实调用, 或整体 mock QDialog 子类。沉淀 L-005。
- **`recognition.recognition` 模型加载与 G-06 fixture 兼容**: `import recognition` 时 `yolo = Yolo()` 触发 `torch.load(opt.weights)`, opencv4 环境必须有 `runs/detect/train/weights/best.pt`; D 层 `_offscreen_platform` autouse fixture 必须在 `import recognition` 之前 setdefault, 否则 Qt 平台插件加载失败。D 层在 test_e2e.py 顶部已加 `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")`, 与 C 层风格一致。

## 下一步

- 全栈 4 子 spec 闭环后, 项目从「功能开发期」进入「可发布维护期」。
- 持续事项（按优先级）:
  1. 补 `tests/test_ui_main.py`（C 层 MainWindow 实例化路径测试覆盖, 避免 L-004 类盲点）
  2. 决策 004 提及的 `H-01` Signal 事件（LOGIN_SUCCESS 等）未在代码中触发, 改用 `dlg.accept()` + 属性读取, 待确认是否要回填 Signal
  3. CI/CD 接入（gitee go 或类似）: 现状无 git 仓库（红线 §5）, 用户未拍板前不主动 `git init`
  4. A 层 12 个 smoke test 仍按决策 002 沿用, 未进 pytest; 若想自动化可加 `tests/test_smoke.py` 复用 A 层 fixture
- 跨子 spec 事项: 4 层累计 47 + 12 = 59 TC 全过, 5 个决策文件归档完整, P1 BACKLOG 已清空, P2 decisions 索引可被新会话快速检索。
