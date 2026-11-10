# 008 · 任务 "人脸照片路径格式错误" Bug 修复闭环（2026-08-24）

- **状态**: 活跃
- **关键词**: bugfix, ui-employees, face-image-path, absolute-vs-relative, qfiledialog, path-normalization
- **相关模块**: `attendance/ui_employees.py` (L9 + L317-336)

## 关联文档

- `AGENTS.md` §1 (项目定位), §5 (红线), §6 (踩坑教训, **L-012 新增**), §10 (变更日志)
- `decisions/004-v1-ui-shipped.md` (C UI 层闭环, 7 个 UI 员工管理 TC, 本任务的 C 层前提)
- `decisions/006-v1-bugfix-checkin-warning-loop.md` (任务 1 弹窗卡死循环 Bug 修复, 走特批小补丁模式, 本任务沿用)
- `decisions/007-v1-admin-features-shipped.md` (SPEC-002 管理员, 58/58 pytest 闭环事实)
- `attendance/services.py:76` (`FACE_IMAGE_PATH_PATTERN` 正则契约, 项目根相对路径)
- `attendance/services.py:91-102` (`_validate_face_image_path` 校验链: 正则 → isfile)
- `attendance/utils.py:60-61` (`FaceImageNotFound` 异常类)
- `tests/conftest.py:86-99` (`face_image` fixture 用 monkeypatch 放宽正则, 所以测试无法复现此 Bug)
- `tests/test_ui_employees.py` (7 个 C-05~C-11 UI TC, 全部 PASSED, 但**未覆盖 `_on_browse` 路径**)
- 闭环事实唯一来源: 本文件

## 变化程度

- **修改 1 个文件**: `attendance/ui_employees.py`
  - L9: 新增 `import os` (1 行)
  - L317-336: `_on_browse` 槽函数改造 (12 行, 含 3 行注释 + 9 行逻辑)
  - 文件从 401 行增到 413 行 (+12 行)
- **未触碰** (红线保护):
  - `attendance/services.py` (业务层契约不变, `FACE_IMAGE_PATH_PATTERN` 仍为项目根相对路径)
  - `attendance/utils.py` (`FaceImageNotFound` 异常类不变)
  - `tests/conftest.py` (D 层 G-06 红线, 6 个 fixture 不变)
  - `recognition.py` / `get_name.py` / `ui.py` (A 层红线, 哈希不变)
  - `attendance/ui_employees.py` 其他方法 (新增 / 编辑 / 删除 / 搜索 / 表格刷新 等逻辑不变)

## 摘要

按用户拍板**方案 A (UI 层归一化)** 修复 "人脸照片保存失败" Bug.

**Bug 现象**: 用户在「人员管理 → 新增」走「浏览...」按钮选 `face_datasets/HuangJiaWei.jpg` 后, 点「保存」弹 "人脸照片路径格式错误: 'D:/yol/yolov8_facenet/face_datasets/HuangJiaWei.jpg' (错误码: FACE_IMAGE_NOT_FOUND)".

**根因**: UI 层 `_on_browse` (`ui_employees.py:316-322` 原版) 用 `QFileDialog.getOpenFileName` 默认返回**绝对路径** (PyQt5 跨平台标准行为), 直接 setText 给 face_path_edit; Service 层 `_validate_face_image_path` (`services.py:91-102`) 校验的正则 `FACE_IMAGE_PATH_PATTERN = r"^face_datasets/[^/]+\.(jpg|jpeg|png)$"` 只接受**项目根相对路径**, 绝对路径以盘符 `D:/` 开头不匹配 → 抛 `FaceImageNotFound` → 弹错误码 → 任何走"浏览..."按钮选文件的用户 100% 失败.

**实施前确认的关键决策** (与用户对齐, 1 项拍板):
1. 修复方案选 A: UI 层归一化 (改 1 个文件, +12 行, 不动 Service 层契约). 备选方案 B (Service 放宽正则) 和方案 C (双层都改) 被用户否决, 理由: 改最小 / 保留业务约束 / 不动测试 fixture.

**实施中确认的次要决策** (落到代码注释中):
- 用 `os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` 计算项目根 (跨平台, 不依赖 CWD)
- `try/except ValueError` 兜底 (Windows 跨盘符 `os.path.relpath` 会抛 ValueError)
- `rel.replace(os.sep, "/")` 转 forward-slash (Service 正则硬编码 `/`)

**测试覆盖盲点 (再次暴露)**: 决策 004 C 层 7 个 UI 员工管理 TC (C05~C11) 全部 PASSED, 但**未覆盖 `_on_browse` 路径** (测试用 `face_image` fixture 直接 setText, 不走 QFileDialog). 本 Bug 现场由用户报告, 非自动化测试发现. 同决策 005 L-004 / 决策 006 教训 — **测试覆盖盲点是项目普遍风险**, 需每个新 bug 修复时主动补 P1 回归测试.

## 验证结果

| 检查 | 命令 / 文件 | 结果 |
|---|---|---|
| 修改文件未引入语法错误 | `pytest tests/test_ui_employees.py -v` | 7/7 PASSED in 0.48s ✅ |
| 全栈无回归 | `QT_QPA_PLATFORM=offscreen pytest tests/ -q` | 58 passed in 6.38s ✅ |
| 归一化逻辑烟雾测试 (4 场景) | 内联 Python 脚本 | 4/4 符合预期 ✅ |
| `tests/conftest.py` 未改 | grep diff | ✅ G-06 红线 |
| 红线保护文件未改 | `recognition.py` / `get_name.py` / `ui.py` 哈希不变 | ✅ |
| `services.py` 未改 (契约保留) | grep diff | ✅ |
| 同一文件多 Edit 严格串行 | L006 教训遵守: 2 个 Edit 串行, 不并行 | ✅ |

**归一化逻辑 4 个场景**:
1. `D:\yol\yolov8_facenet\face_datasets\HuangJiaWei.jpg` (用户实际场景) → `face_datasets/HuangJiaWei.jpg` → 匹配正则 ✅
2. `D:/yol/yolov8_facenet/face_datasets/obama.png` (forward-slash 绝对路径) → `face_datasets/obama.png` → 匹配 ✅
3. `D:\yol\yolov8_facenet\OIP-C.jpg` (项目根但非 face_datasets) → `OIP-C.jpg` → 不匹配 (Service 抛 `FaceImageNotFound` 提示用户) ✅
4. `D:\other\photo.jpg` (项目外) → `../../other/photo.jpg` → 不匹配 ✅

## 闭环: 项目里程碑

任务 "人脸照片路径格式错误" Bug 修复闭环, 与决策 005 (D 层测试盲点) / 006 (任务 1 弹窗卡死循环) / 007 (SPEC-002) 共同形成 "**测试盲点 → 现场 Bug → 修复 + 沉淀**" 模式. 沿用决策 006 模式: 不在 `BACKLOG.md` 新增 #003 排期项, 闭环事实沉淀在 `decisions/008-v1-bugfix-employee-face-path.md` (本文件) + `_INDEX.md` 索引行 + `AGENTS.md` §6 L-012 踩坑 + §10 变更日志.

## 踩坑

- **QFileDialog.getOpenFileName 默认返回绝对路径**: 这是 PyQt5 跨平台标准行为, 不是 BUG 但容易被忽视. UI 收集路径后必须明确归一化策略 (绝对 / 相对), 否则与业务层契约冲突时 100% 失败. **沉淀至 AGENTS.md §6 L-012**.
- **测试覆盖盲点 (同决策 005 L-004 / 决策 006 教训)**: 7 个 UI 员工管理 TC 全过, 但不覆盖 `_on_browse` 路径 (用 fixture 直接 setText 绕过 QFileDialog). 修复时同步补 P1 回归测试可锁住行为, 防未来重构再次踩坑. **用户拍板暂不补 P1 回归测试**, 沉淀为持续事项.
- **未在 conftest.py 加 mock QFileDialog 的 fixture**: 加 fixture 会让所有 UI 员工管理测试加载 QFileDialog 依赖, 复杂度上升; 当前选择不补, 风险已记录到 L-012.

## 下一步

- **持续事项** (按优先级):
  1. (建议, 用户未拍板) 补 P1 回归测试 `tests/test_ui_employees.py::test_TC_ATT_C12_browse_normalizes_absolute_path`, mock `QFileDialog.getOpenFileName` 返回绝对路径, 验证 `face_path_edit.text() == "face_datasets/HuangJiaWei.jpg"`. 跟决策 006 D09/D10 加 P1 断言同理.
  2. 决策 005 L-004 建议 (补 `test_ui_main.py`) 仍未闭环, 与本任务同属 "测试覆盖盲点" 类风险, 下一轮一并处理.
  3. 决策 007 持续事项 #1 (补 `test_ui_main.py`) 仍未闭环.
  4. Round 1 归档的 3 项目内部矛盾 (G-01 数值 / _INDEX 漏列 05 / H-01 Signal) 仍待用户拍板.
- **跨决策事项**: 5 个子 spec + 3 个 bugfix 决策 (006 / 008) + 1 个 SPEC-002 (007) 累计 **9 决策文件** 归档完整. 5 红线 + **12** 踩坑教训 (L-001 ~ L-012) 全部沉淀.
