"""CT-FUS-05 / PT-FUS-07：分阶段身份复核，仅模拟，不证明现场防作弊。"""
import itertools
from threading import Thread

import numpy as np
import pytest

from attendance.active_liveness import Action
from attendance.fused_liveness import FusionSession
from attendance.liveness_pipeline import AsyncFusionPipeline
from attendance.liveness_overlay import preview_lines, draw_chinese_overlay
from tests.test_fused_liveness import ACTIONS, Feed, complete
from tests.test_liveness_pipeline import evaluation


def pipeline_at(phase='identity_check'):
    pipeline = AsyncFusionPipeline(None, None, None)
    pipeline.anchor = np.ones(128)
    pipeline.session = FusionSession(ACTIONS, defer_auxiliary=True, identity_checkpoints=True)
    pipeline.session.phase = phase
    pipeline.session.index = 1
    pipeline.identity_check_at = 100.
    pipeline.metrics.update(baseline_yaw=0., baseline_pitch=45.)
    return pipeline


def check(pipeline, distance=.3, timestamp=101., **changes):
    feature = dict(face_count=1, yaw_deg=0., pitch_deg=45., ear=.3)
    feature.update(changes)
    with pipeline.condition:
        return pipeline._check_identity(feature, distance, timestamp)


def test_PT_FUS_07_every_action_requires_checkpoint():
    for actions in itertools.permutations(ACTIONS):
        session = FusionSession(actions, defer_auxiliary=True, identity_checkpoints=True)
        feed = Feed(session)
        for number, action in enumerate(actions, 1):
            result = complete(feed, action)
            assert result.phase == 'identity_check' and result.completed == number
            for _ in range(3):
                assert feed().phase == 'identity_check'
            result = session.resume_identity()
            assert result.phase == ('verification' if number == 3 else 'baseline')
        assert result.status == 'pending'
    with pytest.raises(ValueError):
        FusionSession(ACTIONS).resume_identity()


@pytest.mark.parametrize('phase', ['baseline', 'outbound', 'return'])
@pytest.mark.parametrize('distance', [.824, .91, 1.4])
def test_PT_FUS_07_action_distance_is_diagnostic(phase, distance):
    pipeline = pipeline_at(phase)
    original = pipeline.anchor.copy()
    assert not check(pipeline, distance, yaw_deg=-22, pitch_deg=55)
    assert pipeline.session.terminal is None and not pipeline.identity_samples
    np.testing.assert_array_equal(pipeline.anchor, original)


def test_CT_FUS_05_old_source_offcenter_and_unstable_not_confirmed():
    pipeline = pipeline_at()
    for _ in range(4):
        assert not check(pipeline, timestamp=99.)
    assert not pipeline.identity_samples
    check(pipeline, yaw_deg=0)
    check(pipeline, yaw_deg=6)  # 极差>4，以当前帧重开。
    assert pipeline.identity_samples == [(6., 45.)]
    check(pipeline, yaw_deg=9)
    assert not pipeline.identity_samples
    check(pipeline)
    check(pipeline)
    assert pipeline.session.phase == 'identity_check'
    check(pipeline)
    assert pipeline.session.phase == 'baseline'


def test_CT_FUS_05_single_outlier_recovers_but_three_failures_reject():
    pipeline = pipeline_at()
    check(pipeline, .9)
    assert pipeline.session.terminal is None
    for _ in range(3):
        check(pipeline, .4)
    assert pipeline.session.phase == 'baseline'
    pipeline = pipeline_at()
    for index, distance in enumerate((.9, .95, 1.0), 1):
        check(pipeline, distance)
        assert pipeline.identity_failures == index
    assert pipeline.result.reason == 'identity_changed'
    np.testing.assert_array_equal(pipeline.anchor, np.ones(128))


@pytest.mark.parametrize('distance', [None, float('nan'), float('inf'), -.1])
def test_CT_FUS_05_invalid_identity_never_deferred(distance):
    pipeline = pipeline_at('outbound')
    check(pipeline, distance)
    assert pipeline.result.reason == 'identity_changed'


def test_CT_FUS_05_timeout_reset_and_verification_gate(monkeypatch):
    import attendance.liveness_pipeline as implementation
    monkeypatch.setattr(implementation, 'monotonic', lambda: 105.01)
    pipeline = pipeline_at()
    pipeline.aux_time = 105.
    with pipeline.condition:
        pipeline._freshness()
    assert pipeline.result.reason == 'identity_check_timeout'
    pipeline.reset()
    assert not pipeline.identity_samples and pipeline.identity_check_at is None
    assert pipeline.identity_failures == 0
    pipeline = pipeline_at('verification')
    assert not check(pipeline, .9)
    assert not check(pipeline, .4, yaw_deg=10)
    assert pipeline.session.terminal is None
    assert check(pipeline, .8)


def test_CT_FUS_05_auxiliary_thread_waits_and_keeps_passive_rejection(monkeypatch):
    import attendance.liveness_pipeline as implementation
    clock = [100.]
    monkeypatch.setattr(implementation, 'monotonic', lambda: clock[0])
    pipeline = pipeline_at('outbound')
    pipeline.aux_time = 100.
    distances = iter((.95, .9, .3, .4, .3, .3))
    statuses = iter(('live_candidate',) * 5 + ('spoof_candidate',))
    def auxiliary(frame, anchor):
        item = evaluation()
        item['identity_distance'] = next(distances)
        item['passive_status'] = next(statuses)
        return item
    pipeline.auxiliary = auxiliary
    worker = Thread(target=pipeline._auxiliary)
    pipeline.threads = [worker]
    worker.start()
    try:
        for number in range(1, 7):
            with pipeline.condition:
                if number == 2:
                    pipeline.session.phase = 'identity_check'
                    pipeline.identity_check_at = clock[0]
                clock[0] += .5
                pipeline.submit(number, clock[0], np.zeros((100, 100, 3), np.uint8))
                assert pipeline.condition.wait_for(lambda: len(pipeline.pending_diagnostics) >= number
                                                   or pipeline.session.terminal is not None, timeout=2)
                if number < 5:
                    assert pipeline.session.terminal is None
                    assert pipeline.session.phase == ('outbound' if number == 1 else 'identity_check')
                if number == 5:
                    assert pipeline.session.phase == 'baseline'
        assert pipeline.result.reason == 'passive_spoof'
    finally:
        pipeline.close()


@pytest.mark.parametrize('status', ['spoof_candidate', 'invalid'])
def test_CT_FUS_05_third_spoof_cannot_resume(monkeypatch, status):
    import attendance.liveness_pipeline as implementation
    clock = [101.]
    monkeypatch.setattr(implementation, 'monotonic', lambda: clock[0])
    pipeline = pipeline_at()
    pipeline.aux_time = 101.
    check(pipeline)
    check(pipeline)
    def auxiliary(frame, anchor):
        item = evaluation()
        item['passive_status'] = status
        return item
    pipeline.auxiliary = auxiliary
    worker = Thread(target=pipeline._auxiliary)
    pipeline.threads = [worker]
    worker.start()
    try:
        pipeline.submit(1, clock[0], np.zeros((100, 100, 3), np.uint8))
        with pipeline.condition:
            assert pipeline.condition.wait_for(lambda: pipeline.session.terminal is not None, timeout=2)
        assert pipeline.result.reason == ('passive_spoof' if status == 'spoof_candidate' else 'invalid_passive')
        assert pipeline.session.phase == 'identity_check'
        assert len(pipeline.identity_samples) == 2
    finally:
        pipeline.close()


def test_CT_FUS_05_inflight_action_cannot_enter_next_baseline(monkeypatch):
    from threading import Event
    import attendance.liveness_pipeline as implementation
    clock = [101.]
    monkeypatch.setattr(implementation, 'monotonic', lambda: clock[0])
    entered, release, processed = Event(), Event(), Event()
    second_entered, second_release = Event(), Event()
    calls = []
    class Detector:
        def detect(self, frame):
            calls.append(True)
            if len(calls) == 1:
                entered.set()
                assert release.wait(2)
            else:
                second_entered.set()
                assert second_release.wait(2)
            return dict(face_count=1, face_box=(0, 0, 100, 100), yaw_deg=0., pitch_deg=45., ear=.3)
        def close(self):
            processed.set()
    pipeline = pipeline_at()
    pipeline.landmarks = Detector()
    pipeline.quality = lambda *a: (True, ())
    pipeline.aux_time = 101.
    pipeline.aux_box = (0, 0, 100, 100)
    pipeline.ready_at = 99.
    pipeline.session.last_timestamp = 100.9
    pipeline.session.start_timestamp = pipeline.session.action_timestamp = 100.
    worker = Thread(target=pipeline._actions)
    pipeline.threads = [worker]
    pipeline.submit(1, 101., np.zeros((100, 100, 3), np.uint8))
    worker.start()
    try:
        assert entered.wait(2)
        clock[0] = 101.1
        for _ in range(3):
            check(pipeline, timestamp=101.05)
        assert pipeline.session.phase == 'baseline'
        assert pipeline.ready_at == pipeline.session.action_timestamp == 101.1
        release.set()
        clock[0] = 101.2
        pipeline.submit(2, 101.2, np.zeros((100, 100, 3), np.uint8))
        assert second_entered.wait(2)  # 第一份结果确已回锁处理，而非close提前截断。
        assert not pipeline.session.baseline_samples
        assert pipeline.session.last_timestamp == 100.9
    finally:
        release.set()
        second_release.set()
        pipeline.close()
    assert processed.is_set()


def test_CT_FUS_05_checkpoint_has_own_timeout_not_previous_action():
    session = FusionSession(ACTIONS, defer_auxiliary=True, identity_checkpoints=True)
    feed = Feed(session)
    complete(feed, ACTIONS[0])
    session.action_timestamp = -10.
    assert feed().status == 'pending'
    assert feed(yaw=13).reason == 'trajectory_jump'


def test_CT_FUS_05_chinese_checkpoint_render():
    pipeline = pipeline_at()
    result = pipeline.session._result()
    assert any('等待身份复核' in line for line in preview_lines(result))
    image = np.zeros((960, 1280, 3), np.uint8)
    painted = draw_chinese_overlay(image, result, dict(identity_check_state='waiting', identity_check_samples=2))
    assert painted.any() and not image.any()
