"""班次管理与员工多班次绑定 UI（SPEC-003）。"""
from datetime import time
from typing import Optional
from PyQt5 import QtCore, QtWidgets
from attendance.services import ScheduleService
from attendance.ui_theme import card, configure_table, label, page_header, prepare_dialog
from attendance.ui_utils import show_error
import re


def parse_coordinate_text(text: str, *, latitude: bool) -> float:
    """解析十进制度或度分秒坐标，并校验纬度/经度范围。"""
    raw = text.strip()
    if not raw:
        raise ValueError("坐标不能为空")
    if "至" in raw or "~" in raw or "～" in raw:
        raise ValueError("这里只能填写一个签到中心坐标；范围请用“中心坐标 + 允许半径”表示")
    # 允许复制“北纬：”/“东经：”等文字前缀，但不接受区域范围。
    raw = re.sub(r"^(?:北纬|南纬|东经|西经|纬度|经度)\s*[:：]\s*", "", raw, flags=re.IGNORECASE)
    try:
        value = float(raw)
    except ValueError:
        match = re.fullmatch(
            r"([+-]?\d+(?:\.\d+)?)\s*[°º]\s*"
            r"(\d+(?:\.\d+)?)?\s*[′'’]?\s*"
            r"(\d+(?:\.\d+)?)?\s*[″\"]?\s*([东西南北EWNS])?", 
            raw,
            re.IGNORECASE,
        )
        if not match:
            raise ValueError("坐标格式应为十进制度或度分秒")
        degrees = float(match.group(1))
        minutes = float(match.group(2) or 0)
        seconds = float(match.group(3) or 0)
        if minutes >= 60 or seconds >= 60:
            raise ValueError("度分秒中的分和秒必须小于60")
        value = abs(degrees) + minutes / 60 + seconds / 3600
        direction = (match.group(4) or "").upper()
        if degrees < 0:
            value = -value
        if direction in {"S", "W", "南", "西"}:
            value = -abs(value)
        elif direction in {"N", "E", "北", "东"}:
            value = abs(value)
    limit = 90 if latitude else 180
    if not -limit <= value <= limit:
        raise ValueError(("纬度" if latitude else "经度") + f"必须在{-limit}到{limit}之间")
    return value


def _qtime(value):
    return QtCore.QTime(value.hour, value.minute) if value else QtCore.QTime(9, 0)


def _time(qt):
    return time(qt.hour(), qt.minute())


class ScheduleDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, schedule=None):
        super().__init__(parent); self.schedule = schedule
        self.name_edit = QtWidgets.QLineEdit(); self.name_edit.setMaxLength(50)
        self.work_start = QtWidgets.QTimeEdit(); self.work_start.setDisplayFormat("HH:mm")
        self.work_end = QtWidgets.QTimeEdit(); self.work_end.setDisplayFormat("HH:mm")
        self.check_in_start = QtWidgets.QTimeEdit(); self.check_in_start.setDisplayFormat("HH:mm")
        self.late_end = QtWidgets.QTimeEdit(); self.late_end.setDisplayFormat("HH:mm")
        self.check_out_end = QtWidgets.QTimeEdit(); self.check_out_end.setDisplayFormat("HH:mm")
        self.location_name = QtWidgets.QLineEdit(); self.location_name.setPlaceholderText("签到地点名称（可选）")
        self.location_latitude = QtWidgets.QLineEdit(); self.location_latitude.setPlaceholderText("如 39.9042 或 39°54′15″N")
        self.location_longitude = QtWidgets.QLineEdit(); self.location_longitude.setPlaceholderText("如 116.4074 或 116°24′27″E")
        self.location_radius_m = QtWidgets.QDoubleSpinBox(); self.location_radius_m.setRange(0, 100000); self.location_radius_m.setDecimals(1); self.location_radius_m.setSuffix(" m")
        self.active = QtWidgets.QCheckBox("启用"); self.active.setChecked(True)
        form = QtWidgets.QFormLayout()
        for text, widget in (("班次名称*", self.name_edit), ("上班时间*", self.work_start), ("下班时间*", self.work_end), ("签到起始*", self.check_in_start), ("迟到截止*", self.late_end), ("签退截止*", self.check_out_end), ("签到地点", self.location_name), ("地点纬度", self.location_latitude), ("地点经度", self.location_longitude), ("允许半径", self.location_radius_m)):
            form.addRow(text, widget)
        form.addRow("", self.active)
        self.btn_save = QtWidgets.QPushButton("保存"); self.btn_cancel = QtWidgets.QPushButton("取消")
        self.btn_save.clicked.connect(self._save); self.btn_cancel.clicked.connect(self.reject)
        buttons = QtWidgets.QHBoxLayout(); buttons.addStretch(); buttons.addWidget(self.btn_save); buttons.addWidget(self.btn_cancel)
        layout = QtWidgets.QVBoxLayout(self); layout.addLayout(form); layout.addLayout(buttons)
        prepare_dialog(self, "班次", "配置签到、迟到与签退时间窗口。", self.btn_save, 520)
        self.setWindowTitle("编辑班次" if schedule else "新增班次")
        if schedule:
            self.name_edit.setText(schedule.name); self.work_start.setTime(_qtime(schedule.work_start)); self.work_end.setTime(_qtime(schedule.work_end)); self.check_in_start.setTime(_qtime(schedule.check_in_start)); self.late_end.setTime(_qtime(schedule.late_end)); self.check_out_end.setTime(_qtime(schedule.check_out_end)); self.location_name.setText(schedule.location_name or ""); self.location_latitude.setText("" if schedule.location_latitude is None else str(schedule.location_latitude)); self.location_longitude.setText("" if schedule.location_longitude is None else str(schedule.location_longitude)); self.location_radius_m.setValue(schedule.location_radius_m or 0); self.active.setChecked(bool(schedule.is_active))

    def values(self):
        return dict(name=self.name_edit.text().strip(), work_start=_time(self.work_start.time()), work_end=_time(self.work_end.time()), check_in_start=_time(self.check_in_start.time()), late_end=_time(self.late_end.time()), check_out_end=_time(self.check_out_end.time()), location_name=self.location_name.text().strip() or None, location_latitude=parse_coordinate_text(self.location_latitude.text(), latitude=True) if self.location_latitude.text().strip() else None, location_longitude=parse_coordinate_text(self.location_longitude.text(), latitude=False) if self.location_longitude.text().strip() else None, location_radius_m=self.location_radius_m.value() or None, duplicate_policy="reject", is_active=self.active.isChecked())

    def _save(self):
        try:
            values = self.values()
        except ValueError as exc:
            show_error(self, "LOCATION_CONFIG_INVALID", f"地点坐标格式无效：{exc} (错误码: LOCATION_CONFIG_INVALID)")
            return
        if not values["name"]:
            show_error(self, "SCHEDULE_TIME_INVALID", "班次名称不能为空 (错误码: SCHEDULE_TIME_INVALID)"); return
        try:
            if self.schedule: ScheduleService.update(self.schedule.id, **values)
            else: ScheduleService.create(**values)
        except Exception as exc:
            show_error(self, "SCHEDULE_TIME_INVALID", f"保存班次失败: {exc} (错误码: SCHEDULE_TIME_INVALID)"); return
        self.accept()


class SchedulesTab(QtWidgets.QWidget):
    COLUMNS = ["ID", "班次名称", "上班", "下班", "签到起始", "迟到截止", "签退截止", "状态"]
    def __init__(self, parent=None):
        super().__init__(parent); self._build_ui(); self._refresh()
    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self); layout.setContentsMargins(0,0,0,0)
        header = page_header("班次管理", "新增、编辑或停用考勤班次。"); layout.addWidget(header)
        bar = QtWidgets.QHBoxLayout(); self.btn_add=QtWidgets.QPushButton("新增班次"); self.btn_edit=QtWidgets.QPushButton("编辑"); self.btn_disable=QtWidgets.QPushButton("停用"); self.btn_refresh=QtWidgets.QPushButton("刷新")
        self.btn_add.setObjectName("primary"); self.btn_disable.setObjectName("danger")
        for b in (self.btn_add,self.btn_edit,self.btn_disable,self.btn_refresh): bar.addWidget(b)
        bar.addStretch(); c=card(); c.setLayout(bar); layout.addWidget(c)
        self.table=QtWidgets.QTableWidget(0,len(self.COLUMNS)); self.table.setHorizontalHeaderLabels(self.COLUMNS); self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows); self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection); configure_table(self.table); layout.addWidget(self.table)
        self.btn_add.clicked.connect(self._add); self.btn_edit.clicked.connect(self._edit); self.btn_disable.clicked.connect(self._disable); self.btn_refresh.clicked.connect(self._refresh)
    def _selected(self):
        rows=self.table.selectionModel().selectedRows(); return int(self.table.item(rows[0].row(),0).text()) if rows else None
    def _refresh(self):
        try: rows=ScheduleService.list_all()
        except Exception as exc: show_error(self,"INTERNAL_ERROR",f"加载班次失败: {exc}"); return
        self.table.setRowCount(len(rows))
        for r,s in enumerate(rows):
            vals=[s.id,s.name,s.work_start.strftime('%H:%M'),s.work_end.strftime('%H:%M'),s.check_in_start.strftime('%H:%M'),s.late_end.strftime('%H:%M'),s.check_out_end.strftime('%H:%M'),"启用" if s.is_active else "停用"]
            for c,v in enumerate(vals): self.table.setItem(r,c,QtWidgets.QTableWidgetItem(str(v)))
    def _add(self):
        if ScheduleDialog(self).exec_()==QtWidgets.QDialog.Accepted: self._refresh()
    def _edit(self):
        sid=self._selected()
        if sid is None: show_error(self,"SCHEDULE_NOT_FOUND","请先选择班次 (错误码: SCHEDULE_NOT_FOUND)"); return
        try: s=ScheduleService.get(sid)
        except Exception as exc: show_error(self,"SCHEDULE_NOT_FOUND",f"加载班次失败: {exc}"); return
        if ScheduleDialog(self,s).exec_()==QtWidgets.QDialog.Accepted: self._refresh()
    def _disable(self):
        sid=self._selected()
        if sid is None: show_error(self,"SCHEDULE_NOT_FOUND","请先选择班次 (错误码: SCHEDULE_NOT_FOUND)"); return
        try: ScheduleService.disable(sid); self._refresh()
        except Exception as exc: show_error(self,"SCHEDULE_NOT_FOUND",f"停用班次失败: {exc} (错误码: SCHEDULE_NOT_FOUND)")


class EmployeeScheduleDialog(QtWidgets.QDialog):
    def __init__(self, employee_id, parent=None):
        super().__init__(parent); self.employee_id=employee_id; self.boxes=[]
        self.setWindowTitle(f"绑定班次 - {employee_id}"); layout=QtWidgets.QVBoxLayout(self); layout.addWidget(QtWidgets.QLabel("可多选班次（时间冲突将由服务层拒绝）"))
        try: schedules=ScheduleService.list_all()
        except Exception: schedules=[]
        for s in schedules:
            cb=QtWidgets.QCheckBox(f"{s.id} - {s.name} ({s.work_start:%H:%M}-{s.work_end:%H:%M})"); cb.setProperty("schedule_id",s.id); self.boxes.append(cb); layout.addWidget(cb)
        try: current={s.id for s in ScheduleService.list_for_employee(employee_id)}
        except Exception: current=set()
        for cb in self.boxes: cb.setChecked(cb.property("schedule_id") in current)
        ok=QtWidgets.QPushButton("保存绑定"); cancel=QtWidgets.QPushButton("取消"); ok.clicked.connect(self._save); cancel.clicked.connect(self.reject); row=QtWidgets.QHBoxLayout(); row.addStretch(); row.addWidget(ok); row.addWidget(cancel); layout.addLayout(row)
    def _save(self):
        ids=[cb.property("schedule_id") for cb in self.boxes if cb.isChecked()]
        try: ScheduleService.bind_employee(self.employee_id, ids)
        except Exception as exc: show_error(self,"SCHEDULE_CONFLICT",f"绑定班次失败: {exc} (错误码: SCHEDULE_CONFLICT)"); return
        self.accept()
