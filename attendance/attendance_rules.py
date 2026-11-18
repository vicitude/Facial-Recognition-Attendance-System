"""可配置班次的纯时间规则，不依赖 Qt、摄像头或数据库。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date, time, timedelta


@dataclass(frozen=True)
class RuleDecision:
    allowed: bool
    status: str
    reason: str


def _minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def _offset(value: time, start: time) -> int:
    """返回从周期起点 start 到 value 的分钟偏移，支持跨午夜。"""
    result = _minutes(value) - _minutes(start)
    return result if result >= 0 else result + 24 * 60


def _in_closed(value: int, begin: int, end: int) -> bool:
    return begin <= value <= end


def _cycle_date(now: datetime, check_in_start: time | None, late_end: time | None = None, check_out_end: time | None = None) -> date:
    if check_in_start is not None and late_end is not None and _minutes(late_end) < _minutes(check_in_start):
        cutoff = check_out_end or late_end
        if _minutes(now.time()) <= _minutes(cutoff):
            return now.date() - timedelta(days=1)
    return now.date()


def _record_types(records, current_date: date):
    rows = [r for r in records if getattr(r, "check_date", current_date) == current_date]
    return [r.check_type for r in sorted(rows, key=lambda r: r.check_timestamp)]


def decide_check(
    records,
    check_type: str,
    now: datetime,
    *,
    work_start: time | None = None,
    work_end: time | None = None,
    check_in_start: time | None = None,
    late_end: time | None = None,
    check_out_end: time | None = None,
    duplicate_minutes: int = 5,
) -> RuleDecision:
    """按闭区间判定一次签到或签退。

    旧调用只传 work_start/work_end 时保留旧兼容行为；新调用传入三个显式窗口端点。
    """
    if check_type not in ("check_in", "check_out"):
        return RuleDecision(False, "invalid_sequence", "新流程只允许签到或签退")

    cycle_date = _cycle_date(now, check_in_start, late_end, check_out_end)
    if (check_type == "check_out" and check_in_start and late_end and check_out_end
            and _minutes(late_end) < _minutes(check_in_start)
            and _minutes(now.time()) > _minutes(check_out_end)):
        cycle_date = now.date() - timedelta(days=1)
    types = _record_types(records, cycle_date)
    if check_type == "check_in" and "check_in" in types:
        return RuleDecision(False, "duplicate", "今日已签到")
    if check_type == "check_out":
        if "check_in" not in types:
            return RuleDecision(False, "invalid_sequence", "尚未签到，不能签退")
        if "check_out" in types:
            return RuleDecision(False, "duplicate", "今日已签退")

    if work_start is None or work_end is None:
        return RuleDecision(True, "normal", "打卡正常")

    start = check_in_start or work_start
    value = _offset(now.time(), start)
    work_start_offset = 0
    work_end_offset = _offset(work_end, start)

    if check_type == "check_in":
        check_start = check_in_start or work_start
        current_minutes = _minutes(now.time())
        start_minutes = _minutes(check_start)
        late_minutes = _minutes(late_end or work_end)
        crosses_midnight = late_minutes < start_minutes
        # 跨午夜签到窗口例如 20:00–次日 01:00：20:00 前的当日时刻仍是过早，
        # 只有 00:00–01:00 属于窗口的次日部分。
        if current_minutes < start_minutes:
            if crosses_midnight:
                if current_minutes <= late_minutes:
                    return RuleDecision(True, "late", "迟到签到")
                if now.date() != cycle_date:
                    return RuleDecision(False, "too_late", "已超过最晚签到时间")
                return RuleDecision(False, "too_early", "尚未到签到时间")
            return RuleDecision(False, "too_early", "尚未到签到时间")
        check_value = _offset(now.time(), check_start)
        work_value = _offset(work_start, check_start)
        late_value = _offset(late_end or work_end, check_start)
        if check_value <= work_value:
            return RuleDecision(True, "normal", "正常签到")
        if check_value <= late_value:
            return RuleDecision(True, "late", "迟到签到")
        return RuleDecision(False, "too_late", "已超过最晚签到时间")

    checkout_end = _offset(check_out_end or work_end, start)
    if value > checkout_end:
        return RuleDecision(False, "too_late", "已超过最晚签退时间")
    if value < work_end_offset:
        return RuleDecision(True, "early_leave", "早于班次结束时间签退")
    return RuleDecision(True, "normal", "正常签退")
