"""当前员工当轮活体试运行；不写考勤记录。"""
from time import monotonic, sleep
from threading import Condition, Event, Thread
import cv2
from PyQt5 import QtCore, QtGui, QtWidgets
from attendance.liveness_pipeline import AsyncFusionPipeline
from attendance.liveness_overlay import draw_chinese_overlay


class BorrowedCapture:
    """借用父窗口相机，但把可能阻塞的 read 放到独立线程。"""
    error = None
    def __init__(self, capture):
        self.capture = capture
        self.sequence = 0
        self.stop = Event()
        self.condition = Condition()
        self.latest = None
        self.thread = Thread(target=self._run, name='liveness-camera-reader', daemon=True)
        self.thread.start()

    def _run(self):
        try:
            while not self.stop.is_set():
                ok, frame = self.capture.read()
                if not ok:
                    self.error = 'camera_error'
                    return
                with self.condition:
                    self.sequence += 1
                    self.latest = (self.sequence, monotonic(), frame)
                    self.condition.notify_all()
        except Exception:
            self.error = 'camera_error'

    def snapshot(self):
        with self.condition:
            return self.latest

    def close(self):
        self.stop.set()
        self.thread.join(timeout=0.5)
        # 不 release：相机所有权仍归 CheckInTab；父 timer 在 dialog 期间已暂停。

    def release(self):
        self.close()


class LivenessDialog(QtWidgets.QDialog):
    def __init__(self, employee_id: str, name: str, capture, parent=None):
        super().__init__(parent)
        self.verified = False
        self.pipeline = self.camera = None
        self.started_at = monotonic()
        self.setWindowTitle(f'三次眨眼活体（试运行）· {name} ({employee_id})')
        self.resize(960, 760)
        layout = QtWidgets.QVBoxLayout(self)
        self.message = QtWidgets.QLabel('请单人面向镜头，按提示完成校准和三次眨眼。照片攻击尚未验收。')
        self.message.setWordWrap(True)
        self.preview = QtWidgets.QLabel()
        self.preview.setMinimumSize(640, 480)
        self.preview.setAlignment(QtCore.Qt.AlignCenter)
        cancel = QtWidgets.QPushButton('取消本次验证')
        cancel.clicked.connect(self.reject)
        layout.addWidget(self.message)
        layout.addWidget(self.preview, 1)
        layout.addWidget(cancel)
        self.timer = QtCore.QTimer(self)
        # 活体阶段不需要 30 FPS 预览；降低 GUI 重绘和相机提交压力。
        self.timer.setInterval(80)
        self.timer.timeout.connect(self._tick)
        try:
            from attendance.services import FaceTemplateService
            from attendance.face_template_crypto import default_key_path, load_or_create_key
            from attendance.liveness_backend import BoundAuxiliary, Landmarks
            from attendance.liveness_research import assess_quality
            vectors = FaceTemplateService.load_employee_vectors(employee_id, load_or_create_key(default_key_path()))
            self.pipeline = AsyncFusionPipeline(Landmarks(), BoundAuxiliary(list(vectors.values())), assess_quality)
            self.pipeline.start()
            self.camera = BorrowedCapture(capture)
            self.timer.start()
        except Exception:
            self.message.setText('无法初始化活体验证（LIVENESS_UNAVAILABLE），未放行。请取消后检查模型和员工模板。')
            self._shutdown()

    def _tick(self):
        try:
            if monotonic() - self.started_at > 90 or self.camera.error:
                self.reject()
                return
            latest = self.camera.snapshot()
            if latest is None:
                return
            frame_id, timestamp, frame = latest
            self.pipeline.submit(frame_id, timestamp, frame)
            snapshot = self.pipeline.snapshot()
            result = snapshot['result']
            # 预览只做一次镜像和降采样，避免高分辨率帧持续占满 GUI 事件循环。
            preview_frame = cv2.resize(frame, (640, 480), interpolation=cv2.INTER_AREA)
            image = draw_chinese_overlay(cv2.flip(preview_frame, 1), result, snapshot['metrics'], snapshot['warming'])
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            height, width, _ = rgb.shape
            qimage = QtGui.QImage(rgb.data, width, height, rgb.strides[0], QtGui.QImage.Format_RGB888).copy()
            self.preview.setPixmap(QtGui.QPixmap.fromImage(qimage).scaled(self.preview.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
            if result is not None and result.status != 'pending':
                if result.status == 'passed':
                    self.verified = True
                    self.accept()
                else:
                    self.message.setText('本次活体未通过（LIVENESS_REJECTED），未放行。取消后重新识别重试。')
                    self._shutdown()
        except Exception:
            self.verified = False
            self.message.setText('活体验证异常（LIVENESS_UNAVAILABLE），未放行。')
            self._shutdown()

    def _shutdown(self):
        self.timer.stop()
        if self.camera is not None:
            self.camera.close()
            self.camera = None
        if self.pipeline is not None:
            self.pipeline.close()
            self.pipeline = None

    def done(self, result):
        self._shutdown()
        if not self.verified:
            result = QtWidgets.QDialog.Rejected
        super().done(result)
