# 验收清单: SPEC-001-A 基础层

> 与 `specs/attendance/01-foundation/spec.md` v1.0.0 配套。闭环后: `decisions/002-v1-foundation-shipped.md` + `_INDEX.md` 追加 002 行。

---

## A. 文件存在

- [ ] **A-01** `attendance/__init__.py` 存在且含 `__version__ = "1.0.0"` — 阻塞
- [ ] **A-02** `attendance/config.py` 存在 — 阻塞
- [ ] **A-03** `attendance/db.py` 存在 — 阻塞
- [ ] **A-04** `attendance/models.py` 存在 — 阻塞
- [ ] **A-05** `attendance/utils.py` 存在 — 阻塞
- [ ] **A-06** `attendance_config.ini` 存在且含 [database]/[admin]/[schedule_seed] 三节 — 阻塞
- [ ] **A-07** `.gitignore` 包含 `attendance_config.ini` 与 `logs/` — 阻塞

## B. utils.py 异常类

- [ ] **B-01** `from attendance.utils import AttendanceError` 成功 — 阻塞
- [ ] **B-02** `INIReadFailed`, `DBConnectFailed`, `InternalError` 均为 `AttendanceError` 子类 — 阻塞
- [ ] **B-03** 其他 11 个异常类占位存在且为 `AttendanceError` 子类 — 阻塞
- [ ] **B-04** `sha256_hex('admin123') == '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9'` — 阻塞 → TC-ATT-A04
- [ ] **B-05** 14 个异常类均存在 — 阻塞 → TC-ATT-A05

## C. models.py 字段

- [ ] **C-01** `Admin` 含 `id` (AutoField) / `username` (CharField(50, unique=True)) / `password_hash` (CharField(64)) / `is_super` (BooleanField default=True) / `created_at` (DateTimeField default=datetime.now) — 阻塞 → TC-ATT-A09
- [ ] **C-02** `Schedule` 含 `id` / `name` (CharField(50, unique=True)) / `work_start` (TimeField) / `work_end` (TimeField) / `late_threshold_min` (IntegerField) / `early_leave_threshold_min` (IntegerField) / `created_at` — 阻塞 → TC-ATT-A12
- [ ] **C-03** `Employee` 含 `employee_id` (CharField(6, primary_key=True)) / `name` (CharField(50)) / `department` (CharField(50, null=True)) / `position` (CharField(50, null=True)) / `phone` (CharField(20, null=True)) / `email` (CharField(100, null=True)) / `face_image_path` (CharField(255)) / `schedule` (ForeignKeyField(Schedule)) / `is_active` (BooleanField default=True) / `created_at` / `updated_at` — 阻塞 → TC-ATT-A10
- [ ] **C-04** `CheckRecord` 含 `id` / `employee` (ForeignKeyField(Employee)) / `check_timestamp` (DateTimeField default=datetime.now) / `check_type` (CharField(10)) / `check_date` (DateField) / `created_at` — 阻塞 → TC-ATT-A11

## D. config.py

- [ ] **D-01** `ConfigService.load()` 在 INI 存在时返回 §4.1 dict — 阻塞 → TC-ATT-A01
- [ ] **D-02** `ConfigService.load()` 在 INI 缺失时抛 `INIReadFailed`, 错误码 `INI_READ_FAILED` — 阻塞 → TC-ATT-A02
- [ ] **D-03** `ConfigService.ensure_exists()` 在 INI 缺失时创建 INI 并写入 T-002 默认值 — 阻塞 → TC-ATT-A03

## E. db.py

- [ ] **E-01** `init_db(config)` 在 MySQL 可达时建库 + 建表 + 预置 schedule — 阻塞 → TC-ATT-A06
- [ ] **E-02** `init_db` 第二次调用(表已存在) < 500ms — 阻塞 → TC-ATT-A06
- [ ] **E-03** `init_db` 在 MySQL 不可达时抛 `DBConnectFailed`, 错误码 `DB_CONNECT_FAILED` — 阻塞 → TC-ATT-A07
- [ ] **E-04** `close_db()` 后 `db.is_closed() == True` — 阻塞 → TC-ATT-A08

## F. 静态检查

- [ ] **F-01** `grep -REn "raise Exception" attendance/` 0 命中 — 阻塞
- [ ] **F-02** `grep -REn "from attendance.services" attendance/{config,db,models,utils}.py` 0 命中 — 阻塞
- [ ] **F-03** `git check-ignore -v attendance_config.ini` 退出码 0 — 阻塞
- [ ] **F-04** `grep -REn "['\"](check_in|check_out|middle)['\"]" attendance/{config,db,models,utils}.py` 0 命中 — 阻塞 (本子 spec 范围不涉及)

## G. 测试

- [ ] **G-01** `pytest tests/test_foundation.py -q` 全绿 — 阻塞
- [ ] **G-02** `pytest --collect-only -q | grep "test_TC_ATT_A"` 输出 12 行 — 阻塞

## H. 闭环

- [ ] **H-01** 全部阻塞项通过后, 在 `decisions/002-v1-foundation-shipped.md` 写入闭环决策
- [ ] **H-02** 在 `decisions/_INDEX.md` 追加 002 行
