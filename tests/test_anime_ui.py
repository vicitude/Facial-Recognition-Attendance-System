import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets
from attendance.recognition_results import RecognitionResult


class FakeCapture:
    def __init__(self, camera_id):
        self.opened = True

    def isOpened(self):
        return self.opened

    def release(self):
        self.opened = False

    def read(self):
        return False, None


class AnimeUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        if not QtGui.QFontDatabase().families():
            font_path = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / 'msyh.ttc'
            if font_path.exists():
                QtGui.QFontDatabase.addApplicationFont(str(font_path))
        if not QtGui.QFontDatabase().families():
            raise unittest.SkipTest('离屏环境无可用字体，无法验证界面渲染')
        cls.app.setStyle('Fusion')
        from attendance.ui_theme import apply_theme
        apply_theme(cls.app)
        fake_recognition = types.ModuleType('recognition')
        fake_recognition.recognition = lambda frame: [[0, 0, 10, 10]]
        fake_names = types.ModuleType('get_name')
        fake_names.rec = lambda frame, box: 'sample'
        cls.module_patch = patch.dict(sys.modules, {'recognition': fake_recognition, 'get_name': fake_names})
        cls.module_patch.start()
        cls.addClassCleanup(cls.module_patch.stop)
        from attendance.ui_main import MainWindow
        cls.window_type = MainWindow

    def setUp(self):
        from attendance.services import AdminService, CheckService, EmployeeService, ScheduleService
        self.patches = [
            patch.object(EmployeeService, 'list_all', return_value=[]),
            patch.object(CheckService, 'list_records', return_value=[]),
            patch.object(AdminService, 'list_all', return_value=[]),
            patch.object(ScheduleService, 'list_all', return_value=[]),
            patch.object(ScheduleService, 'list_for_employee', return_value=[]),
        ]
        for service_patch in self.patches:
            service_patch.start()
            self.addCleanup(service_patch.stop)
        self.window = self.window_type(types.SimpleNamespace(id=1, username='预览管理员'))
        self.window.show()
        self.app.processEvents()
        self.addCleanup(self.window.close)

    def test_navigation(self):
        self.assertEqual(self.window.tabs.count(), 5)
        self.assertEqual(self.window.navigation.count(), 5)
        self.assertEqual(self.window.navigation.currentRow(), 0)
        for index in range(5):
            self.window.navigation.setCurrentRow(index)
            self.assertEqual(self.window.tabs.currentIndex(), index)
            self.assertEqual(self.window.page_title.text(), self.window.tabs.tabText(index))
            preview_dir = os.environ.get('UI_PREVIEW_DIR')
            if preview_dir:
                destination = Path(preview_dir)
                destination.mkdir(parents=True, exist_ok=True)
                self.assertTrue(self.window.grab().save(str(destination / f'page-{index + 1}.png')))
        self.window.tabs.setCurrentIndex(1)
        self.assertEqual(self.window.navigation.currentRow(), 1)
        self.window.action_admin_management.trigger()
        self.assertEqual(self.window.navigation.currentRow(), 3)

    def test_text_widths(self):
        navigation = self.window.navigation
        for index in range(navigation.count()):
            text_width = navigation.fontMetrics().horizontalAdvance(navigation.item(index).text())
            self.assertGreaterEqual(navigation.viewport().width(), text_width + 24)
        detail = self.window.checkin_tab.result_detail
        self.assertGreaterEqual(detail.width(), detail.fontMetrics().horizontalAdvance('签到成功 · 17:06:16'))

    def assert_dialog_fits(self, dialog):
        dialog.show()
        self.app.processEvents()
        self.assertTrue(dialog.styleSheet())
        self.assertGreaterEqual(dialog.width(), 480)
        controls = dialog.findChildren(QtWidgets.QPushButton) + dialog.findChildren(QtWidgets.QLineEdit)
        for control in controls:
            if not control.isVisible():
                continue
            bounds = QtCore.QRect(control.mapTo(dialog, QtCore.QPoint()), control.size())
            self.assertTrue(dialog.rect().contains(bounds), f'{dialog.windowTitle()}: {control.text()} outside dialog')
            self.assertGreaterEqual(control.height(), control.sizeHint().height())
            if isinstance(control, QtWidgets.QPushButton):
                self.assertGreaterEqual(control.width(), control.fontMetrics().horizontalAdvance(control.text()) + 24)
        preview_dir = os.environ.get('UI_PREVIEW_DIR')
        if preview_dir:
            Path(preview_dir).mkdir(parents=True, exist_ok=True)
            self.assertTrue(dialog.grab().save(str(Path(preview_dir) / f'dialog-{type(dialog).__name__}.png')))

    def test_dialog_layouts(self):
        from attendance.ui_admins import AdminCreateDialog
        from attendance.ui_change_password import ChangePasswordDialog
        from attendance.ui_checkin import CheckConfirmDialog
        from attendance.ui_employees import EmployeeDialog
        from attendance.ui_login import LoginDialog
        from attendance.services import ScheduleService
        admin = types.SimpleNamespace(id=1, username='预览管理员')
        with patch.object(ScheduleService, 'list_all', return_value=[]):
            dialogs = [LoginDialog(), CheckConfirmDialog(employee_id='111111', name='示例员工'),
                       ChangePasswordDialog(admin), AdminCreateDialog(), EmployeeDialog()]
        for dialog in dialogs:
            with self.subTest(dialog=type(dialog).__name__):
                try:
                    self.assert_dialog_fits(dialog)
                finally:
                    dialog.hide()
                    dialog.deleteLater()

    def test_login_authentication(self):
        from attendance.ui_login import LoginDialog
        from attendance.services import AdminService
        from attendance.utils import AuthFailed
        dialog = LoginDialog()
        dialog.username_edit.setText('admin')
        dialog.password_edit.setText('test-only-password')
        try:
            with patch.object(AdminService, 'authenticate', side_effect=AuthFailed), patch('attendance.ui_login.show_error') as show_error:
                dialog.login_button.click()
                self.assertTrue(show_error.called)
                self.assertIsNone(dialog.admin)
            admin = types.SimpleNamespace(id=1, username='admin')
            with patch.object(AdminService, 'authenticate', return_value=admin):
                dialog.login_button.click()
            self.assertEqual(dialog.result(), QtWidgets.QDialog.Accepted)
            self.assertIs(dialog.admin, admin)
        finally:
            dialog.deleteLater()

    @unittest.skipIf(os.environ.get('QT_QPA_PLATFORM') == 'offscreen', '本机 Qt 离屏插件构造 QMessageBox 原生崩溃，需桌面环境验收')
    def test_message_box_theme(self):
        message = QtWidgets.QMessageBox(QtWidgets.QMessageBox.NoIcon, '操作提示', '本次操作已完成。', QtWidgets.QMessageBox.Ok)
        try:
            message.show()
            self.app.processEvents()
            self.assertEqual(message.palette().color(QtGui.QPalette.Window).name(), '#f5f6fc')
            for button in message.buttons():
                self.assertGreaterEqual(button.height(), button.sizeHint().height())
        finally:
            message.hide()
            message.deleteLater()

    def test_camera_states(self):
        tab = self.window.checkin_tab
        with patch('attendance.ui_checkin.cv2.VideoCapture', FakeCapture):
            tab.btn_open.click()
        self.assertEqual(tab.device_status.text(), '相机已连接')
        self.assertTrue(tab.btn_start.isEnabled())
        tab.btn_start.click()
        self.assertTrue(tab.flag_recognition)
        self.assertTrue(tab.btn_stop.isEnabled())
        tab.btn_stop.click()
        self.assertFalse(tab.flag_recognition)
        tab.btn_open.click()
        self.assertEqual(tab.device_status.text(), '相机未连接')
        self.assertFalse(tab.btn_start.isEnabled())
        self.assertFalse(tab.btn_stop.isEnabled())
        self.assertIsNone(tab.video_label.pixmap())

    def test_preview_horizontal_flip(self):
        tab = self.window.checkin_tab
        frame = np.zeros((60, 120, 3), dtype=np.uint8)
        frame[:, :60] = [0, 0, 255]
        frame[:, 60:] = [255, 0, 0]
        original = frame.copy()
        self.assertTrue(tab.flip_preview_check.isChecked())
        for flipped in (True, False):
            tab.flip_preview_check.setChecked(flipped)
            tab._show_frame(frame)
            image = tab.video_label.pixmap().toImage()
            left = image.pixelColor(image.width() // 4, image.height() // 2)
            right = image.pixelColor(image.width() * 3 // 4, image.height() // 2)
            self.assertEqual(left.name(), '#0000ff' if flipped else '#ff0000')
            self.assertEqual(right.name(), '#ff0000' if flipped else '#0000ff')
            np.testing.assert_array_equal(frame, original)

    def test_result_feedback(self):
        from attendance.services import EmployeeService
        from attendance.ui_checkin import CheckConfirmDialog
        employee = types.SimpleNamespace(name='示例员工', employee_id='100001')

        def fake_confirm(dialog):
            dialog.recorded.emit('示例员工', 'check_in', '08:30:00')
            return QtWidgets.QDialog.Accepted

        with patch.object(self.window.checkin_tab, '_identify_frame_boxes', return_value=[RecognitionResult('live_candidate', '100001', .1, 'front', (0, 0, 10, 10))]), patch.object(EmployeeService, 'get', return_value=employee), patch.object(CheckConfirmDialog, 'exec_', fake_confirm), patch('attendance.ui_checkin.show_error'):
            self.window.checkin_tab._do_recognition(np.zeros((20, 20, 3), dtype=np.uint8))
        tab = self.window.checkin_tab
        self.assertEqual(tab.result_name.text(), '示例员工')
        self.assertEqual(tab.result_detail.text(), '签到成功 · 08:30:00')
        self.assertIn('签到成功', self.window.statusBar().currentMessage())
        self.assertFalse(tab.flag_recognition)

    def test_cancel_does_not_report_success(self):
        from attendance.services import EmployeeService
        from attendance.ui_checkin import CheckConfirmDialog
        with patch.object(self.window.checkin_tab, '_identify_frame_boxes', return_value=[RecognitionResult('live_candidate', '100001', .1, 'front', (0, 0, 10, 10))]), patch.object(CheckConfirmDialog, 'exec_', return_value=QtWidgets.QDialog.Rejected), patch.object(EmployeeService, 'get', return_value=types.SimpleNamespace(name='示例员工', employee_id='100001')):
            self.window.checkin_tab._do_recognition(np.zeros((20, 20, 3), dtype=np.uint8))
        self.assertNotIn('成功', self.window.checkin_tab.result_detail.text())
        self.assertFalse(self.window.checkin_tab._pending_dialog_open)

    def test_unknown_stops_recognition(self):
        tab = self.window.checkin_tab
        tab.flag_recognition = True
        with patch('attendance.ui_checkin.recognition.recognition', return_value=[]), patch.object(QtWidgets.QMessageBox, 'warning'):
            tab._do_recognition(np.zeros((20, 20, 3), dtype=np.uint8))
        self.assertFalse(tab.flag_recognition)
        self.assertTrue(tab.btn_start.isEnabled())
        self.assertIn('未识别', tab.activity_label.text())

    def test_recognition_worker_contract(self):
        from attendance.recognition_worker import RecognitionWorker
        results = []
        errors = []
        worker = RecognitionWorker(
            np.zeros((4, 4, 3), dtype=np.uint8),
            lambda frame: [[1, 2, 3, 4]],
            lambda frame, box: 'sample',
        )
        worker.finished.connect(results.append)
        worker.failed.connect(errors.append)
        worker.run()
        self.assertEqual(results, ['sample'])
        self.assertEqual(errors, [])

        empty_results = []
        empty_worker = RecognitionWorker(
            np.zeros((4, 4, 3), dtype=np.uint8),
            lambda frame: [],
            lambda frame, box: 'should-not-run',
        )
        empty_worker.finished.connect(empty_results.append)
        empty_worker.run()
        self.assertEqual(empty_results, ['unknown'])

        failed_errors = []
        failed_worker = RecognitionWorker(
            np.zeros((4, 4, 3), dtype=np.uint8),
            lambda frame: (_ for _ in ()).throw(RuntimeError('worker failed')),
            lambda frame, box: 'should-not-run',
        )
        failed_worker.failed.connect(failed_errors.append)
        failed_worker.run()
        self.assertEqual(failed_errors, ['worker failed'])

    def test_recognition_busy_drops_new_frames(self):
        tab = self.window.checkin_tab
        tab.flag_recognition = True
        tab._recognition_busy = True
        with patch('attendance.ui_checkin.recognition.recognition') as detect:
            tab._submit_recognition(np.zeros((4, 4, 3), dtype=np.uint8))
        detect.assert_not_called()
        self.assertTrue(tab._recognition_busy)

    def test_layout(self):
        for width, height in [(1100, 720), (1440, 900)]:
            self.window.resize(width, height)
            self.app.processEvents()
            self.assertEqual(self.window.width(), width)
            self.assertEqual(self.window.height(), height)
            tab = self.window.checkin_tab
            video_rect = QtCore.QRect(tab.video_label.mapTo(tab, QtCore.QPoint()), tab.video_label.size())
            result_rect = QtCore.QRect(tab.result_name.mapTo(tab, QtCore.QPoint()), tab.result_name.size())
            self.assertGreaterEqual(video_rect.width(), 480)
            self.assertGreaterEqual(video_rect.height(), 320)
            self.assertFalse(video_rect.intersects(result_rect))
            self.assertTrue(tab.rect().contains(video_rect))
            for button in (tab.btn_open, tab.btn_start, tab.btn_stop):
                button_rect = QtCore.QRect(button.mapTo(tab, QtCore.QPoint()), button.size())
                self.assertTrue(tab.rect().contains(button_rect))
                self.assertFalse(video_rect.intersects(button_rect))
            if os.environ.get('UI_PREVIEW_DIR'):
                destination = Path(os.environ['UI_PREVIEW_DIR'])
                destination.mkdir(parents=True, exist_ok=True)
                self.assertTrue(self.window.grab().save(str(destination / f'phase1-{width}.png')))
        preview_dir = os.environ.get('UI_PREVIEW_DIR')
        if preview_dir:
            destination = Path(preview_dir)
            destination.mkdir(parents=True, exist_ok=True)
            self.assertTrue(self.window.grab().save(str(destination / 'phase1-preview.png')))


if __name__ == '__main__':
    unittest.main(verbosity=2)
