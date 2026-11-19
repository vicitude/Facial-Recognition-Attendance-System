import sys
sys.argv = [sys.argv[0]]
import pytest
from PyQt5 import QtWidgets

@pytest.fixture
def app(qtbot):
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

def test_schedule_tab_mock_service(monkeypatch, app):
    from attendance.ui_schedules import SchedulesTab
    class S:
        id=1; name='白班'; work_start=__import__('datetime').time(9); work_end=__import__('datetime').time(18); check_in_start=__import__('datetime').time(8); late_end=__import__('datetime').time(12); check_out_end=__import__('datetime').time(23); is_active=True
    monkeypatch.setattr('attendance.ui_schedules.ScheduleService.list_all', staticmethod(lambda: [S()]))
    tab = SchedulesTab(); assert tab.table.rowCount() == 1; assert tab.table.item(0,1).text() == '白班'; tab.close()

def test_coordinate_text_parser_accepts_decimal_and_dms():
    from attendance.ui_schedules import parse_coordinate_text
    assert abs(parse_coordinate_text("116.4074", latitude=False) - 116.4074) < 1e-9
    assert abs(parse_coordinate_text("116°24′27″E", latitude=False) - (116 + 24 / 60 + 27 / 3600)) < 1e-9
    assert abs(parse_coordinate_text("24°23′N", latitude=True) - (24 + 23 / 60)) < 1e-9


def test_coordinate_text_parser_rejects_ranges_and_accepts_prefix():
    from attendance.ui_schedules import parse_coordinate_text
    assert abs(parse_coordinate_text("北纬：24°23′", latitude=True) - (24 + 23 / 60)) < 1e-9
    with pytest.raises(ValueError):
        parse_coordinate_text("北纬：24°23′ 至 25°06′", latitude=True)


def test_coordinate_text_parser_rejects_invalid_range():
    from attendance.ui_schedules import parse_coordinate_text
    with pytest.raises(ValueError):
        parse_coordinate_text("181", latitude=False)
    with pytest.raises(ValueError):
        parse_coordinate_text("24°60′N", latitude=True)


def test_employee_bind_entry(monkeypatch, app):
    from attendance.ui_employees import EmployeesTab
    monkeypatch.setattr('attendance.ui_employees.EmployeeService.list_all', staticmethod(lambda: []))
    tab = EmployeesTab(); assert tab.btn_bind_schedules.text() == '绑定班次'; tab.close()
