# 任务拆解: SPEC-001-B 业务服务层

> 与 `specs/attendance/02-service/spec.md` v1.0.0 配套。

---

## T-201 实现 ScheduleService

- **依赖**: SPEC-001-A 已闭环 (models + utils)
- **前置**: 无
- **产出物**: `attendance/services.py` 含 `class ScheduleService` 与 `get / list_all` 两个静态方法
- **关联**: §3.1 ScheduleService
- **覆盖**: TC-ATT-B01, TC-ATT-B02, TC-ATT-B03

## T-202 实现 EmployeeService 增删改查

- **依赖**: T-201
- **前置**: `face_datasets/100001.jpg` 测试用文件由测试 fixture 准备
- **产出物**: `attendance/services.py` 追加 `class EmployeeService`, 含 6 个方法:
  - `create(...)` — 4 个校验器顺序执行 (id 格式 / id 唯一 / 照片存在 / schedule 存在), 全部通过后 `Employee.create(**fields)`
  - `update(employee_id, **fields)` — `_validate_face_image_path` 仅当 face_image_path 非 None 时执行; `Employee.update(...).where(...).execute()` 后 `updated_at = datetime.now()`
  - `delete(employee_id)` — `CheckRecord.select().where(employee=...).count() > 0` 时抛 `EmployeeHasRecords`;否则 `Employee.delete_by_id(employee_id)`
  - `get(employee_id)` — 查不到抛 `EmployeeNotFound`
  - `list_all(is_active)` — `Employee.select().where(...)`
  - `search(keyword)` — `keyword == ''` 返回 `[]`;否则 `Employee.select().where((employee_id.contains(keyword)) | (name.contains(keyword)))`
- **关联**: §3.2 EmployeeService, §5.1 B-BR-001/B-BR-002
- **覆盖**: TC-ATT-B04, B05, B06, B07, B08, B09, B10, B11

## T-203 实现 CheckService

- **依赖**: T-201
- **前置**: 无
- **产出物**: `attendance/services.py` 追加 `class CheckService` 与 `VALID_TYPES`, 含:
  - `create_record(employee_id, check_type)` — 校验顺序: EmployeeNotFound / EmployeeInactive / CheckTypeInvalid; 全部通过后 `CheckRecord.create(employee=e, check_type=t, check_timestamp=now, check_date=now.date())`
  - `list_records(...)` — 校验 DateRangeInvalid 后 `CheckRecord.select().where(*conds).order_by(CheckRecord.check_timestamp.desc())`
- **关联**: §3.3 CheckService, §5.1 B-BR-003/B-BR-004
- **覆盖**: TC-ATT-B12, B13, B14, B15, B16

## T-204 实现 AdminService

- **依赖**: T-201 (T-202 间接)
- **前置**: 无
- **产出物**: `attendance/services.py` 追加 `class AdminService` 与 `MIN_PASSWORD_LENGTH = 6`, 含:
  - `authenticate(username, password)` — `Admin.select().where(username=...).get_or_none()`; 若 None 抛 `AuthFailed`; 否则 `sha256_hex(password) == admin.password_hash` 校验, 失败抛 `AuthFailed`
  - `change_password(admin_id, old_password, new_password)` — 先 `authenticate(admin.username, old_password)` 校验旧密码 (会复用 authenticate); 再校验新密码长度; 最后 `Admin.update(...).where(id=admin_id).execute()`
  - `ensure_default(username, password)` — `Admin.select().count() == 0` 时 `Admin.create(username=..., password_hash=sha256_hex(password), is_super=True)`; 插入异常时 `try/except peewee.IntegrityError` 重抛 `InternalError`
- **关联**: §3.4 AdminService
- **覆盖**: TC-ATT-B17, B18

---

## 任务依赖图

```text
T-201 ──┬──> T-202 ──┐
        │            │
        ├──> T-203 ──┤
        │            ├──> T-204
        └──> ... ────┘
```

## 排期

| 阶段 | 任务 | 工时(单人时) |
|------|------|--------------|
| 服务 | T-201, T-202, T-203, T-204 | 4 |
| **合计** | - | **4** |
