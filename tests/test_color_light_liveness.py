import numpy as np
import pytest
from attendance.color_light_controller import ScreenColorController
from attendance.color_light_liveness import ColorLightConfig, ColorLivenessSession


def fact(rgb=(100, 100, 100), **overrides):
    values = dict(face_count=1, quality_ok=True, mean_rgb=rgb, identity_vector=np.zeros(128, np.float32),
                  identity_distance=.2, passive_status='live_candidate', motion_score=.001)
    values.update(overrides)
    return values


def submit(s, number, rgb=(100,100,100), color='white', **kw):
    return s.submit(number, number * .1, fact(rgb, **kw), color)


def session():
    s = ColorLivenessSession('e1', ColorLightConfig(enabled=True))
    s.start(0)
    return s


def test_color_ratio_config_accepts_adjustable_threshold():
    assert ColorLightConfig(enabled=True, min_color_ratio=0.90).min_color_ratio == 0.90
    with pytest.raises(ValueError):
        ColorLightConfig(enabled=True, min_color_ratio=0.45)


def test_controller_roundtrip_and_invalid():
    c = ScreenColorController()
    c.set_color('red')
    assert c.current_color() == 'red'
    with pytest.raises(ValueError):
        c.set_color('purple')


def test_UT_CLR_04_two_cycles_and_final_white_gate():
    s = ColorLivenessSession('e1', ColorLightConfig(enabled=True, cycles=2))
    s.start(0)
    for i in range(1, 4):
        result = submit(s, i)
        assert result.metrics['baseline_samples'] == i
        assert result.accepted_samples == 0
    assert result.phase == 'color_challenge'
    fid = 4
    for _ in range(2):
        for color, rgb in (('red', (160,20,20)), ('green', (20,160,20)), ('blue', (20,20,160))):
            for _ in range(3):
                result = submit(s, fid, rgb, color)
                fid += 1
                assert result.color == color
            result = s.finish_color()
    assert (result.phase, result.color, result.accepted_samples) == ('verifying', 'white', 18)
    assert submit(s, fid).status == 'passed'
    assert s.cancel().status == 'passed'


@pytest.mark.parametrize('color,rgb,reason', [('red',(160,20,20),'COLOR_UNRESPONSIVE'),
                                              ('red',(30,200,20),'COLOR_UNRESPONSIVE'),
                                              ('blue',(20,20,160),'COLOR_SEQUENCE_MISMATCH')])
def test_UT_CLR_05_static_cast_wrong_response_and_color(color, rgb, reason):
    s = session()
    for i in range(1, 4):
        submit(s, i, (160,20,20))
    for i in range(4, 7):
        result = submit(s, i, rgb, color)
    if color == 'red':
        assert result.status == 'pending'
        result = s.finish_color()
    assert result.status == 'rejected' and result.reason == reason


def test_UT_CLR_07_invalid_motion_is_quality_rejected():
    s = session()
    for i in range(1, 4):
        submit(s, i)
    result = submit(s, 4, color='red', motion_score=1.1)
    assert (result.status, result.reason) == ('rejected', 'COLOR_QUALITY_REJECTED')


@pytest.mark.parametrize('distance', [None, -.1, .81, float('nan')])
def test_UT_CLR_07_baseline_does_not_bypass_identity(distance):
    s = session()
    result = submit(s, 1, identity_distance=distance)
    assert result.reason == 'COLOR_IDENTITY_REJECTED' and result.status == 'rejected'
    assert result.metrics['baseline_samples'] == 0


@pytest.mark.parametrize('kw,reason', [(dict(face_count=0), 'COLOR_WAITING_FACE'),
                                       (dict(quality_ok=False), 'COLOR_QUALITY_REJECTED'),
                                       (dict(passive_status='low_confidence'), 'COLOR_PASSIVE_REJECTED')])
def test_UT_CLR_07_recovers_baseline_after_wait(kw, reason):
    s = session()
    submit(s, 1)
    result = submit(s, 2, **kw)
    assert result.status == 'pending' and result.reason == reason and result.metrics['baseline_samples'] == 0
    assert submit(s, 3).metrics['baseline_samples'] == 1


def test_PT_CLR_06_motion_is_skipped_without_advancing_color():
    s = session()
    for i in range(1, 4):
        submit(s, i)
    before = s.snapshot()
    result = submit(s, 4, (160, 20, 20), 'red', motion_score=.5)
    assert result.status == 'pending' and result.phase == before.phase and result.color == 'red'
    assert result.accepted_samples == before.accepted_samples
    assert result.metrics['color_motion_skips'] == 1
    good = submit(s, 5, (160, 20, 20), 'red')
    assert good.metrics['color_samples'] == good.metrics['color_hits'] == 1
    for i in (6, 7):
        submit(s, i, (160, 20, 20), 'red')
    next_color = s.finish_color()
    assert next_color.color == 'green'
    assert all(next_color.metrics[key] == 0 for key in ('color_samples', 'color_hits', 'color_motion_skips'))


@pytest.mark.parametrize('overrides,reason', [({'identity_distance': .81}, 'COLOR_IDENTITY_REJECTED'),
                                             ({'passive_status': 'spoof_candidate'}, 'COLOR_PASSIVE_REJECTED')])
def test_PT_CLR_06_motion_does_not_hide_rejections(overrides, reason):
    s = session()
    for i in range(1, 4):
        submit(s, i)
    result = submit(s, 4, color='red', motion_score=.5, **overrides)
    assert (result.status, result.reason) == ('rejected', reason)
    assert result.metrics['color_motion_skips'] == 0


def test_UT_CLR_08_spoof_rejected_and_terminal_immutable():
    s = session()
    result = submit(s, 1, passive_status='spoof_candidate')
    assert result.reason == 'COLOR_PASSIVE_REJECTED'
    assert submit(s, 2) == s.cancel() == result
