"""签到/签退人员管理系统 - 实时签到 Tab (SPEC-001-C §3 CheckInTab / CheckConfirmDialog).

T-303: 工具栏 (打开/关闭相机/开始识别/停止识别) + QLabel 显示画面 + 识别后弹 4 按钮确认.
- 复用现有 recognition.recognition、加密模板与活体检测，不修改旧识别入口。
- CheckConfirmDialog: 4 按钮 (签到/签退/中间打卡/取消), 调 CheckService.create_record.
- 错误码按 §6.1, 弹窗统一走 attendance.ui_utils.show_error.
"""

from dataclasses import replace
from typing import TYPE_CHECKING, Optional

import cv2
import numpy as np
from PIL import Image
from PyQt5 import QtCore, QtGui, QtWidgets

import recognition
from attendance.services import CheckService, EmployeeService, ScheduleService
from attendance.checkin_location import decide_checkin_location
from attendance.windows_location import WindowsLocationSource
from attendance.location_worker import LocationWorker
from attendance.recognition_results import RecognitionResult, recognize_faces
from attendance.face_template_crypto import default_key_path, load_or_create_key
from attendance.ui_utils import show_error
from attendance.ui_theme import label, prepare_dialog
from attendance.recognition_worker import RecognitionWorker
from attendance.utils import (
    CheckTypeInvalid,
    EmployeeInactive,
    EmployeeNotFound,
    InternalError,
)


if TYPE_CHECKING:
    from attendance.liveness_research import LivenessResearch


_PASSIVE_LIVENESS_LABEL = '普通模式：被动活体检测'

_EXC_TO_ERROR_CODE = {
    "EmployeeNotFound": "EMPLOYEE_NOT_FOUND",
    "EmployeeInactive": "EMPLOYEE_INACTIVE",
    "CheckTypeInvalid": "CHECK_TYPE_INVALID",
}


class CheckConfirmDialog(QtWidgets.QDialog):
    """签到确认弹窗 (识别出员工后弹出, 4 按钮选择打卡类型)."""

    # 测试和部署可替换为模拟定位源；默认使用 Windows 定位。
    LOCATION_SOURCE_FACTORY = WindowsLocationSource

    # 成功打卡后发射: (name, check_type, time_str) → 供父窗口更新 statusBar
    recorded = QtCore.pyqtSignal(str, str, str)

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        employee_id: str = "",
        name: str = "",
    ) -> None:
        super().__init__(parent)
        self._employee_id = employee_id
        self._name = name
        self._schedules = ScheduleService.list_for_employee(employee_id)
        self._selected_schedule_id = None
        self._location_thread = None
        self._location_worker = None
        self._pending_check_type = None
        self._build_ui()
        self._wire_signals()

    def _build_ui(self) -> None:
        self.setWindowTitle(f"已识别: {self._name} ({self._employee_id})")
        self.setModal(True)

        info = QtWidgets.QLabel(
            f"已识别员工: {self._name} ({self._employee_id})\n\n"
            f"请选择打卡类型:"
        )
        info.setAlignment(QtCore.Qt.AlignCenter)
        info.setWordWrap(True)
        self.schedule_combo = QtWidgets.QComboBox()
        self.schedule_combo.addItems([schedule.name for schedule in self._schedules])
        self.schedule_combo.setVisible(len(self._schedules) > 1)
        if self._schedules:
            self._selected_schedule_id = self._schedules[0].id
        self.schedule_combo.currentIndexChanged.connect(
            lambda index: self._set_schedule(index)
        )

        self.btn_in = QtWidgets.QPushButton("签到")
        self.btn_out = QtWidgets.QPushButton("签退")
        self.btn_cancel = QtWidgets.QPushButton("取消")

        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addWidget(self.btn_in)
        btn_layout.addWidget(self.btn_out)
        btn_layout.addWidget(self.btn_cancel)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(info, 1)
        if len(self._schedules) > 1:
            layout.addWidget(self.schedule_combo)
        layout.addLayout(btn_layout)
        prepare_dialog(self, '确认本次打卡', '识别已完成，请选择本次考勤类型。', self.btn_in, 560)

    def _wire_signals(self) -> None:
        self.btn_in.clicked.connect(
            lambda: self._confirm("check_in")
        )
        self.btn_out.clicked.connect(
            lambda: self._confirm("check_out")
        )
        self.btn_cancel.clicked.connect(self.reject)

    def _set_schedule(self, index):
        if 0 <= index < len(self._schedules):
            self._selected_schedule_id = self._schedules[index].id

    def _confirm(self, check_type: str) -> None:
        if self._location_thread is not None:
            return
        if not self._schedules:
            show_error(self, "NO_SCHEDULE", "员工未绑定启用班次 (错误码: NO_SCHEDULE)")
            return
        self._pending_check_type = check_type
        schedule = next((item for item in self._schedules if item.id == self._selected_schedule_id), None)
        # 未配置地点限制时保持原同步确认路径，避免无谓启动后台线程。
        if schedule is not None and all(
            getattr(schedule, field, None) is None
            for field in ("location_latitude", "location_longitude", "location_radius_m")
        ):
            self._create_record_after_location(check_type)
            return
        for button in (self.btn_in, self.btn_out):
            button.setEnabled(False)
        self._location_thread = QtCore.QThread(self)
        self._location_worker = LocationWorker(self.LOCATION_SOURCE_FACTORY)
        self._location_worker.moveToThread(self._location_thread)
        self._location_thread.started.connect(self._location_worker.run)
        self._location_worker.finished.connect(self._on_location_ready)
        self._location_worker.finished.connect(self._location_thread.quit)
        self._location_worker.finished.connect(self._location_worker.deleteLater)
        self._location_thread.finished.connect(self._location_thread.deleteLater)
        self._location_thread.finished.connect(self._on_location_finished)
        self._location_thread.start()

    @QtCore.pyqtSlot(object)
    def _on_location_ready(self, probe) -> None:
        schedule = next((item for item in self._schedules if item.id == self._selected_schedule_id), None)
        source = type("ProbeSource", (), {"get_current_location": lambda _self: probe.coordinate})()
        location = decide_checkin_location(schedule, source)
        if not location.allowed:
            code = location.status.upper()
            messages = {"outside_radius": "当前不在班次签到地点范围内", "location_unavailable": "无法获取当前签到位置", "invalid_location_config": "班次地点配置无效"}
            show_error(self, code, f"{messages.get(location.status, location.status)} (错误码: {code})")
            return
        self._create_record_after_location(self._pending_check_type)

    def _on_location_finished(self) -> None:
        self._location_thread = None
        self._location_worker = None
        for button in (self.btn_in, self.btn_out):
            button.setEnabled(True)

    def _create_record_after_location(self, check_type: str, confirmed_early_leave: bool = False) -> None:
        try:
            record = CheckService.create_record(self._employee_id, check_type, schedule_id=self._selected_schedule_id, confirmed_early_leave=confirmed_early_leave)
        except InternalError as e:
            if "EARLY_LEAVE_CONFIRM_REQUIRED" in str(e) and not confirmed_early_leave:
                answer = QtWidgets.QMessageBox.question(self, "早退确认", "当前时间未到下班时间，确认要提前签退吗？", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
                if answer == QtWidgets.QMessageBox.Yes:
                    return self._create_record_after_location(check_type, True)
                return
            show_error(self, "CHECK_RULE_REJECTED", str(e)); return
        except (EmployeeNotFound, EmployeeInactive, CheckTypeInvalid) as e:
            code = _EXC_TO_ERROR_CODE.get(type(e).__name__, "CHECK_TYPE_INVALID")
            show_error(self, code, f"{e} (错误码: {code})"); return
        time_str = record.check_timestamp.strftime("%H:%M:%S")
        self.recorded.emit(self._name, check_type, time_str)
        self.accept()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """关闭确认框时等待定位线程结束，避免 QThread 被提前销毁。"""
        thread = self._location_thread
        if thread is not None and thread.isRunning():
            thread.quit()
            thread.wait(2000)
        self._location_thread = None
        self._location_worker = None
        event.accept()

    def _legacy_confirm(self, check_type: str) -> None:
        try:
            if not self._schedules:
                show_error(self, "NO_SCHEDULE", "员工未绑定启用班次 (错误码: NO_SCHEDULE)")
                return
            schedule = next((item for item in self._schedules if item.id == self._selected_schedule_id), None)
            location = decide_checkin_location(schedule, self.LOCATION_SOURCE_FACTORY())
            if not location.allowed:
                code = location.status.upper()
                messages = {"outside_radius": "当前不在班次签到地点范围内", "location_unavailable": "无法获取当前签到位置", "invalid_location_config": "班次地点配置无效"}
                show_error(self, code, f"{messages.get(location.status, location.status)} (错误码: {code})")
                return
            record = CheckService.create_record(self._employee_id, check_type, schedule_id=self._selected_schedule_id)
        except (EmployeeNotFound, EmployeeInactive, CheckTypeInvalid) as e:
            code = _EXC_TO_ERROR_CODE.get(type(e).__name__, "CHECK_TYPE_INVALID")
            show_error(self, code, f"{e} (错误码: {code})")
            return
        except InternalError as e:
            message = str(e)
            code = "CHECK_RULE_REJECTED"
            if "EARLY_LEAVE_CONFIRM_REQUIRED" in message:
                answer = QtWidgets.QMessageBox.question(self, "早退确认", "当前时间未到下班时间，确认要提前签退吗？", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
                if answer == QtWidgets.QMessageBox.Yes:
                    try:
                        record = CheckService.create_record(self._employee_id, check_type, schedule_id=self._selected_schedule_id, confirmed_early_leave=True)
                    except InternalError as retry_error:
                        show_error(self, "CHECK_RULE_REJECTED", str(retry_error)); return
                else:
                    return
            elif "NO_SCHEDULE" in message: code = "NO_SCHEDULE"
            elif "SCHEDULE_SELECTION_REQUIRED" in message: code = "SCHEDULE_SELECTION_REQUIRED"
            elif "INVALID_SEQUENCE" in message: code = "INVALID_SEQUENCE"
            elif "DUPLICATE" in message: code = "DUPLICATE"
            elif "TOO_LATE" in message: code = "TOO_LATE"
            show_error(self, code, f"{message} (错误码: {code})"); return
        time_str = record.check_timestamp.strftime("%H:%M:%S")
        self.recorded.emit(self._name, check_type, time_str)
        self.accept()


class CheckInTab(QtWidgets.QWidget):
    """实时签到 Tab - 工具栏 + 摄像头画面 + 识别回调."""

    TIMER_INTERVAL_MS: int = 30

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._camera: Optional[cv2.VideoCapture] = None
        self._timer: Optional[QtCore.QTimer] = None
        self.flag_recognition: bool = False
        self._pending_dialog_open: bool = False  # 防止连续弹 dialog
        self._recognition_thread: Optional[QtCore.QThread] = None
        self._recognition_worker: Optional[RecognitionWorker] = None
        self._recognition_busy = False
        self._recognition_generation = 0
        self._multi_queue: list[RecognitionResult] = []
        self._passive_liveness: Optional[LivenessResearch] = None
        self._multi_processing = False
        self.color_liveness_enabled = False
        self.color_liveness_ratio = 0.85
        self._color_camera_lease = None
        self._color_return_timer = QtCore.QTimer(self)
        self._color_return_timer.setInterval(80)
        self._color_return_timer.timeout.connect(self._return_color_camera)
        self.color_liveness_status = '彩色光活体未启用（试运行开关关闭）'
        self.liveness_enabled = False
        self._build_ui()
        self._wire_signals()

    # ----------------------------------------------------------
    # UI 构造
    # ----------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        intro = QtWidgets.QFrame()
        intro.setObjectName('card')
        intro_layout = QtWidgets.QHBoxLayout(intro)
        intro_layout.setContentsMargins(20, 16, 20, 16)
        intro_text = QtWidgets.QVBoxLayout()
        intro_text.addWidget(label('让今天的到来，有迹可循', 'sectionTitle'))
        intro_text.addWidget(label('打开相机，开始识别，再确认你的签到类型。'))
        intro_layout.addLayout(intro_text, 1)
        self.device_status = label('相机未连接', 'badge')
        intro_layout.addWidget(self.device_status)
        layout.addWidget(intro)
        body = QtWidgets.QHBoxLayout()
        body.setSpacing(16)
        camera_card = QtWidgets.QFrame()
        camera_card.setObjectName('card')
        camera_layout = QtWidgets.QVBoxLayout(camera_card)
        camera_layout.setContentsMargins(16, 16, 16, 16)
        camera_layout.setSpacing(16)
        camera_layout.addWidget(label('实时画面', 'sectionTitle'))
        self.video_label = QtWidgets.QLabel('相机未打开\n\n点击下方「打开相机」，开启今日签到')
        self.video_label.setObjectName('videoCanvas')
        self.video_label.setAlignment(QtCore.Qt.AlignCenter)
        self.video_label.setMinimumSize(480, 320)
        self.video_label.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored)
        camera_layout.addWidget(self.video_label, 1)
        toolbar = QtWidgets.QHBoxLayout()
        self.btn_open = QtWidgets.QPushButton("打开相机")
        self.btn_start = QtWidgets.QPushButton("开始识别")
        self.btn_stop = QtWidgets.QPushButton("停止识别")
        self.btn_start.setObjectName('primary')
        self.btn_stop.setObjectName('danger')
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(False)
        toolbar.addWidget(self.btn_open)
        toolbar.addWidget(self.btn_start)
        toolbar.addWidget(self.btn_stop)
        toolbar.addStretch(1)
        self.flip_preview_check = QtWidgets.QCheckBox('水平翻转')
        self.flip_preview_check.setToolTip('仅翻转预览画面的左右方向，不影响人脸识别；取消可恢复摄像头原始方向。')
        self.flip_preview_check.setChecked(True)
        toolbar.addWidget(self.flip_preview_check)
        camera_layout.addLayout(toolbar)
        body.addWidget(camera_card, 1)
        result_card = QtWidgets.QFrame()
        result_card.setObjectName('card')
        result_card.ensurePolished()
        result_card.setFixedWidth(max(300, result_card.fontMetrics().horizontalAdvance('01  面向镜头，保持光线充足') + 48))
        result_layout = QtWidgets.QVBoxLayout(result_card)
        result_layout.setContentsMargins(20, 24, 20, 24)
        result_layout.setSpacing(16)
        result_layout.addWidget(label('识别结果', 'sectionTitle'))
        result_layout.addWidget(label('等候一次熟悉的相遇', 'eyebrow'))
        self.result_name = label('等待识别', 'resultName')
        self.result_detail = label('识别成功后，这里会显示员工姓名与工号。')
        result_layout.addWidget(self.result_name)
        result_layout.addWidget(self.result_detail)
        self.multi_results = QtWidgets.QListWidget()
        self.multi_results.setObjectName("multiResults")
        self.multi_results.setVisible(False)
        result_layout.addWidget(self.multi_results)
        result_layout.addSpacing(12)
        self.liveness_status = label(_PASSIVE_LIVENESS_LABEL, 'badge')
        result_layout.addWidget(self.liveness_status)
        result_layout.addWidget(label('当前动态', 'sectionTitle'))
        self.activity_label = label('尚未开始识别')
        result_layout.addWidget(self.activity_label)
        result_layout.addStretch(1)
        result_layout.addWidget(label('签到小贴士', 'sectionTitle'))
        result_layout.addWidget(label('01  面向镜头，保持光线充足\n\n02  识别后选择签到或签退\n\n03  下一位请重新开始识别'))
        body.addWidget(result_card)
        layout.addLayout(body, 1)

    def _wire_signals(self) -> None:
        self.btn_open.clicked.connect(self._on_open_close_clicked)
        self.btn_start.clicked.connect(self._on_start_clicked)
        self.btn_stop.clicked.connect(self._on_stop_clicked)

    # ----------------------------------------------------------
    # 相机控制
    # ----------------------------------------------------------

    def _on_open_close_clicked(self) -> None:
        if self._camera is None:
            self._open_camera()
        else:
            self._close_camera()

    def _open_camera(self) -> None:
        try:
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        except TypeError:
            # 兼容仅接受 camera_id 的测试替身；真实 OpenCV 使用上面的 DSHOW 后端。
            cap = cv2.VideoCapture(0)
        # 测试替身及部分后端不实现 set；缓冲区设置失败不应阻断相机打开。
        if hasattr(cap, "set"):
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not cap.isOpened():
            show_error(
                self, "CAMERA_OPEN_FAILED",
                "请检查相机于电脑是否连接正确 "
                "(错误码: CAMERA_OPEN_FAILED)",
            )
            cap.release()
            return
        self._camera = cap
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(self.TIMER_INTERVAL_MS)
        self._timer.timeout.connect(self._on_timer_tick)
        self._timer.start()
        self.btn_open.setText("关闭相机")
        self.btn_start.setEnabled(True)
        self._emit_status("相机已打开")
        self.device_status.setText('相机已连接')

    def _close_camera(self) -> bool:
        if self._color_camera_lease is not None:
            self._emit_status('彩光后台正在归还摄像头，请等待后再关闭。')
            return False
        self._multi_queue.clear()
        self._multi_processing = False
        self._recognition_generation += 1
        self._stop_recognition_thread()
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        if self._camera is not None:
            self._camera.release()
            self._camera = None
        self.flag_recognition = False
        self.btn_open.setText("打开相机")
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.video_label.setText("相机未打开")
        self._emit_status("相机已关闭")
        self.device_status.setText('相机未连接')
        return True

    # ----------------------------------------------------------
    # 识别控制
    # ----------------------------------------------------------

    def _on_start_clicked(self) -> None:
        if self._camera is None or self._color_camera_lease is not None:
            return
        self.flag_recognition = True
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._emit_status("识别中...")
        self.result_name.setText('等待识别')
        self.result_detail.setText('请面向镜头，识别成功后确认打卡类型。')

    def _on_stop_clicked(self) -> None:
        self._multi_queue.clear()
        self._multi_processing = False
        self._recognition_generation += 1
        self.flag_recognition = False
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self._emit_status("识别已停止")

    def _on_timer_tick(self) -> None:
        if self._color_camera_lease is not None or self._camera is None or not self._camera.isOpened():
            return
        ret, frame = self._camera.read()
        if not ret:
            return
        frame = cv2.flip(frame, 1)
        self._show_frame(frame)
        if self.flag_recognition and not self._pending_dialog_open:
            self._submit_recognition(frame)

    def _show_frame(self, frame: np.ndarray) -> None:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qimg = QtGui.QImage(
            rgb.data, w, h, bytes_per_line,
            QtGui.QImage.Format_RGB888,
        )
        if not self.flip_preview_check.isChecked():
            qimg = qimg.mirrored(True, False)
        pixmap = QtGui.QPixmap.fromImage(qimg)
        self.video_label.setPixmap(
            pixmap.scaled(
                self.video_label.size(),
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation,
            )
        )

    def _do_recognition(self, frame: np.ndarray) -> None:
        "保留同步入口，供既有测试和非摄像头调用使用。"
        if self._recognition_busy or self._pending_dialog_open or self._multi_processing:
            return
        try:
            boxes = recognition.recognition(frame)
            results = self._identify_frame_boxes(frame, boxes[:1]) if boxes else []
        except Exception:
            self._stop_recognition_after_unknown()
            QtWidgets.QMessageBox.warning(self, "未识别", "未能完成加密模板识别")
            return
        self._handle_recognition_results(results)

    def _identify_frame_boxes(self, frame, boxes):
        queries = []
        for box in boxes:
            x1, y1, x2, y2 = [int(v) for v in box[:4]]
            crop = frame[max(0, y1):y2, max(0, x1):x2]
            image = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
            if not hasattr(self, "_template_facenet"):
                from facenet.facenet import Facenet
                self._template_facenet = Facenet()
            queries.append((box[:4], self._template_facenet.extract_embedding(image)))
        employees = EmployeeService.list_all(is_active=True)
        key = load_or_create_key(default_key_path())
        results = recognize_faces(queries, [emp.employee_id for emp in employees], key=key)
        return self._apply_passive_liveness(frame, results)

    def _apply_passive_liveness(self, frame, results: list[RecognitionResult]) -> list[RecognitionResult]:
        if self.liveness_enabled or self.color_liveness_enabled or not any(
            result.status == 'matched' for result in results
        ):
            return results
        if self._passive_liveness is None:
            try:
                from attendance.liveness_research import LivenessResearch
                self._passive_liveness = LivenessResearch()
            except Exception:
                return [
                    replace(result, status='liveness_unavailable', employee_id=None, distance=None, pose=None)
                    if result.status == 'matched' else result for result in results
                ]

        checked = []
        for result in results:
            if result.status != 'matched':
                checked.append(result)
                continue
            try:
                status = self._passive_liveness.evaluate(frame, [result.box]).status
                if status not in ('live_candidate', 'spoof_candidate', 'low_confidence', 'low_quality'):
                    status = 'inconclusive'
            except Exception:
                status = 'liveness_unavailable'
            if status == 'live_candidate':
                checked.append(replace(result, status=status))
            else:
                checked.append(replace(result, status=status, employee_id=None, distance=None, pose=None))
        return checked

    def _submit_recognition(self, frame: np.ndarray) -> None:
        if self._recognition_busy:
            return
        self._recognition_busy = True
        generation = self._recognition_generation
        self._emit_status('正在分析画面...')
        thread = QtCore.QThread(self)
        worker = RecognitionWorker(
            frame.copy(), recognition.recognition, None, generation,
            batch_identify=self._identify_frame_boxes,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.completed.connect(self._on_worker_finished)
        worker.errored.connect(self._on_worker_failed)
        worker.finished.connect(thread.quit, QtCore.Qt.DirectConnection)
        worker.failed.connect(thread.quit, QtCore.Qt.DirectConnection)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_worker_thread_finished)
        self._recognition_thread = thread
        self._recognition_worker = worker
        thread.start()

    @QtCore.pyqtSlot(int, object)
    def _on_worker_finished(self, generation: int, name) -> None:
        if generation != self._recognition_generation or not self.flag_recognition:
            return
        if isinstance(name, list):
            self._handle_recognition_results(name)
        else:
            self._handle_recognition_name(name)

    def _handle_recognition_results(self, results: list[RecognitionResult]) -> None:
        trial = self.liveness_enabled or self.color_liveness_enabled
        status = 'matched' if trial else 'live_candidate'
        matched = [item for item in results if item.status == status and item.employee_id]
        if len(matched) == 1:
            self._handle_recognition_result(matched[0])
        elif len(matched) > 1:
            self.flag_recognition = False
            self._multi_queue = matched
            self._multi_processing = True
            self.multi_results.clear()
            for item in matched:
                row = QtWidgets.QListWidgetItem(item.employee_id)
                row.setData(QtCore.Qt.UserRole, item.employee_id)
                self.multi_results.addItem(row)
            self.multi_results.setVisible(True)
            QtCore.QTimer.singleShot(0, self._process_next_multi)
        else:
            if not trial:
                statuses = {item.status for item in results}
                for failed in ('liveness_unavailable', 'spoof_candidate', 'low_quality', 'low_confidence', 'inconclusive'):
                    if failed in statuses:
                        self._show_passive_liveness_failure(failed)
                        return
            self._handle_recognition_name('unknown')

    def _handle_recognition_result(self, result: RecognitionResult) -> None:
        self._handle_recognition_name(result.employee_id, passive_verified=result.status == 'live_candidate')

    def _show_passive_liveness_failure(self, status: str) -> None:
        messages = {
            'liveness_unavailable': '活体检测暂不可用，未放行，请重新开始识别。',
            'spoof_candidate': '未通过真人检测，请本人面向镜头后重新开始识别。',
        }
        message = messages.get(status, '未能确认活体，请正对镜头、调整光线后重新开始识别。')
        self._stop_recognition_after_unknown()
        self.result_name.setText('活体未通过')
        self.result_detail.setText(message)
        self._emit_status(message)

    def _process_next_multi(self):
        if self._multi_queue:
            self._handle_recognition_result(self._multi_queue.pop(0))
        else:
            self._multi_processing = False
            self._stop_recognition_after_unknown()

    def _on_multi_result_selected(self, item):
        # 兼容旧调用：现在多人结果不再通过列表选择。
        employee_id = item.data(QtCore.Qt.UserRole)
        if employee_id:
            return

    def _on_worker_failed(self, generation: int, message: str) -> None:
        if generation != self._recognition_generation or not self.flag_recognition:
            return
        show_error(
            self, 'EMPLOYEE_NOT_FOUND',
            f'识别失败: {message} (错误码: EMPLOYEE_NOT_FOUND)',
        )

    @QtCore.pyqtSlot()
    def _on_worker_thread_finished(self) -> None:
        if self.sender() is not self._recognition_thread:
            return
        self._recognition_busy = False
        self._recognition_thread = None
        self._recognition_worker = None

    def _stop_recognition_thread(self) -> None:
        thread = self._recognition_thread
        if thread is not None and thread.isRunning():
            thread.quit()
            thread.wait()
        self._recognition_busy = False
        self._recognition_thread = None
        self._recognition_worker = None

    def set_liveness_enabled(self, enabled: bool) -> bool:
        if self._camera is not None or self._recognition_busy or self._pending_dialog_open or self._multi_processing:
            return False
        if enabled and self.color_liveness_enabled:
            return False
        self.liveness_enabled = bool(enabled)
        self.liveness_status.setText('三次眨眼活体已启用（试运行）' if enabled else _PASSIVE_LIVENESS_LABEL)
        return True

    def set_color_liveness_ratio(self, ratio: float) -> bool:
        if not isinstance(ratio, (int, float)) or not 0.50 <= float(ratio) <= 1.00:
            return False
        self.color_liveness_ratio = float(ratio)
        return True

    def set_color_liveness_enabled(self, enabled: bool) -> bool:
        if self._camera is not None or self._recognition_busy or self._pending_dialog_open or self._multi_processing:
            return False
        if enabled and self.liveness_enabled:
            return False
        self.color_liveness_enabled = bool(enabled)
        self.liveness_status.setText('彩色光活体已启用（试运行）' if enabled else _PASSIVE_LIVENESS_LABEL)
        return True

    def _verify_color_liveness(self, employee) -> bool:
        from attendance.ui_color_liveness import ColorLivenessDialog
        if self._camera is None or self._color_camera_lease is not None:
            return False
        self._stop_recognition_thread()
        timer, camera = self._timer, self._camera
        if timer is not None:
            timer.stop()
        dialog = None
        accepted = False
        stopped = True
        try:
            dialog = ColorLivenessDialog(employee.employee_id, employee.name, camera, self, min_color_ratio=self.color_liveness_ratio)
            self._color_camera_lease = (dialog, camera, timer)
            accepted = dialog.exec_() == QtWidgets.QDialog.Accepted and dialog.verified
        except Exception:
            self._emit_status('无法完成彩色光活体验证（COLOR_LIVENESS_UNAVAILABLE），未放行。')
        finally:
            if dialog is not None:
                stopped = dialog._shutdown()
            if stopped:
                if dialog is not None:
                    self._return_color_camera()
                elif timer is not None and timer is self._timer and camera is self._camera:
                    timer.start()
            else:
                self._multi_queue.clear()
                self._multi_processing = False
                self.btn_open.setEnabled(False)
                self.btn_start.setEnabled(False)
                self._emit_status('彩光已停止，正在等待后台归还摄像头。')
                self._color_return_timer.start()
        return accepted and stopped

    def _return_color_camera(self) -> None:
        if self._color_camera_lease is None:
            self._color_return_timer.stop()
            return
        dialog, camera, timer = self._color_camera_lease
        if not dialog._shutdown():
            return
        self._color_camera_lease = None
        self._color_return_timer.stop()
        dialog.deleteLater()
        if timer is not None and timer is self._timer and camera is self._camera:
            timer.start()
        self.btn_open.setEnabled(True)
        if not self._pending_dialog_open and self._camera is not None:
            self.btn_start.setEnabled(True)
            self._emit_status('摄像头已归还，可重新识别。')

    def _verify_liveness(self, employee):
        from attendance.ui_liveness import LivenessDialog
        if self._camera is None:
            return False
        self._stop_recognition_thread()
        timer = self._timer
        if timer is not None:
            timer.stop()
        dialog = None
        try:
            dialog = LivenessDialog(employee.employee_id, employee.name, self._camera, self)
            return dialog.exec_() == QtWidgets.QDialog.Accepted and dialog.verified
        except Exception:
            show_error(self, 'LIVENESS_UNAVAILABLE', '无法完成活体验证，未放行，请重新识别。')
            return False
        finally:
            if dialog is not None:
                dialog._shutdown()
            if timer is not None and self._camera is not None:
                timer.start()

    def _handle_recognition_name(self, name: str, *, passive_verified: bool = False) -> None:
        if name == 'unknown' or not name:
            # 先停掉识别再显示模态弹窗：QMessageBox.warning 会继续处理
            # QTimer 事件；若延后停止，定时器会在弹窗期间反复提交识别任务。
            self._stop_recognition_after_unknown()
            QtWidgets.QMessageBox.warning(self, '未识别', '人脸不在库中, 无法打卡')
            return
        if not (self.liveness_enabled or self.color_liveness_enabled or passive_verified):
            self._show_passive_liveness_failure('inconclusive')
            return
        try:
            emp = EmployeeService.get(name)
        except EmployeeNotFound:
            # 同上：必须在进入模态弹窗前关闭识别，避免未知人脸持续弹窗。
            self._stop_recognition_after_unknown()
            QtWidgets.QMessageBox.warning(self, '未识别', f'识别结果 {name} 不在员工库中, 无法打卡')
            return
        self.result_name.setText(emp.name)
        self.result_detail.setText(f'工号 · {emp.employee_id}\n请在弹窗中确认打卡类型。')
        self._pending_dialog_open = True
        self.flag_recognition = False
        try:
            if self.color_liveness_enabled:
                verified = self._verify_color_liveness(emp)
            else:
                verified = not self.liveness_enabled or self._verify_liveness(emp)
            if verified and (self.liveness_enabled or self.color_liveness_enabled):
                try:
                    verified = EmployeeService.get(emp.employee_id).is_active
                except Exception:
                    verified = False
            if verified:
                dlg = CheckConfirmDialog(parent=self, employee_id=emp.employee_id, name=emp.name)
                dlg.recorded.connect(self._on_recorded)
                dlg.exec_()
            else:
                self.result_detail.setText('本次活体未通过或已取消，未进入打卡确认。')
        finally:
            self._pending_dialog_open = False
        if self._multi_processing:
            QtCore.QTimer.singleShot(0, self._process_next_multi)
            return
        self.flag_recognition = False
        self.btn_start.setEnabled(self._color_camera_lease is None)
        self.btn_stop.setEnabled(False)

    # ----------------------------------------------------------
    # 未识别分支的统一停止识别 helper (任务 1: 修复弹窗卡死循环)
    # ----------------------------------------------------------

    def _on_recorded(self, name: str, check_type: str, time_str: str) -> None:
        type_text = {'check_in': '签到', 'check_out': '签退', 'middle': '中间打卡'}.get(check_type, check_type)
        self.result_name.setText(name)
        self.result_detail.setText(f'{type_text}成功 · {time_str}')
        self._emit_status(f'{name} · {type_text}成功 · {time_str}')

    def _stop_recognition_after_unknown(self) -> None:
        """未识别分支统一调用: 停识别 + 状态栏反馈.

        防止 L255/L270/L278 三处 warning 早退路径不重置 flag_recognition,
        触发 30ms timer 循环弹窗. (关联决策 005 沉淀的 L-005)
        """
        self.flag_recognition = False
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self._emit_status(
            "未识别, 已停止识别, 需重新点「开始识别」继续"
        )

    # ----------------------------------------------------------
    # 状态栏反馈 (供 MainWindow 注入回调)
    # ----------------------------------------------------------

    def _emit_status(self, message: str) -> None:
        """把状态消息推给父窗口的 statusBar, 若父是 QMainWindow."""
        self.activity_label.setText(message)
        main = self.window()
        if isinstance(main, QtWidgets.QMainWindow):
            main.statusBar().showMessage(message)
