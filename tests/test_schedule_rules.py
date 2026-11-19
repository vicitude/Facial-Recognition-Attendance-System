"""SPEC-003 纯规则契约测试。"""
from datetime import datetime, time
from types import SimpleNamespace

from attendance.attendance_rules import decide_check


def test_UT_SCH_001_closed_checkin_endpoints():
    kwargs = dict(work_start=time(9), work_end=time(18), check_in_start=time(8), late_end=time(12), check_out_end=time(23))
    assert decide_check([], "check_in", datetime(2026, 1, 1, 8, 0), **kwargs).status == "normal"
    assert decide_check([], "check_in", datetime(2026, 1, 1, 9, 0), **kwargs).status == "normal"
    assert decide_check([], "check_in", datetime(2026, 1, 1, 9, 1), **kwargs).status == "late"
    assert decide_check([], "check_in", datetime(2026, 1, 1, 12, 0), **kwargs).status == "late"
    assert decide_check([], "check_in", datetime(2026, 1, 1, 12, 1), **kwargs).status == "too_late"


def test_UT_SCH_002_overnight_window():
    kwargs = dict(work_start=time(22), work_end=time(6), check_in_start=time(20), late_end=time(1), check_out_end=time(10))
    assert decide_check([], "check_in", datetime(2026, 1, 1, 22, 0), **kwargs).status == "normal"
    assert decide_check([], "check_in", datetime(2026, 1, 2, 0, 30), **kwargs).status == "late"
    assert decide_check([], "check_in", datetime(2026, 1, 2, 1, 1), **kwargs).status == "too_late"


def test_UT_SCH_003_early_leave_is_allowed_decision():
    kwargs = dict(work_start=time(9), work_end=time(18), check_in_start=time(8), late_end=time(12), check_out_end=time(23))
    records = [SimpleNamespace(check_type="check_in", check_date=datetime(2026, 1, 1).date(), check_timestamp=datetime(2026, 1, 1, 9))]
    result = decide_check(records, "check_out", datetime(2026, 1, 1, 17, 30), **kwargs)
    assert result.allowed and result.status == "early_leave"


def test_UT_SCH_004_duplicate_and_sequence():
    kwargs = dict(work_start=time(9), work_end=time(18), check_in_start=time(8), late_end=time(12), check_out_end=time(23))
    records = [SimpleNamespace(check_type="check_in", check_date=datetime(2026, 1, 1).date(), check_timestamp=datetime(2026, 1, 1, 9))]
    assert decide_check(records, "check_in", datetime(2026, 1, 1, 9, 1), **kwargs).status == "duplicate"
    assert decide_check([], "check_out", datetime(2026, 1, 1, 18), **kwargs).status == "invalid_sequence"
