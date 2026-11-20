"""彩光窗口只绘制预览和反馈，不读相机、不运行推理。"""
from time import monotonic
from typing import Optional

from attendance.color_failure_log import append_color_failure

import cv2
from PyQt5 import QtCore, QtGui, QtWidgets

from attendance.color_light_controller import ScreenColorController
from attendance.color_light_liveness import ColorLightConfig
from attendance.color_liveness_worker import ColorLivenessWorker
from attendance.face_template_crypto import default_key_path, load_or_create_key
from attendance.services import FaceTemplateService


_COLORS = {"white": "白光", "red": "红光", "green": "绿光", "blue": "蓝光"}
_BACKGROUNDS = {"off": "", "white": "white", "red": "#f02020", "green": "#20d968", "blue": "#2463d4"}
_QUALITY_LABELS = {
    'face_too_small': '脸部太小', 'too_dark': '过暗', 'too_bright': '过亮',
    'blurry': '模糊', 'other_quality': '其他画质问题',
}
_QUALITY_HINTS = {
    'face_too_small': '请靠近一点', 'too_dark': '请增加面部照明',
    'too_bright': '请减少面部直射光', 'blurry': '请正对镜头并保持稳定',
    'other_quality': '请调整光线并保持人脸清晰',
}
_STATUS_LABELS = {'passed': '通过', 'rejected': '未通过', 'timeout': '超时', 'error': '异常', 'pending': '进行中'}
_MESSAGES = {
    'COLOR_QUALITY_SKIPPED': '本帧画质不足，已跳过，继续采样',
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


def choose_environment_light(parent=None):
    dialog = QtWidgets.QDialog(parent)
    dialog.setWindowTitle('选择测试环境')
    layout = QtWidgets.QVBoxLayout(dialog)
    layout.addWidget(QtWidgets.QLabel('请选择当前环境灯光，并在测试期间保持不变：'))
    group = QtWidgets.QButtonGroup(dialog)
    choices = [('normal', '正常灯光'), ('off', '关灯'), ('other', '其他/不确定')]
    buttons = []
    for value, text in choices:
        button = QtWidgets.QRadioButton(text)
        button.setProperty('environment_light', value)
        group.addButton(button)
        layout.addWidget(button)
        buttons.append(button)
    buttons[0].setChecked(True)
    actions = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
    actions.accepted.connect(dialog.accept)
    actions.rejected.connect(dialog.reject)
    layout.addWidget(actions)
    if dialog.exec_() != QtWidgets.QDialog.Accepted:
        return None
    return group.checkedButton().property('environment_light')


class ColorLivenessDialog(QtWidgets.QDialog):
    def __init__(self, employee_id: str, name: str, capture, parent=None, *, min_color_ratio: float = 0.85,
                 environment_light: str = 'unknown'):
        super().__init__(parent)
        self.employee_id = employee_id
        self.environment_light = environment_light if environment_light in {'normal', 'off', 'other'} else 'unknown'
        self.verified = False
        self._controller = ScreenColorController()
        self._started = None
        self._preview_id = 0
        self._failure_reason = None
        self._failure_logged = False
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
            if result.reason == 'COLOR_SAMPLES_INSUFFICIENT':
                hint = _QUALITY_HINTS.get(result.metrics.get('quality_issue'))
                if hint:
                    progress += f'\n{hint}'
            self._show_failure(result.reason or "COLOR_INTERNAL_ERROR", progress, snap)
            return
        if snap["error"] and snap["error"] != "COLOR_PERFORMANCE_INSUFFICIENT":
            self._show_failure(snap["error"], progress, snap)
            return
        if expired:
            self._show_failure("COLOR_TIMEOUT", progress, snap)
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
                self._show_failure("COLOR_DEVICE_ERROR", progress, snap)
                return
        waiting = snap["error"] or result.reason
        detail = (f" · {_MESSAGES.get(waiting, '等待有效帧')}（{waiting}）" if waiting else "")
        if waiting == 'COLOR_QUALITY_SKIPPED':
            hint = _QUALITY_HINTS.get(result.metrics.get('quality_issue'))
            if hint:
                detail += f' · {hint}'
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

    def diagnostics_text(self) -> str:
        result = self._worker.snapshot()['result']
        reason = self._failure_reason or result.reason
        status = result.status
        if self._failure_reason == 'COLOR_TIMEOUT':
            status = 'timeout'
        elif self._failure_reason and self._failure_reason != result.reason:
            status = 'error'
        lines = [f'检测结果：{_STATUS_LABELS[status]}（{reason or "—"}） · 合格帧比例 {self._config.min_color_ratio:.0%}']

        def points(value):
            return '—' if value is None else f'{value * 100:+.2f} 个百分点'

        for row in result.metrics.get('color_diagnostics', []):
            skips = '、'.join(f'{label} {row["quality_skips"][key]}'
                             for key, label in _QUALITY_LABELS.items() if key in row['quality_skips'])
            lines.append(f'第{row["cycle"]}轮 {_COLORS[row["color"]]} · 有效 {row["samples"]} · 达标 {row["hits"]}'
                         f' · 位移丢弃 {row["motion_skips"]} · 画质丢弃 {skips or "无"}'
                         f' · 目标通道增量 中位数 {points(row["delta_median"])} / 峰值 {points(row["delta_peak"])}')
        return '\n'.join(lines)

    def log_failure(self, reason: str, snapshot: Optional[dict] = None) -> None:
        if self._failure_logged:
            return
        self._failure_logged = True
        append_color_failure(reason, min_color_ratio=self._config.min_color_ratio,
                             snapshot=snapshot if snapshot is not None else self._worker.snapshot(),
                             config=self._config, environment_light=self.environment_light)

    def _show_failure(self, reason, progress, snapshot):
        self._failure_reason = reason
        self._shutdown()
        self.log_failure(reason, snapshot)
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
        if not self._failure_logged and not self.verified:
            snap = self._worker.snapshot()
            outcome = snap['result']
            if outcome.status in ('rejected', 'timeout', 'error') and outcome.reason != 'COLOR_CANCELLED':
                self.log_failure(outcome.reason or 'COLOR_INTERNAL_ERROR', snap)
        if not self.verified or not stopped:
            result = QtWidgets.QDialog.Rejected
        super().done(result)
