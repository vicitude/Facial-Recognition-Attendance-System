# 003 · SPEC-001-B 业务服务层闭环（2026-08-24）

- **状态**：活跃
- **关键词**：service, business-logic, peewee, pytest, smoke-test
- **相关模块**：attendance/ 业务服务层

## 关联文档

- `AGENTS.md` §1（项目定位）、§2（当前入口）、§3.2（测试依赖）
- `specs/attendance/02-service/spec.md` v1.0.0（本闭环对应的 spec）
- `specs/attendance/02-service/tasks.md`（T-201~T-204 任务拆解）
- `specs/attendance/02-service/checklist.md`（A-H 验收清单）
- `decisions/_INDEX.md`（本决策的索引行）
- `BACKLOG.md` #001 进度更新（A/B 闭环，C/D 继续）
- 闭环事实唯一来源：本文件

## 变化程度

- 新建：`attendance/services.py`（4 个 Service 类 + 校验器 + 决策表 + logger）
- 新建：`tests/conftest.py`（session 级 init_db + 每 TC 清表 + face_image fixture monkeypatch path pattern）
- 新建：`tests/test_services.py`（18 个 TC，对应 spec §7 覆盖矩阵）
- 新建（用后即删）：`temp_check_b.py`（一次性跑 pytest + 4 项静态检查，闭环后已删）
- 新装依赖：`pytest==8.4.2`、`pytest-qt==4.5.0`（含依赖 `pluggy==1.6.0`、`iniconfig==2.1.0`）
- 修改：`tests/test_services.py::test_TC_ATT_B08_employee_update_partial`（MySQL DATETIME 精度 0 适配，见下文踩坑）

## 摘要

按 SPEC-001-B v1.0.0 落地 4 个静态方法类（`ScheduleService` / `EmployeeService` / `CheckService` / `AdminService`），配套 18 个单元测试全绿。

**实施前确认的关键决策**（与用户对齐）：

1. 测试归属：B 一并落地 `tests/test_services.py`，自闭环。
2. 测试库策略：复用 `attendance_db`，每 TC 用 conftest fixture 清表（`CheckRecord` → `Employee` → `Admin` 顺序，保留 `Schedule`）。
3. `face_image` fixture：tmp_path 创建真实 .jpg + `monkeypatch.setattr(EmployeeService, "FACE_IMAGE_PATH_PATTERN", r".+\.(jpg|jpeg|png)$")` 放宽路径规则。function scope，TC 结束自动还原，不污染业务代码。

**验证结果**：

| 检查 | 命令 / 文件 | 结果 |
|---|---|---|
| pytest 18 TC | `pytest tests/test_services.py -v` | 18 passed in 0.46s ✅ |
| F-01 `raise Exception` 0 命中 | `re.search(r"\braise Exception[\s(]")` | 0 hits ✅ |
| F-02 `import attendance.ui` 0 命中 | `re.findall(r"import attendance\.ui")` | 0 hits ✅ |
| F-03 `check_*` 字面量仅在 `VALID_TYPES` 行 | 字面量散落检查 | 0 violations ✅ |
| F-04 异常类名 15 个一致 | `vars(attendance.utils)` 对比 | 15/15 (0 missing, 0 extra) ✅ |
| G-01 pytest 全绿 | 见上 | ✅ |
| G-02 18 个 `test_TC_ATT_B` 函数 | `pytest --collect-only` | 18 个 ✅ |

## 闭环：排期清单 #001（B 部分）

`BACKLOG.md` #001 中"业务服务层"部分闭环。**未闭环**："UI 层"（SPEC-001-C 待启动）和"测试层"（SPEC-001-D 待启动）。

## 踩坑

- **MySQL DATETIME 默认精度 0（秒）**：`B-08` 第一版断言 `db_emp.updated_at >= before`（`before = datetime.now()` 带微秒）失败，原因是 `Employee.updated_at = DateTimeField(default=datetime.now)` 存到 MySQL 时微秒被截断。修法：测试断言前 `before_create = datetime.now().replace(microsecond=0)` 截断到秒，再断言 `db_emp.updated_at >= before_create`。语义不变（仍证明"被刷新"），贴合 MySQL DATETIME 默认行为。
- **opencv4 环境缺 pytest**：A 闭环时只跑了 `init_db/close_db` 两条静态用例，没暴露此问题。B 跑 18 个 TC 前装 `pytest + pytest-qt`（用户确认）。
- **PowerShell 5.1 不支持 `&&` 串行**：`temp_check_b.py` 用 Python `subprocess` 一次性跑 pytest + 4 项静态检查，绕开 shell 转义问题。
- **`dir(module)` 不返回 `from x import y` 引入的名字**：F-04 检查脚本第一版用 `dir(attendance.utils)` 只列到 `AttendanceError` + `InternalError`，漏 13 个子类。改用 `vars(module).items()` 才能拿到 import 进来的所有符号。

## 下一步

- SPEC-001-C（UI 层）：`attendance_ui.py` PyQt5 主窗口，集成 YOLOv8 识别 + 4 个 Service 类入口。具体 Spec 三件套待与用户对齐。
- SPEC-001-D（测试层）：补充集成测试（UI 端到端、打卡流程回放），与 B 层 18 个单元测试一起构成完整测试矩阵。
- 持续事项：BACKLOG #001 整体仍登记在排期清单；C/D 完成后将再次闭环决策。
