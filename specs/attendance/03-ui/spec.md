# SPEC-001-C: UI 层

> **规范状态**: 已批准
> **版本**: v1.0.0
> **拆分自**: SPEC-001 v1.0.0(见 `_LEGACY.md`)
> **依赖**: SPEC-001-A + SPEC-001-B 已闭环
> **代码包路径**: `attendance/ui_*.py` + `attendance_ui.py`(根)
> **最后修改**: 2026-08-24

---

## 0. 文档头与元数据

- **文件路径**: `/specs/attendance/03-ui/spec.md`
- **关联代码路径**:
  - `attendance/ui_login.py` — LoginDialog
  - `attendance/ui_employees.py` — EmployeesTab + EmployeeDialog
  - `attendance/ui_checkin.py` — CheckInTab + CheckConfirmDialog
  - `attendance/ui_records.py` — RecordsTab
  - `attendance/ui_main.py` — MainWindow (含复制自 ui.py 的识别能力)
  - `attendance_ui.py` — 根入口
  - 消费: `attendance.services` + `recognition` + `get_name`(原 ui.py 识别能力)
- **CI 门禁规则**:
  - 复制的识别代码必须以 `# COPIED FROM ui.py @ 2026-08-24` 注释开头。
  - `recognition.py` / `get_name.py` / `ui.py` 三个原文件哈希与工作区初始化时一致 (不被修改)。

---

## 1. 术语表

| 术语 | 英文名 | 类型 | 定义 | 代码映射 |
|------|--------|------|------|----------|
| 登录对话框 | LoginDialog | UI 组件 | 启动时弹出, 校验管理员账号 | `attendance.ui_login.LoginDialog` |
| 主窗口 | MainWindow | UI 组件 | 登录后进入, 含 3 个 Tab | `attendance.ui_main.MainWindow` |
| 实时签到 Tab | CheckInTab | UI 组件 | 摄像头识别 + 弹窗确认 | `attendance.ui_checkin.CheckInTab` |
| 人员管理 Tab | EmployeesTab | UI 组件 | 表格 + 增删改查按钮 | `attendance.ui_employees.EmployeesTab` |
| 打卡记录 Tab | RecordsTab | UI 组件 | 筛选 + 表格 | `attendance.ui_records.RecordsTab` |
| 人员编辑对话框 | EmployeeDialog | UI 组件 | 新增/编辑员工表单 | `attendance.ui_employees.EmployeeDialog` |
| 签到确认弹窗 | CheckConfirmDialog | UI 组件 | 识别后弹 4 按钮 | `attendance.ui_checkin.CheckConfirmDialog` |
| 识别回调 | RecognitionCallback | UI 事件 | QTimer.timeout 触发, 调用 recognition() + get_name.rec() | `CheckInTab.show_camera` |
| 信息栏 | InfoBar | UI 组件 | MainWindow 底部 QStatusBar | `MainWindow.statusBar()` |

(其他模型/服务相关术语见 SPEC-001-A §1 / SPEC-001-B §1)

---

## 2. 用户故事与验收场景(Gherkin)

```gherkin
功能: 登录流程
  作为系统
  我需要登录对话框
  以便仅管理员可进入主窗口

  场景: 启动后弹登录框
    假设 配置正确, MySQL 可达, 默认 admin 已 seed
    当 执行 python attendance_ui.py
    那么 弹出 LoginDialog
    且 LoginDialog 顶部显示"签到系统 v1.0.0"
    且 LoginDialog 含 username(QLineEdit) + password(QLineEdit, EchoMode.Password) + 登录(QPushButton)

  场景: 登录成功进入主窗口
    假设 LoginDialog 已弹出
    当 输入 username='admin', password='admin123', 点击登录
    那么 LoginDialog 关闭
    且 MainWindow 显示, 标题"签到/签退人员管理系统 v1.0.0"
    且 MainWindow 含 3 个 Tab: 实时签到 / 人员管理 / 打卡记录
    且 statusBar 显示"当前管理员: admin | 首次登录后请尽快修改密码"

  场景: 登录失败弹错
    假设 LoginDialog 已弹出
    当 输入错密码, 点击登录
    那么 弹 QMessageBox.warning, 标题"登录失败", 内容"用户名或密码错误 (错误码: AUTH_FAILED)"
    且 LoginDialog 仍保持

  场景: 关闭登录窗口
    当 关闭 LoginDialog 窗口
    那么 整个进程退出

功能: 人员管理 Tab
  作为管理员
  我需要人员增删改查 UI
  以便维护员工列表

  场景: 进入人员 Tab 显示列表
    假设 已登录, employees 表有 3 条记录
    当 点击"人员管理" Tab
    那么 表格显示 3 行
    且 表格列: 工号 / 姓名 / 部门 / 职位 / 在职 / 班次

  场景: 新增员工
    假设 处于人员 Tab
    当 点击"新增", 在 EmployeeDialog 填写:
      | 字段            | 值                |
      | employee_id     | 100001            |
      | name            | 张三              |
      | department      | 研发部            |
      | position        | 工程师            |
      | phone           | 13800138000       |
      | email           | zs@example.com    |
      | face_image_path | face_datasets/100001.jpg |
      | schedule_id     | 1 (QComboBox 选项) |
    且 face_datasets/100001.jpg 存在
    当 点击"保存"
    那么 EmployeeDialog 关闭, 表格新增一行, 数据库 employees 新增一行

  场景: 新增员工校验失败
    当 点击"新增", 填写 employee_id='abc', 点击"保存"
    那么 弹 QMessageBox.warning, 标题"保存失败", 内容含 "工号必须为 6 位数字 (错误码: EMPLOYEE_ID_INVALID)"
    且 EmployeeDialog 仍保持

  场景: 编辑员工
    假设 表格选中 employee_id='100001' 的一行
    当 点击"编辑"
    那么 EmployeeDialog 弹出, 字段预填该员工当前值, 标题"编辑员工 - 100001"
    当 修改 name 字段, 点击"保存"
    那么 表格该行 name 列更新

  场景: 删除员工
    假设 表格选中 employee_id='100002' (无打卡记录)
    当 点击"删除"
    那么 弹 QMessageBox.question, 标题"确认删除", 内容"确认删除员工 100002?"
    当 点击"是"
    那么 表格该行消失, 数据库 employees 该行删除

  场景: 删除有记录的员工作业失败
    假设 表格选中 employee_id='100001' (有打卡记录)
    当 点击"删除", 确认
    那么 弹 QMessageBox.warning, 标题"删除失败", 内容含 "员工 100001 存在 N 条打卡记录,无法删除 (错误码: EMPLOYEE_HAS_RECORDS)"

  场景: 搜索员工
    假设 表格有 3 行: 张三 / 李四 / 王五
    当 在搜索框输入"张"
    那么 表格仅显示 1 行: 张三

  场景: 清空搜索恢复全表
    当 清空搜索框
    那么 表格恢复显示全部行

功能: 实时签到 Tab
  作为管理员
  我需要摄像头识别 + 弹窗确认
  以便精确录入打卡记录

  场景: 打开相机
    当 点击"打开相机"
    那么 cv2.VideoCapture(0) 打开, QTimer 30ms 启动
    且 主窗口信息栏显示"相机已打开"
    且 按钮文本变为"关闭相机"

  场景: 相机打开失败
    假设 相机编号 0 不可用
    当 点击"打开相机"
    那么 弹 QMessageBox.warning, 标题"相机打开失败", 内容"请检查相机于电脑是否连接正确 (错误码: CAMERA_OPEN_FAILED)"

  场景: 开始识别后识别出员工
    假设 相机已打开, frame 中有人脸
    当 点击"开始识别"
    那么 每帧调用 recognition() + get_name.rec()
    当 识别出 employee_id='100001' 姓名='张三'
    那么 弹 CheckConfirmDialog, 标题"已识别: 张三 (100001)", 含 4 按钮 [签到] [签退] [中间打卡] [取消]

  场景: 识别 unknown
    假设 相机已打开, 人脸不在库中
    当 点击"开始识别"
    那么 弹 QMessageBox.warning, 标题"未识别", 内容"人脸不在库中, 无法打卡"
    且 CheckConfirmDialog 不弹

  场景: 签到确认
    假设 CheckConfirmDialog 已弹出, employee_id='100001'
    当 点击"签到"
    那么 CheckService.create_record('100001', 'check_in') 调用, 数据库新增一条 check_in 记录
    且 CheckConfirmDialog 关闭
    且 statusBar 显示"张三 已签到 HH:MM:SS"

  场景: 签退/中间打卡/取消
    类似签到场景, 行为分别:
      | 按钮       | 调用                                              | 反馈                                  |
      | 签退       | CheckService.create_record(id, 'check_out')     | "张三 已签退 HH:MM:SS"                |
      | 中间打卡   | CheckService.create_record(id, 'middle')        | "张三 中间打卡 HH:MM:SS"              |
      | 取消       | 无                                              | 弹窗关闭, statusBar 不更新            |

功能: 打卡记录 Tab
  作为管理员
  我需要按条件筛选打卡记录
  以便查看历史数据

  场景: 进入记录 Tab 显示今天全部
    假设 今日有 5 条 check_in 记录
    当 点击"打卡记录" Tab
    那么 date_from 默认今天, date_to 默认今天, employee="全部", check_type="全部"
    且 表格显示 5 行, 列: 时间 / 工号 / 姓名 / 类型

  场景: 按日期范围筛选
    假设 check_records 已有 2026-08-20 至 2026-08-24 数据
    当 date_from=2026-08-22, date_to=2026-08-24, 点击"刷新"
    那么 表格仅显示 2026-08-22 至 2026-08-24 数据

  场景: 按员工筛选
    当 employee QComboBox 选 "张三 (100001)", 点击"刷新"
    那么 表格仅显示 employee_id='100001' 记录

  场景: 按打卡类型筛选
    当 check_type QComboBox 选 "签到", 点击"刷新"
    那么 表格仅显示 check_type='check_in' 记录

  场景: 清空筛选
    当 点击"清空筛选"
    那么 date_from/today, date_to/today, employee/全部, check_type/全部, 表格刷新
```

---

## 3. UI 事件契约

| UI 控件 | 事件 | 调用服务/方法 | 成功反馈 | 失败反馈 |
|---|---|---|---|---|
| LoginDialog-username 输入 | textChanged | 无 | - | - |
| LoginDialog-password 输入 | textChanged | 无 | - | - |
| LoginDialog-登录按钮 | clicked | AdminService.authenticate | accept() 关闭, MainWindow.show() | QMessageBox.warning, 错误码 |
| LoginDialog-窗口关闭 | closeEvent | sys.exit(0) | - | - |
| MainWindow-退出菜单 | triggered | close_db() + sys.exit(0) | - | - |
| MainWindow-Tab 切换 | currentChanged | 无 | - | - |
| EmployeesTab-新增按钮 | clicked | 打开 EmployeeDialog(mode='add') | - | - |
| EmployeesTab-编辑按钮 | clicked | EmployeeService.get + 打开 EmployeeDialog(mode='edit') | - | EmployeeNotFound 弹窗 |
| EmployeesTab-删除按钮 | clicked | QMessageBox.question + EmployeeService.delete | QMessageBox.information + 刷新表格 | QMessageBox.warning 错误码 |
| EmployeesTab-刷新按钮 | clicked | EmployeeService.list_all 刷新表格 | - | - |
| EmployeesTab-搜索框 | textChanged | EmployeeService.search 刷新表格 | - | - |
| EmployeeDialog-保存按钮 | clicked | EmployeeService.create/update | accept() 关闭 + 父窗口 refresh | QMessageBox.warning 错误码 |
| EmployeeDialog-取消按钮 | clicked | reject() 关闭 | - | - |
| CheckInTab-打开/关闭相机 | clicked | cv2.VideoCapture(0) + QTimer.start(30) / .stop() | statusBar 文本切换 | QMessageBox.warning 错误码 |
| CheckInTab-开始识别 | clicked | self.flag_recognition = True | statusBar "识别中" | - |
| CheckInTab-停止识别 | clicked | self.flag_recognition = False | statusBar "识别已停止" | - |
| CheckInTab-QTimer.timeout | timeout | 读 frame, 若 flag_recognition: recognition() + get_name.rec() | 弹 CheckConfirmDialog (识别出) | 弹 "未识别" (name='unknown') |
| CheckConfirmDialog-签到 | clicked | CheckService.create_record(id, 'check_in') | accept() + statusBar 反馈 | QMessageBox.warning 错误码 |
| CheckConfirmDialog-签退 | clicked | CheckService.create_record(id, 'check_out') | 同上 | 同上 |
| CheckConfirmDialog-中间打卡 | clicked | CheckService.create_record(id, 'middle') | 同上 | 同上 |
| CheckConfirmDialog-取消 | clicked | reject() 关闭 | - | - |
| RecordsTab-刷新按钮 | clicked | CheckService.list_records 刷新表格 | - | QMessageBox.warning 错误码 |
| RecordsTab-清空筛选 | clicked | 重置控件 + refresh | - | - |
| RecordsTab-date_from.dateChanged | dateChanged | 无 (待刷新按钮触发) | - | - |
| RecordsTab-employee.currentIndexChanged | indexChanged | 无 (待刷新按钮触发) | - | - |
| RecordsTab-check_type.currentIndexChanged | indexChanged | 无 (待刷新按钮触发) | - | - |

---

## 4. 数据模型

> 全部数据模型由 SPEC-001-A §4 定义,本子 spec 不再展开。
> UI 控件与字段映射:

| UI 控件 | 数据字段 | 控件类型 |
|---|---|---|
| LoginDialog.username | Admin.username | QLineEdit |
| LoginDialog.password | (输入后 sha256_hex → 比对) | QLineEdit (EchoMode.Password) |
| EmployeeDialog.employee_id | Employee.employee_id | QLineEdit (校验: 6 位数字) |
| EmployeeDialog.name | Employee.name | QLineEdit |
| EmployeeDialog.department | Employee.department | QLineEdit (可空) |
| EmployeeDialog.position | Employee.position | QLineEdit (可空) |
| EmployeeDialog.phone | Employee.phone | QLineEdit (可空) |
| EmployeeDialog.email | Employee.email | QLineEdit (可空) |
| EmployeeDialog.face_image_path | Employee.face_image_path | QLineEdit + "浏览" 按钮 (QFileDialog.getOpenFileName) |
| EmployeeDialog.schedule_id | Employee.schedule | QComboBox (选项来自 ScheduleService.list_all) |
| EmployeeDialog.is_active | Employee.is_active | QCheckBox (默认 checked) |
| CheckConfirmDialog (构造) | 识别结果 employee_id/name | QLabel 显示 |
| RecordsTab.date_from | (查询参数) | QDateEdit (CalendarPopup) |
| RecordsTab.date_to | (查询参数) | QDateEdit (CalendarPopup) |
| RecordsTab.employee | (查询参数) | QComboBox (选项: 全部 + 所有 Employee) |
| RecordsTab.check_type | (查询参数) | QComboBox (选项: 全部 / 签到 / 签退 / 中间打卡) |
| EmployeesTab 表格 | Employee 全字段 | QTableView (model: QStandardItemModel, 6 列) |
| RecordsTab 表格 | CheckRecord + Employee.name | QTableView (4 列) |

---

## 5. UI 导航状态机

```yaml
stateMachine: AppNavigation
initial: LoginDialog
states:
  LoginDialog:
    on:
      LOGIN_SUCCESS: MainWindow
      CLOSE_WINDOW: Exit
  MainWindow:
    on:
      TAB_EMPLOYEES: EmployeesTab
      TAB_CHECKIN: CheckInTab
      TAB_RECORDS: RecordsTab
      EXIT: Exit
  EmployeesTab:
    on:
      OPEN_ADD_DIALOG: EmployeeDialog_Add
      OPEN_EDIT_DIALOG: EmployeeDialog_Edit
      REFRESH: EmployeesTab
      BACK_TO_MAIN: MainWindow
  EmployeeDialog_Add:
    on:
      SAVE_SUCCESS: EmployeesTab
      SAVE_FAIL: EmployeeDialog_Add
      CANCEL: EmployeesTab
  EmployeeDialog_Edit:
    on:
      SAVE_SUCCESS: EmployeesTab
      SAVE_FAIL: EmployeeDialog_Edit
      CANCEL: EmployeesTab
  CheckInTab:
    on:
      FACE_RECOGNIZED: CheckConfirmDialog
      FACE_UNKNOWN: CheckInTab
      BACK_TO_MAIN: MainWindow
  CheckConfirmDialog:
    on:
      CONFIRM_CHECKIN: CheckInTab
      CONFIRM_CHECKOUT: CheckInTab
      CONFIRM_MIDDLE: CheckInTab
      CANCEL: CheckInTab
  RecordsTab:
    on:
      REFRESH: RecordsTab
      BACK_TO_MAIN: MainWindow
  Exit:
    type: final
```

**一致性保障**:
- 事件名 (LOGIN_SUCCESS / SAVE_SUCCESS / CONFIRM_CHECKIN / REFRESH / CANCEL) 在代码中以显式信号名 (PyQt Signal) 出现, CI grep 与本节事件名逐字一致。
- 任何新事件必须先回本节更新。

---

## 6. 错误处理

### 6.1 错误码字典(本子 spec 范围)

| 错误码 | 触发条件 | UI 弹窗标题 | UI 弹窗内容 | 日志级别 |
|--------|----------|-------------|-------------|----------|
| `AUTH_FAILED` | 用户名不存在或密码错 | 登录失败 | "用户名或密码错误 (错误码: AUTH_FAILED)" | WARN |
| `EMPLOYEE_ID_INVALID` | 工号格式错 | 保存失败 | "工号必须为 6 位数字 (错误码: EMPLOYEE_ID_INVALID)" | WARN |
| `EMPLOYEE_ID_EXISTS` | 工号重复 | 保存失败 | "工号 {id} 已存在 (错误码: EMPLOYEE_ID_EXISTS)" | WARN |
| `EMPLOYEE_NOT_FOUND` | 查/改/删时员工不存在 | 操作失败 | "员工 {id} 不存在 (错误码: EMPLOYEE_NOT_FOUND)" | WARN |
| `EMPLOYEE_HAS_RECORDS` | 删员工时存在 check_records | 删除失败 | "员工 {id} 存在 {n} 条打卡记录,无法删除 (错误码: EMPLOYEE_HAS_RECORDS)" | WARN |
| `EMPLOYEE_INACTIVE` | 给 is_active=False 的员工打卡 | 打卡失败 | "员工 {id} 已离职,无法打卡 (错误码: EMPLOYEE_INACTIVE)" | WARN |
| `FACE_IMAGE_NOT_FOUND` | 人脸照片不存在 | 保存失败 | "人脸照片 {path} 不存在 (错误码: FACE_IMAGE_NOT_FOUND)" | WARN |
| `SCHEDULE_NOT_FOUND` | schedule_id 不存在 | 保存失败 | "班次 {id} 不存在 (错误码: SCHEDULE_NOT_FOUND)" | WARN |
| `CHECK_TYPE_INVALID` | check_type 非法 | 打卡失败 | "打卡类型必须为 check_in / check_out / middle (错误码: CHECK_TYPE_INVALID)" | WARN |
| `DATE_RANGE_INVALID` | date_from > date_to | 查询失败 | "起始日期不能晚于结束日期 (错误码: DATE_RANGE_INVALID)" | WARN |
| `CAMERA_OPEN_FAILED` | cv2.VideoCapture.open 返回 False | 相机打开失败 | "请检查相机于电脑是否连接正确 (错误码: CAMERA_OPEN_FAILED)" | WARN |

### 6.2 错误弹窗实现

```python
# attendance/utils.py 辅助函数 (UI 层)
def show_error(parent, error_code: str, message: str) -> None:
    """统一弹 QMessageBox.warning, 标题 '操作失败' 或按错误码决定。"""
```

(具体标题映射见 §6.1 表格。)

### 6.3 日志规范

- 复用 SPEC-001-A §6.3 + SPEC-001-B §6.3 的 logger 规范。
- 关键 UI action: `ui.login.success` / `ui.login.fail` / `ui.employee.create` / `ui.checkin.check_in` / `ui.records.query`。

---

## 7. 测试用例与覆盖矩阵

> 本子 spec 覆盖 UI 行为测试 (烟测 + 关键路径)。

| 需求来源 | 需求 ID | 类型 | 测试用例 ID | 自动化状态 |
|----------|---------|------|-------------|------------|
| Gherkin: 启动后弹登录框 | REQ-C-01 | UI 烟测 | TC-ATT-C01 | 已自动化 |
| Gherkin: 登录成功进入主窗口 | REQ-C-02 | UI 烟测 | TC-ATT-C02 | 已自动化 |
| Gherkin: 登录失败弹错 | REQ-C-03 | UI 烟测 | TC-ATT-C03 | 已自动化 |
| Gherkin: 关闭登录窗口进程退出 | REQ-C-04 | UI 烟测 | TC-ATT-C04 | 已自动化 |
| Gherkin: 进入人员 Tab 显示列表 | REQ-C-05 | UI 烟测 | TC-ATT-C05 | 已自动化 |
| Gherkin: 新增员工 | REQ-C-06 | UI 烟测 | TC-ATT-C06 | 已自动化 |
| Gherkin: 新增员工校验失败 | REQ-C-07 | UI 烟测 | TC-ATT-C07 | 已自动化 |
| Gherkin: 编辑员工 | REQ-C-08 | UI 烟测 | TC-ATT-C08 | 已自动化 |
| Gherkin: 删除员工 | REQ-C-09 | UI 烟测 | TC-ATT-C09 | 已自动化 |
| Gherkin: 删除有记录失败 | REQ-C-10 | UI 烟测 | TC-ATT-C10 | 已自动化 |
| Gherkin: 搜索员工 | REQ-C-11 | UI 烟测 | TC-ATT-C11 | 已自动化 |
| Gherkin: 打开相机 | REQ-C-12 | UI 烟测 | TC-ATT-C12 | 已自动化 |
| Gherkin: 相机打开失败 | REQ-C-13 | UI 烟测 | TC-ATT-C13 | 已自动化 |
| Gherkin: 签到确认 | REQ-C-14 | UI 烟测 | TC-ATT-C14 | 已自动化 |
| Gherkin: 签退/中间打卡/取消 | REQ-C-15 | UI 烟测 | TC-ATT-C15 | 已自动化 |
| Gherkin: 记录 Tab 默认显示 | REQ-C-16 | UI 烟测 | TC-ATT-C16 | 已自动化 |
| Gherkin: 按日期范围筛选 | REQ-C-17 | UI 烟测 | TC-ATT-C17 | 已自动化 |
| Gherkin: 按员工/类型筛选 | REQ-C-18 | UI 烟测 | TC-ATT-C18 | 已自动化 |

> UI 烟测使用 pytest-qt 或模拟 QMessageBox 的方式断言;不依赖真实相机与显示器。

---

## 8. 非功能性需求

| 类别 | 具体要求 | 验证方法 |
|------|----------|----------|
| 性能 | 启动到登录框显示 < 3s | 手动 + time.monotonic 包裹 |
| 性能 | 摄像头帧识别 (含 YOLOv8+FaceNet) 在 GPU 上 < 200ms / 帧 | 单独基准测试 |
| 安全性 | 密码框 EchoMode.Password | TC-ATT-C01 断言 QLineEdit.echoMode() == QLineEdit.Password |
| 可用性 | 弹窗标题"保存失败"/"操作失败"按错误码确定 | §6.1 表格 |
| 可维护性 | 复制的识别代码以注释标记 | CI grep `attendance/ui_main.py` 含 `# COPIED FROM ui.py @ 2026-08-24` |
| 约束 | 原 ui.py / recognition.py / get_name.py 哈希不变 | 初始化时 `sha256` 记录于 decisions; 实施后比对 |

---

## 9. 假设、约束与变更日志

### 9.1 假设

- SPEC-001-A + SPEC-001-B 已闭环。
- PyQt5 5.15+ 已安装。
- 项目当前 `recognition.py` / `get_name.py` 可独立 import。
- 用户有可用的 USB 摄像头 (或可用视频文件 fallback)。
- 测试在无头环境使用 pytest-qt + offscreen platform plugin (`QT_QPA_PLATFORM=offscreen`)。

### 9.2 约束

- 不修改 `recognition.py` / `get_name.py` / `ui.py` 三个现有文件。
- 识别能力以复制方式纳入 `attendance/ui_main.py`, 文件头含 `# COPIED FROM ui.py @ 2026-08-24` 注释。
- UI 控件命名 (对象名) 严格按 §4 表格。
- 状态机事件名严格按 §5 表格。

### 9.3 变更日志

| 日期 | 版本 | 变更说明 | 关联 Commit |
|------|------|----------|-------------|
| 2026-08-24 | v1.0.0 | 拆分自 SPEC-001 v1.0.0;UI 层子 spec | (待提交) |
