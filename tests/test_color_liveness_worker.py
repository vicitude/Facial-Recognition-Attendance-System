from queue import Queue
from threading import Event, current_thread

import numpy as np
import pytest

from attendance.color_light_liveness import ColorLightConfig
from attendance.color_liveness_worker import ColorLivenessWorker


class ControlledCamera:
    def __init__(self):
        self.frames = Queue()
        self.reading = Event()
        self.read_starts = Queue()
        self.releases = 0
        self.reader_names = set()

    def read(self):
        self.reader_names.add(current_thread().name)
        self.reading.set()
        self.read_starts.put(None)
        frame = self.frames.get(timeout=4)
        return frame is not None, frame

    def release(self):
        self.releases += 1

    def send(self, value=100):
        self.frames.put(np.full((40, 40, 3), value, dtype=np.uint8))


def facts():
    return dict(face_count=1, quality_ok=True, identity_vector=np.zeros(128, np.float32),
                identity_distance=.1, passive_status='live_candidate', mean_rgb=(100,100,100), motion_score=0.)


@pytest.fixture
def worker_factory(qtbot):
    created = []
    def make(backend, **limits):
        camera = ControlledCamera()
        worker = ColorLivenessWorker('123456', camera, (), config=ColorLightConfig(enabled=True, **limits),
                                     backend_factory=lambda _: backend)
        created.append((worker, camera))
        worker.start()
        assert camera.reading.wait(1)
        return worker, camera
    yield make
    for worker, camera in created:
        worker.stop()
        camera.frames.put(None)
        qtbot.waitUntil(worker.stopped)


def test_CT_CLR_06_no_samples_before_color_ack_and_settle(worker_factory, qtbot, monkeypatch):
    import attendance.color_liveness_worker as module
    # 用受控时钟分离曝光时序与测试机器运行时间。
    clock = [10.0]
    monkeypatch.setattr(module, 'monotonic', lambda: clock[0])
    calls = []
    def backend(frame):
        calls.append(int(frame[0,0,0]))
        return facts()
    worker, camera = worker_factory(backend)
    camera.read_starts.get(timeout=1)

    def feed(value, timestamp):
        with worker._condition:
            wanted = worker._frame_count + 1
        clock[0] = timestamp
        camera.send(value)
        qtbot.waitUntil(lambda: worker.snapshot()['frame_count'] == wanted)
        camera.read_starts.get(timeout=1)

    assert not worker.acknowledge_color('red')
    assert worker.acknowledge_color('white')
    feed(1, 10.04)  # read 在 ACK 前启动
    feed(2, 10.09)  # read 虽结束在稳定期后，但开始在稳定期内
    feed(3, 10.12)
    qtbot.waitUntil(lambda: worker.snapshot()['result'].metrics['baseline_samples'] == 1)
    assert calls == [3]
    assert worker.snapshot()['valid_count'] == 1
    assert camera.reader_names == {'color-camera'}


def test_CT_CLR_07_inflight_result_cannot_override_cancel(worker_factory, qtbot):
    entered, unblock = Event(), Event()
    def backend(frame):
        entered.set()
        assert unblock.wait(3)
        return facts()
    worker, camera = worker_factory(backend, settle_ms=30)
    assert worker.acknowledge_color('white')
    try:
        # 模拟相机稳定出帧，不让假摄像头的超长间隔触发性能拒绝。
        for n in range(1, 16):
            qtbot.wait(20)
            camera.send()
            qtbot.waitUntil(lambda: worker.snapshot()['frame_count'] >= n)
            if entered.is_set():
                break
        assert entered.wait(.5)
        assert not worker.stop() and not worker.stopped()
        assert camera.releases == 0
    finally:
        unblock.set()
        camera.frames.put(None)
    qtbot.waitUntil(worker.stopped)
    assert worker.snapshot()['valid_count'] == 0
    assert worker.snapshot()['result'].reason == 'COLOR_CANCELLED'


def test_CT_CLR_06_expiry_during_camera_read_is_terminal(worker_factory, monkeypatch):
    import attendance.color_liveness_worker as module
    clock = [10.0]
    monkeypatch.setattr(module, 'monotonic', lambda: clock[0])
    worker, camera = worker_factory(lambda frame: facts())
    clock[0] = 35.0
    snap = worker.snapshot()
    assert snap['result'].status == 'timeout'
    assert snap['result'].reason == 'COLOR_TIMEOUT'
    assert not worker.acknowledge_color('white') and not worker.stop()
    assert worker.snapshot()['result'] == snap['result'] and not camera.releases


@pytest.mark.parametrize('failure', [None, 'COLOR_SAMPLES_INSUFFICIENT', 'COLOR_UNRESPONSIVE'])
def test_CT_CLR_08_worker_holds_color_until_deadline(worker_factory, qtbot, monkeypatch, failure):
    import attendance.color_liveness_worker as module
    clock = [10.0]
    monkeypatch.setattr(module, 'monotonic', lambda: clock[0])
    rgb = {0: (100,100,100), 1: (160,20,20), 2: (20,160,20), 3: (20,20,160), 4: (160,20,20), 5: (160,20,20)}
    def backend(frame):
        value = int(frame[0,0,0])
        return dict(facts(), mean_rgb=rgb[value], motion_score=.02 if value == 4 else 0.,
                    quality_ok=value != 5, quality_issue='blurry' if value == 5 else None)
    # 此用例验证 4/6 的全窗边界，不依赖生产默认 85%。
    worker, camera = worker_factory(backend, baseline_frames=1, min_color_ratio=2 / 3)
    camera.read_starts.get(timeout=1)

    def feed(value, step):
        number = worker.snapshot()['frame_count'] + 1
        clock[0] = round(clock[0] + step, 3)
        camera.send(value)
        qtbot.waitUntil(lambda: worker.snapshot()['frame_count'] >= number
                        or worker.snapshot()['result'].status != 'pending')
        if worker.snapshot()['result'].status == 'pending':
            camera.read_starts.get(timeout=1)

    def apply(color, samples):
        assert worker.snapshot()['desired_color'] == color
        assert worker.acknowledge_color(color)
        painted_at = clock[0]
        count = worker.snapshot()['valid_count']
        feed(0, .09)  # 已在 ACK 前开始读取，不能用
        for value in samples:
            feed(value, .04)
            if value in (4, 5):
                reason = 'COLOR_MOTION_SKIPPED' if value == 4 else 'COLOR_QUALITY_SKIPPED'
                qtbot.waitUntil(lambda: worker.snapshot()['result'].reason == reason)
                assert worker.snapshot()['valid_count'] == count
            else:
                count += 1
                qtbot.waitUntil(lambda: worker.snapshot()['valid_count'] == count)
        if color != 'white':
            clock[0] = painted_at + 1.999
            snapshot = worker.snapshot()
            assert snapshot['desired_color'] == color and snapshot['result'].status == 'pending'
            clock[0] = painted_at + 2.0
            worker.snapshot()  # 不需要再收到新帧
            # 补一帧消化模拟时钟的跳变，避免把它带到下一色的采集帧率。
            if worker.snapshot()['result'].status == 'pending':
                feed(0, .001)

    apply('white', [0])
    if failure:
        samples = [4, 1, 1, 5] if failure == 'COLOR_SAMPLES_INSUFFICIENT' else [4, 1, 5, 0, 0]
        apply('red', samples)
        failed = worker.snapshot()['result']
        assert failed.reason == failure and failed.color == 'red'
        assert failed.metrics['color_samples'] == len(samples) - 2
        assert failed.metrics['color_diagnostics'][0]['quality_skips'] == {'blurry': 1}
        assert failed.metrics['color_hits'] == samples.count(1)
        assert failed.metrics['color_motion_skips'] == 1
        return
    for color, value in [('red',1), ('green',2), ('blue',3)]:
        apply(color, [0, 0, value, value, 5, value, value])  # 前三份不合格，全窗恰好 2/3
    result = worker.snapshot()['result']
    assert (result.status, result.phase, result.accepted_samples) == ('pending', 'verifying', 18)
    apply('white', [0])
    assert worker.snapshot()['result'].status == 'passed'
