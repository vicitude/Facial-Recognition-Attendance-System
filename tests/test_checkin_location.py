from types import SimpleNamespace
from attendance.location_source import StaticLocationSource, UnavailableLocationSource
from attendance.location_validation import Coordinate
from attendance.checkin_location import decide_checkin_location


def schedule(**kwargs):
    values = dict(location_name="总部", location_latitude=39.9, location_longitude=116.4, location_radius_m=100.0)
    values.update(kwargs)
    return SimpleNamespace(**values)


def test_in_range_is_allowed():
    result = decide_checkin_location(schedule(), StaticLocationSource(Coordinate(39.9005, 116.4)))
    assert result.allowed and result.status == "allowed"


def test_outside_and_unavailable_are_rejected():
    outside = decide_checkin_location(schedule(), StaticLocationSource(Coordinate(39.91, 116.4)))
    unavailable = decide_checkin_location(schedule(), UnavailableLocationSource())
    assert outside.status == "outside_radius" and not outside.allowed
    assert unavailable.status == "location_unavailable" and not unavailable.allowed


def test_unconfigured_schedule_is_explicitly_allowed():
    result = decide_checkin_location(schedule(location_name=None, location_latitude=None, location_longitude=None, location_radius_m=None), StaticLocationSource(None))
    assert result.allowed and result.status == "location_not_configured"
