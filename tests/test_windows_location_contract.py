import sys
from attendance.windows_location import WindowsLocationSource, LocationProbe


def test_windows_source_is_safe_when_runtime_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "winrt", None)
    source = WindowsLocationSource()
    assert source.get_current_location() is None
    assert source.last_probe.status in {"runtime_unavailable", "provider_error", "position_unavailable"}


def test_probe_never_exposes_coordinates_in_failure_detail():
    probe = LocationProbe(None, "permission_denied", "Windows location permission denied")
    assert probe.coordinate is None
    assert "39." not in (probe.detail or "")
