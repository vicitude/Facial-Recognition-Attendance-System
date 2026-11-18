from datetime import datetime, time
from types import SimpleNamespace
from attendance.attendance_rules import decide_check

def rec(kind, at):
    return SimpleNamespace(check_type=kind, check_timestamp=at, check_date=at.date())

def test_sequence_and_duplicate():
    now=datetime(2026,1,1,9)
    assert decide_check([], 'check_out', now).status == 'invalid_sequence'
    assert decide_check([], 'check_in', now).status == 'normal'
    assert decide_check([rec('check_in', now)], 'check_in', now).status == 'duplicate'

def test_late_and_early():
    late=decide_check([], 'check_in', datetime(2026,1,1,9,10), work_start=time(9))
    assert late.status == 'late' and late.allowed
    early=decide_check([rec('check_in', datetime(2026,1,1,8,50))], 'check_out', datetime(2026,1,1,17), work_end=time(18))
    assert early.status == 'early_leave'
