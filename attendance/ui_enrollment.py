"""现场三姿态加密人脸登记对话框（研究支线）。"""
from __future__ import annotations

from typing import Optional

import cv2
from PIL import Image
from PyQt5 import QtCore, QtGui, QtWidgets

from attendance.face_template import FacePose, POSE_PROMPTS, assess_registration_quality
from attendance.face_template_crypto import default_key_path, load_or_create_key
from attendance.services import EmployeeService, FaceTemplateService


class EnrollmentDialog(QtWidgets.QDialog):
    """只填写工号/姓名，按正面、左45°、右45°采集三帧。"""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("新增员工 - 三姿态人脸登记")
        self.resize(760, 560)
        self._cap = None
        self._timer = None
        self._latest_frame = None
        self._pose_index = 0
        self._vectors = {}
        self._build_ui()
        self._refresh_enabled()

    def _build_ui(self):
        self.employee_id = QtWidgets.QLineEdit()
        self.employee_id.setPlaceholderText("6位数字工号")
        self.name = QtWidgets.QLineEdit()
        self.name.setPlaceholderText("员工姓名")
        self.consent = QtWidgets.QCheckBox("我已知悉人脸数据仅用于本地考勤，并同意加密保存")
        self.prompt = QtWidgets.QLabel(POSE_PROMPTS[FacePose.FRONTAL])
        self.prompt.setWordWrap(True)
        self.preview = QtWidgets.QLabel("摄像头预览区")
        self.preview.setMinimumSize(480, 320)
        self.preview.setAlignment(QtCore.Qt.AlignCenter)
        self.status = QtWidgets.QLabel("请先填写工号和姓名，并勾选隐私同意")
        self.open_btn = QtWidgets.QPushButton("打开摄像头")
        self.capture_btn = QtWidgets.QPushButton("采集正脸")
        self.capture_btn.setEnabled(False)
        self.save_btn = QtWidgets.QPushButton("完成登记")
        self.save_btn.setEnabled(False)
        self.cancel_btn = QtWidgets.QPushButton("取消")
        form = QtWidgets.QFormLayout()
        form.addRow("工号*", self.employee_id)
        form.addRow("姓名*", self.name)
        form.addRow("隐私同意*", self.consent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.prompt)
        layout.addWidget(self.preview)
        layout.addWidget(self.status)
        row = QtWidgets.QHBoxLayout()
        for button in (self.open_btn, self.capture_btn, self.save_btn, self.cancel_btn):
            row.addWidget(button)
        layout.addLayout(row)
        self.open_btn.clicked.connect(self._open_camera)
        self.capture_btn.clicked.connect(self._capture)
        self.save_btn.clicked.connect(self._save)
        self.cancel_btn.clicked.connect(self.reject)
        self.consent.stateChanged.connect(self._refresh_enabled)
        self.employee_id.textChanged.connect(self._refresh_enabled)
        self.name.textChanged.connect(self._refresh_enabled)

    def _refresh_enabled(self):
        allowed = bool(self.employee_id.text().strip() and self.name.text().strip() and self.consent.isChecked())
        self.open_btn.setEnabled(allowed and self._cap is None)
        self.capture_btn.setEnabled(allowed and self._cap is not None and self._latest_frame is not None)
        self.save_btn.setEnabled(len(self._vectors) == 3)

    def _open_camera(self):
        self._cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not self._cap.isOpened():
            self._cap = None
            self.status.setText("无法打开摄像头")
            return
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(50)
        self._refresh_enabled()

    def _tick(self):
        if self._cap is None:
            return
        ok, frame = self._cap.read()
        if not ok:
            return
        self._latest_frame = frame
        frame = cv2.flip(frame, 1)
        self._latest_frame = frame
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = QtGui.QImage(rgb.data, rgb.shape[1], rgb.shape[0], rgb.strides[0], QtGui.QImage.Format_RGB888)
        self.preview.setPixmap(QtGui.QPixmap.fromImage(image).scaled(self.preview.size(), QtCore.Qt.KeepAspectRatio))
        self._refresh_enabled()

    def _detect(self, frame):
        import recognition
        return recognition.recognition(frame)

    def _reset_capture_sequence(self, message):
        self._vectors.clear()
        self._pose_index = 0
        self.prompt.setText(POSE_PROMPTS[FacePose.FRONTAL])
        self.capture_btn.setText("采集正脸")
        self.status.setText(message)
        self._refresh_enabled()

    def _capture(self):
        if self._pose_index >= 3:
            self._reset_capture_sequence("已重置，请从正脸开始重新采集")
            return
        if self._latest_frame is None:
            self.status.setText("摄像头尚未提供画面，请先打开摄像头")
            self._refresh_enabled()
            return
        frame = self._latest_frame.copy()
        try:
            boxes = self._detect(frame)
            quality = assess_registration_quality(frame, boxes)
        except Exception as exc:
            self._reset_capture_sequence(f"当前姿态检测失败：{exc}，请从正脸开始重新采集")
            return
        if not quality.ok:
            self._reset_capture_sequence(f"当前姿态不合格：{quality.reason}，请从正脸开始重新采集")
            return
        raw_box = boxes[0]
        if len(raw_box) >= 7:
            raw_box = raw_box[:4]
        elif len(raw_box) >= 5 and isinstance(raw_box[0], str):
            raw_box = raw_box[1:5]
        x1, y1, x2, y2 = [int(float(v)) for v in raw_box]
        crop = frame[max(0, y1):y2, max(0, x1):x2]
        try:
            from facenet.facenet import Facenet
            if not hasattr(self, "_facenet"):
                self._facenet = Facenet()
            vector = self._facenet.extract_embedding(Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)))
        except Exception as exc:
            self._reset_capture_sequence(f"特征提取失败：{exc}，请从正脸开始重新采集")
            return
        pose = (FacePose.FRONTAL, FacePose.LEFT_45, FacePose.RIGHT_45)[self._pose_index]
        self._vectors[pose.value] = vector
        self._pose_index += 1
        if self._pose_index < 3:
            next_pose = (FacePose.FRONTAL, FacePose.LEFT_45, FacePose.RIGHT_45)[self._pose_index]
            self.prompt.setText(POSE_PROMPTS[next_pose])
            labels = {FacePose.LEFT_45: "请左转45度后点击采集", FacePose.RIGHT_45: "请右转45度后点击采集"}
            self.capture_btn.setText(labels[next_pose])
            self.status.setText(f"{pose.value} 已合格，请继续")
        else:
            self.capture_btn.setText("重新采集")
            self.capture_btn.setEnabled(True)
            self.status.setText("三种姿态均已合格，可以完成登记")
        self._refresh_enabled()
        if self._pose_index >= 3:
            self.capture_btn.setEnabled(True)

    def _save(self):
        emp = None
        try:
            emp = EmployeeService.create(employee_id=self.employee_id.text().strip(), name=self.name.text().strip(), department=None, position=None, phone=None, email=None, face_image_path=None, schedule_id=None)
            key = load_or_create_key(default_key_path())
            FaceTemplateService.replace_employee_templates(emp.employee_id, self._vectors, key)
        except Exception as exc:
            if emp is not None:
                try:
                    EmployeeService.delete(emp.employee_id)
                except Exception:
                    pass
            self.status.setText(f"登记失败：{exc}")
            return
        self._close_camera()
        self.accept()

    def _close_camera(self):
        if self._timer:
            self._timer.stop()
            self._timer = None
        if self._cap:
            self._cap.release()
            self._cap = None

    def closeEvent(self, event):
        self._close_camera()
        super().closeEvent(event)
