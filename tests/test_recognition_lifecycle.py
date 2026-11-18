import os
import sys
import threading
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from PyQt5 import QtCore, QtWidgets


class LifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        fake = types.ModuleType('recognition')
        fake.recognition = lambda frame: []
        names = types.ModuleType('get_name')
        names.rec = lambda frame, box: 'sample'
        cls.modules = patch.dict(sys.modules, {'recognition': fake, 'get_name': names})
        cls.modules.start()
        cls.addClassCleanup(cls.modules.stop)
        from attendance.ui_checkin import CheckInTab
        cls.tab_type = CheckInTab

    def setUp(self):
        self.tab = self.tab_type()
        self.addCleanup(self.tab._close_camera)

    def drain(self):
        deadline = time.monotonic() + 5
        while self.tab._recognition_busy and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(.005)
        self.assertFalse(self.tab._recognition_busy)

    def test_result_and_error_on_main_thread(self):
        frame = np.zeros((4, 4, 3), dtype=np.uint8)
        calls = []
        self.tab.flag_recognition = True
        self.tab._handle_recognition_name = lambda name: calls.append(QtCore.QThread.currentThread() == self.app.thread())
        with patch('attendance.ui_checkin.recognition.recognition', return_value=[[0, 0, 2, 2]]), patch.object(self.tab, '_identify_frame_boxes', return_value=[]):
            self.tab._submit_recognition(frame)
            self.drain()
        self.assertEqual(calls, [True])
        with patch('attendance.ui_checkin.recognition.recognition', side_effect=RuntimeError('probe')), patch('attendance.ui_checkin.show_error', side_effect=lambda *args: calls.append(QtCore.QThread.currentThread() == self.app.thread())):
            self.tab._submit_recognition(frame)
            self.drain()
        self.assertEqual(calls, [True, True])

    def test_close_waits_for_long_task_and_discards_result(self):
        entered = threading.Event()
        released = threading.Event()
        calls = []
        def detect(frame):
            entered.set()
            released.wait(6)
            return [[0, 0, 2, 2]]
        self.tab.flag_recognition = True
        self.tab._handle_recognition_name = calls.append
        with patch('attendance.ui_checkin.recognition.recognition', side_effect=detect):
            self.tab._submit_recognition(np.zeros((4, 4, 3), dtype=np.uint8))
            self.assertTrue(entered.wait(2))
            timer = threading.Timer(3.2, released.set)
            timer.start()
            started = time.monotonic()
            self.tab._close_camera()
            timer.join()
            self.assertGreaterEqual(time.monotonic() - started, 3)
        self.app.processEvents()
        self.assertEqual(calls, [])
        self.assertIsNone(self.tab._recognition_thread)
        self.assertFalse(self.tab._recognition_busy)

    def test_stop_restart_rejects_old_task_and_drops_busy_frames(self):
        released = threading.Event()
        entered = threading.Event()
        calls = []
        def detect(frame):
            entered.set()
            released.wait(3)
            return [[0, 0, 2, 2]]
        self.tab.flag_recognition = True
        self.tab._handle_recognition_name = calls.append
        with patch('attendance.ui_checkin.recognition.recognition', side_effect=detect) as detector:
            self.tab._submit_recognition(np.zeros((4, 4, 3), dtype=np.uint8))
            self.assertTrue(entered.wait(2))
            self.tab._on_stop_clicked()
            self.tab.flag_recognition = True
            self.tab._submit_recognition(np.zeros((4, 4, 3), dtype=np.uint8))
            self.assertEqual(detector.call_count, 1)
            released.set()
            self.drain()
        self.assertEqual(calls, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
