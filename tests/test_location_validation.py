import pytest
from attendance.location_validation import Coordinate, AllowedLocation, haversine_meters, validate_location

CENTER = AllowedLocation("总部", 39.9000, 116.4000, 100.0)


def test_distance_and_closed_radius():
    center = Coordinate(39.9, 116.4)
    assert haversine_meters(center, center) == 0
    decision = validate_location(Coordinate(39.9005, 116.4), [CENTER])
    assert decision.allowed is True
    assert decision.status == "allowed"


def test_outside_radius_and_unavailable():
    outside = validate_location(Coordinate(39.91, 116.4), [CENTER])
    assert outside.allowed is False
    assert outside.status == "outside_radius"
    unavailable = validate_location(None, [CENTER])
    assert unavailable.status == "location_unavailable"
    assert unavailable.allowed is False


def test_multiple_locations_choose_nearest():
    second = AllowedLocation("分部", 39.9100, 116.4000, 100.0)
    result = validate_location(Coordinate(39.9099, 116.4), [CENTER, second])
    assert result.location_name == "分部"


def test_invalid_coordinates_rejected():
    with pytest.raises(ValueError, match="INVALID_COORDINATE"):
        Coordinate(91, 116)
    with pytest.raises(ValueError, match="INVALID_LOCATION"):
        AllowedLocation("", 39.9, 116.4, 100)
