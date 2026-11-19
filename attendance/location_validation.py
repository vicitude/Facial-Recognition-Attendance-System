"""地点校验纯内存适配层。"""
from __future__ import annotations
from dataclasses import dataclass
from math import asin, cos, isfinite, radians, sin, sqrt

@dataclass(frozen=True)
class Coordinate:
    latitude: float
    longitude: float
    def __post_init__(self):
        if not isfinite(self.latitude) or not isfinite(self.longitude) or not -90 <= self.latitude <= 90 or not -180 <= self.longitude <= 180:
            raise ValueError("INVALID_COORDINATE")

@dataclass(frozen=True)
class AllowedLocation:
    name: str
    latitude: float
    longitude: float
    radius_m: float
    def __post_init__(self):
        if not self.name or not isfinite(self.radius_m) or not 0 < self.radius_m <= 100000:
            raise ValueError("INVALID_LOCATION")
        Coordinate(self.latitude, self.longitude)

@dataclass(frozen=True)
class LocationDecision:
    allowed: bool
    status: str
    distance_m: float | None
    location_name: str | None

def haversine_meters(left: Coordinate, right: Coordinate) -> float:
    radius = 6371000.0
    lat1, lat2 = radians(left.latitude), radians(right.latitude)
    a = sin((lat2-lat1)/2)**2 + cos(lat1)*cos(lat2)*sin(radians(right.longitude-left.longitude)/2)**2
    return 2 * radius * asin(sqrt(a))

def validate_location(current: Coordinate | None, allowed: list[AllowedLocation]) -> LocationDecision:
    if current is None:
        return LocationDecision(False, "location_unavailable", None, None)
    if not allowed:
        return LocationDecision(False, "no_allowed_location", None, None)
    nearest = min((haversine_meters(current, Coordinate(x.latitude, x.longitude)), x) for x in allowed)
    distance, location = nearest
    if distance <= location.radius_m:
        return LocationDecision(True, "allowed", distance, location.name)
    return LocationDecision(False, "outside_radius", distance, location.name)

def schedule_allowed_location(schedule):
    fields = (getattr(schedule, "location_name", None), getattr(schedule, "location_latitude", None), getattr(schedule, "location_longitude", None), getattr(schedule, "location_radius_m", None))
    if all(value is None for value in fields):
        return None
    if not all(value is not None for value in fields):
        raise ValueError("LOCATION_CONFIG_INVALID")
    return AllowedLocation(*fields)
