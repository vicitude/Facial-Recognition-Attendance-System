"""CT-FUS-02 / UT-FUS-08：异步契约只用替身，不加载真实模型。"""
from threading import Event
from time import monotonic
from types import SimpleNamespace

import numpy as np
import pytest

from attendance.fused_liveness import FusionSession
from attendance.liveness_pipeline import AsyncFusionPipeline, LatestFrameCamera
from tests.test_fused_liveness import ACTIONS, Feed, complete


def test_UT_FUS_08_deferred_gate():
    session = FusionSession(ACTIONS, defer_auxiliary=True)
    with pytest.raises(ValueError):
        session.finish_auxiliary(True)
    feed = Feed(session)
    for action in ACTIONS:
        result = complete(feed, action, passive='inconclusive')
    assert result.phase == 'verification' and result.status == 'pending'
    assert feed().status == 'pending'
    assert session.finish_auxiliary(True).status == 'passed'
    assert session.finish_auxiliary(False).status == 'passed'


@pytest.mark.parametrize('kwargs,reason', [
    ({'feature': {'face_count': 0}}, 'need_one_face'),
    ({'quality_ok': False}, 'poor_quality'),
    ({'passive_status': 'spoof_candidate'}, 'passive_spoof'),
    ({'identity_distance': 999}, 'identity_changed'),
])
def test_UT_FUS_08_verification_still_checks_inputs(kwargs, reason):
    session = FusionSession(ACTIONS, defer_auxiliary=True)
    feed = Feed(session)
    for action in ACTIONS:
        complete(feed, action, passive='inconclusive')
    assert feed(**kwargs).reason == reason
    assert session.finish_auxiliary(True).status == 'failed'


class Landmarks:
    def detect(self, frame):
        return dict(face_count=1, face_box=(0, 0, 100, 100), yaw_deg=0, pitch_deg=45, ear=0.3)
    def close(self):
        pass


def evaluation(anchor=None):
    return dict(feature=Landmarks().detect(None), quality_ok=True, identity_distance=0.1,
                passive_status='live_candidate', anchor=np.ones(128), identity_vector=np.ones(128), timings_ms={'yolo_ms': 2})


def test_CT_FUS_02_latest_frame_and_reset_isolate():
    entered, release, second, release_second = Event(), Event(), Event(), Event()
    calls = []
    def auxiliary(frame, anchor):
        calls.append((int(frame[0, 0, 0]), anchor))
        if len(calls) == 1:
            entered.set()
            assert release.wait(3)
        else:
            second.set()
            assert release_second.wait(3)
        return evaluation()
    pipeline = AsyncFusionPipeline(Landmarks(), auxiliary, lambda *a: (True, ()))
    pipeline.start()
    try:
        pipeline.submit(1, monotonic(), np.zeros((100, 100, 3), dtype=np.uint8))
        assert entered.wait(3)
        pipeline.reset()
        # Windows monotonic可能同一tick；替身帧使用严格递增的采集时刻。
        source_start = monotonic() - .02
        for number in range(2, 8):
            pipeline.submit(number, source_start + number * .001, np.full((100, 100, 3), number, dtype=np.uint8))
        release.set()
        assert second.wait(3)
        with pipeline.condition:
            assert pipeline.anchor is None and pipeline.aux is None
        assert calls[1][0] == 7 and calls[1][1] is None
    finally:
        release.set()
        release_second.set()
        pipeline.close()
    assert all(not thread.is_alive() for thread in pipeline.threads)


@pytest.mark.parametrize('broken_channel', ['actions', 'auxiliary'])
def test_CT_FUS_02_old_exception_does_not_poison_reset(broken_channel):
    entered, release, recovered = Event(), Event(), Event()
    calls = [0]
    def flaky():
        calls[0] += 1
        if calls[0] == 1:
            entered.set()
            assert release.wait(3)
            raise RuntimeError('old generation')
        recovered.set()
    class Detector(Landmarks):
        def detect(self, frame):
            if broken_channel == 'actions': flaky()
            return super().detect(frame)
    def auxiliary(frame, anchor):
        if broken_channel == 'auxiliary': flaky()
        return evaluation()
    pipeline = AsyncFusionPipeline(Detector(), auxiliary, lambda *a: (True, ()))
    pipeline.start()
    try:
        pipeline.submit(1, monotonic(), np.zeros((100, 100, 3), dtype=np.uint8))
        assert entered.wait(3)
        pipeline.reset()
        pipeline.submit(2, monotonic(), np.zeros((100, 100, 3), dtype=np.uint8))
        release.set()
        assert recovered.wait(3)
        with pipeline.condition:
            assert pipeline.result is None or pipeline.result.reason != 'pipeline_error'
        assert all(thread.is_alive() for thread in pipeline.threads)
    finally:
        release.set()
        pipeline.close()


def test_CT_FUS_02_stale_auxiliary_cannot_pass():
    finished = Event()
    def auxiliary(frame, anchor):
        finished.set()
        return evaluation()
    pipeline = AsyncFusionPipeline(Landmarks(), auxiliary, lambda *a: (True, ()))
    pipeline.session = FusionSession(ACTIONS, defer_auxiliary=True)
    pipeline.aux_time = monotonic() - 3
    with pipeline.condition:
        pipeline._freshness()
    assert pipeline.snapshot()['result'].reason == 'auxiliary_stale'
    pipeline.start()
    try:
        pipeline.submit(1, monotonic(), np.zeros((100, 100, 3), dtype=np.uint8))
    finally:
        pipeline.close()
    assert not finished.is_set()
    assert pipeline.snapshot()['result'].status == 'failed'


def test_CT_FUS_02_background_exception_fails_closed():
    class Broken(Landmarks):
        def detect(self, frame):
            raise RuntimeError('test')
    pipeline = AsyncFusionPipeline(Broken(), lambda *a: evaluation(), lambda *a: (True, ()))
    pipeline.start()
    pipeline.submit(1, monotonic(), np.zeros((100, 100, 3), dtype=np.uint8))
    try:
        with pipeline.condition:
            assert pipeline.condition.wait_for(lambda: pipeline.result is not None, timeout=3)
        assert pipeline.snapshot()['result'].reason == 'pipeline_error'
    finally:
        pipeline.close()


def test_CT_FUS_02_seven_fresh_post_action_results(monkeypatch):
    from threading import Thread
    import attendance.liveness_pipeline as implementation
    clock = [100.0]
    monkeypatch.setattr(implementation, 'monotonic', lambda: clock[0])
    calls = []
    def auxiliary(frame, anchor):
        calls.append(True)
        return evaluation()
    pipeline = AsyncFusionPipeline(Landmarks(), auxiliary, lambda *a: (True, ()))
    pipeline.session = FusionSession(ACTIONS, defer_auxiliary=True)
    pipeline.session.phase = 'verification'
    pipeline.session.index = 3
    pipeline.completed_at = 100.0
    pipeline.anchor = np.ones(128)
    thread = Thread(target=pipeline._auxiliary)
    pipeline.threads = [thread]
    thread.start()
    try:
        for number in range(1, 8):
            clock[0] += 0.5
            pipeline.submit(number, clock[0], np.zeros((100, 100, 3), dtype=np.uint8))
            with pipeline.condition:
                assert pipeline.condition.wait_for(lambda: pipeline.live_count == number, timeout=2)
                if number < 7:
                    assert pipeline.result is None
        assert pipeline.result.status == 'passed'
        assert len(calls) == 7
    finally:
        pipeline.close()


def test_CT_FUS_02_camera_releases():
    class Capture:
        released = False
        def read(self):
            return False, None
        def release(self):
            self.released = True
    capture = Capture()
    camera = LatestFrameCamera(capture)
    camera.close()
    assert capture.released and camera.error == 'camera_error'
