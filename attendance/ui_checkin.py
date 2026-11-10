"""签到/签退人员管理系统 - 实时签到 Tab (SPEC-001-C §3 CheckInTab / CheckConfirmDialog).

T-303: 工具栏 (打开/关闭相机/开始识别/停止识别) + QLabel 显示画面 + 识别后弹 4 按钮确认.
- 直接 import 现有 recognition.recognition 与 get_name.rec (不复制代码, 原文件哈希不变).
- CheckConfirmDialog: 4 按钮 (签到/签退/中间打卡/取消), 调 CheckService.create_record.
- 错误码按 §6.1, 弹窗统一走 attendance.ui_utils.show_error.
"""

from typing import Optional

import cv2
import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets

import get_name
import recognition
from attendance.services import CheckService, EmployeeService
from attendance.ui_utils import show_error
from attendance.utils import (
    CheckTypeInvalid,
    EmployeeInactive,
    EmployeeNotFound,
)


_EXC_TO_ERROR_CODE = {
    "EmployeeNotFound": "EMPLOYEE_NOT_FOUND",
    "EmployeeInactive": "EMPLOYEE_INACTIVE",
    "CheckTypeInvalid": "CHECK_TYPE_INVALID",
}


class CheckConfirmDialog(QtWidgets.QDialog):
    """签到确认弹窗 (识别出员工后弹出, 4 按钮选择打卡类型)."""

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
        self._build_ui()
        self._wire_signals()

    def _build_ui(self) -> None:
        self.setWindowTitle(f"已识别: {self._name} ({self._employee_id})")
        self.setModal(True)
        self.setFixedSize(400, 200)

        info = QtWidgets.QLabel(
            f"已识别员工: {self._name} ({self._employee_id})\n\n"
            f"请选择打卡类型:"
        )
        info.setAlignment(QtCore.Qt.AlignCenter)
        info.setWordWrap(True)

        self.btn_in = QtWidgets.QPushButton("签到")
        self.btn_out = QtWidgets.QPushButton("签退")
        self.btn_mid = QtWidgets.QPushButton("中间打卡")
        self.btn_cancel = QtWidgets.QPushButton("取消")

        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addWidget(self.btn_in)
        btn_layout.addWidget(self.btn_out)
        btn_layout.addWidget(self.btn_mid)
        btn_layout.addWidget(self.btn_cancel)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(info, 1)
        layout.addLayout(btn_layout)

    def _wire_signals(self) -> None:
        self.btn_in.clicked.connect(
            lambda: self._confirm("check_in")
        )
        self.btn_out.clicked.connect(
            lambda: self._confirm("check_out")
        )
        self.btn_mid.clicked.connect(
            lambda: self._confirm("middle")
        )
        self.btn_cancel.clicked.connect(self.reject)

    def _confirm(self, check_type: str) -> None:
        try:
            record = CheckService.create_record(
                self._employee_id, check_type,
            )
        except (
            EmployeeNotFound,
            EmployeeInactive,
            CheckTypeInvalid,
        ) as e:
            code = _EXC_TO_ERROR_CODE.get(
                type(e).__name__, "CHECK_TYPE_INVALID",
            )
            show_error(self, code, f"{e} (错误码: {code})")
            return
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
        self._build_ui()
        self._wire_signals()

    # ----------------------------------------------------------
    # UI 构造
    # ----------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        # 工具栏
        toolbar = QtWidgets.QHBoxLayout()
        self.btn_open = QtWidgets.QPushButton("打开相机")
        self.btn_start = QtWidgets.QPushButton("开始识别")
        self.btn_stop = QtWidgets.QPushButton("停止识别")
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(False)
        toolbar.addWidget(self.btn_open)
        toolbar.addWidget(self.btn_start)
        toolbar.addWidget(self.btn_stop)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        # 视频画面
        self.video_label = QtWidgets.QLabel("相机未打开")
        self.video_label.setAlignment(QtCore.Qt.AlignCenter)
        self.video_label.setMinimumSize(640, 480)
        self.video_label.setStyleSheet(
            "background-color: #222; color: #888;"
        )
        layout.addWidget(self.video_label, 1)

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
        cap = cv2.VideoCapture(0)
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

    def _close_camera(self) -> None:
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

    # ----------------------------------------------------------
    # 识别控制
    # ----------------------------------------------------------

    def _on_start_clicked(self) -> None:
        if self._camera is None:
            return
        self.flag_recognition = True
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._emit_status("识别中...")

    def _on_stop_clicked(self) -> None:
        self.flag_recognition = False
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self._emit_status("识别已停止")

    def _on_timer_tick(self) -> None:
        if self._camera is None or not self._camera.isOpened():
            return
        ret, frame = self._camera.read()
        if not ret:
            return
        self._show_frame(frame)
        if self.flag_recognition and not self._pending_dialog_open:
            self._do_recognition(frame)

    def _show_frame(self, frame: np.ndarray) -> None:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qimg = QtGui.QImage(
            rgb.data, w, h, bytes_per_line,
            QtGui.QImage.Format_RGB888,
        )
        pixmap = QtGui.QPixmap.fromImage(qimg)
        self.video_label.setPixmap(
            pixmap.scaled(
                self.video_label.size(),
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation,
            )
        )

    def _do_recognition(self, frame: np.ndarray) -> None:
        try:
            boxes = recognition.recognition(frame)
        except Exception as e:
            show_error(
                self, "EMPLOYEE_NOT_FOUND",
                f"识别失败: {e} (错误码: EMPLOYEE_NOT_FOUND)",
            )
            return
        if not boxes:
            QtWidgets.QMessageBox.warning(
                self, "未识别", "人脸不在库中, 无法打卡",
            )
            self._stop_recognition_after_unknown()
            return
        # 取第一个 box: [x1, y1, x2, y2, score, cls, label]
        box = boxes[0][:4]
        try:
            name = get_name.rec(frame, box)
        except Exception as e:
            show_error(
                self, "EMPLOYEE_NOT_FOUND",
                f"特征比对失败: {e} (错误码: EMPLOYEE_NOT_FOUND)",
            )
            return
        if name == "unknown" or not name:
            QtWidgets.QMessageBox.warning(
                self, "未识别", "人脸不在库中, 无法打卡",
            )
            self._stop_recognition_after_unknown()
            return
        # name 来自 get_name.rec 返回的 face_datasets/ 文件 basename (无扩展名),
        # 用 face_image_path 字段反查 DB 找对应员工
        # (原注释"约定为 employee_id"是设计假设错误: 实际 employee_id 是 6 位数字,
        #  file basename 是拼音/中文, 二者不等; 修复后改用 face_image_path 关联)
        try:
            emp = EmployeeService.get_by_face_image_name(name)
        except EmployeeNotFound:
            QtWidgets.QMessageBox.warning(
                self, "未识别",
                f"识别结果 {name} 不在员工库中, 无法打卡",
            )
            self._stop_recognition_after_unknown()
            return
        # 弹确认 dialog
        self._pending_dialog_open = True
        try:
            dlg = CheckConfirmDialog(
                parent=self,
                employee_id=emp.employee_id,
                name=emp.name,
            )
            dlg.exec_()
        finally:
            self._pending_dialog_open = False
        # 弹过 1 次后自动停止识别, 避免连续弹
        self.flag_recognition = False
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

    # ----------------------------------------------------------
    # 未识别分支的统一停止识别 helper (任务 1: 修复弹窗卡死循环)
    # ----------------------------------------------------------

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
        main = self.window()
        if isinstance(main, QtWidgets.QMainWindow):
            main.statusBar().showMessage(message)
