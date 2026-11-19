"""签到/签退人员管理系统 - 打卡记录 Tab (SPEC-001-C §3 RecordsTab).

T-304: 顶部筛选区 (员工/类型/起始日期/截止日期 + 刷新/清空筛选)
       + 底部 6 列记录表格.
- 默认 date_from=date_to=today, employee="全部", check_type="全部"
- 列: 工号 / 姓名 / 部门 / 日期 / 时间 / 类型
- 错误码: DATE_RANGE_INVALID / CHECK_TYPE_INVALID (走 ui_utils.show_error)
"""

from typing import List, Optional

from PyQt5 import QtCore, QtWidgets

from attendance.models import CheckRecord
from attendance.services import CheckService, EmployeeService, ScheduleService
from attendance.ui_utils import show_error
from attendance.ui_theme import card, configure_table, label, page_header
from attendance.utils import CheckTypeInvalid, DateRangeInvalid


# 类型 → 中文标签 映射 (用于表格渲染)
_CHECK_TYPE_LABEL: dict[str, str] = {
    "check_in": "签到",
    "check_out": "签退",
    "middle": "中间打卡（历史）",
}
_STATUS_LABEL = {"normal": "正常", "late": "迟到", "early_leave": "早退", "manual_adjusted": "管理员补录", "duplicate": "重复", "invalid_sequence": "顺序错误"}


class RecordsTab(QtWidgets.QWidget):
    """打卡记录 Tab - 筛选区 + 6 列记录表."""

    COLUMNS: List[str] = ["工号", "姓名", "部门", "班次", "日期", "时间", "类型", "状态", "异常原因", "补录管理员"]

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
        self.record_summary = label('今日记录', 'badge')
        header = page_header('打卡记录', '按员工、考勤类型和日期查看历史记录。')
        header.layout().addWidget(self.record_summary)
        layout.addWidget(header)

        # ----- 筛选区 -----
        filter_layout = QtWidgets.QHBoxLayout()
        filter_card = card()
        filter_card_layout = QtWidgets.QVBoxLayout(filter_card)
        filter_card_layout.setContentsMargins(16, 12, 16, 12)
        filter_card_layout.addWidget(label('筛选条件', 'sectionTitle'))

        filter_layout.addWidget(QtWidgets.QLabel("员工:"))
        self.employee_combo = QtWidgets.QComboBox()
        self.employee_combo.addItem("全部", "")
        try:
            for emp in EmployeeService.list_all():
                self.employee_combo.addItem(
                    f"{emp.employee_id} - {emp.name}",
                    emp.employee_id,
                )
        except Exception:
            pass
        filter_layout.addWidget(self.employee_combo)

        filter_layout.addWidget(QtWidgets.QLabel("类型:"))
        self.check_type_combo = QtWidgets.QComboBox()
        self.check_type_combo.addItem("全部", "")
        for value in CheckService.VALID_TYPES:
            self.check_type_combo.addItem(_CHECK_TYPE_LABEL[value], value)
        filter_layout.addWidget(self.check_type_combo)

        today = QtCore.QDate.currentDate()
        filter_layout.addWidget(QtWidgets.QLabel("起始:"))
        self.date_from = QtWidgets.QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        self.date_from.setDate(today)
        filter_layout.addWidget(self.date_from)

        filter_layout.addWidget(QtWidgets.QLabel("截止:"))
        self.date_to = QtWidgets.QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        self.date_to.setDate(today)
        filter_layout.addWidget(self.date_to)

        self.btn_refresh = QtWidgets.QPushButton("刷新")
        self.btn_clear = QtWidgets.QPushButton("清空筛选")
        self.btn_adjust = QtWidgets.QPushButton("管理员补签")
        filter_layout.addWidget(self.btn_refresh)
        filter_layout.addWidget(self.btn_clear)
        filter_layout.addWidget(self.btn_adjust)
        filter_layout.addStretch(1)
        filter_card_layout.addLayout(filter_layout)
        layout.addWidget(filter_card)

        # ----- 表格 -----
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.NoEditTriggers
        )
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows
        )
        self.table.verticalHeader().setVisible(False)
        configure_table(self.table)
        layout.addWidget(self.table)

    def _wire_signals(self) -> None:
        self.btn_refresh.clicked.connect(self._refresh_table)
        self.btn_clear.clicked.connect(self._on_clear)
        self.btn_adjust.clicked.connect(self._on_adjust)

    # ----------------------------------------------------------
    # 内部辅助
    # ----------------------------------------------------------

    def _refresh_table(self) -> None:
        """收集筛选条件 → CheckService.list_records → 渲染表格."""
        eid = self.employee_combo.currentData() or None
        ctype = self.check_type_combo.currentData() or None
        d_from = self.date_from.date().toPyDate()
        d_to = self.date_to.date().toPyDate()

        try:
            records = CheckService.list_records(
                date_from=d_from,
                date_to=d_to,
                employee_id=eid,
                check_type=ctype,
            )
        except DateRangeInvalid as e:
            show_error(
                self, "DATE_RANGE_INVALID",
                f"{e} (错误码: DATE_RANGE_INVALID)",
            )
            return
        except CheckTypeInvalid as e:
            show_error(
                self, "CHECK_TYPE_INVALID",
                f"{e} (错误码: CHECK_TYPE_INVALID)",
            )
            return
        self._render_table(records)

    def _render_table(self, records: list) -> None:
        self.table.setRowCount(len(records))
        self.record_summary.setText(f'当前筛选 · {len(records)} 条记录')
        for r, rec in enumerate(records):
            emp = rec.employee
            self.table.setItem(
                r, 0, QtWidgets.QTableWidgetItem(emp.employee_id),
            )
            self.table.setItem(
                r, 1, QtWidgets.QTableWidgetItem(emp.name or ""),
            )
            self.table.setItem(
                r, 2, QtWidgets.QTableWidgetItem(emp.department or ""),
            )
            schedule = getattr(rec, "schedule", None)
            self.table.setItem(r, 3, QtWidgets.QTableWidgetItem(schedule.name if schedule else ""))
            self.table.setItem(
                r, 4,
                QtWidgets.QTableWidgetItem(rec.check_date.isoformat()),
            )
            self.table.setItem(
                r, 5,
                QtWidgets.QTableWidgetItem(
                    rec.check_timestamp.strftime("%H:%M:%S"),
                ),
            )
            self.table.setItem(
                r, 6,
                QtWidgets.QTableWidgetItem(
                    _CHECK_TYPE_LABEL.get(rec.check_type, rec.check_type),
                ),
            )
            self.table.setItem(r, 7, QtWidgets.QTableWidgetItem(_STATUS_LABEL.get(getattr(rec, "status", "normal"), getattr(rec, "status", "normal"))))
            self.table.setItem(r, 8, QtWidgets.QTableWidgetItem(getattr(rec, "anomaly_reason", "") or ""))
            adjusted = getattr(rec, "adjusted_by", None)
            self.table.setItem(r, 9, QtWidgets.QTableWidgetItem(adjusted.username if adjusted else ""))

    def _on_adjust(self) -> None:
        admin = getattr(self.window(), "_admin", None)
        eid = self.employee_combo.currentData()
        if admin is None or not eid:
            show_error(self, "EMPLOYEE_NOT_FOUND", "请先选择员工")
            return
        schedules = ScheduleService.list_for_employee(eid)
        if not schedules:
            show_error(self, "NO_SCHEDULE", "该员工没有绑定班次")
            return
        check_type = self.check_type_combo.currentData() or "check_in"
        schedule_id = schedules[0].id
        try:
            CheckService.admin_adjust(admin.id, eid, check_type, schedule_id)
        except Exception as exc:
            show_error(self, "INTERNAL_ERROR", f"补签失败: {exc}")
            return
        self._refresh_table()

    def _on_clear(self) -> None:
        """G-04: 清空筛选恢复默认 (今天 / 全部) + 刷新."""
        today = QtCore.QDate.currentDate()
        self.date_from.setDate(today)
        self.date_to.setDate(today)
        self.employee_combo.setCurrentIndex(0)
        self.check_type_combo.setCurrentIndex(0)
        self._refresh_table()
