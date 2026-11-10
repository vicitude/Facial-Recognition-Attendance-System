# SPEC-001-A: 基础层

> **规范状态**: 已批准
> **版本**: v1.0.0
> **拆分自**: SPEC-001 v1.0.0(见 `_LEGACY.md`)
> **负责人**: PO: @user | TL: @user | QA: @user
> **代码包路径**: `attendance/`
> **配置文件**: `attendance_config.ini`
> **入口文件**: `attendance_ui.py`(由 SPEC-001-C 创建)
> **最后修改**: 2026-08-24

---

## 0. 文档头与元数据

- **文件路径**: `/specs/attendance/01-foundation/spec.md`
- **关联代码路径**:
  - `attendance/__init__.py`(空)
  - `attendance/config.py`
  - `attendance/db.py`
  - `attendance/models.py`
  - `attendance/utils.py`
  - `attendance_config.ini`(项目根)
  - `.gitignore`(追加)
- **CI 门禁规则**:
  - 本文件 §4 字段映射表任一字段被修改时,`attendance/models.py` 必须同步修改,否则 CI 阻断。
  - `attendance_config.ini` 必须被 `.gitignore` 排除;CI 运行 `git check-ignore -v attendance_config.ini` 验证。
  - `grep -REn "raise Exception" attendance/` 必须 0 命中。

---

## 1. 术语表

| 术语 | 英文名 | 类型 | 定义 | 代码映射 | 数据库映射 | 示例 |
|------|--------|------|------|----------|------------|------|
| 配置文件 | ConfigFile | 资源 | INI 格式,含 [database] / [admin] / [schedule_seed] 三节 | `ConfigService` | 不持久化 | `attendance_config.ini` |
| 数据库节 | DatabaseSection | 值对象 | INI 的 [database] 节 | `dict` | 不持久化 | `{"host":"127.0.0.1","port":3306,...}` |
| 管理员节 | AdminSection | 值对象 | INI 的 [admin] 节 | `dict` | 不持久化 | `{"default_username":"admin","default_password":"admin123"}` |
| 班次种子节 | ScheduleSeedSection | 值对象 | INI 的 [schedule_seed] 节 | `dict` | 不持久化 | `{"name":"常规班","work_start":"08:00:00",...}` |
| 异常基类 | AttendanceError | 类 | 所有业务异常继承自此 | `class AttendanceError(Exception)` | 不持久化 | `AttendanceError` |
| SHA-256 哈希 | PasswordHash | 值对象 | 64 字符小写十六进制 | `str` | `password_hash VARCHAR(64)` | `'240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9'` |
| 管理员 | Admin | 聚合根 | 系统登录账号 | `class Admin(Model)` | `admins` 表 | `Admin { id=1, username='admin' }` |
| 班次 | Schedule | 聚合根 | 上下班时间与迟到/早退阈值 | `class Schedule(Model)` | `schedules` 表 | `Schedule { id=1, name='常规班' }` |
| 员工 | Employee | 聚合根 | 被签到人员 | `class Employee(Model)` | `employees` 表 | `Employee { employee_id='100001' }` |
| 打卡记录 | CheckRecord | 聚合根 | 每次识别后写入的记录 | `class CheckRecord(Model)` | `check_records` 表 | `CheckRecord { id=1, employee_id='100001', check_type='check_in' }` |
| 打卡类型 | CheckType | 枚举 | `check_in` / `check_out` / `middle` | `str`(在 B 中定义枚举类) | `check_type VARCHAR(10)` | `'check_in'` |
| 数据库实例 | DatabaseInstance | 服务 | peewee MySQLDatabase 单例 | `peewee.MySQLDatabase` | 不适用 | `db = MySQLDatabase('attendance_db', ...)` |
| 初始化数据库 | InitDB | 服务 | 启动时建库建表预置班次 | `init_db(config)` | 不适用 | `init_db(config_dict)` |

---

## 2. 用户故事与验收场景(Gherkin)

```gherkin
功能: 配置文件加载
  作为系统
  我需要读取 attendance_config.ini
  以便获知数据库连接与默认账号

  场景: INI 存在且格式正确
    假设 项目根存在 attendance_config.ini,含 [database]/[admin]/[schedule_seed] 三节
    当 调用 ConfigService.load()
    那么 返回 dict, 形如:
      | 键              | 类型 | 值示例                |
      | database.host   | str  | '127.0.0.1'           |
      | database.port   | int  | 3306                  |
      | database.user   | str  | 'root'                |
      | database.password| str | ''                    |
      | database.database| str | 'attendance_db'       |
      | database.charset| str  | 'utf8mb4'             |
      | admin.default_username|str|'admin'             |
      | admin.default_password|str|'admin123'           |
      | schedule_seed.name|str   | '常规班'              |
      | schedule_seed.work_start|str|'08:00:00'        |
      | schedule_seed.work_end|str  |'17:00:00'         |
      | schedule_seed.late|int     | 15                |
      | schedule_seed.early|int    | 15                |

  场景: INI 缺失
    假设 项目根不存在 attendance_config.ini
    当 调用 ConfigService.load()
    那么 抛 INIReadFailed, 错误码 INI_READ_FAILED
    且 错误信息含 "无法读取 attendance_config.ini"

  场景: INI 自动创建
    假设 项目根不存在 attendance_config.ini
    当 调用 ConfigService.ensure_exists()
    那么 在项目根创建 attendance_config.ini, 含默认 [database]/[admin]/[schedule_seed] 三节
    且 后续 ConfigService.load() 返回默认值

功能: 工具类
  作为开发者
  我需要异常类层级与 sha256_hex
  以便在服务层抛出语义化异常与生成密码哈希

  场景: SHA-256 哈希
    当 调用 sha256_hex('admin123')
    那么 返回 '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9'

  场景: 异常类层级完整
    那么 从 attendance.utils 可 import:
      | AttendanceError | INIReadFailed | DBConnectFailed | AuthFailed | PasswordTooShort |
      | EmployeeIdInvalid | EmployeeIdExists | EmployeeNotFound | EmployeeHasRecords |
      | EmployeeInactive | FaceImageNotFound | ScheduleNotFound |
      | CheckTypeInvalid | DateRangeInvalid | InternalError |
    且 上述 14 个异常类均为 AttendanceError 的子类

功能: 数据库初始化
  作为系统
  我需要在启动时建库建表
  以便业务服务层可直接使用

  场景: 首次启动,正常建库
    假设 ConfigService.load() 成功, MySQL 可达
    当 调用 init_db(config)
    那么 创建数据库 attendance_db(若不存在)
    且 创建表 admins / schedules / employees / check_records(若不存在)
    且 预置 schedules 一条记录: id=1, name='常规班', work_start='08:00:00', work_end='17:00:00', late_threshold_min=15, early_leave_threshold_min=15
    且 调用 create_tables 第二次不报错(safe=True)

  场景: MySQL 不可达
    假设 config['database']['host'] = '127.0.0.2' (不可达)
    当 调用 init_db(config)
    那么 抛 DBConnectFailed, 错误码 DB_CONNECT_FAILED

  场景: 关闭数据库
    假设 已成功 init_db
    当 调用 close_db()
    那么 db.is_closed() == True
```

---

## 3. 服务层 API 契约

### 3.1 ConfigService

```python
class ConfigService:
    INI_PATH: str = "attendance_config.ini"

    @staticmethod
    def load() -> dict:
        """读取并解析 INI。
        返回: dict 形如
          {
            "database": {"host": str, "port": int, "user": str,
                         "password": str, "database": str, "charset": str},
            "admin": {"default_username": str, "default_password": str},
            "schedule_seed": {"name": str, "work_start": str,
                              "work_end": str, "late": int, "early": int}
          }
        抛出: INIReadFailed
        """

    @staticmethod
    def ensure_exists() -> None:
        """若 INI 不存在,创建并写入模板默认值(同 §9 假设)。"""
```

### 3.2 Database

```python
def init_db(config: dict) -> None:
    """连接 MySQL, 确保数据库存在, 创建表(若不存在), 预置 schedule。
    抛出: DBConnectFailed"""

def get_db() -> peewee.MySQLDatabase:
    """返回当前 peewee Database 实例。"""

def close_db() -> None:
    """关闭连接。"""
```

### 3.3 AuthUtils

```python
def sha256_hex(password: str) -> str:
    """返回 SHA-256 十六进制 64 字符。"""
```

### 3.4 Models (peewee)

```python
class Admin(Model):
    id = AutoField()
    username = CharField(50, unique=True)
    password_hash = CharField(64)
    is_super = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.now)

class Schedule(Model):
    id = AutoField()
    name = CharField(50, unique=True)
    work_start = TimeField()
    work_end = TimeField()
    late_threshold_min = IntegerField()
    early_leave_threshold_min = IntegerField()
    created_at = DateTimeField(default=datetime.now)

class Employee(Model):
    employee_id = CharField(6, primary_key=True)
    name = CharField(50)
    department = CharField(50, null=True)
    position = CharField(50, null=True)
    phone = CharField(20, null=True)
    email = CharField(100, null=True)
    face_image_path = CharField(255)
    schedule = ForeignKeyField(Schedule)
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

class CheckRecord(Model):
    id = AutoField()
    employee = ForeignKeyField(Employee)
    check_timestamp = DateTimeField(default=datetime.now)
    check_type = CharField(10)
    check_date = DateField()
    created_at = DateTimeField(default=datetime.now)
```

---

## 4. 数据模型与校验规则

### 4.1 JSON Schema: INI 结构(`attendance_config.ini`)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AttendanceConfig",
  "type": "object",
  "required": ["database", "admin", "schedule_seed"],
  "properties": {
    "database": {
      "type": "object",
      "required": ["host", "port", "user", "password", "database", "charset"],
      "properties": {
        "host": { "type": "string", "minLength": 1 },
        "port": { "type": "integer", "minimum": 1, "maximum": 65535 },
        "user": { "type": "string", "minLength": 1 },
        "password": { "type": "string" },
        "database": { "type": "string", "pattern": "^[a-zA-Z0-9_]+$" },
        "charset": { "enum": ["utf8", "utf8mb4"] }
      }
    },
    "admin": {
      "type": "object",
      "required": ["default_username", "default_password"],
      "properties": {
        "default_username": { "type": "string", "minLength": 3, "maxLength": 50 },
        "default_password": { "type": "string", "minLength": 6, "maxLength": 50 }
      }
    },
    "schedule_seed": {
      "type": "object",
      "required": ["name", "work_start", "work_end", "late", "early"],
      "properties": {
        "name": { "type": "string", "minLength": 1, "maxLength": 50 },
        "work_start": { "type": "string", "pattern": "^\\d{2}:\\d{2}:\\d{2}$" },
        "work_end": { "type": "string", "pattern": "^\\d{2}:\\d{2}:\\d{2}$" },
        "late": { "type": "integer", "minimum": 0, "maximum": 240 },
        "early": { "type": "integer", "minimum": 0, "maximum": 240 }
      }
    }
  }
}
```

### 4.2 字段映射表(peewee Model ↔ DB Column)

| 业务字段 | peewee Field | MySQL 列 | 必填 | 默认值 |
|----------|--------------|----------|------|--------|
| Admin.id | `AutoField()` | `id INT AUTO_INCREMENT PRIMARY KEY` | 是 | auto |
| Admin.username | `CharField(50, unique=True)` | `username VARCHAR(50) UNIQUE NOT NULL` | 是 | 无 |
| Admin.password_hash | `CharField(64)` | `password_hash VARCHAR(64) NOT NULL` | 是 | 无 |
| Admin.is_super | `BooleanField(default=True)` | `is_super BOOLEAN NOT NULL` | 是 | `True` |
| Admin.created_at | `DateTimeField(default=datetime.now)` | `created_at DATETIME NOT NULL` | 是 | now |
| Schedule.id | `AutoField()` | `id INT AUTO_INCREMENT PRIMARY KEY` | 是 | auto |
| Schedule.name | `CharField(50, unique=True)` | `name VARCHAR(50) UNIQUE NOT NULL` | 是 | 无 |
| Schedule.work_start | `TimeField()` | `work_start TIME NOT NULL` | 是 | 无 |
| Schedule.work_end | `TimeField()` | `work_end TIME NOT NULL` | 是 | 无 |
| Schedule.late_threshold_min | `IntegerField()` | `late_threshold_min INT NOT NULL` | 是 | 无 |
| Schedule.early_leave_threshold_min | `IntegerField()` | `early_leave_threshold_min INT NOT NULL` | 是 | 无 |
| Schedule.created_at | `DateTimeField(default=datetime.now)` | `created_at DATETIME NOT NULL` | 是 | now |
| Employee.employee_id | `CharField(6, primary_key=True)` | `employee_id CHAR(6) PRIMARY KEY` | 是 | 无 |
| Employee.name | `CharField(50)` | `name VARCHAR(50) NOT NULL` | 是 | 无 |
| Employee.department | `CharField(50, null=True)` | `department VARCHAR(50) NULL` | 否 | `None` |
| Employee.position | `CharField(50, null=True)` | `position VARCHAR(50) NULL` | 否 | `None` |
| Employee.phone | `CharField(20, null=True)` | `phone VARCHAR(20) NULL` | 否 | `None` |
| Employee.email | `CharField(100, null=True)` | `email VARCHAR(100) NULL` | 否 | `None` |
| Employee.face_image_path | `CharField(255)` | `face_image_path VARCHAR(255) NOT NULL` | 是 | 无 |
| Employee.schedule | `ForeignKeyField(Schedule)` | `schedule_id INT NOT NULL, FK schedules.id` | 是 | 无 |
| Employee.is_active | `BooleanField(default=True)` | `is_active BOOLEAN NOT NULL` | 是 | `True` |
| Employee.created_at | `DateTimeField(default=datetime.now)` | `created_at DATETIME NOT NULL` | 是 | now |
| Employee.updated_at | `DateTimeField(default=datetime.now)` | `updated_at DATETIME NOT NULL` | 是 | now |
| CheckRecord.id | `AutoField()` | `id INT AUTO_INCREMENT PRIMARY KEY` | 是 | auto |
| CheckRecord.employee | `ForeignKeyField(Employee)` | `employee_id CHAR(6) NOT NULL, FK employees.employee_id` | 是 | 无 |
| CheckRecord.check_timestamp | `DateTimeField(default=datetime.now)` | `check_timestamp DATETIME NOT NULL` | 是 | now |
| CheckRecord.check_type | `CharField(10)` | `check_type VARCHAR(10) NOT NULL` | 是 | 无 |
| CheckRecord.check_date | `DateField()` | `check_date DATE NOT NULL` | 是 | 无 |
| CheckRecord.created_at | `DateTimeField(default=datetime.now)` | `created_at DATETIME NOT NULL` | 是 | now |

**校验器**(本子 spec 范围):
- `ConfigService._validate_loaded(d)` : 校验返回 dict 符合 §4.1;若缺键抛 INIReadFailed。

---

## 5. 业务规则

### 5.1 决策表

**规则 A-BR-001: init_db 启动顺序**

| 条件: MySQL 可达 | 条件: 数据库已存在 | 条件: 表已存在 | 动作 |
|---|---|---|---|
| 否 | - | - | 抛 DBConnectFailed |
| 是 | 否 | - | CREATE DATABASE + CREATE TABLE × 4 + INSERT schedule |
| 是 | 是 | 否 | CREATE TABLE × 4 + INSERT schedule |
| 是 | 是 | 是 | 跳过建表;检查 schedule id=1 存在,否则补插 |

**规则 A-BR-002: ensure_exists 行为**

| 条件: INI 存在 | 动作 |
|---|---|
| 是 | 无操作 |
| 否 | 写入模板默认内容 |

### 5.2 工厂方法

| 工厂 | 签名 | 用途 |
|---|---|---|
| `make_config_template() -> dict` | 返回 §4.1 默认 dict | ConfigService.ensure_exists 内部使用 |
| `build_database(config) -> peewee.MySQLDatabase` | 接受 config['database'],返回 `MySQLDatabase(database=..., **config['database'])` | db.py 内部使用 |

---

## 6. 错误处理

### 6.1 错误码字典(本子 spec 范围)

| 错误码 | 触发条件 | 日志级别 |
|--------|----------|----------|
| `INI_READ_FAILED` | INI 缺失、解析失败、缺键、值类型错 | ERROR |
| `DB_CONNECT_FAILED` | MySQL 连接失败、库无法创建 | ERROR |
| `INTERNAL_ERROR` | 未预期异常 | ERROR |

### 6.2 异常类层级(在 `attendance/utils.py`)

```text
AttendanceError(Exception)
├── INIReadFailed
├── DBConnectFailed
└── InternalError
```

(其他 11 个异常类在 SPEC-001-B 中定义,本子 spec 仅占用此 3 个。)

### 6.3 日志规范

- 日志写入 `logs/attendance_{YYYYMMDD}.log`,启动时 `if os.path.isfile(log) and os.path.getsize(log) > 5 * 1024 * 1024: os.rename(log, log + ".1")`。
- 格式: `%(asctime)s [%(levelname)s] %(name)s: %(message)s`。
- 必须记录 `action=init` / `action=ini.read` / `action=db.init` / `action=db.close`。
- 禁止记录明文密码、INI 内容。

---

## 7. 测试用例与覆盖矩阵

| 需求来源 | 需求 ID | 类型 | 测试用例 ID | 自动化状态 |
|----------|---------|------|-------------|------------|
| Gherkin: INI 存在且格式正确 | REQ-A-01 | 单元 | TC-ATT-A01 | 已自动化 |
| Gherkin: INI 缺失抛 INIReadFailed | REQ-A-02 | 单元 | TC-ATT-A02 | 已自动化 |
| Gherkin: INI 自动创建 | REQ-A-03 | 单元 | TC-ATT-A03 | 已自动化 |
| Gherkin: SHA-256 哈希 | REQ-A-04 | 单元 | TC-ATT-A04 | 已自动化 |
| Gherkin: 异常类层级完整 | REQ-A-05 | 单元 | TC-ATT-A05 | 已自动化 |
| Gherkin: 首次启动正常建库 | REQ-A-06 | 集成 | TC-ATT-A06 | 已自动化 |
| Gherkin: MySQL 不可达抛 DBConnectFailed | REQ-A-07 | 集成 | TC-ATT-A07 | 已自动化 |
| Gherkin: 关闭数据库 | REQ-A-08 | 单元 | TC-ATT-A08 | 已自动化 |
| 数据模型: Admin 字段映射 | REQ-A-09 | 单元 | TC-ATT-A09 | 已自动化 |
| 数据模型: Employee 字段映射 | REQ-A-10 | 单元 | TC-ATT-A10 | 已自动化 |
| 数据模型: CheckRecord 字段映射 | REQ-A-11 | 单元 | TC-ATT-A11 | 已自动化 |
| 数据模型: Schedule 字段映射 | REQ-A-12 | 单元 | TC-ATT-A12 | 已自动化 |

---

## 8. 非功能性需求

| 类别 | 具体要求 | 验证方法 |
|------|----------|----------|
| 性能 | `init_db` 二次调用(表已存在) < 500ms | TC-ATT-A06 中 `time.perf_counter()` 断言 |
| 安全性 | INI 不进仓库 | CI `git check-ignore -v attendance_config.ini` 退出码 0 |
| 可观测性 | 启动/关闭/重连均写日志 | 集成测试读 `logs/*.log` grep `action=init` |
| 可维护性 | utils.py 异常类 import 不出现外部依赖 | CI `grep -E "^(import\|from) (?!datetime\|os\|hashlib)" attendance/utils.py` |

---

## 9. 假设、约束与变更日志

### 9.1 假设

- Python 3.10+ 已安装。
- MySQL 8.0+ 服务可在本机 `127.0.0.1:3306` 访问, root 用户存在。
- 项目当前的人脸识别代码不修改, 本子 spec 不 import `recognition.py` / `get_name.py`。
- PyQt5 5.15+ 已安装(给后续子 spec 用)。
- 用户首次运行前不修改 `attendance_config.ini`, 模板默认的 `user=root` 与空密码可用。

### 9.2 约束

- 不可使用 ORM 之外的裸 SQL 字符串拼接。
- `models.py` / `db.py` / `config.py` 不允许 import `attendance.services` / `attendance.ui_*`(分层)。
- 错误码、字段名、TC ID 严格按本 spec;实施阶段不二次发挥。

### 9.3 变更日志

| 日期 | 版本 | 变更说明 | 关联 Commit |
|------|------|----------|-------------|
| 2026-08-24 | v1.0.0 | 拆分自 SPEC-001 v1.0.0;基础层子 spec | (待提交) |
