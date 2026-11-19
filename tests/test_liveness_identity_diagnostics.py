"""CT-FUS-03 身份准备与终态诊断，不加载模型或摄像头。"""
import numpy as np
import pytest
from attendance.liveness_pipeline import StableIdentityBaseline, AsyncFusionPipeline
from attendance.fused_liveness import FusionSession


def feature(**changes):
    return dict(dict(face_count=1, yaw_deg=0., pitch_deg=45., ear=.3), **changes)


def test_CT_FUS_03_three_stable_samples():
    baseline = StableIdentityBaseline()
    vector = np.ones(128)
    assert not baseline.observe(feature(), vector)
    assert not baseline.observe(feature(yaw_deg=2), vector)
    assert baseline.observe(feature(yaw_deg=4), vector)
    baseline.reset()
    assert not baseline.samples


@pytest.mark.parametrize('changes', [dict(yaw_deg=8.1), dict(pitch_deg=19.9), dict(pitch_deg=70.1), dict(ear=.27), dict(face_count=2)])
def test_CT_FUS_03_invalid_pose_resets(changes):
    baseline = StableIdentityBaseline()
    baseline.observe(feature(), np.ones(128))
    assert not baseline.observe(feature(**changes), np.ones(128))
    assert not baseline.samples


def test_CT_FUS_03_spread_restarts_and_invalid_vector_rejected():
    baseline = StableIdentityBaseline()
    baseline.observe(feature(yaw_deg=-3), np.ones(128))
    assert not baseline.observe(feature(yaw_deg=3), np.ones(128))
    assert baseline.samples == [(3., 45.)]
    with pytest.raises(ValueError):
        baseline.observe(feature(), np.full(128, np.nan))


def test_CT_FUS_03_auxiliary_baseline_then_identity_reject(monkeypatch):
    from threading import Thread
    import attendance.liveness_pipeline as implementation
    clock = [100.]
    monkeypatch.setattr(implementation, 'monotonic', lambda: clock[0])
    observed_anchors = []
    def auxiliary(frame, anchor):
        observed_anchors.append(anchor)
        return dict(feature=dict(feature(), face_box=(0, 0, 100, 100)), quality_ok=True,
                    identity_vector=np.ones(128), identity_distance=None if anchor is None else .91,
                    passive_status='live_candidate', timings_ms={})
    pipeline = AsyncFusionPipeline(None, auxiliary, None)
    # 此测试隔离身份门禁；实际校准入口由CT-FUS-04覆盖。
    pipeline.preparation.ready = True
    pipeline.preparation.calibrated_at = 99.
    pipeline.preparation.open_threshold = .2175
    worker = Thread(target=pipeline._auxiliary)
    pipeline.threads = [worker]
    worker.start()
    try:
        for number in range(1, 5):
            clock[0] += .5
            pipeline.submit(number, clock[0], np.zeros((100, 100, 3), dtype=np.uint8))
            with pipeline.condition:
                assert pipeline.condition.wait_for(
                    lambda: len(pipeline.pending_diagnostics) >= number, timeout=2)
                if number < 3:
                    assert pipeline.anchor is None and pipeline.session is None
                if number == 3:
                    assert pipeline.anchor is not None
        snapshot = pipeline.snapshot()
        assert all(anchor is None for anchor in observed_anchors[:3])
        assert observed_anchors[3] is not None
        assert snapshot['result'].reason == 'identity_changed'
        assert snapshot['metrics']['identity_distance'] == .91
        assert snapshot['metrics']['baseline_samples'] == 3
        assert len(snapshot['diagnostics']) == 4
        assert pipeline.snapshot()['diagnostics'] == []
    finally:
        pipeline.close()


def test_CT_FUS_03_terminal_freezes_and_reset_clears(monkeypatch):
    import attendance.liveness_pipeline as implementation
    clock = [100.]
    monkeypatch.setattr(implementation, 'monotonic', lambda: clock[0])
    pipeline = AsyncFusionPipeline(None, None, None)
    pipeline.metrics = dict(identity_distance=.91, identity_threshold=.8)
    pipeline.aux_time = 90.
    with pipeline.condition:
        pipeline._fail('identity_changed', source_timestamp=99.)
    first = pipeline.snapshot()
    assert first['metrics']['aux_age_ms'] == 1000.
    clock[0] = 120.
    assert pipeline.snapshot()['metrics'] == first['metrics']
    assert first['result'].reason == 'identity_changed'
    pipeline.reset()
    assert pipeline.snapshot()['metrics'] == {'aux_age_ms': None}
    assert pipeline.terminal_metrics is None and not pipeline.baseline.samples
