"""定位来源契约与模拟实现；不调用真实 Windows API。"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol
from attendance.location_validation import Coordinate

class LocationSource(Protocol):
    def get_current_location(self) -> Coordinate | None: ...

@dataclass
class StaticLocationSource:
    coordinate: Coordinate | None = None
    def get_current_location(self) -> Coordinate | None:
        return self.coordinate

class LocationSourceUnavailable(RuntimeError):
    pass

class UnavailableLocationSource:
    def get_current_location(self) -> Coordinate | None:
        return None
