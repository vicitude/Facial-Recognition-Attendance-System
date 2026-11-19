from types import SimpleNamespace
from attendance.checkin_location import decide_checkin_location
from attendance.location_source import StaticLocationSource, UnavailableLocationSource
from attendance.location_validation import Coordinate


def schedule(**kwargs):
    values = dict(location_name="总部", location_latitude=39.9, location_longitude=116.4, location_radius_m=100.0)
    values.update(kwargs)
    return SimpleNamespace(**values)


def test_location_must_pass_before_record_contract():
    result = decide_checkin_location(schedule(), StaticLocationSource(Coordinate(39.9005, 116.4)))
    assert result.allowed


def test_rejection_is_before_database_write_contract():
    result = decide_checkin_location(schedule(), StaticLocationSource(Coordinate(39.91, 116.4)))
    assert result.status == "outside_radius"
    assert not result.allowed


def test_unavailable_is_rejected_without_fallback():
    result = decide_checkin_location(schedule(), UnavailableLocationSource())
    assert result.status == "location_unavailable"
    assert not result.allowed
