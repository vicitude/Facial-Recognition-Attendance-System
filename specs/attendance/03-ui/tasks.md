# 任务拆解: SPEC-001-C UI 层

> 与 `specs/attendance/03-ui/spec.md` v1.0.0 配套。

---

## T-301 实现 LoginDialog

- **依赖**: SPEC-001-B 已闭环 (AdminService 可用)
- **前置**: 无
- **产出物**: `attendance/ui_login.py` 含:
  - `class LoginDialog(QDialog)`:
    - `__init__(self, parent=None)`: 构造 UI, 含 QLabel 标题 + QLineEdit username + QLineEdit password (EchoMode.Password) + QPushButton 登录
    - `on_login_clicked(self)`: 校验非空, 调 `AdminService.authenticate`, 成功 `self.accept()`, 失败 `show_error`
    - `closeEvent(self, event)`: `sys.exit(0)`
- **关联**: §3 LoginDialog 事件契约
- **覆盖**: TC-ATT-C01 ~ C04

## T-302 实现 EmployeesTab + EmployeeDialog

- **依赖**: T-301
- **前置**: SPEC-001-B 中 EmployeeService 已实现
- **产出物**: `attendance/ui_employees.py` 含:
  - `class EmployeesTab(QWidget)`: 表格 + 工具栏 (新增/编辑/删除/刷新/搜索框)
  - `class EmployeeDialog(QDialog)`: 表单 + 8 输入控件 + 保存/取消按钮
- **关联**: §3 EmployeesTab / EmployeeDialog 事件契约, §4 字段映射
- **覆盖**: TC-ATT-C05 ~ C11

## T-303 实现 CheckInTab + CheckConfirmDialog

- **依赖**: T-301
- **前置**: SPEC-001-B 中 CheckService 已实现
- **产出物**: `attendance/ui_checkin.py` 含:
  - `class CheckInTab(QWidget)`: 工具栏 (打开/关闭相机/开始识别/停止识别) + QLabel 显示画面
  - `class CheckConfirmDialog(QDialog)`: 标题显示员工姓名+工号 + 4 按钮 [签到] [签退] [中间打卡] [取消]
  - 内部 `letterbox` / `Yolo` / `recognition` 函数 (复制自 recognition.py)
- **关联**: §3 CheckInTab / CheckConfirmDialog 事件契约
- **覆盖**: TC-ATT-C12 ~ C15

## T-304 实现 RecordsTab

- **依赖**: T-301
- **前置**: SPEC-001-B 中 CheckService.list_records 已实现
- **产出物**: `attendance/ui_records.py` 含:
  - `class RecordsTab(QWidget)`: 顶部筛选栏 (date_from QDateEdit + date_to QDateEdit + employee QComboBox + check_type QComboBox + 刷新按钮 + 清空筛选按钮) + QTableView
- **关联**: §3 RecordsTab 事件契约
- **覆盖**: TC-ATT-C16 ~ C18

## T-305 实现 MainWindow

- **依赖**: T-301, T-302, T-303, T-304
- **前置**: 全部 UI 子模块完成
- **产出物**: `attendance/ui_main.py` 含:
  - `class MainWindow(QMainWindow)`: 标题"签到/签退人员管理系统 v1.0.0" + QTabWidget × 3 + QStatusBar
  - 顶部菜单 (文件 > 退出)
  - statusBar 显示"当前管理员: {username} | {密码提示}"
- **关联**: §5 状态机 MainWindow 节点
- **覆盖**: TC-ATT-C02

## T-306 实现 attendance_ui.py 根入口

- **依赖**: T-305
- **前置**: 全部
- **产出物**: `attendance_ui.py` 含:
  ```python
  from attendance.config import ConfigService
  from attendance.db import init_db, close_db
  from attendance.services import AdminService
  from attendance.ui_login import LoginDialog
  from attendance.ui_main import MainWindow
  import sys
  from PyQt5 import QtWidgets

  def main():
      try:
          config = ConfigService.load()
      except Exception as e:
          # 弹 QMessageBox.critical 后 sys.exit(1)
          ...
      try:
          init_db(config)
      except Exception as e:
          # 弹 QMessageBox.critical 后 sys.exit(1)
          ...
      try:
          AdminService.ensure_default(config['admin']['default_username'],
                                       config['admin']['default_password'])
      except Exception as e:
          # 弹 QMessageBox.critical 后 sys.exit(1)
          ...
      app = QtWidgets.QApplication(sys.argv)
      login = LoginDialog()
      if login.exec_() == QtWidgets.QDialog.Accepted:
          admin = login.admin  # LoginDialog 暴露的属性
          window = MainWindow(admin)
          window.show()
          exit_code = app.exec_()
          close_db()
          sys.exit(exit_code)

  if __name__ == '__main__':
      main()
  ```
- **关联**: §0 入口文件
- **覆盖**: TC-ATT-C01

---

## 任务依赖图

```text
T-301 ──┬──> T-302 ──┐
        │            │
        ├──> T-303 ──┤
        │            ├──> T-305 ──> T-306
        └──> T-304 ──┘
```

## 排期

| 阶段 | 任务 | 工时(单人时) |
|------|------|--------------|
| UI | T-301, T-302, T-303, T-304, T-305, T-306 | 8 |
| **合计** | - | **8** |
