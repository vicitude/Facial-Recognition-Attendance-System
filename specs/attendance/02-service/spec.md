# SPEC-001-B: 业务服务层

> **规范状态**: 已批准
> **版本**: v1.0.0
> **拆分自**: SPEC-001 v1.0.0(见 `_LEGACY.md`)
> **依赖**: SPEC-001-A 基础层(必须先闭环)
> **代码包路径**: `attendance/services.py`
> **最后修改**: 2026-08-24

---

## 0. 文档头与元数据

- **文件路径**: `/specs/attendance/02-service/spec.md`
- **关联代码路径**:
  - `attendance/services.py`
  - 消费: `attendance.models` (Admin/Schedule/Employee/CheckRecord), `attendance.utils` (异常类 + sha256_hex)
- **CI 门禁规则**:
  - `grep -REn "raise Exception" attendance/services.py` 必须 0 命中(只允许 `raise AttendanceError 子类`)。
  - 业务异常类名与 SPEC-001-A §6.2 占位的 11 个子类逐字一致。
  - 测试用例 ID (TC-ATT-B01~B18) 与 tests/test_services.py 函数名一一对应。

---

## 1. 术语表

| 术语 | 英文名 | 类型 | 定义 | 代码映射 |
|------|--------|------|------|----------|
| 业务服务层 | ServiceLayer | 架构层 | 静态方法类集合, 封装业务规则 | `attendance/services.py` |
| 校验器 | Validator | 函数 | `_validate_xxx` 私有方法, 失败抛异常 | `EmployeeService._validate_employee_id` |
| 工厂方法 | Factory | 函数 | 服务层暴露给 UI 的入口, 完成"校验+持久化" | `EmployeeService.create` |
| 决策表 | DecisionTable | 文档 | §5 业务规则, 决定动作 | 本 spec §5 |

(其他模型相关术语见 SPEC-001-A §1)

---

## 2. 用户故事与验收场景(Gherkin)

```gherkin
功能: ScheduleService
  作为服务层
  我需要班次查询
  以便人员管理 UI 列出可选班次

  场景: 按 id 查询班次
    假设 schedules 表存在 id=1, name='常规班'
    当 调用 ScheduleService.get(1)
    那么 返回 Schedule(id=1, name='常规班', ...)

  场景: 查询不存在的班次
    假设 schedules 表无 id=999
    当 调用 ScheduleService.get(999)
    那么 抛 ScheduleNotFound, 错误码 SCHEDULE_NOT_FOUND

  场景: 列出所有班次
    当 调用 ScheduleService.list_all()
    那么 返回 list[Schedule], 按 id 升序

功能: EmployeeService 增删改查
  作为服务层
  我需要人员 CRUD
  以便人员管理 UI 完成增删改查

  场景: 新增员工全条件通过
    假设 schedules id=1 存在
    且 face_datasets/100001.jpg 文件存在
    当 调用 EmployeeService.create(employee_id='100001', name='张三', department='研发部', position='工程师', phone='13800138000', email='zs@example.com', face_image_path='face_datasets/100001.jpg', schedule_id=1)
    那么 返回 Employee(employee_id='100001', ...)
    且 数据库 employees 表新增一行

  场景: 工号格式错
    当 调用 EmployeeService.create(employee_id='abc123', name='测试', ..., schedule_id=1)
    那么 抛 EmployeeIdInvalid, 错误码 EMPLOYEE_ID_INVALID
    且 数据库 employees 表无新增

  场景: 工号重复
    假设 employees 表存在 employee_id='100001'
    当 调用 EmployeeService.create(employee_id='100001', name='李四', ..., schedule_id=1)
    那么 抛 EmployeeIdExists, 错误码 EMPLOYEE_ID_EXISTS

  场景: 人脸照片不存在
    假设 face_datasets/999999.jpg 不存在
    当 调用 EmployeeService.create(employee_id='999999', face_image_path='face_datasets/999999.jpg', ..., schedule_id=1)
    那么 抛 FaceImageNotFound, 错误码 FACE_IMAGE_NOT_FOUND

  场景: 部分字段更新
    假设 employees 表存在 employee_id='100001'
    当 调用 EmployeeService.update('100001', name='张三改名')
    那么 返回 Employee(name='张三改名')
    且 数据库中 name 字段已更新, 其他字段未变
    且 updated_at 自动刷新

  场景: 更新不存在的员工
    当 调用 EmployeeService.update('999999', name='X')
    那么 抛 EmployeeNotFound, 错误码 EMPLOYEE_NOT_FOUND

  场景: 更新人脸照片时文件不存在
    假设 employees 表存在 employee_id='100001'
    当 调用 EmployeeService.update('100001', face_image_path='face_datasets/notexist.jpg')
    那么 抛 FaceImageNotFound, 错误码 FACE_IMAGE_NOT_FOUND

  场景: 删除无打卡记录的员工
    假设 employees 表存在 employee_id='100002' 且无 check_records
    当 调用 EmployeeService.delete('100002')
    那么 employees 表该行被删除

  场景: 删除有打卡记录的员工
    假设 employees 表存在 employee_id='100001' 且有至少 1 条 check_records
    当 调用 EmployeeService.delete('100001')
    那么 抛 EmployeeHasRecords, 错误码 EMPLOYEE_HAS_RECORDS
    且 employees 表该行仍在

  场景: 按工号查询
    假设 employees 表存在 employee_id='100001'
    当 调用 EmployeeService.get('100001')
    那么 返回 Employee(employee_id='100001')

  场景: 查询不存在的员工
    当 调用 EmployeeService.get('999999')
    那么 抛 EmployeeNotFound, 错误码 EMPLOYEE_NOT_FOUND

  场景: 列出所有员工
    当 调用 EmployeeService.list_all()
    那么 返回所有 Employee 列表

  场景: 按在职状态过滤列出
    当 调用 EmployeeService.list_all(is_active=True)
    那么 仅返回 is_active=True 的 Employee

  场景: 按关键词搜索
    假设 employees 表存在 employee_id='100001' name='张三'
    当 调用 EmployeeService.search('张')
    那么 返回包含 '张' 的 Employee 列表

  场景: 空关键词搜索返回空
    当 调用 EmployeeService.search('')
    那么 返回空列表

功能: CheckService
  作为服务层
  我需要打卡记录增查
  以便签到 UI 与记录查询 UI 完成业务

  场景: 写入 check_in 记录
    假设 employees 表存在 employee_id='100001' is_active=True
    当 调用 CheckService.create_record('100001', 'check_in')
    那么 返回 CheckRecord(employee_id='100001', check_type='check_in', check_timestamp=now, check_date=today)
    且 数据库 check_records 新增一行

  场景: 写入 check_in 但员工已离职
    假设 employees 表存在 employee_id='100002' is_active=False
    当 调用 CheckService.create_record('100002', 'check_in')
    那么 抛 EmployeeInactive, 错误码 EMPLOYEE_INACTIVE

  场景: 写入非法 check_type
    假设 employees 表存在 employee_id='100001'
    当 调用 CheckService.create_record('100001', 'foo')
    那么 抛 CheckTypeInvalid, 错误码 CHECK_TYPE_INVALID

  场景: 写入但员工不存在
    当 调用 CheckService.create_record('999999', 'check_in')
    那么 抛 EmployeeNotFound, 错误码 EMPLOYEE_NOT_FOUND

  场景: 按日期范围查询
    假设 check_records 已有 2026-08-20 至 2026-08-24 数据
    当 调用 CheckService.list_records(date_from=date(2026,8,22), date_to=date(2026,8,24))
    那么 仅返回 2026-08-22 至 2026-08-24 的 CheckRecord 列表

  场景: 日期范围反向抛错
    当 调用 CheckService.list_records(date_from=date(2026,8,24), date_to=date(2026,8,22))
    那么 抛 DateRangeInvalid, 错误码 DATE_RANGE_INVALID

  场景: 多条件组合查询
    假设存在 employee_id='100001' 与 '100002' 的打卡记录
    当 调用 CheckService.list_records(employee_id='100001', check_type='check_in')
    那么 仅返回 employee_id='100001' 且 check_type='check_in' 的 CheckRecord 列表

功能: AdminService
  作为服务层
  我需要管理员认证与默认账号
  以便登录 UI 校验与首次启动

  场景: 校验默认账号成功
    假设 admins 表存在 username='admin', password_hash=SHA-256('admin123')
    当 调用 AdminService.authenticate('admin', 'admin123')
    那么 返回 Admin(id=1, username='admin', ...)

  场景: 校验密码错
    假设 admins 表存在 username='admin'
    当 调用 AdminService.authenticate('admin', 'wrongpass')
    那么 抛 AuthFailed, 错误码 AUTH_FAILED

  场景: 校验用户不存在
    当 调用 AdminService.authenticate('ghost', 'any')
    那么 抛 AuthFailed, 错误码 AUTH_FAILED

  场景: 改密码全条件通过
    假设 admins 表存在 admin_id=1, password_hash=SHA-256('admin123')
    当 调用 AdminService.change_password(1, 'admin123', 'newpass123')
    那么 admins 表该行 password_hash 更新为 SHA-256('newpass123')
    且 AdminService.authenticate('admin', 'newpass123') 返回该 Admin

  场景: 改密码旧密码错
    当 调用 AdminService.change_password(1, 'wrong', 'newpass123')
    那么 抛 AuthFailed, 错误码 AUTH_FAILED

  场景: 改密码新密码过短
    当 调用 AdminService.change_password(1, 'admin123', '123')
    那么 抛 PasswordTooShort, 错误码 PASSWORD_TOO_SHORT

  场景: 首次启动插入默认账号
    假设 admins 表为空
    当 调用 AdminService.ensure_default('admin', 'admin123')
    那么 admins 表新增一行: username='admin', password_hash=SHA-256('admin123'), is_super=True

  场景: 二次调用 ensure_default 无操作
    假设 admins 表已存在默认账号
    当 调用 AdminService.ensure_default('admin', 'admin123')
    那么 admins 表无新增, 无修改
```

---

## 3. 服务层 API 契约

### 3.1 ScheduleService

```python
class ScheduleService:
    @staticmethod
    def get(schedule_id: int) -> Schedule:
        """按 id 查询。
        抛出: ScheduleNotFound"""

    @staticmethod
    def list_all() -> list[Schedule]:
        """按 id 升序。"""
```

### 3.2 EmployeeService

```python
class EmployeeService:
    EMPLOYEE_ID_PATTERN: str = r"^\d{6}$"
    FACE_IMAGE_PATH_PATTERN: str = r"^face_datasets/[^/]+\.(jpg|jpeg|png)$"

    @staticmethod
    def create(*, employee_id: str, name: str, department: Optional[str],
               position: Optional[str], phone: Optional[str], email: Optional[str],
               face_image_path: str, schedule_id: int,
               is_active: bool = True) -> Employee:
        """校验 + 插入。
        抛出: EmployeeIdInvalid / EmployeeIdExists /
              FaceImageNotFound / ScheduleNotFound"""

    @staticmethod
    def update(employee_id: str, *, name: Optional[str] = None,
               department: Optional[str] = None,
               position: Optional[str] = None,
               phone: Optional[str] = None, email: Optional[str] = None,
               face_image_path: Optional[str] = None,
               schedule_id: Optional[int] = None,
               is_active: Optional[bool] = None) -> Employee:
        """仅更新非 None 字段;updated_at 自动刷新。
        抛出: EmployeeNotFound / FaceImageNotFound / ScheduleNotFound"""

    @staticmethod
    def delete(employee_id: str) -> None:
        """硬删除。
        抛出: EmployeeNotFound / EmployeeHasRecords"""

    @staticmethod
    def get(employee_id: str) -> Employee:
        """按工号查询。
        抛出: EmployeeNotFound"""

    @staticmethod
    def list_all(is_active: Optional[bool] = None) -> list[Employee]:
        """列出所有; is_active 为 None 时不过滤。"""

    @staticmethod
    def search(keyword: str) -> list[Employee]:
        """按 employee_id 包含 keyword OR name 包含 keyword。
        keyword 长度 0 返回空列表。"""
```

### 3.3 CheckService

```python
class CheckService:
    VALID_TYPES: tuple[str, ...] = ("check_in", "check_out", "middle")

    @staticmethod
    def create_record(employee_id: str, check_type: str) -> CheckRecord:
        """根据当前时间生成 check_timestamp 与 check_date。
        抛出: EmployeeNotFound / EmployeeInactive / CheckTypeInvalid"""

    @staticmethod
    def list_records(*, date_from: Optional[date] = None,
                     date_to: Optional[date] = None,
                     employee_id: Optional[str] = None,
                     check_type: Optional[str] = None) -> list[CheckRecord]:
        """全部条件可选; None 表示不过滤。
        date_from > date_to 抛出: DateRangeInvalid
        check_type 不在 VALID_TYPES 抛出: CheckTypeInvalid"""
```

### 3.4 AdminService

```python
class AdminService:
    MIN_PASSWORD_LENGTH: int = 6

    @staticmethod
    def authenticate(username: str, password: str) -> Admin:
        """校验密码 (SHA-256 hex)。
        抛出: AuthFailed"""

    @staticmethod
    def change_password(admin_id: int, old_password: str,
                        new_password: str) -> None:
        """先校验旧密码, 再校验新密码长度, 再更新。
        抛出: AuthFailed / PasswordTooShort"""

    @staticmethod
    def ensure_default(default_username: str,
                       default_password: str) -> None:
        """admins 表为空时插入默认账号;否则无操作。
        抛出: InternalError (插入失败时)"""
```

---

## 4. 数据模型

(全部数据模型由 SPEC-001-A 定义,本子 spec 不再展开。引用 SPEC-001-A §4.2 即可。)

新增 CheckType 枚举(在本子 spec 中定义,仅作为校验使用):

```python
# attendance/services.py 内
VALID_CHECK_TYPES: tuple[str, ...] = ("check_in", "check_out", "middle")
```

---

## 5. 业务规则与状态流转

### 5.1 决策表

**规则 B-BR-001: EmployeeService.create (新增员工)**

| 条件: employee_id 格式 | 条件: employee_id 唯一 | 条件: face_image_path 文件存在 | 条件: schedule_id 存在 | 动作 |
|---|---|---|---|---|
| 失败 | - | - | - | 拒绝, 抛 EmployeeIdInvalid |
| 通过 | 失败 | - | - | 拒绝, 抛 EmployeeIdExists |
| 通过 | 通过 | 失败 | - | 拒绝, 抛 FaceImageNotFound |
| 通过 | 通过 | 通过 | 失败 | 拒绝, 抛 ScheduleNotFound |
| 通过 | 通过 | 通过 | 通过 | 接受, 插入 employees |

**规则 B-BR-002: EmployeeService.delete (删除员工)**

| 条件: 员工存在 | 条件: 员工有 check_records | 动作 |
|---|---|---|
| 失败 | - | 拒绝, 抛 EmployeeNotFound |
| 通过 | 有记录 | 拒绝, 抛 EmployeeHasRecords |
| 通过 | 无记录 | 接受, 硬删除 employees 行 |

**规则 B-BR-003: CheckService.create_record (打卡记录写入)**

| 条件: 员工存在 | 条件: 员工 is_active=True | 条件: check_type 合法 | 动作 |
|---|---|---|---|
| 失败 | - | - | 拒绝, 抛 EmployeeNotFound |
| 通过 | 失败 | - | 拒绝, 抛 EmployeeInactive |
| 通过 | 通过 | 失败 | 拒绝, 抛 CheckTypeInvalid |
| 通过 | 通过 | 通过 | 接受, 插入 check_records |

**规则 B-BR-004: CheckService.list_records (打卡记录查询)**

| 条件: date_from 与 date_to 都给 | 条件: date_from > date_to | 动作 |
|---|---|---|
| 是 | 是 | 拒绝, 抛 DateRangeInvalid |
| 任意 | 否 | 接受, 按条件过滤 |

### 5.2 校验器实现细节

| 校验器 | 触发条件 | 抛错 |
|---|---|---|
| `EmployeeService._validate_employee_id(v)` | `not re.fullmatch(EMPLOYEE_ID_PATTERN, v)` | `EmployeeIdInvalid` |
| `EmployeeService._validate_face_image_path(v)` | `not re.fullmatch(FACE_IMAGE_PATH_PATTERN, v)` 或 `not os.path.isfile(v)` | `FaceImageNotFound` |
| `CheckService._validate_check_type(v)` | `v not in VALID_TYPES` | `CheckTypeInvalid` |
| `AdminService._validate_new_password(v)` | `len(v) < MIN_PASSWORD_LENGTH` | `PasswordTooShort` |

---

## 6. 错误处理

### 6.1 错误码字典(本子 spec 范围)

| 错误码 | 触发条件 | 日志级别 |
|--------|----------|----------|
| `EMPLOYEE_ID_INVALID` | employee_id 不匹配 ^\d{6}$ | WARN |
| `EMPLOYEE_ID_EXISTS` | employee_id 已存在 | WARN |
| `EMPLOYEE_NOT_FOUND` | 查/改/删时员工不存在 | WARN |
| `EMPLOYEE_HAS_RECORDS` | 删员工时存在 check_records | WARN |
| `EMPLOYEE_INACTIVE` | 给 is_active=False 的员工打卡 | WARN |
| `FACE_IMAGE_NOT_FOUND` | face_image_path 文件不存在或格式错 | WARN |
| `SCHEDULE_NOT_FOUND` | schedule_id 不存在 | WARN |
| `CHECK_TYPE_INVALID` | check_type 不在合法集合 | WARN |
| `DATE_RANGE_INVALID` | date_from > date_to | WARN |
| `AUTH_FAILED` | 用户名不存在或密码错 | WARN |
| `PASSWORD_TOO_SHORT` | 新密码长度 < 6 | WARN |

(其他 4 个由 SPEC-001-A / SPEC-001-C 触发:INI_READ_FAILED / DB_CONNECT_FAILED / CAMERA_OPEN_FAILED / INTERNAL_ERROR)

### 6.2 异常类引用

本子 spec 全部使用 SPEC-001-A §6.2 已定义的 11 个业务异常类。不新增异常类。

### 6.3 日志规范

- 复用 SPEC-001-A §6.3 的 logger 规范。
- 关键 action: `employee.create` / `employee.update` / `employee.delete` / `checkin.check_in` / `checkin.check_out` / `checkin.middle` / `admin.login` / `admin.change_password`。
- 日志内容禁止明文密码、姓名、电话、邮箱、邮件内容。

---

## 7. 测试用例与覆盖矩阵

| 需求来源 | 需求 ID | 类型 | 测试用例 ID | 自动化状态 |
|----------|---------|------|-------------|------------|
| Gherkin: ScheduleService.get 命中 | REQ-B-01 | 单元 | TC-ATT-B01 | 已自动化 |
| Gherkin: ScheduleService.get 不存在 | REQ-B-02 | 单元 | TC-ATT-B02 | 已自动化 |
| Gherkin: ScheduleService.list_all | REQ-B-03 | 单元 | TC-ATT-B03 | 已自动化 |
| Gherkin: EmployeeService.create 全过 | REQ-B-04 | 单元 | TC-ATT-B04 | 已自动化 |
| Gherkin: 工号格式错 | REQ-B-05 | 单元 | TC-ATT-B05 | 已自动化 |
| Gherkin: 工号重复 | REQ-B-06 | 单元 | TC-ATT-B06 | 已自动化 |
| Gherkin: 人脸照片不存在 | REQ-B-07 | 单元 | TC-ATT-B07 | 已自动化 |
| Gherkin: EmployeeService.update 部分字段 | REQ-B-08 | 单元 | TC-ATT-B08 | 已自动化 |
| Gherkin: EmployeeService.update 不存在员工 | REQ-B-09 | 单元 | TC-ATT-B09 | 已自动化 |
| Gherkin: EmployeeService.delete 无记录 | REQ-B-10 | 单元 | TC-ATT-B10 | 已自动化 |
| Gherkin: EmployeeService.delete 有记录 | REQ-B-11 | 单元 | TC-ATT-B11 | 已自动化 |
| Gherkin: CheckService.create_record 正常 | REQ-B-12 | 单元 | TC-ATT-B12 | 已自动化 |
| Gherkin: CheckService.create_record 离职 | REQ-B-13 | 单元 | TC-ATT-B13 | 已自动化 |
| Gherkin: CheckService.create_record 非法 type | REQ-B-14 | 单元 | TC-ATT-B14 | 已自动化 |
| Gherkin: CheckService.list_records 日期范围 | REQ-B-15 | 单元 | TC-ATT-B15 | 已自动化 |
| Gherkin: CheckService.list_records 日期反向 | REQ-B-16 | 单元 | TC-ATT-B16 | 已自动化 |
| Gherkin: AdminService.authenticate 成功 | REQ-B-17 | 单元 | TC-ATT-B17 | 已自动化 |
| Gherkin: AdminService.authenticate 失败 | REQ-B-18 | 单元 | TC-ATT-B18 | 已自动化 |

---

## 8. 非功能性需求

| 类别 | 具体要求 | 验证方法 |
|------|----------|----------|
| 性能 | `CheckService.create_record` 单次 < 200ms (本地 MySQL) | TC-ATT-B12 中 `time.perf_counter()` 断言 |
| 性能 | `EmployeeService.list_all` < 100ms (1000 条记录) | 单独基准测试 |
| 安全性 | 日志不出现明文密码 | CI grep `logs/*.log` 不含 `admin123` 字符串 |
| 可观测性 | 关键操作含 action 字段 | 测试中触发后 read log, grep `action=employee.create` |

---

## 9. 假设、约束与变更日志

### 9.1 假设

- SPEC-001-A 已闭环, `attendance.models` / `attendance.utils` 可直接 import。
- MySQL 服务可达, 测试库 `attendance_test_db` 可创建与删除。
- 测试用 `face_datasets/100001.jpg` 文件可临时创建 (测试 fixture)。

### 9.2 约束

- 不可在 services.py 中 `import attendance.ui_*`。
- 所有异常 `raise` 必须使用 SPEC-001-A §6.2 已定义的 11 个业务异常类;不允许 `raise Exception(...)`。
- check_type 字符串字面量仅允许在 `services.py` (VALID_CHECK_TYPES) 与本 spec 文件中出现;其他模块必须通过 `CheckService.VALID_TYPES` 或参数传递,禁止硬编码。

### 9.3 变更日志

| 日期 | 版本 | 变更说明 | 关联 Commit |
|------|------|----------|-------------|
| 2026-08-24 | v1.0.0 | 拆分自 SPEC-001 v1.0.0;业务服务层子 spec | (待提交) |
