"""SPEC-001-C 阶段 2 - 实时签到 Tab 烟测 (TC-ATT-C12 ~ C15).

策略:
- 用 pytest-qt + offscreen 平台, 不依赖真实显示器.
- cv2.VideoCapture 通过 monkeypatch 拦截, 避免依赖真实相机.
- CheckConfirmDialog 直接实例化, 调对应按钮 click 即可触发 CheckService.
- 不主动 processEvents, 避免 QTimer 30ms 间隔真的去读 frame.
"""

import pytest

pytest.importorskip("PyQt5")


@pytest.fixture(scope="session", autouse=True)
def _offscreen_platform():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def app():
    from PyQt5 import QtWidgets
    a = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield a


# ============================================================
# C-12 / C-13: 相机开关
# ============================================================


class _FakeCaptureOk:
    """模拟一个能成功 open 的 cv2.VideoCapture."""

    def __init__(self, *args, **kwargs):
        self._opened = True

    def isOpened(self):
        return self._opened

    def read(self):
        import numpy as np
        return True, np.zeros((480, 640, 3), dtype=np.uint8)

    def release(self):
        self._opened = False


class _FakeCaptureFail:
    """模拟一个 open 失败的 cv2.VideoCapture."""

    def __init__(self, *args, **kwargs):
        pass

    def isOpened(self):
        return False

    def read(self):
        return False, None

    def release(self):
        pass


def test_TC_ATT_C12_checkin_open_camera_ok(app, monkeypatch):
    """C-12: 打开相机 → 启动 QTimer(30ms), 按钮文本切换; 关闭 → 反向."""
    from attendance.ui_checkin import CheckInTab
    import cv2

    monkeypatch.setattr(cv2, "VideoCapture", _FakeCaptureOk)

    tab = CheckInTab()
    assert tab._camera is None
    assert tab.btn_open.text() == "打开相机"

    # 打开
    tab.btn_open.click()
    assert tab._camera is not None
    assert tab._camera.isOpened()
    assert tab._timer is not None
    assert tab._timer.isActive()
    assert tab.btn_open.text() == "关闭相机"
    assert tab.btn_start.isEnabled() is True

    # 关闭
    tab.btn_open.click()
    assert tab._timer is None or not tab._timer.isActive()
    assert tab._camera is None or not tab._camera.isOpened()
    assert tab.btn_open.text() == "打开相机"
    assert tab.btn_start.isEnabled() is False


def test_TC_ATT_C13_checkin_open_camera_fail(app, monkeypatch):
    """C-13: 相机打开失败 → show_error 触发 CAMERA_OPEN_FAILED."""
    from attendance.ui_checkin import CheckInTab
    import cv2

    monkeypatch.setattr(cv2, "VideoCapture", _FakeCaptureFail)

    captured = {}

    def fake_show_error(parent, error_code, message):
        captured["error_code"] = error_code
        captured["message"] = message

    monkeypatch.setattr(
        "attendance.ui_checkin.show_error", fake_show_error,
    )

    tab = CheckInTab()
    tab.btn_open.click()

    assert captured["error_code"] == "CAMERA_OPEN_FAILED"
    assert "CAMERA_OPEN_FAILED" in captured["message"]
    assert tab._camera is None
    assert tab._timer is None
    assert tab.btn_open.text() == "打开相机"


# ============================================================
# C-14 / C-15: CheckConfirmDialog 4 按钮
# ============================================================


def test_TC_ATT_C14_checkin_confirm_check_in(
    app, monkeypatch, face_image, sample_schedule,
):
    """C-14: CheckConfirmDialog 签到 → CheckService.create_record, accept()."""
    from attendance.models import CheckRecord
    from attendance.services import EmployeeService
    from attendance.ui_checkin import CheckConfirmDialog

    EmployeeService.create(
        employee_id="100001", name="张三", department=None,
        position=None, phone=None, email=None,
        face_image_path=face_image, schedule_id=sample_schedule.id,
    )

    dlg = CheckConfirmDialog(employee_id="100001", name="张三")
    assert dlg.windowTitle() == "已识别: 张三 (100001)"

    # 捕获 recorded 信号 (供 statusBar 反馈)
    captured = {}
    dlg.recorded.connect(
        lambda n, t, ts: captured.update(
            name=n, check_type=t, time=ts,
        )
    )

    dlg.btn_in.click()
    assert dlg.result() == dlg.Accepted
    assert captured.get("name") == "张三"
    assert captured.get("check_type") == "check_in"
    assert captured.get("time")  # HH:MM:SS 格式

    rec = CheckRecord.select().where(
        CheckRecord.check_type == "check_in"
    ).get()
    assert rec.employee_id == "100001"


def test_TC_ATT_C15_checkin_confirm_other_buttons(
    app, monkeypatch, face_image, sample_schedule,
):
    """C-15: 无签到时签退拒绝，中间打卡已移除，取消不写入。"""
    from attendance.models import CheckRecord
    from attendance.services import EmployeeService
    from attendance.ui_checkin import CheckConfirmDialog

    EmployeeService.create(
        employee_id="100001", name="张三", department=None,
        position=None, phone=None, email=None,
        face_image_path=face_image, schedule_id=sample_schedule.id,
    )
    errors = []
    monkeypatch.setattr(
        "attendance.ui_checkin.show_error",
        lambda parent, code, message: errors.append((code, message)),
    )

    # 没有签到记录时签退应被顺序规则拒绝，且不写库。
    dlg1 = CheckConfirmDialog(employee_id="100001", name="张三")
    dlg1.btn_out.click()
    assert dlg1.result() == dlg1.Rejected
    assert errors and errors[-1][0] == "CHECK_RULE_REJECTED"
    assert not CheckRecord.select().where(
        CheckRecord.check_type == "check_out"
    ).exists()

    # SPEC-003 删除中间打卡入口。
    assert not hasattr(dlg1, "btn_mid")

    # 取消: 不创建记录, dialog rejected
    records_before = CheckRecord.select().count()
    dlg3 = CheckConfirmDialog(employee_id="100001", name="张三")
    dlg3.btn_cancel.click()
    assert dlg3.result() == dlg3.Rejected
    assert CheckRecord.select().count() == records_before
