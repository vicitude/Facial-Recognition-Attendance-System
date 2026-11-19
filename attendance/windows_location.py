"""可选 Windows Runtime 定位来源与非敏感失败诊断。"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import timedelta
from attendance.location_validation import Coordinate

@dataclass(frozen=True)
class LocationProbe:
    coordinate: Coordinate | None
    status: str
    detail: str | None = None

class WindowsLocationSource:
    def __init__(self, timeout_ms: int = 3000):
        self.timeout_ms = timeout_ms
        self.last_probe = LocationProbe(None, "not_checked")

    def probe(self) -> LocationProbe:
        try:
            from winrt.windows.devices.geolocation import Geolocator
        except ImportError:
            self.last_probe = LocationProbe(None, "runtime_unavailable", "winrt not installed")
            return self.last_probe
        try:
            locator = Geolocator()
            operation = locator.get_geoposition_async_with_age_and_timeout(timedelta(milliseconds=self.timeout_ms), timedelta(milliseconds=self.timeout_ms))
            result = operation.get() if hasattr(operation, "get") else None
            point = getattr(getattr(result, "coordinate", None), "point", None)
            position = getattr(point, "position", None)
            if position is None:
                self.last_probe = LocationProbe(None, "position_unavailable", "no position returned")
                return self.last_probe
            coordinate = Coordinate(float(position.latitude), float(position.longitude))
            self.last_probe = LocationProbe(coordinate, "available")
            return self.last_probe
        except PermissionError:
            self.last_probe = LocationProbe(None, "permission_denied", "Windows location permission denied")
        except TimeoutError:
            self.last_probe = LocationProbe(None, "timeout", "location request timed out")
        except Exception as exc:
            self.last_probe = LocationProbe(None, "provider_error", type(exc).__name__)
        return self.last_probe

    def get_current_location(self) -> Coordinate | None:
        return self.probe().coordinate
