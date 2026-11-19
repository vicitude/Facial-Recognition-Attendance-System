"""签到前地点判定服务；只读班次地点配置，不写数据库。"""
from __future__ import annotations
from attendance.location_source import LocationSource
from attendance.location_validation import LocationDecision, schedule_allowed_location, validate_location

def decide_checkin_location(schedule, source: LocationSource) -> LocationDecision:
    try:
        current = source.get_current_location()
    except Exception:
        return LocationDecision(False, "location_unavailable", None, None)
    try:
        allowed = schedule_allowed_location(schedule)
    except ValueError:
        return LocationDecision(False, "invalid_location_config", None, None)
    if allowed is None:
        return LocationDecision(True, "location_not_configured", None, None)
    return validate_location(current, [allowed])
