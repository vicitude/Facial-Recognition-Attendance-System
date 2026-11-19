from types import SimpleNamespace
import attendance.recognition_results as mod


def test_unknown_never_becomes_matched(monkeypatch):
    monkeypatch.setattr(mod, "identify", lambda *a, **k: None)
    rows = mod.recognize_faces([((0, 0, 20, 20), [0.1] * 128)], ["100001"])
    assert rows[0].status == "unknown"
    assert rows[0].employee_id is None


def test_invalid_match_is_rejected(monkeypatch):
    emp = SimpleNamespace(employee_id="100001")
    monkeypatch.setattr(mod, "identify", lambda *a, **k: (emp, float("nan"), "frontal"))
    row = mod.recognize_faces([((0, 0, 20, 20), [0.1] * 128)], ["100001"])[0]
    assert row.status == "invalid"
    assert row.employee_id is None


def test_overlap_threshold_is_inclusive(monkeypatch):
    emp = SimpleNamespace(employee_id="100001")
    monkeypatch.setattr(mod, "identify", lambda *a, **k: (emp, 0.2, "frontal"))
    rows = mod.recognize_faces([
        ((0, 0, 10, 10), [0.1] * 128),
        ((0, 0, 10, 10), [0.1] * 128),
    ], ["100001"], overlap_threshold=0.5)
    assert len(rows) == 1
