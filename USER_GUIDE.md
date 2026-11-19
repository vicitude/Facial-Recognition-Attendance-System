# 签到/签退人员管理系统 — 使用说明书

> 本文档面向**最终用户**(本项目当前是单人使用, 用户 = 开发者本人)。
> 阅读本文档约 10 分钟, 可避免 90% 的人脸识别相关 Bug。

---

## 目录

- [1. 系统是什么](#1-系统是什么)
- [2. 启动前准备](#2-启动前准备)
- [3. 启动应用](#3-启动应用)
- [4. 数据模型速览](#4-数据模型速览)
- [5. 命名规范 (重要! 上一个 Bug 就是这个没搞清)](#5-命名规范-重要-上一个-bug-就是这个没搞清)
- [6. 完整操作流程](#6-完整操作流程)
- [7. 常见问题 FAQ](#7-常见问题-faq)
- [8. 上一个 Bug 真相复盘](#8-上一个-bug-真相复盘)
- [9. 文件组织约定](#9-文件组织约定)
- [10. 出错时怎么办](#10-出错时怎么办)

---

## 1. 系统是什么

基于 YOLOv8 人脸检测 + FaceNet 特征比对的本地桌面应用, 支持:

- **人员管理**: 增 / 改 / 删 / 查员工档案
- **实时签到/签退**: 摄像头识别 → 弹确认 → 写入打卡记录
- **记录查询**: 按日期范围 / 员工工号查打卡流水
- **管理员账户**: 多管理员 + 改密

**两个 UI 入口并存** (历史原因):

| 入口 | 用途 | 是否维护 |
|---|---|---|
| `ui.py` | 原项目遗留, 纯识别 demo (不打卡入库) | 不动, 仅供参考 |
| `attendance_ui.py` | **新系统, 完整业务功能 (签到/签退/人员/记录/管理)** | 日常使用 |

**日常使用走 `attendance_ui.py`**。

---

## 2. 启动前准备

### 2.1 Python 依赖

```powershell
pip install peewee pymysql PyQt5
pip install opencv-python numpy Pillow requests
pip install pytest pytest-qt    # 可选, 仅跑测试时需要
```

> 注意: 人脸识别核心 (YOLOv8 + FaceNet) 的依赖在 `recognition.py` / `get_name.py` 中按需 import, 启动 `attendance_ui.py` 时**不会**强制加载, 仅在"实时签到"实际跑识别时才需要。如果只做人员管理/查记录, 不连摄像头即可不装 torch/tensorflow。

### 2.2 MySQL 数据库

**首次接入**必须确认本机 MySQL 已启动, 修改 `attendance_config.ini` 填入实际密码:

```ini
[database]
host = 127.0.0.1
port = 3306
user = root
password = 你的实际密码    ← 改这里
database = attendance_db
charset = utf8mb4
```

> `attendance_db` 库**不需要手动建**, 程序首次启动时自动 `CREATE DATABASE IF NOT EXISTS` + 建表 + seed 默认班次。

### 2.3 现场设置首个管理员

交付时使用客户自己的数据库，不要把开发数据库一起交付。新库没有默认管理员，也不需要在配置文件里填管理员账号密码。把签到电脑交给员工前，请客户负责人在签到页点右上角齿轮，自己输入用户名、密码（至少 12 个字符）并确认。点击「创建账号」后会显示登录页，需要用刚设置的账号和密码登录一次。

如果数据库已有管理员，齿轮会直接打开登录页，不会重置已有账号。旧配置中的 `[admin]` 不再使用，可从本机配置中移除；改密仍通过后台「修改密码」。

---

## 3. 启动应用

```powershell
cd d:\yol\yolov8_facenet
python attendance_ui.py
```

启动流程:
1. 读 INI 配置
2. 连 MySQL, 建库建表
3. 直接显示「实时签到」。员工无需登录，手动点击「打开相机」→「开始识别」，识别后确认签到或签退。
4. 管理员点击签到页右上角的齿轮。已设置账号则直接登录；新库按上文现场设置，创建后再登录。后台包含人员管理、打卡记录、管理员管理和班次管理。
5. 点击「退出管理」或关闭后台窗口，返回实时签到。下次进入后台需要重新登录；切换后不会自动打开相机。

---

## 4. 数据模型速览

| 表 | 关键字段 | 业务含义 |
|---|---|---|
| `admins` | `username`, `password_hash` | 管理员账号 |
| `schedules` | `name`, `work_start`, `work_end` | 班次 (上下班时间) |
| `employees` | `employee_id`, `name`, `face_image_path` | **员工档案** (核心) |
| `check_records` | `employee_id`, `check_timestamp`, `check_type` | 打卡记录 |

**employees 表特别重要** (本系统的核心实体), 关键字段:

| 字段 | 类型 | 含义 | 必填 |
|---|---|---|---|
| `employee_id` | 6 位数字字符串 | **业务标识 (工号)**, UI 表格显示, 主键 | ✓ |
| `name` | ≤ 50 字符 | 中文姓名 | ✓ |
| `department` | ≤ 50 字符 | 部门 | ✗ |
| `position` | ≤ 50 字符 | 职位 | ✗ |
| `phone` | ≤ 20 字符 | 电话 | ✗ |
| `email` | ≤ 100 字符 | 邮箱 | ✗ |
| `face_image_path` | `face_datasets/xxx.jpg` 格式 | **人脸照片路径** | ✓ |
| `schedule_id` | 外键 | 关联班次 | ✓ |
| `is_active` | bool | 在职状态 (离职后置 false) | 默认 true |

---

## 5. 命名规范 (重要! 上一个 Bug 就是这个没搞清)

### 5.1 核心区分: 工号 vs 人脸照片文件名

**这两个是完全独立的标识体系**, 很多人会搞混:

| 维度 | 工号 (employee_id) | 人脸照片文件名 (basename) |
|---|---|---|
| **格式** | 6 位数字, 如 `200007` | 任意 ASCII/中文, 如 `HuangJiaWei` |
| **唯一性范围** | 全局唯一 (主键) | 在 `face_datasets/` 目录下唯一 |
| **谁定** | 业务方 (HR/公司工号体系) | 用户自由命名 (但要稳定) |
| **业务作用** | 业务标识, 用于查记录/查员工 | 识别标识, 用于人脸比对反查员工 |
| **数据库字段** | `employees.employee_id` (主键) | `employees.face_image_path` (路径) |

**系统怎么把"识别结果"关联到"员工"?**

```
摄像头拍到人脸
   ↓
YOLOv8 检测人脸框
   ↓
FaceNet 提取 128 维特征
   ↓
与 face_datasets/ 下所有人脸图片逐一比距离
   ↓
距离最小者 = 命中, 返 basename (如 "HuangJiaWei")
   ↓
查 DB: face_image_path 以 "face_datasets/HuangJiaWei." 开头的员工 = 黄家伟
   ↓
弹"签到确认", 写入 CheckRecord
```

**关键点**: 系统**不**用工号查员工, **也不**用人名查员工, 是用**人脸照片文件名**查员工。

### 5.2 人脸照片命名规范 (硬约束)

文件必须放在项目根的 `face_datasets/` 目录下, 命名规则:

| 要求 | 示例 ✓ | 示例 ✗ |
|---|---|---|
| **必须放在 `face_datasets/`** | `face_datasets/HuangJiaWei.jpg` | `d:/photos/zhangsan.jpg` ❌ |
| **扩展名** `.jpg` / `.jpeg` / `.png` 三选一 | `HuangJiaWei.jpg` | `HuangJiaWei.bmp` ❌ |
| **basename 在目录下唯一** | `face_datasets/` 下没有重名 | 两个 `HuangJiaWei.jpg` ❌ |
| **推荐用拼音/英文** (兼容性好) | `HuangJiaWei.jpg` | `黄家伟.jpg` (中文 basename 也行, 但识别时 path 拼接需注意) |
| **无空格** (避免命令行/HTTP 转义) | `ZhangSan.jpg` | `Zhang San.jpg` ❌ |
| **无特殊字符** (`.` `-` `_` 外避免) | `zhang_san.jpg` | `zhang/san.jpg` ❌ |
| **不要和工号同名** (避免认知混淆) | `HuangJiaWei.jpg` + 工号 `200007` | `200007.jpg` + 工号 `200007` ⚠️ (可以但易混) |

**目录样例**:

```
d:\yol\yolov8_facenet\
├── face_datasets/                  ← 所有人脸照片放这里
│   ├── HuangJiaWei.jpg             ← 文件名 = 识别键
│   ├── ZhangSan.png
│   ├── LiSi.jpeg
│   └── WangWu.jpg
├── attendance_db.sqlite            (SQLite 模式, 本系统用 MySQL 无此文件)
├── runs/
│   └── detect/train/weights/best.pt    (YOLOv8 权重, 识别时需要)
└── ...
```

### 5.3 工号 (employee_id) 命名规范

| 要求 | 示例 ✓ | 示例 ✗ |
|---|---|---|
| **必须 6 位数字** | `200007` | `007` (5位) / `ABC123` (字母) ❌ |
| **全局唯一** | `200001` ~ `999999` | 两个 `200001` ❌ |
| **不可修改** (主键) | 提交后只能删后重建 | 改 employee_id 需用 DB 直接改 |

### 5.4 姓名/部门/职位 命名规范

- **姓名**: 中文 1-50 字符, 推荐真实姓名 (如"黄家伟"), 不用昵称/花名
- **部门**: ≤ 50 字符, 推荐统一名 (如"研发部"), 避免"研发部-北京"等长串
- **职位**: ≤ 50 字符, 如"工程师"/"产品经理"

---

## 6. 完整操作流程

### 6.1 首次使用: 系统初始化

```
1. 启动 MySQL, 修改 attendance_config.ini 的 password
2. python attendance_ui.py
3. 点击签到页右上角的齿轮；如果看到「设置首个管理员」，由客户负责人创建账号
4. 在登录页输入管理员密码，再进入管理后台
```

### 6.2 准备人脸照片 (离线操作)

把每个人的清晰正面照放到 `face_datasets/` 目录, 文件名按 5.2 规范。

**照片要求** (FaceNet 模型特性):
- 单人正面照, 五官清晰
- 尺寸 ≥ 100x100 像素
- 光线均匀, 不要逆光
- 尽量不戴口罩/墨镜

**注意**: 文件名一旦确定并录入员工档案后, **不要随意改**! 改文件名后, 旧的人脸照片将无法被识别 (新文件名查不到 employee)。

### 6.3 新增员工 (走"人员管理"Tab)

```
1. 登录后, 切到"人员管理" Tab
2. 点 "新增" 按钮
3. 填表:
   - 工号: 6 位数字, 必填 (如 200007)
   - 姓名: 中文名, 必填
   - 部门/职位/电话/邮箱: 选填
   - 人脸照片路径: 点 "浏览..." 选 face_datasets/ 下的照片
     (选完后会自动归一化为相对路径, 填入 "face_datasets/xxx.jpg" 格式)
   - 班次: 下拉选 (默认"常规班")
   - 在职: 默认勾选
4. 点 "保存"
5. 弹"保存成功" → 表格新增一行
```

**关键校验** (B 层 `EmployeeService.create` 强制, 不会绕过):
- 工号必须 6 位数字
- 工号不能重复
- 人脸照片路径必须匹配 `^face_datasets/[^/]+\.(jpg|jpeg|png)$` 正则
- 人脸照片文件必须真实存在

### 6.4 实时签到

1. 启动应用进入「实时签到」，无需登录。
2. 点击「打开相机」，再点击「开始识别」。
3. 识别成功后核对工号和姓名，选择「签到」或「签退」；也可取消。
4. 不再使用时点击「停止识别」或「关闭相机」。

### 6.5 查看记录 (走"打卡记录"Tab)

```
1. 切到"打卡记录" Tab
2. 选日期范围 (默认今天)
3. 点 "刷新" → 表格显示范围内所有打卡记录
4. 双击行可看详情
5. 可导出 (后续功能, 当前未实现)
```

### 6.6 改密 / 多管理员 (走"管理员账户" Tab)

```
- 修改自己的密码: 顶部菜单 → 修改密码 → 输旧+新+确认
- 新增管理员: 管理员账户 Tab → 新增 (需 super admin 权限)
- 删除管理员: 管理员账户 Tab → 选中 → 删除 (不能删自己, 不能删最后一个 super)
```

---

## 7. 常见问题 FAQ

### Q1: 启动报"数据库连接失败"
A: 检查 `attendance_config.ini` 的 user/password 是否正确, MySQL 是否启动 (服务列表里 MySQL 服务是否 running)。

### Q2: 启动报"无法读取配置"
A: 确认 `attendance_config.ini` 在项目根目录, 文件名别打错。

### Q3: 实时签到弹"未识别, 不在员工库中"
A: 三步排查 (按顺序):
1. **检查人脸照片**: 该员工的人脸照片是否在 `face_datasets/` 下? 文件名拼写是否与"人员管理"中 `face_image_path` 完全一致? (含扩展名前的 basename)
2. **检查员工是否在职**: 切到"人员管理" → 看该员工"在职"列是否勾选。离职员工 (`is_active=false`) 不参与识别。
3. **检查照片质量**: 摄像头拍到的角度/光线是否与 `face_datasets/` 中差异太大? 重新拍一张清晰的放进去试试。

### Q4: 实时签到弹"识别结果 X 不在员工库中", X 是数字
A: **这是上一个版本的 Bug, 已在 v2 修复** (commit 见 `decisions/009`)。如果你用的是 v1, 请升级到 v2: 拉取最新代码重启 `attendance_ui.py` 即可。

### Q5: 同一张照片, 在 `face_datasets/` 下能用, 复制到别处再用就不行
A: 系统只认 `face_datasets/` 目录下的文件, 这是 B 层硬约束。在"人员管理"→"新增"→"人脸照片路径"必须填 `face_datasets/xxx.jpg` 格式, 不能填 `d:/photos/xxx.jpg`。

### Q6: 新增员工保存时报"人脸照片路径格式错误"
A: 不要手输入路径, 用 "浏览..." 按钮选文件 (UI 会自动归一化)。如必须手输, 必须是 `face_datasets/xxx.{jpg,png,jpeg}` 格式, 不能是绝对路径。

### Q7: 摄像头能用, 但视频文件/图片不能
A: 检查 `runs/detect/train/weights/best.pt` 是否存在, 这是 YOLOv8 训练权重, 没有它无法检测人脸框。

### Q8: 怎么备份数据
A: 整个 `attendance_db` MySQL 库就是全部业务数据, 用 `mysqldump` 备份:
```powershell
mysqldump -u root -p attendance_db > backup_20260824.sql
```
人脸照片备份直接复制 `face_datasets/` 目录即可。

### Q9: 怎么重置系统 (清空所有数据重来)
A: 在 MySQL 中 `DROP DATABASE attendance_db;`, 重启 `attendance_ui.py` 会自动重建。

### Q10: 同一员工可以有多张人脸照片吗
A: **当前 v1 不支持**。每个员工对应 `face_datasets/` 下唯一一张照片, 多个员工不要用同名文件。后续 v2 可能支持多张特征融合, 见 `BACKLOG.md`。

---

## 8. 上一个 Bug 真相复盘

### 8.1 Bug 现象

用户实测: 在"人员管理"加了员工"黄家伟"(工号 `200007`), 走 `attendance_ui.py` 实时签到, 摄像头识别成功后弹"未识别, 不在员工库中"。但同一个员工走 `ui.py` 旧版能正常识别。

### 8.2 用户操作回顾

- 人脸照片文件名: `face_datasets/HuangJiaWei.jpg` (拼音)
- 员工工号: `200007` (6 位数字)
- 部门: 研发部

**用户的命名是符合规范的, 不是用户的错。**

### 8.3 真正根因 (代码设计假设错误)

旧版 `attendance/ui_checkin.py:282` 代码:
```python
emp = EmployeeService.get(name)   # ← 错!
```

代码假设 `name` (即 `get_name.rec` 返回值) = `employee_id`, 但 `get_name.rec` 实际返回的是 `face_datasets/xxx.{jpg,png}` 文件的 **basename (无扩展名)**, 也就是 `"HuangJiaWei"`, **不是** `"200007"`。

**结果**: 系统拿 `"HuangJiaWei"` 去查 `employees.employee_id` 字段, 当然找不到, 弹"未识别"。

**为什么 `ui.py` 旧版能正常识别**: 旧版不查 DB, 拿到识别结果直接显示, 不做"识别 → 员工"关联, 所以绕过了这个 Bug。

### 8.4 修复方案 (v2)

详见 `decisions/009-v1-bugfix-checkin-face-name-lookup.md` 和 `AGENTS.md` L-014。

**核心改动**:
- B 层 `EmployeeService` 新增 `get_by_face_image_name(name)`, 按 `face_image_path.startswith(f"face_datasets/{name}.")` 反查员工
- UI 层 `ui_checkin.py` 改用新方法, 关联关系从 `employee_id` → `face_image_path`

**修复后**:
- 用户在 `face_datasets/` 下放 `HuangJiaWei.jpg`
- 在"人员管理"新增员工, `face_image_path` 自动存为 `face_datasets/HuangJiaWei.jpg`
- 实时签到 → 识别到 `HuangJiaWei` → 按 basename 查 → 找到工号 `200007` 的员工 → 弹确认 → 打卡

### 8.5 用户的启示

**虽然不是用户的错, 但用户的命名习惯是合理的**:

| 维度 | 你的命名 | 系统期望 | 是否兼容 |
|---|---|---|---|
| 人脸照片文件名 | `HuangJiaWei.jpg` (拼音) | basename 唯一即可 | ✓ |
| 工号 | `200007` (6位数字) | 6位数字 | ✓ |

**只要遵循本文档 §5.2 和 §5.3 的命名规范, 这个 Bug 不会发生**。新员工按规范命名, 关联就能正常工作。

---

## 9. 文件组织约定

```
d:\yol\yolov8_facenet\
├── attendance_ui.py              # 主入口 (启动用)
├── ui.py                         # 旧版入口 (纯识别 demo, 不用)
├── recognition.py                # YOLOv8 检测 (不修改)
├── get_name.py                   # FaceNet 比对 (不修改)
├── mydata.yaml                   # YOLOv8 类别配置 (不修改)
│
├── face_datasets/                # ★ 人脸照片根目录 (硬约束)
│   ├── HuangJiaWei.jpg
│   ├── ZhangSan.png
│   └── ... (一人一图, basename 全局唯一)
│
├── attendance/                   # 业务模块 (新系统)
│   ├── config.py                 # INI 配置加载
│   ├── db.py                     # DB 初始化/连接管理
│   ├── models.py                 # 4 张表 ORM
│   ├── services.py               # 业务服务层
│   ├── utils.py                  # 异常类 + 工具函数
│   ├── ui_login.py               # 登录对话框
│   ├── ui_main.py                # 主窗口
│   ├── ui_checkin.py             # 实时签到 Tab
│   ├── ui_employees.py           # 人员管理 Tab
│   ├── ui_records.py             # 打卡记录 Tab
│   ├── ui_change_password.py     # 改密对话框
│   ├── ui_admins.py              # 管理员管理 Tab
│   └── ui_utils.py               # UI 工具函数
│
├── tests/                        # 测试
│   ├── conftest.py               # 公共 fixture (G-06: 不修改)
│   ├── test_services.py          # B 层单元测试 (18+ 个 TC)
│   ├── test_ui_*.py              # C 层 UI 测试
│   ├── test_integration.py       # 集成测试
│   └── test_e2e.py               # 端到端测试
│
├── decisions/                    # 决策记录 (一决策一文件)
│   ├── _INDEX.md                 # 决策索引
│   ├── 002-v1-foundation-shipped.md
│   ├── 003-v1-services-shipped.md
│   ├── 004-v1-ui-shipped.md
│   ├── 005-v1-test-shipped.md
│   ├── 006-v1-bugfix-checkin-warning-loop.md
│   ├── 007-v1-admin-features-shipped.md
│   ├── 008-v2-bugfix-employee-face-path-defensive-save.md
│   └── 009-v1-bugfix-checkin-face-name-lookup.md
│
├── specs/                        # Spec 三件套
│   ├── 01-foundation/
│   ├── 02-services/
│   ├── 03-ui/
│   ├── 04-test/
│   └── 05-admin-features/
│
├── AGENTS.md                     # P0 事实源 (Agent 协作规范)
├── BACKLOG.md                    # 未完成排期
├── USER_GUIDE.md                 # ★ 本文档
├── attendance_config.ini         # 个人配置 (含密码, .gitignore)
├── mydata.yaml
├── requirements.txt
└── README.md                     # 项目简介 (英文)
```

---

## 10. 出错时怎么办

### 10.1 报错信息有"错误码"格式 (如 `EMPLOYEE_ID_INVALID`)

这是 B 层抛出的标准错误码, 含义:

| 错误码 | 含义 | 用户操作 |
|---|---|---|
| `EMPLOYEE_ID_INVALID` | 工号格式错 (非 6 位数字) | 改成 6 位数字 |
| `EMPLOYEE_ID_EXISTS` | 工号已存在 | 换工号 |
| `EMPLOYEE_NOT_FOUND` | 员工不存在 | 确认录入后重试 |
| `EMPLOYEE_HAS_RECORDS` | 员工有打卡记录, 不能删 | 先清记录或改"在职"为 false |
| `EMPLOYEE_INACTIVE` | 员工已离职 | 在"人员管理"勾上"在职" |
| `FACE_IMAGE_NOT_FOUND` | 人脸照片路径格式错或文件不存在 | 用"浏览..."重选, 不要手输入绝对路径 |
| `SCHEDULE_NOT_FOUND` | 班次不存在 | 检查 schedules 表 |
| `DATE_RANGE_INVALID` | 日期范围错 (开始 > 结束) | 调整日期 |
| `CHECK_TYPE_INVALID` | 打卡类型错 (不是 check_in/check_out) | 内部错误, 反馈 |
| `AUTH_FAILED` | 登录失败 (账号或密码错) | 重输 |
| `PASSWORD_TOO_SHORT` | 密码太短 (需 ≥ 6 位) | 输更长的密码 |
| `USERNAME_EXISTS` | 用户名已存在 | 换用户名 |
| `USERNAME_TOO_LONG` | 用户名 > 50 字符 | 改短 |
| `INTERNAL_ERROR` | 内部错误 | 看 message 字段 |
| `SELF_DELETE_FORBIDDEN` | 不能删自己 | 换个管理员删 |
| `LAST_ADMIN_FORBIDDEN` | 不能删最后一个 super 管理员 | 先新增一个管理员再删 |

### 10.2 报 traceback / 段错误 / 进程崩溃

1. 截图保存 traceback
2. 看 `AGENTS.md` §6 踩坑教训, 搜关键字 (如 "段错误" / "argparse" / "DLL")
3. 找到对应 L-NNN 后按"对"的方法处理
4. 处理不了走 §10.3 提工单

### 10.3 提工单 (TODO)

走 `task-handoff` skill 整理可交接的工单包。

---

## 附录: 命名速查表 (打印贴墙上)

```
┌────────────────────────────────────────────────────────┐
│  人脸照片文件 (face_datasets/xxx.{jpg,png,jpeg})        │
│    - 必须放 face_datasets/ 下                          │
│    - basename 全局唯一                                  │
│    - 推荐拼音: HuangJiaWei.jpg                          │
│    - 名字一旦确定, 录入员工后不要改!                    │
│    - 中文 basename 也行, 但拼音兼容性更好              │
│                                                        │
│  工号 (employee_id)                                    │
│    - 6 位数字, 主键                                    │
│    - 范围 100000 ~ 999999                              │
│    - 与人脸照片文件名无关!                              │
│                                                        │
│  姓名                                                   │
│    - 中文 1-50 字符                                     │
│    - 推荐真实姓名                                       │
│                                                        │
│  流程: 拍照放 face_datasets/ → 人员管理新增 → 实时签到 │
└────────────────────────────────────────────────────────┘
```

---

> **文档版本**: 2026-08-24 v1.0
> **配套决策**: `decisions/009-v1-bugfix-checkin-face-name-lookup.md`
> **配套教训**: `AGENTS.md` §6 L-014
> **如有更新**: 改完代码后, 同步更新本文件 + AGENTS.md 变更日志
