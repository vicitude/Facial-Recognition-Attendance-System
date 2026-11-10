"""人脸库管理界面 (PyQt5)。

功能：
- 员工列表 (来自 face_datasets/ 目录)
- 注册新员工: 输入姓名 + 手动连点 3 次「拍一张」从摄像头采集
- 删除员工: 选中列表项 -> 点「删除」
- 重载人脸库: 触发 ui.py 的识别缓存刷新

不修改 ui.py, 不修改 recognition.py / get_name.py。
由 ui.py 内「人脸库管理」按钮启动 (从 ui.py import + 调 open_face_manager_window)。

依赖：
- PyQt5
- OpenCV (cv2.VideoCapture)
- face_library (本仓库新文件)
"""

from __future__ import annotations

import os
import shutil
from typing import List, Optional

import cv2
from PyQt5 import QtCore, QtGui, QtWidgets

import face_library

# 每个员工采集的照片数 (与用户约定)
PHOTOS_PER_EMPLOYEE = 3


class FaceManagerDialog(QtWidgets.QDialog):
    """人脸库管理对话框 (主窗口)。"""

    # 自定义信号: 重载人脸库后通知 ui.py 刷新识别缓存
    library_reloaded = QtCore.pyqtSignal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("人脸库管理")
        self.resize(900, 600)

        # 摄像头相关
        self._cap: Optional[cv2.VideoCapture] = None
        self._timer: Optional[QtCore.QTimer] = None
        self._captured_frames: List[QtGui.QImage] = []  # 当前注册员工的预览帧
        self._current_register_name: str = ""

        self._build_ui()
        self._wire_signals()
        self._refresh_list()
        # 初始化保存按钮状态 (初始: 无照片 + 无姓名 -> 禁用)
        self._update_save_button_state()

    # ----------------------- UI 构建 -----------------------

    def _build_ui(self):
        """构建界面布局 (左侧列表 + 右侧注册面板)。"""
        root = QtWidgets.QHBoxLayout(self)

        # ===== 左侧: 员工列表 =====
        left = QtWidgets.QVBoxLayout()
        left.addWidget(QtWidgets.QLabel("已注册员工 (face_datasets/):"))
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setMinimumWidth(280)
        left.addWidget(self.list_widget)

        btn_row = QtWidgets.QHBoxLayout()
        self.btn_refresh = QtWidgets.QPushButton("刷新列表")
        self.btn_reload_lib = QtWidgets.QPushButton("重载人脸库")
        self.btn_delete = QtWidgets.QPushButton("删除选中")
        btn_row.addWidget(self.btn_refresh)
        btn_row.addWidget(self.btn_reload_lib)
        btn_row.addWidget(self.btn_delete)
        left.addLayout(btn_row)

        root.addLayout(left)

        # ===== 右侧: 注册新员工 =====
        right = QtWidgets.QVBoxLayout()

        # 姓名输入
        name_row = QtWidgets.QHBoxLayout()
        name_row.addWidget(QtWidgets.QLabel("姓名:"))
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText("输入员工姓名 (作为文件名 basename)")
        name_row.addWidget(self.name_edit)
        right.addLayout(name_row)

        # 摄像头预览
        self.camera_label = QtWidgets.QLabel("摄像头预览区")
        self.camera_label.setMinimumSize(480, 360)
        self.camera_label.setAlignment(QtCore.Qt.AlignCenter)
        self.camera_label.setStyleSheet(
            "QLabel { background-color: #222; color: #aaa; border: 1px solid #555; }"
        )
        right.addWidget(self.camera_label)

        # 拍照按钮 + 进度
        capture_row = QtWidgets.QHBoxLayout()
        self.btn_open_camera = QtWidgets.QPushButton("打开摄像头")
        self.btn_capture = QtWidgets.QPushButton(f"拍一张 (0/{PHOTOS_PER_EMPLOYEE})")
        self.btn_capture.setEnabled(False)
        self.btn_close_camera = QtWidgets.QPushButton("关闭摄像头")
        self.btn_close_camera.setEnabled(False)
        capture_row.addWidget(self.btn_open_camera)
        capture_row.addWidget(self.btn_capture)
        capture_row.addWidget(self.btn_close_camera)
        right.addLayout(capture_row)

        # 已采集预览缩略图
        right.addWidget(QtWidgets.QLabel("已采集预览:"))
        self.thumbnails = QtWidgets.QHBoxLayout()
        thumb_widget = QtWidgets.QWidget()
        thumb_widget.setLayout(self.thumbnails)
        right.addWidget(thumb_widget)

        # 保存 / 取消
        save_row = QtWidgets.QHBoxLayout()
        self.btn_save = QtWidgets.QPushButton("保存注册")
        self.btn_save.setEnabled(False)
        self.btn_cancel = QtWidgets.QPushButton("取消")
        save_row.addStretch()
        save_row.addWidget(self.btn_save)
        save_row.addWidget(self.btn_cancel)
        right.addLayout(save_row)

        right.addStretch()
        root.addLayout(right, stretch=1)

    def _wire_signals(self):
        self.btn_refresh.clicked.connect(self._refresh_list)
        self.btn_reload_lib.clicked.connect(self._on_reload_library)
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        self.btn_open_camera.clicked.connect(self._open_camera)
        self.btn_close_camera.clicked.connect(self._close_camera)
        self.btn_capture.clicked.connect(self._on_capture_clicked)
        self.btn_save.clicked.connect(self._on_save_clicked)
        self.btn_cancel.clicked.connect(self.reject)
        # 关键: 姓名变化也要触发保存按钮 enable 重算
        self.name_edit.textChanged.connect(self._update_save_button_state)

    # ----------------------- 列表 / 重载 / 删除 -----------------------

    def _refresh_list(self):
        """重新扫描 face_datasets/, 更新左侧列表。"""
        self.list_widget.clear()
        paths, names = face_library.load_face_library()
        if not names:
            placeholder = QtWidgets.QListWidgetItem("(人脸库为空)")
            placeholder.setFlags(QtCore.Qt.NoItemFlags)
            self.list_widget.addItem(placeholder)
            return
        for name, path in zip(names, paths):
            item = QtWidgets.QListWidgetItem(name)
            item.setData(QtCore.Qt.UserRole, path)
            item.setToolTip(path)
            self.list_widget.addItem(item)

    def _on_reload_library(self):
        """点「重载人脸库」: 刷新模块缓存 + 通知 ui.py。"""
        paths, names = face_library.reload_face_library()
        QtWidgets.QMessageBox.information(
            self, "已重载",
            f"已重载人脸库, 共 {len(names)} 人:\n" + "\n".join(names[:10]) +
            ("\n..." if len(names) > 10 else ""),
        )
        self.library_reloaded.emit()
        self._refresh_list()

    def _on_delete_clicked(self):
        """删除选中员工的所有人脸图片 (硬删除, 不可恢复)。"""
        item = self.list_widget.currentItem()
        if not item:
            QtWidgets.QMessageBox.warning(self, "提示", "请先选中一个员工")
            return
        path = item.data(QtCore.Qt.UserRole)
        if not path or not os.path.isfile(path):
            QtWidgets.QMessageBox.warning(self, "提示", "该条目无法定位文件")
            return
        name = item.text()
        confirm = QtWidgets.QMessageBox.question(
            self, "确认删除",
            f"确定要删除员工 {name} 的人脸照片吗?\n{path}\n(此操作不可恢复)",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if confirm != QtWidgets.QMessageBox.Yes:
            return
        try:
            os.remove(path)
            QtWidgets.QMessageBox.information(self, "已删除", f"已删除 {name}")
            # 删除后顺手 reload, 让 ui.py 立即生效
            face_library.reload_face_library()
            self.library_reloaded.emit()
            self._refresh_list()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "删除失败", f"{e}")

    # ----------------------- 摄像头 / 拍照 -----------------------

    def _open_camera(self):
        if self._cap is not None:
            return
        self._cap = cv2.VideoCapture(0)
        if not self._cap.isOpened():
            QtWidgets.QMessageBox.warning(self, "打开失败", "无法打开摄像头 (编号 0)")
            self._cap = None
            return
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._on_camera_tick)
        self._timer.start(50)  # 20 FPS 预览
        self.btn_open_camera.setEnabled(False)
        self.btn_close_camera.setEnabled(True)
        self.btn_capture.setEnabled(True)

    def _close_camera(self):
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self.camera_label.clear()
        self.camera_label.setText("摄像头预览区")
        self.btn_open_camera.setEnabled(True)
        self.btn_close_camera.setEnabled(False)
        self.btn_capture.setEnabled(False)

    def _on_camera_tick(self):
        if self._cap is None:
            return
        ret, frame = self._cap.read()
        if not ret:
            return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        q_img = QtGui.QImage(rgb.data, w, h, ch * w, QtGui.QImage.Format_RGB888)
        pix = QtGui.QPixmap.fromImage(q_img).scaled(
            self.camera_label.size(),
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation,
        )
        self.camera_label.setPixmap(pix)
        # 保留最近一帧供「拍一张」使用
        self._latest_frame = frame

    def _on_capture_clicked(self):
        if not hasattr(self, "_latest_frame"):
            QtWidgets.QMessageBox.warning(self, "提示", "摄像头尚未产生画面")
            return
        if len(self._captured_frames) >= PHOTOS_PER_EMPLOYEE:
            return
        # 转 QImage 给缩略图
        frame = self._latest_frame
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        q_img = QtGui.QImage(rgb.data, w, h, ch * w, QtGui.QImage.Format_RGB888)
        self._captured_frames.append(q_img)
        # 更新缩略图 + 按钮文案
        self._refresh_thumbnails()
        taken = len(self._captured_frames)
        self.btn_capture.setText(f"拍一张 ({taken}/{PHOTOS_PER_EMPLOYEE})")
        if taken >= PHOTOS_PER_EMPLOYEE:
            self.btn_capture.setEnabled(False)
            self.btn_capture.setText(f"已完成 ({taken}/{PHOTOS_PER_EMPLOYEE})")
        # 满足条件后允许保存 (统一交给 _update_save_button_state)
        self._update_save_button_state()

    def _update_save_button_state(self):
        """根据 (已采集照片数 + 姓名) 统一决定保存按钮是否可用。

        修复 L-018: 原版只在拍照回调末尾检查, 姓名字段变化时不会重新计算。
        现在通过 textChanged 信号 + 这里统一入口, 任一条件变化都会刷新按钮。
        """
        enough_photos = len(self._captured_frames) >= PHOTOS_PER_EMPLOYEE
        has_name = bool(self.name_edit.text().strip())
        self.btn_save.setEnabled(enough_photos and has_name)

    def _refresh_thumbnails(self):
        # 清空旧缩略图
        while self.thumbnails.count():
            item = self.thumbnails.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        for i, q_img in enumerate(self._captured_frames):
            label = QtWidgets.QLabel()
            label.setFixedSize(120, 90)
            label.setStyleSheet("QLabel { border: 1px solid #888; }")
            pix = QtGui.QPixmap.fromImage(q_img).scaled(
                120, 90,
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation,
            )
            label.setPixmap(pix)
            label.setToolTip(f"第 {i+1} 张")
            self.thumbnails.addWidget(label)

    # ----------------------- 保存注册 -----------------------

    def _on_save_clicked(self):
        name = self.name_edit.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "提示", "请先输入姓名")
            return
        if len(self._captured_frames) < PHOTOS_PER_EMPLOYEE:
            QtWidgets.QMessageBox.warning(
                self, "提示",
                f"需采集 {PHOTOS_PER_EMPLOYEE} 张照片, 当前 {len(self._captured_frames)} 张",
            )
            return
        target_dir = face_library.DEFAULT_DIR
        os.makedirs(target_dir, exist_ok=True)
        # 文件命名: <name>_<idx>.jpg (避免同名冲突; 中文也支持)
        # 若用户提供的 name 已有同名文件, 提示覆盖风险
        existing = [f for f in os.listdir(target_dir)
                    if os.path.splitext(f)[0] == name]
        if existing:
            confirm = QtWidgets.QMessageBox.question(
                self, "确认覆盖",
                f"已存在同名员工 {name} 的 {len(existing)} 张照片, 是否覆盖?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )
            if confirm != QtWidgets.QMessageBox.Yes:
                return
            for old in existing:
                try:
                    os.remove(os.path.join(target_dir, old))
                except Exception:
                    pass

        saved: List[str] = []
        try:
            for i, q_img in enumerate(self._captured_frames, start=1):
                filename = f"{name}_{i}.jpg"
                target_path = os.path.join(target_dir, filename)
                # QImage -> numpy(BGR) -> cv2.imwrite
                q_img.save(target_path, "JPG", quality=95)
                saved.append(target_path)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "保存失败", f"{e}")
            return

        # 重载缓存 + 通知 ui.py
        face_library.reload_face_library()
        self.library_reloaded.emit()
        self._refresh_list()

        # 重置 UI 状态
        self._captured_frames = []
        self.name_edit.clear()
        self._refresh_thumbnails()
        self.btn_capture.setText(f"拍一张 (0/{PHOTOS_PER_EMPLOYEE})")
        self.btn_capture.setEnabled(False)
        # 统一刷新保存按钮状态 (姓名/照片均清空 -> 自动 disable)
        self._update_save_button_state()
        self._close_camera()

        QtWidgets.QMessageBox.information(
            self, "注册成功",
            f"员工 {name} 已注册, 保存 {len(saved)} 张照片到\n{target_dir}",
        )

    # ----------------------- 生命周期 -----------------------

    def closeEvent(self, event):
        self._close_camera()
        super().closeEvent(event)


def open_face_manager_window(parent: Optional[QtWidgets.QWidget] = None):
    """供 ui.py 调用的工厂函数。

    弹出 FaceManagerDialog, 与 ui.py 主窗口通过 library_reloaded 信号联动:
    ui.py 应在收到信号时同步刷新其内部识别缓存。
    """
    dlg = FaceManagerDialog(parent)
    dlg.setModal(False)
    dlg.show()
    return dlg


if __name__ == "__main__":
    # 独立调试入口: python face_manager_ui.py
    import sys
    app = QtWidgets.QApplication(sys.argv)
    face_library.reload_face_library()
    window = FaceManagerDialog()
    window.show()
    sys.exit(app.exec_())