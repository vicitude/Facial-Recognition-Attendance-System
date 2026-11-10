# 验收清单: SPEC-001-B 业务服务层

> 与 `specs/attendance/02-service/spec.md` v1.0.0 配套。闭环后: `decisions/003-v1-service-shipped.md` + `_INDEX.md` 追加 003 行。

---

## A. 文件存在

- [ ] **A-01** `attendance/services.py` 存在 — 阻塞
- [ ] **A-02** 4 个 Service 类均存在: `ScheduleService`, `EmployeeService`, `CheckService`, `AdminService` — 阻塞

## B. ScheduleService

- [ ] **B-01** `ScheduleService.get(1)` 在已 seed 后返回 Schedule — 阻塞 → TC-ATT-B01
- [ ] **B-02** `ScheduleService.get(999)` 抛 `ScheduleNotFound` — 阻塞 → TC-ATT-B02
- [ ] **B-03** `ScheduleService.list_all()` 返回 list[Schedule] — 阻塞 → TC-ATT-B03

## C. EmployeeService

- [ ] **C-01** `create` 全条件通过返回 Employee — 阻塞 → TC-ATT-B04
- [ ] **C-02** `create(employee_id='abc123')` 抛 `EmployeeIdInvalid` — 阻塞 → TC-ATT-B05
- [ ] **C-03** `create` 工号重复抛 `EmployeeIdExists` — 阻塞 → TC-ATT-B06
- [ ] **C-04** `create` 照片不存在抛 `FaceImageNotFound` — 阻塞 → TC-ATT-B07
- [ ] **C-05** `update('100001', name='新名')` 返回 Employee 且数据库 name 已更新, updated_at 刷新 — 阻塞 → TC-ATT-B08
- [ ] **C-06** `update('999999', name='X')` 抛 `EmployeeNotFound` — 阻塞 → TC-ATT-B09
- [ ] **C-07** `delete('100002')` (无记录) 成功删除 — 阻塞 → TC-ATT-B10
- [ ] **C-08** `delete('100001')` (有记录) 抛 `EmployeeHasRecords` — 阻塞 → TC-ATT-B11
- [ ] **C-09** `get('999999')` 抛 `EmployeeNotFound` — 阻塞

## D. CheckService

- [ ] **D-01** `create_record('100001', 'check_in')` 正常返回 CheckRecord — 阻塞 → TC-ATT-B12
- [ ] **D-02** `create_record` 对 is_active=False 员工抛 `EmployeeInactive` — 阻塞 → TC-ATT-B13
- [ ] **D-03** `create_record` 对 check_type='foo' 抛 `CheckTypeInvalid` — 阻塞 → TC-ATT-B14
- [ ] **D-04** `list_records(date_from, date_to)` 正确过滤 — 阻塞 → TC-ATT-B15
- [ ] **D-05** `list_records(date_from > date_to)` 抛 `DateRangeInvalid` — 阻塞 → TC-ATT-B16
- [ ] **D-06** `list_records(employee_id='X', check_type='Y')` 组合过滤正确 — 阻塞

## E. AdminService

- [ ] **E-01** `authenticate('admin', 'admin123')` 成功返回 Admin — 阻塞 → TC-ATT-B17
- [ ] **E-02** `authenticate` 错密码抛 `AuthFailed` — 阻塞 → TC-ATT-B18
- [ ] **E-03** `change_password` 旧密码错抛 `AuthFailed` — 阻塞
- [ ] **E-04** `change_password` 新密码长度 < 6 抛 `PasswordTooShort` — 阻塞
- [ ] **E-05** `change_password` 全条件通过后, 旧密码不可登录, 新密码可登录 — 阻塞
- [ ] **E-06** `ensure_default('admin', 'admin123')` 在空 admins 表时插入默认账号 — 阻塞
- [ ] **E-07** `ensure_default` 在已存在账号时无操作 — 阻塞

## F. 静态检查

- [ ] **F-01** `grep -REn "raise Exception" attendance/services.py` 0 命中 — 阻塞
- [ ] **F-02** `grep -REn "import attendance.ui" attendance/services.py` 0 命中 — 阻塞
- [ ] **F-03** `grep -REn "['\"](check_in|check_out|middle)['\"]" attendance/services.py` 仅在 `VALID_CHECK_TYPES` 行出现 — 阻塞
- [ ] **F-04** 业务异常类名与 SPEC-001-A §6.2 占位逐字一致 — 阻塞

## G. 测试

- [ ] **G-01** `pytest tests/test_services.py -q` 全绿 — 阻塞
- [ ] **G-02** `pytest --collect-only -q | grep "test_TC_ATT_B"` 输出 18 行 — 阻塞

## H. 闭环

- [ ] **H-01** 全部阻塞项通过后, 在 `decisions/003-v1-service-shipped.md` 写入闭环决策
- [ ] **H-02** 在 `decisions/_INDEX.md` 追加 003 行
