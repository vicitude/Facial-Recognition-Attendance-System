"""签到/签退人员管理系统 - 人员管理 Tab (SPEC-001-C §3 EmployeesTab / EmployeeDialog).

T-302: 表格 + 工具栏 (新增/编辑/删除/刷新/搜索) + 增改表单对话框.
- EmployeesTab: 6 列表格 (工号/姓名/部门/职位/在职/班次)
- EmployeeDialog: 9 输入控件 (employee_id/name/department/position/phone/email/face_image_path/schedule_id/is_active)
- 模式: 'add' / 'edit', 由 mode 参数决定 (edit 时工号只读)
"""

import os
import re
from typing import List, Optional

from PyQt5 import QtCore, QtWidgets

from attendance.models import Employee
from attendance.face_template import FacePose, POSE_PROMPTS, assess_registration_quality
from attendance.services import EmployeeService, ScheduleService
from attendance.ui_utils import show_error
from attendance.ui_theme import card, configure_table, label, page_header, prepare_dialog
from attendance.utils import (
    EmployeeHasRecords,
    EmployeeIdExists,
    EmployeeIdInvalid,
    EmployeeNotFound,
    FaceImageNotFound,
    ScheduleNotFound,
)


# 异常类 → 错误码 映射 (SPEC-001-C §6.1)
_EXC_TO_ERROR_CODE = {
    "EmployeeIdInvalid": "EMPLOYEE_ID_INVALID",
    "EmployeeIdExists": "EMPLOYEE_ID_EXISTS",
    "EmployeeNotFound": "EMPLOYEE_NOT_FOUND",
    "EmployeeHasRecords": "EMPLOYEE_HAS_RECORDS",
    "FaceImageNotFound": "FACE_IMAGE_NOT_FOUND",
    "ScheduleNotFound": "SCHEDULE_NOT_FOUND",
}


class EmployeesTab(QtWidgets.QWidget):
    """人员管理 Tab - 表格 + 工具栏."""

    COLUMNS: List[str] = ["工号", "姓名", "部门", "职位", "在职", "班次"]

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._wire_signals()
        self._refresh_table()

    # ----------------------------------------------------------
    # UI 构造
    # ----------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        self.employee_summary = label('共 0 人', 'badge')
        header = page_header('人员管理', '维护员工资料、班次和本机加密人脸模板。')
        header.layout().addWidget(self.employee_summary)
        layout.addWidget(header)

        # 工具栏
        toolbar = QtWidgets.QHBoxLayout()
        self.btn_add = QtWidgets.QPushButton("新增")
        self.btn_edit = QtWidgets.QPushButton("编辑")
        self.btn_delete = QtWidgets.QPushButton("删除")
        self.btn_refresh = QtWidgets.QPushButton("刷新")
        self.btn_bind_schedules = QtWidgets.QPushButton("绑定班次")
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("搜索工号/姓名")
        self.search_edit.setClearButtonEnabled(True)
        self.btn_add.setObjectName('primary')
        self.btn_delete.setObjectName('danger')
        toolbar.addWidget(label('快速搜索'))
        toolbar.addWidget(self.btn_add)
        toolbar.addWidget(self.btn_edit)
        toolbar.addWidget(self.btn_delete)
        toolbar.addWidget(self.btn_refresh)
        toolbar.addWidget(self.btn_bind_schedules)
        toolbar.addWidget(self.search_edit)
        toolbar_card = card()
        toolbar_card_layout = QtWidgets.QHBoxLayout(toolbar_card)
        toolbar_card_layout.setContentsMargins(16, 12, 16, 12)
        toolbar_card_layout.addLayout(toolbar)
        layout.addWidget(toolbar_card)

        # 表格
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows
        )
        self.table.setSelectionMode(
            QtWidgets.QAbstractItemView.SingleSelection
        )
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.NoEditTriggers
        )
        self.table.verticalHeader().setVisible(False)
        configure_table(self.table)
        layout.addWidget(self.table)

    def _wire_signals(self) -> None:
        self.btn_add.clicked.connect(self._on_add)
        self.btn_edit.clicked.connect(self._on_edit)
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_refresh.clicked.connect(
            lambda: self._refresh_table()
        )
        self.btn_bind_schedules.clicked.connect(self._on_bind_schedules)
        self.search_edit.textChanged.connect(self._on_search)

    # ----------------------------------------------------------
    # 内部辅助
    # ----------------------------------------------------------

    def _selected_employee_id(self) -> Optional[str]:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.table.item(rows[0].row(), 0)
        return item.text() if item else None

    def _refresh_table(
        self, employees: Optional[List[Employee]] = None
    ) -> None:
        if employees is None:
            try:
                employees = EmployeeService.list_all()
            except Exception as e:
                show_error(
                    self, "EMPLOYEE_NOT_FOUND",
                    f"加载员工列表失败: {e} (错误码: EMPLOYEE_NOT_FOUND)",
                )
                return
        self.table.setRowCount(len(employees))
        self.employee_summary.setText(f'共 {len(employees)} 人')
        for r, emp in enumerate(employees):
            self.table.setItem(
                r, 0,
                QtWidgets.QTableWidgetItem(emp.employee_id),
            )
            self.table.setItem(
                r, 1, QtWidgets.QTableWidgetItem(emp.name or ""),
            )
            self.table.setItem(
                r, 2,
                QtWidgets.QTableWidgetItem(emp.department or ""),
            )
            self.table.setItem(
                r, 3,
                QtWidgets.QTableWidgetItem(emp.position or ""),
            )
            self.table.setItem(
                r, 4,
                QtWidgets.QTableWidgetItem("是" if emp.is_active else "否"),
            )
            schedule_name = (
                emp.schedule.name if emp.schedule else ""
            )
            self.table.setItem(
                r, 5, QtWidgets.QTableWidgetItem(schedule_name),
            )

    # ----------------------------------------------------------
    # 槽函数
    # ----------------------------------------------------------

    def _on_add(self) -> None:
        # M2: 新增员工统一走三姿态加密登记流程。
        from attendance.ui_enrollment import EnrollmentDialog
        dlg = EnrollmentDialog(parent=self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self._refresh_table()

    def _on_edit(self) -> None:
        eid = self._selected_employee_id()
        if not eid:
            show_error(
                self, "EMPLOYEE_NOT_FOUND",
                "请先选中一行员工 (错误码: EMPLOYEE_NOT_FOUND)",
            )
            return
        try:
            emp = EmployeeService.get(eid)
            dlg = EmployeeDialog(parent=self, mode="edit", employee=emp)
            if dlg.exec_() == QtWidgets.QDialog.Accepted:
                self._refresh_table()
        except EmployeeNotFound as e:
            show_error(
                self, "EMPLOYEE_NOT_FOUND",
                f"{e} (错误码: EMPLOYEE_NOT_FOUND)",
            )
        except Exception as e:
            # 编辑窗口构造/执行失败必须可见，避免用户误以为按钮无效。
            show_error(
                self, "EMPLOYEE_EDIT_FAILED",
                f"打开编辑窗口失败: {e} (错误码: EMPLOYEE_EDIT_FAILED)",
            )

    def _on_delete(self) -> None:
        eid = self._selected_employee_id()
        if not eid:
            show_error(
                self, "EMPLOYEE_NOT_FOUND",
                "请先选中一行员工 (错误码: EMPLOYEE_NOT_FOUND)",
            )
            return
        reply = QtWidgets.QMessageBox.question(
            self, "确认删除", f"确认删除员工 {eid}?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return
        try:
            EmployeeService.delete(eid)
        except EmployeeNotFound as e:
            show_error(
                self, "EMPLOYEE_NOT_FOUND",
                f"{e} (错误码: EMPLOYEE_NOT_FOUND)",
            )
            return
        self._refresh_table()

    def _on_bind_schedules(self) -> None:
        eid = self._selected_employee_id()
        if not eid:
            show_error(self, "EMPLOYEE_NOT_FOUND", "请先选中员工 (错误码: EMPLOYEE_NOT_FOUND)")
            return
        from attendance.ui_schedules import EmployeeScheduleDialog
        if EmployeeScheduleDialog(eid, self).exec_() == QtWidgets.QDialog.Accepted:
            self._refresh_table()

    def _on_search(self, text: str) -> None:
        if not text:
            self._refresh_table()
            return
        self._refresh_table(EmployeeService.search(text))


class EmployeeDialog(QtWidgets.QDialog):
    """人员编辑对话框 (新增 / 编辑)."""

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        mode: str = "add",
        employee: Optional[Employee] = None,
    ) -> None:
        super().__init__(parent)
        self._mode = mode
        self._employee = employee
        self._build_ui()
        self._wire_signals()
        if mode == "edit" and employee is not None:
            self._load_employee(employee)
            self.setWindowTitle(f"编辑员工 - {employee.employee_id}")
        else:
            self.setWindowTitle("新增员工")

    # ----------------------------------------------------------
    # UI 构造
    # ----------------------------------------------------------

    def _build_ui(self) -> None:

        # 输入控件
        self.employee_id_edit = QtWidgets.QLineEdit()
        self.employee_id_edit.setMaxLength(6)
        self.employee_id_edit.setPlaceholderText("6 位数字")

        self.name_edit = QtWidgets.QLineEdit()
        self.privacy_check = QtWidgets.QCheckBox(
            "我已知悉人脸数据仅用于本地考勤，并同意采集和加密保存"
        )
        self.privacy_check.setChecked(False)

        self.department_edit = QtWidgets.QLineEdit()
        self.department_edit.setPlaceholderText("可空")

        self.position_edit = QtWidgets.QLineEdit()
        self.position_edit.setPlaceholderText("可空")

        self.phone_edit = QtWidgets.QLineEdit()
        self.phone_edit.setPlaceholderText("可空")

        self.email_edit = QtWidgets.QLineEdit()
        self.email_edit.setPlaceholderText("可空")

        self.face_path_edit = QtWidgets.QLineEdit()
        self.face_path_edit.setPlaceholderText("face_datasets/xxx.jpg")
        self.btn_browse = QtWidgets.QPushButton("浏览...")

        # 班次下拉
        self.schedule_combo = QtWidgets.QComboBox()
        try:
            self._schedules = ScheduleService.list_all()
        except Exception:
            self._schedules = []
        for s in self._schedules:
            self.schedule_combo.addItem(f"{s.id} - {s.name}", s.id)

        self.is_active_check = QtWidgets.QCheckBox("在职")
        self.is_active_check.setChecked(True)

        # 表单布局
        form = QtWidgets.QFormLayout()
        form.addRow("工号*", self.employee_id_edit)
        form.addRow("姓名*", self.name_edit)
        form.addRow("部门", self.department_edit)
        form.addRow("职位", self.position_edit)
        form.addRow("电话", self.phone_edit)
        form.addRow("邮箱", self.email_edit)

        face_layout = QtWidgets.QHBoxLayout()
        face_layout.addWidget(self.face_path_edit, 1)
        face_layout.addWidget(self.btn_browse)
        form.addRow("人脸照片路径*", face_layout)

        form.addRow("班次*", self.schedule_combo)
        form.addRow("", self.is_active_check)

        # 按钮
        self.btn_save = QtWidgets.QPushButton("保存")
        self.btn_cancel = QtWidgets.QPushButton("取消")
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_cancel)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(btn_layout)
        prepare_dialog(self, '人员资料', '完善人员信息，带 * 的项目为必填项。', self.btn_save, 640)

    def _wire_signals(self) -> None:
        self.btn_save.clicked.connect(self._on_save)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_browse.clicked.connect(self._on_browse)

    # ----------------------------------------------------------
    # 槽函数
    # ----------------------------------------------------------

    def _normalize_face_path(self, path: str) -> str:
        """把人脸照片路径归一化为项目根相对路径 (face_datasets/xxx.jpg).

        业务层 FACE_IMAGE_PATH_PATTERN (services.py:76) 硬要求
        项目根相对路径, 不接受盘符开头的绝对路径. UI 任何入口
        (_on_browse 选文件 / _on_save 前兜底) 都需要归一化.

        Returns:
            项目根相对路径 (forward-slash), 跨平台一致. 已匹配
            业务层正则的输入直接返回, 避免无谓 relpath.

        2026-08-24 v2 升级 (决策 008 v2):
          v1 仅 _on_browse 归一化, 实测发现某些场景 (缓存/旧版本/
          其他 UI 入口) 仍可能把绝对路径传到 Service, 弹 FACE_IMAGE_NOT_FOUND.
          v2 抽 helper, _on_browse 即时反馈 + _on_save 兜底,
          Service 边界前必定归一化一次.
        """
        if not path:
            return path
        # 已匹配业务层正则 → 不变 (避免无谓 relpath)
        if re.fullmatch(
            EmployeeService.FACE_IMAGE_PATH_PATTERN, path,
        ):
            return path
        project_root = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )
        try:
            rel = os.path.relpath(path, project_root)
        except ValueError:
            # 跨盘符 (Windows) 抛 ValueError, 保留原值让 Service 报错
            rel = path
        return rel.replace(os.sep, "/")

    def _on_browse(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "选择人脸照片", "face_datasets",
            "Images (*.jpg *.jpeg *.png)",
        )
        if path:
            # QFileDialog 返回绝对路径; 归一化 helper 见 _normalize_face_path.
            # 决策 008 v2: 即时反馈 + _on_save 兜底 双层防御.
            self.face_path_edit.setText(
                self._normalize_face_path(path)
            )

    def _load_employee(self, emp: Employee) -> None:
        self.employee_id_edit.setText(emp.employee_id)
        self.employee_id_edit.setReadOnly(True)
        self.name_edit.setText(emp.name or "")
        self.department_edit.setText(emp.department or "")
        self.position_edit.setText(emp.position or "")
        self.phone_edit.setText(emp.phone or "")
        self.email_edit.setText(emp.email or "")
        self.face_path_edit.setText(emp.face_image_path or "")
        # 编辑允许员工暂时没有班次；不能因为 None 访问 .id 导致对话框无声失败。
        schedule_id = emp.schedule.id if emp.schedule is not None else None
        for i in range(self.schedule_combo.count()):
            if schedule_id is not None and self.schedule_combo.itemData(i) == schedule_id:
                self.schedule_combo.setCurrentIndex(i)
                break
        if schedule_id is None:
            self.schedule_combo.setCurrentIndex(-1)
        self.is_active_check.setChecked(bool(emp.is_active))

    def _on_save(self) -> None:
        eid = self.employee_id_edit.text().strip()
        name = self.name_edit.text().strip()
        # 决策 008 v2: 防御性归一化, 即 _on_browse 漏了 (缓存/旧版本/
        # 其他入口手输入) 也能在 Service 调用前兜住, 弹 FACE_IMAGE_NOT_FOUND
        # 的根因被堵死.
        face_path = self._normalize_face_path(
            self.face_path_edit.text().strip()
        ) if self._mode == "add" or self.face_path_edit.text().strip() else None
        schedule_id_raw = self.schedule_combo.currentData()
        if not eid or not name or (self._mode == "add" and (not face_path or schedule_id_raw is None)):
            show_error(
                self, "EMPLOYEE_ID_INVALID",
                "工号 / 姓名不能为空；新增员工还必须提供人脸照片路径和班次 "
                "(错误码: EMPLOYEE_ID_INVALID)",
            )
            return
        if schedule_id_raw is None and self._mode == "edit":
            schedule_id = None
        else:
            try:
                schedule_id = int(schedule_id_raw)
            except (TypeError, ValueError):
                show_error(
                    self, "SCHEDULE_NOT_FOUND",
                    f"班次 id 非法: {schedule_id_raw!r} (错误码: SCHEDULE_NOT_FOUND)",
                )
                return

        # 空字符串统一转 None (Service 接受 Optional)
        def _opt(s: str) -> Optional[str]:
            return s if s else None

        try:
            if self._mode == "add":
                EmployeeService.create(
                    employee_id=eid,
                    name=name,
                    department=_opt(self.department_edit.text().strip()),
                    position=_opt(self.position_edit.text().strip()),
                    phone=_opt(self.phone_edit.text().strip()),
                    email=_opt(self.email_edit.text().strip()),
                    face_image_path=face_path,
                    schedule_id=schedule_id,
                    is_active=self.is_active_check.isChecked(),
                )
            else:
                EmployeeService.update(
                    eid,
                    name=name,
                    department=_opt(self.department_edit.text().strip()),
                    position=_opt(self.position_edit.text().strip()),
                    phone=_opt(self.phone_edit.text().strip()),
                    email=_opt(self.email_edit.text().strip()),
                    face_image_path=face_path,
                    schedule_id=schedule_id,
                    is_active=self.is_active_check.isChecked(),
                )
        except (
            EmployeeIdInvalid,
            EmployeeIdExists,
            EmployeeNotFound,
            FaceImageNotFound,
            ScheduleNotFound,
        ) as e:
            code = _EXC_TO_ERROR_CODE.get(
                type(e).__name__, "EMPLOYEE_ID_INVALID",
            )
            show_error(self, code, f"{e} (错误码: {code})")
            return
        self.accept()
