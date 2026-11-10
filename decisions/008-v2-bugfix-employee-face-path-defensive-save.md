# 008 · v2 · 任务 "人脸照片路径格式错误" Bug 修复 v2 升级（2026-08-24）

- **状态**: 活跃
- **版本**: v2（在 008 v1 基础上补强，详见 [008-v1](008-v1-bugfix-employee-face-path.md)）
- **关键词**: bugfix, ui-employees, face-image-path, defensive-normalization, save-boundary, regression-test
- **相关模块**: `attendance/ui_employees.py` (L9-10, L318-350, L385-387) + `tests/test_ui_employees.py` (C12, C13)

## 关联文档

- `AGENTS.md` §1, §5, §6 (**L-013 新增**), §10 变更日志
- `decisions/008-v1-bugfix-employee-face-path.md` (v1 修复背景，UI 归一化起点，本 v2 补强)
- `decisions/004-v1-ui-shipped.md` (C UI 层闭环)
- `decisions/006-v1-bugfix-checkin-warning-loop.md` (任务 1 bugfix 模式，沿用)
- `decisions/007-v1-admin-features-shipped.md` (SPEC-002，58/58 pytest 闭环事实)
- `attendance/services.py:76` (`FACE_IMAGE_PATH_PATTERN` 正则契约，本 v2 **不修改**)
- `attendance/services.py:91-102` (`_validate_face_image_path` 校验链)
- `tests/test_ui_employees.py` (C-05~C-11 旧 UI TC + **C-12/C-13 新增 P1 回归测试**)
- 闭环事实唯一来源：本文件 + 008-v1（v1 部分）

## 变化程度

- **修改 1 个文件**: `attendance/ui_employees.py`
  - L10: 新增 `import re`（1 行，v1 没有需要 re）
  - L318-350: 新增 `_normalize_face_path` helper（33 行，含 16 行 docstring + 17 行实现）
  - L352-362: `_on_browse` 改用 helper（-12 行 / +6 行，净 -6 行）
  - L379-387: `_on_save` **新增** `face_path` 走 helper 兜底归一化（+5 行，含 4 行注释）
  - 文件从 413 行（v1）增到 432 行（+19 行）
- **新增 1 个文件**:
  - `tests/test_ui_employees.py` L285-382: 2 个 P1 回归测试（C12 单元 + C13 集成，+98 行）
- **未触碰** (红线保护):
  - `attendance/services.py` (业务层契约不变，v1 已确认)
  - `attendance/utils.py` (异常类不变)
  - `tests/conftest.py` (D 层 G-06 红线)
  - `recognition.py` / `get_name.py` / `ui.py` (A 层红线)
  - `attendance/ui_employees.py` 其他方法（add/edit/delete/search/refresh 不变）

## 摘要

按用户拍板**v2 补强方案**修复 v1 漏掉的"绝对路径仍能透传 Service"场景。

**v1 复发现象**: v1 fix (`_on_browse` 归一化) 上线后用户实测仍报 "人脸照片路径格式错误: 'D:/yol/yolov8_facenet/face_datasets/HuangJiaWei.jpg' (错误码: FACE_IMAGE_NOT_FOUND)"。用户确认走"浏览..."按钮选文件，理论上 v1 应在 `_on_browse` 把绝对路径归一化为 `face_datasets/HuangJiaWei.jpg`，但 Service 收到的仍是绝对路径。

**v1 漏掉根因（推测）**: 1) 用户本地 Python 解释器 / 进程缓存了未含 v1 fix 的旧 .pyc；2) `attendance_ui.py` 入口可能在 import 期或运行时另一路径初始化 `EmployeeDialog`（不是 v1 改的 `_on_browse` 触发路径）；3) QFileDialog 在某些 PyQt5 版本 / Windows 主题下返回值行为差异。**根因未在 v2 阶段完全复现**，但 v2 用**边界兜底**设计 (Save-time 也归一化) 堵住所有可能路径，**不再依赖 `_on_browse` 单层防御**。

**v2 关键决策**:
1. **抽 helper `_normalize_face_path`**: 单一归一化函数入口，已匹配业务层正则 → 不变；未匹配 → relpath 转项目根相对 + replace os.sep。复用 v1 的 `os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` 项目根算法 + `try/except ValueError` 跨盘符兜底 + forward-slash 转换。
2. **双层防御**:
   - `_on_browse` 即时反馈 (v1 沿用)：选完文件立即归一化，UI 编辑框显示正确的相对路径
   - `_on_save` 边界兜底 (**v2 新增**)：Service 调用前再归一化一次，**任何** UI 入口 (按钮/手输入/拖拽/旧版本) 漏掉都能在 Service 边界前被堵死
3. **P1 回归测试**: 补 2 个测试锁住行为
   - C12 单元测试 `_normalize_face_path` (4 场景: 已匹配/back-slash 绝对/forward-slash 绝对/空串)
   - C13 集成测试 v2 双层防御 (场景 1 mock QFileDialog → 验证 face_path_edit；场景 2 手输入绝对路径 → 验证 EmployeeService.create 收到归一化路径)
4. **决策 008 沿用**: 不开 009，v2 是 v1 的补强不是新 bug；008-v1 + 008-v2 共存，v1 文档保留作历史。

## 实施前确认的关键决策

1. **修复策略选 v2 (Save 时也归一化 + 抽 helper)**: 用户在 AskUserQuestion 拍板 "Save 时也归一化 (推荐)"，v1 单层防御不够 → v2 双层防御；方案 B (只加 Save 兜底不动决策) 和方案 C (口头说明不动代码) 被否决。
2. **回归测试补 P1**: v1 决策"持续事项 #1"已列 v2 补 `test_TC_ATT_C12_browse_normalizes_absolute_path`，本 v2 落地为 C12 + C13 双测试。

## 测试覆盖盲点 (彻底解决)

- **v1 盲点**: 决策 008 v1 §踩坑 明确写 "7 个 UI 员工管理 TC 全过, 但**未覆盖 `_on_browse` 路径** (用 fixture 直接 setText, 不走 QFileDialog)".
- **v2 解法**: 
  - C13 场景 1 mock `QFileDialog.getOpenFileName` 返回绝对路径 → 真实触发 `_on_browse` → 验证 `face_path_edit.text() == "face_datasets/HuangJiaWei.jpg"`
  - C13 场景 2 直接 setText 绝对路径（模拟手输入 / `_on_browse` 漏掉的场景）→ 真实触发 `_on_save` → mock `EmployeeService.create` 捕获参数 → 验证归一化路径
  - 完整覆盖 UI → Service 边界, 防止 v1 测试盲点再次漏掉生产 Bug.
- **L-013 教训沉淀**: 测试不能依赖 fixture 放宽契约, 必须 mock 真实入口 (QFileDialog / QMessageBox / Drag-Drop 等).

## 验证结果

| 检查 | 命令 / 文件 | 结果 |
|---|---|---|
| 新增 2 个 P1 回归测试 | `pytest tests/test_ui_employees.py::test_TC_ATT_C12_normalize_face_path_unit tests/test_ui_employees.py::test_TC_ATT_C13_v2_defensive_normalization -v` | 2/2 PASSED in 0.16s ✅ |
| 全栈无回归 | `pytest tests/ -q` | **60 passed** in 5.66s ✅ (v1 58 + v2 2) |
| Flake 3 遍稳定 | `for i in 1..3: pytest tests/ -q` | 60/60/60 passed, 5.88s/4.97s/4.96s ✅ |
| `tests/conftest.py` 未改 | grep diff | ✅ G-06 红线 |
| 红线保护文件未改 | `recognition.py` / `get_name.py` / `ui.py` 哈希不变 | ✅ |
| `services.py` 未改 (契约保留) | grep diff | ✅ |
| 同一文件多 Edit 严格串行 | L-006 教训遵守: 3 个 Edit 串行 + 1 个 Read 验证 | ✅ |
| `import re` 不与现有命名冲突 | ui_employees.py 顶部 7 个 import 静态检查 | ✅ |

**归一化逻辑 4 场景 (C12 单元覆盖)**:
1. `face_datasets/abc.jpg` (已匹配) → 不变 ✅
2. `D:\yol\yolov8_facenet\face_datasets\HuangJiaWei.jpg` (back-slash 绝对) → `face_datasets/HuangJiaWei.jpg` ✅
3. `D:/yol/yolov8_facenet/face_datasets/HuangJiaWei.jpg` (forward-slash 绝对) → `face_datasets/HuangJiaWei.jpg` ✅
4. `""` (空串) → `""` ✅

**集成双层防御 2 场景 (C13 覆盖)**:
1. mock `QFileDialog.getOpenFileName` 返回绝对路径 → `_on_browse` → `face_path_edit.text() == "face_datasets/HuangJiaWei.jpg"` ✅
2. 直接 setText 绝对路径 (模拟手输入 / `_on_browse` 漏掉) → `_on_save` → mock `EmployeeService.create` 收到 `face_image_path == "face_datasets/HuangJiaWei.jpg"` ✅

## 闭环：项目里程碑

决策 008 v2 与 008 v1 共同形成"**测试盲点 → 现场 Bug → 单层修复 → 复现 → 边界兜底补强**"完整闭环模式。沿用决策 006 模式：不在 `BACKLOG.md` 新增排期项，闭环事实沉淀在 `decisions/008-v1-bugfix-employee-face-path.md` (v1 历史) + `decisions/008-v2-bugfix-employee-face-path-defensive-save.md` (本文件) + `_INDEX.md` 索引行 + `AGENTS.md` §6 L-013 踩坑 + §10 变更日志。

## 踩坑

- **v1 单层防御不够** (本任务触发): 实际生产 v1 fix 仍有漏, 用户现场复现, 根因可能是 .pyc 缓存 / 另一 UI 入口 / QFileDialog 行为差异 (任一或多个). **对：v2 用 Save 边界兜底 + 双层防御, 不依赖单一入口**. 沉淀至 AGENTS.md §6 L-013.
- **测试覆盖盲点 (v1 教训延伸)**: 之前 fixture 放宽契约 (face_image monkeypatch 正则) + 直接 setText 跳过 QFileDialog 是 v1 漏 Bug 的根因. **v2 解决**: C13 场景 1 mock QFileDialog 走真实入口, 场景 2 setText 绝对路径验证 Save 兜底. 沉淀至 L-013.
- **`os.path.dirname(__file__)` 与 Windows 盘符大小写**: 测试用 `os.path.join(project_root, ...)` 动态拼绝对路径, 与 helper 内部算法保持 case 一致, 避免 relpath 失真. 沉淀至 L-013 注释.

## 下一步

- **持续事项** (按优先级):
  1. 决策 005 L-004 建议 (补 `tests/test_ui_main.py` 覆盖 `MainWindow.__init__` 完整路径) 仍未闭环, 与本任务同属 "测试覆盖盲点" 类风险.
  2. 决策 007 持续事项 #1 (补 `test_ui_main.py`) 仍未闭环 (与 #1 是同一件事).
  3. Round 1 归档的 3 项目内部矛盾 (G-01 数值 / _INDEX 漏列 05 / H-01 Signal) 仍待用户拍板.
- **跨决策事项**: 6 决策 (002/003/004/005/006/007) + 2 bugfix 决策 (008-v1, 008-v2) = **8 决策文件**归档完整. 5 红线 + **13** 踩坑教训 (L-001 ~ L-013) 全部沉淀.
- **环境沉淀**: v2 验证用 `D:\python\miniconda3\envs\opencv4\python.exe` (pytest 8.4.2 / PyQt5 5.15.11 / peewee / pymysql 全装; pytest-qt 缺失但 test_ui_employees.py 不强需). 建议下次新增任务时优先用此环境跑测试, 避免误用裸 Python 3.12 (依赖全 MISSING).
