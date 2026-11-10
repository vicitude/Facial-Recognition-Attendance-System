# 验收清单: SPEC-001-C UI 层

> 与 `specs/attendance/03-ui/spec.md` v1.0.0 配套。闭环后: `decisions/004-v1-ui-shipped.md` + `_INDEX.md` 追加 004 行。

---

## A. 文件存在

- [ ] **A-01** `attendance/ui_login.py` 存在, 含 `LoginDialog` — 阻塞
- [ ] **A-02** `attendance/ui_employees.py` 存在, 含 `EmployeesTab` + `EmployeeDialog` — 阻塞
- [ ] **A-03** `attendance/ui_checkin.py` 存在, 含 `CheckInTab` + `CheckConfirmDialog` — 阻塞
- [ ] **A-04** `attendance/ui_records.py` 存在, 含 `RecordsTab` — 阻塞
- [ ] **A-05** `attendance/ui_main.py` 存在, 含 `MainWindow` — 阻塞
- [ ] **A-06** `attendance_ui.py` 在项目根 — 阻塞

## B. 原文件未改

- [ ] **B-01** `recognition.py` 内容哈希与初始化时一致 — 阻塞 → §9.2 约束
- [ ] **B-02** `get_name.py` 内容哈希与初始化时一致 — 阻塞
- [ ] **B-03** `ui.py` 内容哈希与初始化时一致 — 阻塞
- [ ] **B-04** `attendance/ui_main.py` 含 `# COPIED FROM ui.py @ 2026-08-24` 注释 — 阻塞

## C. LoginDialog

- [ ] **C-01** 启动 `python attendance_ui.py` 弹 LoginDialog, 标题"签到系统 v1.0.0" — 阻塞 → TC-ATT-C01
- [ ] **C-02** 密码框 echoMode == QLineEdit.Password — 阻塞
- [ ] **C-03** 输入 admin/admin123 + 登录, 关闭对话框, MainWindow 显示, statusBar 含"当前管理员: admin" — 阻塞 → TC-ATT-C02
- [ ] **C-04** 输入错密码, 弹 QMessageBox.warning 标题"登录失败"内容含 "AUTH_FAILED" — 阻塞 → TC-ATT-C03
- [ ] **C-05** 关闭 LoginDialog 窗口触发 sys.exit(0) — 阻塞 → TC-ATT-C04

## D. MainWindow

- [ ] **D-01** 标题"签到/签退人员管理系统 v1.0.0" — 阻塞
- [ ] **D-02** 含 3 个 Tab: 实时签到 / 人员管理 / 打卡记录 — 阻塞
- [ ] **D-03** statusBar 持久显示"当前管理员: {username} | 首次登录后请尽快修改密码" — 阻塞
- [ ] **D-04** 菜单"文件 > 退出"触发 close_db + sys.exit(0) — 阻塞

## E. EmployeesTab

- [ ] **E-01** 进入人员 Tab 显示 employees 表格 6 列 — 阻塞 → TC-ATT-C05
- [ ] **E-02** "新增"按钮打开 EmployeeDialog (mode='add') — 阻塞 → TC-ATT-C06
- [ ] **E-03** EmployeeDialog 含 8 输入控件 + schedule_id QComboBox 选项来自 ScheduleService.list_all — 阻塞
- [ ] **E-04** EmployeeDialog 填写合法后保存, 表格新增一行, 数据库新增 — 阻塞 → TC-ATT-C06
- [ ] **E-05** EmployeeDialog 填写 employee_id='abc' 后保存, 弹 QMessageBox 含 "EMPLOYEE_ID_INVALID" — 阻塞 → TC-ATT-C07
- [ ] **E-06** "编辑"按钮打开 EmployeeDialog (mode='edit') 字段预填 — 阻塞 → TC-ATT-C08
- [ ] **E-07** "删除"按钮弹 QMessageBox.question 确认, 确认后调 EmployeeService.delete, 表格移除该行 — 阻塞 → TC-ATT-C09
- [ ] **E-08** 删除有记录员工弹 QMessageBox 含 "EMPLOYEE_HAS_RECORDS" — 阻塞 → TC-ATT-C10
- [ ] **E-09** 搜索框输入"张"表格过滤, 清空恢复 — 阻塞 → TC-ATT-C11

## F. CheckInTab

- [ ] **F-01** "打开相机"按钮调 cv2.VideoCapture(0) + QTimer.start(30) — 阻塞 → TC-ATT-C12
- [ ] **F-02** 相机打开失败弹 QMessageBox 含 "CAMERA_OPEN_FAILED" — 阻塞 → TC-ATT-C13
- [ ] **F-03** 识别出员工后弹 CheckConfirmDialog, 标题"已识别: {name} ({id})", 4 按钮 — 阻塞
- [ ] **F-04** "签到"按钮调 CheckService.create_record('check_in'), statusBar 反馈 — 阻塞 → TC-ATT-C14
- [ ] **F-05** "签退" / "中间打卡" / "取消" 行为与 §3 表格一致 — 阻塞 → TC-ATT-C15

## G. RecordsTab

- [ ] **G-01** 进入记录 Tab, date_from/today, date_to/today, 默认显示今日全部 — 阻塞 → TC-ATT-C16
- [ ] **G-02** 改 date_from/date_to 点"刷新" 过滤生效 — 阻塞 → TC-ATT-C17
- [ ] **G-03** 选 employee / check_type 点"刷新" 过滤生效 — 阻塞 → TC-ATT-C18
- [ ] **G-04** "清空筛选" 恢复默认 + 刷新 — 阻塞

## H. 静态检查

- [ ] **H-01** 状态机事件名 (LOGIN_SUCCESS 等) 在代码中以 Signal 形式出现且与 §5 逐字一致 — 阻塞
- [ ] **H-02** 错误码字符串与 §6.1 表格逐字一致 — 阻塞
- [ ] **H-03** `attendance/ui_*.py` 中 `from attendance.services import` 列表与 SPEC-001-B 暴露的 4 个 Service 类一致 — 阻塞

## I. 测试

- [ ] **I-01** `pytest tests/test_ui.py -q` 全绿 (使用 pytest-qt + QT_QPA_PLATFORM=offscreen) — 阻塞
- [ ] **I-02** `pytest --collect-only -q | grep "test_TC_ATT_C"` 输出 18 行 — 阻塞

## J. 闭环

- [ ] **J-01** 全部阻塞项通过后, 在 `decisions/004-v1-ui-shipped.md` 写入闭环决策
- [ ] **J-02** 在 `decisions/_INDEX.md` 追加 004 行
