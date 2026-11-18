"""SPEC-003 固定时间模拟验收，不依赖系统当前时间。"""
from datetime import datetime, time
from types import SimpleNamespace

from attendance.attendance_rules import decide_check


def rec(kind, stamp, cycle):
    return SimpleNamespace(check_type=kind, check_timestamp=stamp, check_date=cycle)


def test_day_shift_closed_boundaries_and_statuses():
    kw = dict(work_start=time(9), work_end=time(18), check_in_start=time(8), late_end=time(12), check_out_end=time(23))
    assert decide_check([], "check_in", datetime(2026, 1, 5, 7, 59), **kw).status == "too_early"
    assert decide_check([], "check_in", datetime(2026, 1, 5, 8), **kw).status == "normal"
    assert decide_check([], "check_in", datetime(2026, 1, 5, 9), **kw).status == "normal"
    assert decide_check([], "check_in", datetime(2026, 1, 5, 12), **kw).status == "late"
    assert decide_check([], "check_in", datetime(2026, 1, 5, 12, 1), **kw).status == "too_late"


def test_day_shift_duplicate_sequence_and_early_leave():
    kw = dict(work_start=time(9), work_end=time(18), check_in_start=time(8), late_end=time(12), check_out_end=time(23))
    cycle = datetime(2026, 1, 5).date()
    signed = [rec("check_in", datetime(2026, 1, 5, 9), cycle)]
    assert decide_check(signed, "check_in", datetime(2026, 1, 5, 9, 1), **kw).status == "duplicate"
    assert decide_check(signed, "check_out", datetime(2026, 1, 5, 17, 30), **kw).status == "early_leave"
    assert decide_check([], "check_out", datetime(2026, 1, 5, 18), **kw).status == "invalid_sequence"


def test_overnight_shift_uses_previous_cycle_date():
    kw = dict(work_start=time(22), work_end=time(6), check_in_start=time(20), late_end=time(1), check_out_end=time(10))
    assert decide_check([], "check_in", datetime(2026, 1, 5, 19, 59), **kw).status == "too_early"
    assert decide_check([], "check_in", datetime(2026, 1, 5, 22), **kw).status == "normal"
    cycle = datetime(2026, 1, 5).date()
    signed = [rec("check_in", datetime(2026, 1, 5, 22), cycle)]
    assert decide_check(signed, "check_out", datetime(2026, 1, 6, 6), **kw).status == "normal"
    assert decide_check(signed, "check_out", datetime(2026, 1, 6, 10, 1), **kw).status == "too_late"


def test_multishift_selection_is_service_contract():
    assert "SCHEDULE_SELECTION_REQUIRED" in open("attendance/services.py", encoding="utf-8").read()
