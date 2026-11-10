# 002 · SPEC-001-A 基础层闭环（2026-08-24）

- **状态**: 活跃
- **关键词**: foundation, peewee, pymysql, smoke-test
- **相关模块**: attendance/__init__.py, attendance/config.py, attendance/db.py, attendance/models.py, attendance/utils.py, attendance_config.ini, .gitignore

## 关联文档

- `specs/attendance/01-foundation/spec.md` v1.0.0（已 15/15 自检通过）
- `specs/attendance/01-foundation/checklist.md`（本决策的验收依据）
- `BACKLOG.md` #001 排期项
- `AGENTS.md` §6 L-001 踩坑教训（本实施过程中发现并修复）

## 变化程度

- 新建 7 个文件：
  - `attendance/__init__.py` (4 字节, 仅 `__version__`)
  - `attendance/config.py` (ConfigService + 3 静态方法)
  - `attendance/db.py` (init_db / get_db / close_db, pymysql 引导 + peewee 接管)
  - `attendance/models.py` (4 个 Model: Admin/Schedule/Employee/CheckRecord)
  - `attendance/utils.py` (AttendanceError + 14 子类 + sha256_hex + logger)
  - `attendance_config.ini` (3 节模板, 含默认 admin/admin123)
  - `.gitignore` (追加 `attendance_config.ini` 与 `logs/`)
- 修改：`AGENTS.md` §3.2 追加依赖说明；§6 新增 L-001 踩坑教训；§10 变更日志追加一行
- 未触碰：`recognition.py` / `get_name.py` / `ui.py` / `mydata.yaml` / 训练权重

## 摘要

按 SPEC-001-A 完成 6 个任务（T-001 ~ T-104），使用 `D:\python\miniconda3\envs\opencv4\python.exe` 验证（用户已确认 opencv4 环境具备全部运行时依赖）。

**冒烟测试结果**（非正式，仅供本会话内验证）：
- TC-ATT-A01 INI 加载 ✅
- TC-ATT-A02 INI 缺失抛 `INIReadFailed` ✅
- TC-ATT-A03 `ensure_exists` 自动创建 ✅
- TC-ATT-A04 `sha256_hex('admin123')` == `'240be518...720a9'` ✅
- TC-ATT-A05 14 个异常类均为 `AttendanceError` 子类 ✅
- TC-ATT-A06 `init_db`（凭证正确时建库建表预置班次） — 需 MySQL root 可用, 当前凭证不匹配, 见下方"遗留"
- TC-ATT-A07 `init_db` 不可达抛 `DBConnectFailed` ✅
- TC-ATT-A08 `close_db` ✅
- TC-ATT-A09 ~ A12 4 个 Model 字段名与 §4.2 逐字一致 ✅

**静态检查 (CI 门禁)**:
- `grep -REn "raise Exception" attendance/` 0 命中 ✅
- `grep -REn "from attendance.services" attendance/{config,db,models,utils}.py` 0 命中 ✅
- `grep -REn "'(check_in|check_out|middle)'" attendance/{config,db,models,utils}.py` 0 命中 ✅
- `.gitignore` 含 `attendance_config.ini` 与 `logs/` ✅

**实施过程中发现的问题**（已修复）:
1. `peewee.MySQLDatabase(None)` 不允许（database 参数不能为 None）
2. `peewee.MySQLError` 类不存在（应使用 `peewee.DatabaseError` / `peewee.OperationalError`）
3. 修复方案：用 `pymysql.connect()` 先直连建库，再让 peewee 接管（已写入 AGENTS.md §6 L-001）

**遗留 (非本子 spec 阻塞项)**:
- **MySQL root 凭证**：本机 MySQL root 有密码，而 `attendance_config.ini` 中 `password=` 为空。`init_db` 触发 `pymysql.err.OperationalError: (1045, "Access denied")` 并正确上抛 `DBConnectFailed`。用户需在 `attendance_config.ini` 中填入正确的 root 密码，或将 MySQL root 设为无密码。
- 项目仍非 git 仓库，`git check-ignore` 无法跑（CHECKLIST F-03 的实际验证待 `git init` 后再做）。

**下一步**：进入 SPEC-001-B 业务服务层。需在用户启动 B 之前先解决 MySQL 凭证（或者在 B 的测试中用临时库连接，绕开 root 凭证）。
