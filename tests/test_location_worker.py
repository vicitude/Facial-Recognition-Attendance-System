from attendance.location_worker import LocationWorker
from attendance.windows_location import LocationProbe

class FakeSource:
    def probe(self):
        return LocationProbe(None, "location_unavailable", "test")

def test_worker_uses_injected_source(qtbot):
    worker = LocationWorker(FakeSource)
    received = []
    worker.finished.connect(received.append)
    worker.run()
    assert received[0].status == "location_unavailable"
