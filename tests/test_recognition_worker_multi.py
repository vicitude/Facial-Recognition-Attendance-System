from attendance.recognition_worker import RecognitionWorker


def test_worker_batch_identify_path(qtbot):
    worker = RecognitionWorker(
        frame="frame", recognize=lambda _: [[0, 0, 2, 2]], identify=lambda *_: "legacy",
        batch_identify=lambda *_: ["batch"], generation=3,
    )
    received = []
    worker.completed.connect(lambda generation, value: received.append((generation, value)))
    worker.run()
    assert received == [(3, ["batch"])]
