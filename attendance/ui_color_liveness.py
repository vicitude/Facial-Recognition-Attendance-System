"""彩光窗口只绘制预览和反馈，不读相机、不运行推理。"""
from time import monotonic

import cv2
from PyQt5 import QtCore, QtGui, QtWidgets

from attendance.color_light_controller import ScreenColorController
from attendance.color_light_liveness import ColorLightConfig
from attendance.color_liveness_worker import ColorLivenessWorker
from attendance.face_template_crypto import default_key_path, load_or_create_key
from attendance.services import FaceTemplateService


_COLORS = {"white": "白光", "red": "红光", "green": "绿光", "blue": "蓝光"}
_BACKGROUNDS = {"off": "", "white": "white", "red": "#f02020", "green": "#20d968", "blue": "#2463d4"}
_MESSAGES = {
    "COLOR_WAITING_FACE": "未检测到人脸，请正面对准摄像头",
    "COLOR_QUALITY_REJECTED": "人脸数量或画面质量不符合要求",
    "COLOR_MOTION_SKIPPED": "本帧位移过大，已跳过，继续采样",
    "COLOR_PASSIVE_REJECTED": "被动活体证据不足",
    "COLOR_IDENTITY_REJECTED": "未能确认是当前员工",
    "COLOR_PERFORMANCE_INSUFFICIENT": "采集或分析未跟上，已跳过慢帧",
    "COLOR_SAMPLES_INSUFFICIENT": "本色照明结束，有效样本不足",
    "COLOR_UNRESPONSIVE": "未检测到足够稳定的屏幕光响应",
    "COLOR_CAMERA_READ_FAILED": "摄像头读取失败",
    "COLOR_MODEL_UNAVAILABLE": "模型未能加载",
    "COLOR_DEVICE_ERROR": "彩光显示未能确认",
    "COLOR_TIMEOUT": "检测超时",
}


class ColorLivenessDialog(QtWidgets.QDialog):
    def __init__(self, employee_id: str, name: str, capture, parent=None, *, min_color_ratio: float = 0.85):
        super().__init__(parent)
        self.employee_id = employee_id
        self.verified = False
        self._controller = ScreenColorController()
        self._started = None
        self._preview_id = 0
        key = load_or_create_key(default_key_path())
        templates = FaceTemplateService.load_employee_vectors(employee_id, key)
        self._config = ColorLightConfig(enabled=True, min_color_ratio=float(min_color_ratio))
        self._worker = ColorLivenessWorker(employee_id, capture, templates.values(), config=self._config)
        self._build_ui(name)
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

    def _build_ui(self, name):
        self.setWindowTitle(f"彩色光活体试运行 · {name} ({self.employee_id})")
        self.setWindowState(self.windowState() | QtCore.Qt.WindowMaximized)
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        self.message = QtWidgets.QLabel("请保持正面对准摄像头，不需要眨眼或转头")
        self.message.setAlignment(QtCore.Qt.AlignCenter)
        self.message.setWordWrap(True)
        self.message.setStyleSheet("font-size: 22px; font-weight: bold;")
        root.addWidget(self.message)
        self.preview = QtWidgets.QLabel("等待摄像头画面")
        self.preview.setAlignment(QtCore.Qt.AlignCenter)
        self.preview.setMinimumSize(480, 360)
        self.preview.setStyleSheet("border: 3px solid white;")
        root.addWidget(self.preview, 1, QtCore.Qt.AlignCenter)
        self.cancel_button = QtWidgets.QPushButton("取消本次检测")
        self.cancel_button.clicked.connect(self.reject)
        root.addWidget(self.cancel_button)

    def _apply_color(self, color):
        self._controller.set_color(color)
        background = _BACKGROUNDS[color]
        self.setStyleSheet(f"QDialog {{ background: {background}; }}" if background else "")
        self.repaint()
        if self._controller.current_color() != color:
            raise RuntimeError("COLOR_DEVICE_ERROR")

    def _refresh(self):
        if not self.isVisible():
            return
        if self._started is None:
            self._started = monotonic()
            self._worker.start()
        snap = self._worker.snapshot()
        result = snap["result"]
        progress = (f"白光有效 {result.metrics['baseline_samples']}/{self._config.baseline_frames} · "
                    f"摄像头 {snap['frame_count']} · 已分析 {snap['processed_count']} · 有效 {snap['valid_count']} · 本色达标比例阈值 {self._config.min_color_ratio:.0%}")
        if result.status == "passed" and self._worker.stopped():
            self.verified = True
            self.accept()
            return
        expired = monotonic() - self._started >= self._config.max_session_ms / 1000
        if result.status in ("rejected", "timeout", "error"):
            if result.color in ("red", "green", "blue"):
                metrics = result.metrics
                progress += (f"\n失败颜色：{_COLORS[result.color]} · 本色有效 {metrics['color_samples']} 帧"
                             f" · 色差达标 {metrics['color_hits']} 帧 · 位移丢弃 {metrics['color_motion_skips']} 帧")
            self._show_failure(result.reason or "COLOR_INTERNAL_ERROR", progress)
            return
        if snap["error"] and snap["error"] != "COLOR_PERFORMANCE_INSUFFICIENT":
            self._show_failure(snap["error"], progress)
            return
        if expired:
            self._show_failure("COLOR_TIMEOUT", progress)
            return
        if result.status == "passed":
            self.message.setText("检测已完成，正在归还摄像头。")
            return
        color = snap["desired_color"]
        if color != self._controller.current_color():
            try:
                self._apply_color(color)
                if not self._worker.acknowledge_color(color):
                    return
            except Exception:
                self._show_failure("COLOR_DEVICE_ERROR", progress)
                return
        waiting = snap["error"] or result.reason
        detail = (f" · {_MESSAGES.get(waiting, '等待有效帧')}（{waiting}）" if waiting else "")
        self.message.setText(f"{_COLORS.get(color, '准备中')} · {progress} · 彩光样本 {result.accepted_samples}{detail}")
        if snap["frame_count"] != self._preview_id and snap["frame"] is not None:
            self._preview_id = snap["frame_count"]
            frame = snap["frame"]
            h, w = frame.shape[:2]
            scale = min(1, 640 / w, 480 / h)
            small = cv2.resize(frame, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
            rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            h, w = rgb.shape[:2]
            image = QtGui.QImage(rgb.data, w, h, rgb.strides[0], QtGui.QImage.Format_RGB888).copy()
            self.preview.setPixmap(QtGui.QPixmap.fromImage(image))

    def _show_failure(self, reason, progress):
        self._shutdown()
        self.message.setText(f"{_MESSAGES.get(reason, '彩光检测未完成')}（{reason}），未放行。\n{progress}")
        self.cancel_button.setText("关闭")

    def _shutdown(self) -> bool:
        self._timer.stop()
        stopped = self._worker.stop()
        if self._controller.current_color() != "off":
            self._controller.set_color("off")
            self.setStyleSheet("")
        return stopped

    def done(self, result):
        stopped = self._shutdown()
        if not self.verified or not stopped:
            result = QtWidgets.QDialog.Rejected
        super().done(result)
