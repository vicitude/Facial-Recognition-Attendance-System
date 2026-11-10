# 006 · 任务 1 弹窗卡死循环修复闭环（2026-08-24）

- **状态**: 活跃
- **关键词**: bugfix, ui-checkin, warning-loop, race-condition, p1-assertion
- **相关模块**: attendance/ui_checkin.py, tests/test_e2e.py (D09/D10 增强)

## 关联文档

- `AGENTS.md` §1（项目定位）、§2（当前入口）、§4（协作原则）、§5（红线）
- `decisions/004-v1-ui-shipped.md`（C UI 层闭环, 本任务的 C 层前提）
- `decisions/005-v1-test-shipped.md`（D 测试层闭环, 本任务的测试基础, 11 TC 全绿）
- `specs/attendance/03-ui/spec.md` v1.0.0 + `tasks.md` + `checklist.md`（C 层规范, 本任务修复点在 C 层代码）
- `specs/attendance/04-test/spec.md` v1.0.0（决策 005 闭环的 D 层规范, D09/D10 TC 矩阵）
- 闭环事实唯一来源：本文件

## 背景

用户在生产运行 `python attendance_ui.py` + 实时签到 Tab + 打开相机 + 开始识别时, 实际遇到「人脸不在库中」warning 弹窗关闭后, **30ms 后立即又弹同一条**, 1 秒 33 个弹窗, UI 阻塞, 软件无法操作。报告此 bug 时已配「使用报告 + 任务 2/3 任务报告」, 用户拍板"走法 A: 先补任务 1 决策 006"。

## 变化程度

- 修改 1 个 C 层文件: `attendance/ui_checkin.py`
  - L255/L271/L280 三处 warning 早退路径**各加 1 行** `self._stop_recognition_after_unknown()` 调用（实际 L255 是 boxes=[] 路径, L271 是 name=="unknown" 路径, L280 是 EmployeeNotFound 路径）
  - L302-317 追加新方法 `_stop_recognition_after_unknown(self) -> None`: 重置 `flag_recognition=False` + `btn_start.setEnabled(True)` + `btn_stop.setEnabled(False)` + 调 `_emit_status("未识别, 已停止识别, 需重新点「开始识别」继续")`
  - 文件从 324 行增到 339 行（+15 行, 含 12 行 helper docstring + 3 行调用）
- 修改 1 个 D 层测试文件: `tests/test_e2e.py`
  - D09 `test_TC_ATT_D09_e2e_checkin_recognition_unknown` 末尾追加 4 个 P1 断言
  - D10 `test_TC_ATT_D10_e2e_checkin_face_not_in_db` 末尾追加 4 个 P1 断言
  - 文件增 16 行（2 × 8 行 P1 断言块）
- 未触碰: `tests/conftest.py`（G-06 红线）/ `attendance/ui_main.py`（决策 005 闭环 1 行 import 修复后稳定）/ `attendance/services.py`（B 层红线）/ `recognition.py` + `get_name.py` + `ui.py`（A 层红线, 哈希不变）

## 摘要

按方案 B（用户拍板: DRY 改法, 提取 helper 方法, 4 处早退路径调 helper）修复任务 1 bug, 同时给 D09/D10 各补 4 个 P1 断言锁住修复行为, 防回归。

**实施前确认的关键决策**（与用户对齐, 3 项拍板）:

1. 修复方案选 B: 提取 helper `_stop_recognition_after_unknown()`, 4 处早退路径调 helper (非方案 A 重复 12 行 / 非方案 C 重构 try/finally)
2. D09/D10 补 P1 断言锁住修复行为（参考决策 005 D 阶段 13 个 P1 缺口经验）
3. 任务 1 走特批小补丁（不建独立 spec 三件套, 不在 SPEC-002 范围, 闭环事实沉淀在本决策 006 + L-006）

**实施中发现的 1 个工作流坑**（已报告 + 修复 + 沉淀 L-006）:

- 4 个 Edit 并行触发（boxes=[] / unknown / EmployeeNotFound 3 处早退 + 1 处加 helper）撞行号 race condition: harness 内部按"当前文件状态"匹配 `old_string`, 但行号因前置 Edit 加行而偏移, Edit 3 (EmployeeNotFound 分支) 报告成功但实际未改对应块, 测试 D10 失败定位"helper 未被调"。修法: 重新 Edit 1 次（串行, 不并行）, 加 `self._stop_recognition_after_unknown()` 到 L285。教训: **同一文件多 Edit 必须严格串行, 不并行**。沉淀 L-006。

## 验证结果

| 检查 | 命令 / 文件 | 结果 |
|---|---|---|
| pytest D 9 TC (D01~D04 + D05~D11) 增强后 | `pytest tests/ -v` | 47 passed in 6.66s ✅（D09/D10 各 +4 断言, 0 回归）|
| D09 P1 断言: 4 行全部 PASSED | `assert tab.flag_recognition is False` + `btn_start.isEnabled() is True` + `btn_stop.isEnabled() is False` + `"未识别" in statusBar().currentMessage()` | ✅ |
| D10 P1 断言: 4 行全部 PASSED | 同上 | ✅ |
| C 层 ui_checkin.py 4 个 TC (C12~C15) | `pytest tests/test_ui_checkin.py -v` | 4 passed ✅ |
| conftest.py 未改 | grep diff | ✅ G-06 红线 |
| 红线保护文件未改 | `recognition.py` / `get_name.py` / `ui.py` 哈希不变 | ✅ |

## 闭环：项目里程碑

任务 1 弹窗卡死循环修复闭环, 与决策 005（D 测试层 11 TC 闭环）共同形成"生产 bug 修复 + 测试覆盖增强"完整闭环。SPEC-002 范围**不**包含本任务（已澄清, 任务 2/3 走 SPEC-002 三件套, 任务 1 走本决策 006）。

## 踩坑

- **4 Edit 并行 race condition**: 同一文件多次 Edit 撞行号, harness 报告成功但实际未改。修法: 串行 Edit, 严格 1 次响应 1 个 Edit。沉淀 L-006。
- **D09/D10 原缺修复行为断言**: 原 18 个 UI 测试 (决策 004 闭环) + 11 个 D 层 TC (决策 005 闭环) 全绿, 但未断言"未识别后停止识别"这一修复核心行为。修法: 补 8 个 P1 断言 (D09/D10 各 4 个) 锁住行为, 防回归。本质同决策 005 D 阶段 13 个 P1 缺口, **测试覆盖盲点**是项目普遍风险, 需每个新 spec 落地时主动检查。
- **`_stop_recognition_after_unknown` 复用 `_emit_status`**: helper 末尾调 `self._emit_status(...)` 走 statusBar 状态栏反馈, 与 `MainWindow._build_ui` 注入的 statusBar 回调兼容 (L312 决策 005 沉淀的 `status_bar_message: Signal(str) = Signal(str)` 模式), 修复后 `statusBar().currentMessage()` 实时反映状态。

## 下一步

- 任务 1 闭环后, 继续走 SPEC-002 (用户拍板"和之前一样处理")：T-601 (B 层 3 方法 + 2 Unit TC) → T-602 (改密 UI + 5 UI TC) → T-603 (AdminsTab + 3 UI TC) → T-604 (1 E2E + 闭环决策 007)。
- 持续事项: 项目从 4 子 spec 闭环（决策 005） → 任务 1 修复闭环（决策 006） → SPEC-002 启动（决策 007 待写）, 状态为「可发布维护期 + 新功能开发期并行」。
- 跨决策事项: 决策 005 提及的 `H-01` Signal 事件（LOGIN_SUCCESS 等）未在代码中触发, 改用 `dlg.accept()` + 属性读取, 待确认是否要回填 Signal（保留为持续事项, 不阻塞 SPEC-002）。
