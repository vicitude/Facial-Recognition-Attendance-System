from types import SimpleNamespace
import attendance.recognition_results as mod


def test_box_and_iou():
    assert mod.normalize_box([1.9, 2, 10, 12]) == (1, 2, 10, 12)
    assert mod.iou((0,0,10,10), (5,5,15,15)) > 0


def test_multi_results_keep_order_and_dedupe(monkeypatch):
    def fake_identify(vector, ids, threshold, key):
        return SimpleNamespace(employee_id=str(int(vector[0]))), 0.2, "frontal"
    monkeypatch.setattr(mod, "identify", fake_identify)
    rows = mod.recognize_faces([
        ((0,0,10,10), [1]), ((1,1,9,9), [2]), ((20,20,30,30), [3])
    ], ["1", "2", "3"])
    assert [r.employee_id for r in rows] == ["1", "3"]
    assert all(r.status == "matched" for r in rows)


def test_unknown_and_invalid(monkeypatch):
    monkeypatch.setattr(mod, "identify", lambda *args, **kwargs: None)
    rows = mod.recognize_faces([((0,0,10,10), [1])], [])
    assert rows[0].status == "unknown"
    assert mod.recognize_faces([(None, [1])], [])[0].status == "invalid"
