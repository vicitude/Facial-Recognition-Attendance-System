"""CT-FUS-04 / UT-FUS-09：只用数值和预览替身验证准备门禁。"""
import numpy as np
import pytest
from attendance.liveness_preparation import EyePreparation
from attendance.fused_liveness import FusionSession
from attendance.liveness_pipeline import StableIdentityBaseline, AsyncFusionPipeline


def feature(ear=.25, **changes):
    return dict(dict(face_count=1, yaw_deg=0., pitch_deg=53., ear=ear), **changes)


class Feed:
    def __init__(self):
        self.prep = EyePreparation()
        self.time = 0.
    def __call__(self, ear=.25, count=1, **changes):
        for _ in range(count):
            self.time += .05
            self.prep.update(feature(ear, **changes), timestamp=self.time, quality_ok=True)
        return self.prep


def calibrate(feed):
    feed(count=15)
    assert feed.prep.stage == 'close'
    feed(.12, count=3)
    assert feed.prep.stage == 'reopen'
    feed(count=5)
    assert feed.prep.stage == 'ready' and not feed.prep.ready
    feed(count=15)
    assert feed.prep.ready
    return feed.prep


def test_CT_FUS_04_low_ear_complete_and_fixed_thresholds():
    prep = calibrate(Feed())
    assert prep.closed_threshold == pytest.approx(.1525)
    assert prep.open_threshold == pytest.approx(.2175)
    baseline = StableIdentityBaseline()
    for _ in range(3):
        ready = baseline.observe(feature(), np.ones(128), prep.open_threshold)
    assert ready
    session = FusionSession(eye_thresholds=(prep.closed_threshold, prep.open_threshold))
    for n in range(3):
        result = session.update(feature(), timestamp=n*.1, quality_ok=True,
                                passive_status='inconclusive', identity_distance=.1)
    assert result.phase == 'outbound'
    assert session.open_threshold < .25
    # 校准阈值贯穿三个动作，而非只放过准备阶段。
    from attendance.active_liveness import Action
    session = FusionSession((Action.BLINK, Action.TURN_LEFT, Action.TURN_RIGHT),
                            defer_auxiliary=True, eye_thresholds=(prep.closed_threshold, prep.open_threshold))
    timestamp = 0.
    def send(ear=.25, yaw=0., count=1):
        nonlocal timestamp
        for _ in range(count):
            timestamp += .1
            result = session.update(feature(ear, yaw_deg=yaw), timestamp=timestamp,
                                    quality_ok=True, passive_status='inconclusive', identity_distance=.1)
        return result
    send(count=3)
    send(.12, count=2)
    send(count=3)
    for sign in (-1, 1):
        send(count=3)
        send(yaw=sign*10)
        send(yaw=sign*20, count=3)
        send(yaw=sign*10)
        result = send(count=3)
    assert result.phase == 'verification' and result.completed == 3
    assert result.status == 'pending'  # 动作完成仍须辅助确认。


@pytest.mark.parametrize('ear', [.12, .25])
def test_CT_FUS_04_static_never_ready(ear):
    feed = Feed()
    feed(ear, count=200)
    assert not feed.prep.ready and feed.prep.calibrated_at is None


def test_CT_FUS_04_invalid_and_timeout_reset():
    feed = Feed()
    feed(count=15)
    feed(face_count=2)
    assert feed.prep.stage == 'open'
    calibrate(feed)
    thresholds = (feed.prep.closed_threshold, feed.prep.open_threshold)
    feed(yaw_deg=9)
    assert not feed.prep.ready and feed.prep.stage == 'ready'
    assert thresholds == (feed.prep.closed_threshold, feed.prep.open_threshold)
    feed.time += .6
    feed()
    assert feed.prep.calibrated_at is None and not feed.prep.ready
    feed.prep.update(feature(), timestamp=30., quality_ok=True)
    assert feed.prep.failed and feed.prep.reason == 'calibration_timeout'
    feed.prep.reset()
    assert feed.prep.stage == 'open' and not feed.prep.failed
    feed.prep.update(feature(), timestamp=float('nan'), quality_ok=True)
    assert feed.prep.reason == 'invalid_time'


def test_CT_FUS_04_quality_and_unstable_never_ready():
    prep = EyePreparation()
    prep.update(feature(), timestamp=0., quality_ok=False)
    assert prep.reason == 'poor_quality'
    for n in range(1, 30):
        prep.update(feature(yaw_deg=(-3 if n % 2 else 3)), timestamp=n*.05, quality_ok=True)
    assert len(prep.samples) == 1 and not prep.ready


def test_CT_FUS_04_auxiliary_requires_calibrated_new_source(monkeypatch):
    from threading import Thread
    import attendance.liveness_pipeline as implementation
    clock = [100.]
    monkeypatch.setattr(implementation, 'monotonic', lambda: clock[0])
    def auxiliary(frame, anchor):
        return dict(feature=dict(feature(), face_box=(0, 0, 100, 100)), quality_ok=True,
                    identity_vector=np.ones(128), identity_distance=None,
                    passive_status='live_candidate', timings_ms={})
    pipeline = AsyncFusionPipeline(None, auxiliary, None)
    worker = Thread(target=pipeline._auxiliary)
    pipeline.threads = [worker]
    worker.start()
    try:
        for n in range(1, 6):
            clock[0] += .5
            if n == 2:
                pipeline.preparation = calibrate(Feed())
                pipeline.preparation.calibrated_at = clock[0] + .1
            pipeline.submit(n, clock[0], np.zeros((100, 100, 3), dtype=np.uint8))
            with pipeline.condition:
                assert pipeline.condition.wait_for(lambda: len(pipeline.pending_diagnostics) >= n, timeout=2)
                if n <= 2:
                    assert pipeline.anchor is None and pipeline.metrics['baseline_samples'] == 0
        assert pipeline.anchor is not None and pipeline.metrics['baseline_samples'] == 3
        assert pipeline.session is None  # 辅助线程不能自行开始动作。
    finally:
        pipeline.close()


def test_CT_FUS_04_actions_start_with_calibrated_thresholds():
    from threading import Thread
    from time import monotonic
    from tests.test_liveness_pipeline import Landmarks
    class LowEar(Landmarks):
        def detect(self, frame):
            return dict(super().detect(frame), ear=.25)
    pipeline = AsyncFusionPipeline(LowEar(), None, lambda *a: (True, ()))
    pipeline.preparation = calibrate(Feed())
    pipeline.anchor = np.ones(128)
    pipeline.aux = {}
    pipeline.aux_time = monotonic()
    pipeline.preparation.last_timestamp = monotonic() - .05
    pipeline.preparation.samples = [(monotonic() - .7 + i*.04, 0., 45., .25) for i in range(16)]
    worker = Thread(target=pipeline._actions)
    pipeline.threads = [worker]
    worker.start()
    try:
        pipeline.submit(1, monotonic(), np.zeros((100, 100, 3), dtype=np.uint8))
        # 动作线程该路径不通知；condition周期等待同时验证线程仍存活。
        with pipeline.condition:
            assert pipeline.condition.wait_for(lambda: pipeline.session is not None, timeout=2)
        assert pipeline.session.open_threshold == pytest.approx(.2175)
        assert pipeline.session.closed_threshold == pytest.approx(.1525)
    finally:
        pipeline.close()


def test_CT_FUS_04_reset_clears_preparation():
    pipeline = AsyncFusionPipeline(None, None, None)
    pipeline.preparation = calibrate(Feed())
    pipeline.reset()
    assert pipeline.preparation.open_threshold is None and not pipeline.preparation.ready


def test_UT_FUS_09_preparation_chinese_in_actual_drawing(monkeypatch):
    from attendance.liveness_overlay import draw_chinese_overlay
    from PIL import ImageDraw
    text = []
    original = ImageDraw.ImageDraw.text
    def record(draw, xy, value, **kwargs):
        text.append(value)
        return original(draw, xy, value, **kwargs)
    monkeypatch.setattr(ImageDraw.ImageDraw, 'text', record)
    for stage, expected in [('open', '自然睁眼'), ('close', '请闭眼'), ('reopen', '重新睁眼'), ('ready', '眼部校准完成')]:
        text.clear()
        draw_chinese_overlay(np.zeros((960, 1280, 3), dtype=np.uint8), None,
                             dict(preparation_stage=stage), warming=True)
        assert expected in '\n'.join(text)


@pytest.mark.parametrize('thresholds', [(0, .2), (.3, .2), (.1, float('nan'))])
def test_CT_FUS_04_invalid_thresholds(thresholds):
    with pytest.raises(ValueError):
        FusionSession(eye_thresholds=thresholds)
