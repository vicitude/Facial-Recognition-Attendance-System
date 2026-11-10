# 010 · 表名复数规范化 + 遗留表清理（2026-08-24）

- **状态**: 活跃
- **关键词**: table-name, plural, legacy-table, drop-database, rebuild, peewee-meta
- **相关模块**: `attendance/models.py`、`attendance/db.py`、`temp_rebuild_db.py`

## 关联文档

- `specs/attendance/01-foundation/spec.md` §1 术语表（`admins` / `schedules` / `employees` / `check_records` 复数形式约定）
- `AGENTS.md` §6 L-016（peewee 默认表名为单数 + 显式声明）
- `USER_GUIDE.md` §3 数据模型速览（用户视角表名描述）
- `decisions/002-v1-foundation-shipped.md`（A 阶段闭环事实）

## 背景与问题

用户实测发现本地 MySQL `attendance_db` 库存在 6 张表：

| 表名 | 来源 | 状态 |
|---|---|---|
| `admin` | peewee 默认（A 阶段 v0） | 已废弃 |
| `schedule` | peewee 默认（A 阶段 v0） | 已废弃 |
| `employee` | peewee 默认（A 阶段 v0） | 已废弃 |
| `checkrecord` | peewee 默认（A 阶段 v0） | 已废弃 |
| `person` | 历史项目遗留 | 业务废弃，可能含错放数据 |
| `attendance_record` | 历史项目遗留 | 业务废弃 |

`attendance/db.py:80` `create_tables([Admin, Schedule, Employee, CheckRecord], safe=True)` 启动时自动建表但**未显式声明 `table_name`**，peewee 默认用类名小写作为表名（**单数**），与 `specs/attendance/01-foundation/spec.md` §1 术语表中规定的复数形式（`admins` / `schedules` / `employees` / `check_records`）不一致，导致：
1. 文档与代码表名长期对不上，沟通成本高。
2. 早期项目遗留表（`person`、`attendance_record`）一直存在，新表名（`admin` / `employee` / `schedule` / `checkrecord`）与之并存，数据库结构混乱。
3. 业务数据可能错放（`person` 表混入了本应属于 `employee` 的数据）。

## 变化程度

- **修改 1 个文件**：
  - `attendance/models.py`：4 个 Model 各加 `class Meta: table_name = "<plural>"` 显式声明复数表名（见下方代码片段）。
- **新建 1 个临时脚本**：
  - `temp_rebuild_db.py`：用 pymysql DROP 整个 `attendance_db` 库，再调 `init_db` 重建（详见 §执行步骤）。
- **新建 1 个决策文档**：本文件。
- **更新 2 个文档**：
  - `decisions/_INDEX.md`：追加 010 行。
  - `AGENTS.md`：§6 新增 L-016 教训，§10 变更日志追加一行。
- **未触碰**：`ui.py` / `recognition.py` / `get_name.py` / `mydata.yaml` / 训练权重 / 既有业务代码 / Spec 正文（Spec 早已是复数）。

## 关键代码片段

`attendance/models.py` 修改后 4 个 Model 末尾各追加：

```python
class Admin(BaseModel):
    ...
    class Meta:
        table_name = "admins"

class Schedule(BaseModel):
    ...
    class Meta:
        table_name = "schedules"

class Employee(BaseModel):
    ...
    class Meta:
        table_name = "employees"

class CheckRecord(BaseModel):
    ...
    class Meta:
        table_name = "check_records"
```

## 执行步骤（用户侧）

1. **执行 temp_rebuild_db.py**：脚本读取 `attendance_config.ini` 拿到 MySQL 凭证，用 pymysql 直连执行 `DROP DATABASE IF EXISTS attendance_db;`，然后调 `attendance.db.init_db(config)` 重建（自动建 4 张复数表 + 预置 schedule + 创建默认 admin 账号）。
2. **验证**：脚本最后打印新表清单（应只含 4 张：`admins` / `schedules` / `employees` / `check_records`）。
3. **清理**：脚本运行后立即删除（`temp_*` 前缀临时文件规范，见 AGENTS.md §5）。

## 测试影响

- 既有 60 个测试**不需要修改**：测试通过 peewee Model 访问表，不直接 SQL 引用表名，Model 内 `table_name` 改了之后测试自动用新表。
- 既有测试 conftest 中 `_per_test_reset` 等 fixture 基于 `Admin.delete().execute()` 清行，**不依赖具体表名**（已通过决策 002 沉淀），无需调整。
- 既有数据（`admin/admin123` 默认账号 + 已添加员工 + 打卡记录）会随 DROP 一起清空，用户需重新添加员工（业务可接受，旧库数据本就怀疑错放）。

## 后续

- 若用户后续需要保留旧 `person` 表中可能含的正确员工数据，需在 DROP 前单独导出（SQL dump / CSV），但本次按用户拍板「直接 DROP 不要备份」执行，不导出。
- 下一轮可考虑在 `init_db` 中加迁移检查：检测到旧单数表（`admin` / `schedule` / `employee` / `checkrecord`）时主动提示用户迁移，避免历史包袱再次累积（暂不实施，仅记录）。
