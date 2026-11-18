"""SPEC-007 模拟轨迹，不代替真人/攻击现场验收。"""
import itertools
import random
import pytest

from attendance.active_liveness import Action
from attendance.fused_liveness import FusionSession, choose_actions, adapt_feature
from attendance.active_liveness_features import build_action_feature

ACTIONS = (Action.BLINK, Action.TURN_LEFT, Action.NOD)


class Feed:
    def __init__(self, session):
        self.session = session
        self.t = 0.0

    def __call__(self, yaw=0, pitch=45, ear=0.30, **kw):
        self.t += 0.1
        feature = dict(face_count=1, yaw_deg=yaw, pitch_deg=pitch, ear=ear)
        feature.update(kw.pop('feature', {}))
        args = dict(timestamp=self.t, quality_ok=True, passive_status='live_candidate', identity_distance=0.1)
        args.update(kw)
        return self.session.update(feature, **args)


def complete(feed, action, passive='live_candidate'):
    for _ in range(3):
        feed(passive_status=passive)
    if action == Action.BLINK:
        for ear in (0.20, 0.20, 0.30, 0.30, 0.30):
            result = feed(ear=ear, passive_status=passive)
    else:
        sign = -1 if action == Action.TURN_LEFT else 1
        for angle in (10, 20, 22, 22, 12, 4, 0, 0):
            result = feed(yaw=angle * sign if action != Action.NOD else 0,
                          pitch=45 + angle if action == Action.NOD else 45,
                          passive_status=passive)
    return result


def test_PT_FUS_03_default_blinks():
    for seed in range(100):
        assert choose_actions(random.Random(seed)) == (Action.BLINK,) * 3
    assert FusionSession().actions == (Action.BLINK,) * 3
    for invalid in ((), (Action.BLINK,) * 2, (Action.BLINK, Action.BLINK, Action.NOD), (Action.TURN_LEFT, Action.TURN_RIGHT, Action.NOD)):
        with pytest.raises(ValueError):
            FusionSession(invalid)


def test_PT_FUS_08_three_distinct_blink_cycles():
    feed = Feed(FusionSession())
    for expected in range(1, 4):
        for _ in range(3):
            feed()
        feed(ear=.2)  # 单帧闭眼不能形成目标。
        feed()
        assert feed.session.index == expected - 1
        for _ in range(20):
            result = feed(ear=.2)
        assert result.completed == expected - 1  # 长闭眼不能重复计数。
        for _ in range(3):
            result = feed()
        assert result.completed == expected
    assert result.status == 'passed'


def test_CT_FUS_06_default_checkpoints_and_auxiliary():
    from attendance.liveness_overlay import preview_lines
    session = FusionSession(defer_auxiliary=True, identity_checkpoints=True)
    feed = Feed(session)
    for expected in range(1, 4):
        result = complete(feed, Action.BLINK)
        assert result.phase == 'identity_check'
        assert result.completed == expected
        assert result.status == 'pending'
        session.resume_identity()  # 辅助三份规则由pipeline既有测试覆盖。
    assert session.phase == 'verification'
    assert session.terminal is None
    assert '三次眨眼' in ''.join(preview_lines(session._result()))
    assert session.finish_auxiliary(True).status == 'passed'
    assert FusionSession().index == 0


def test_PT_FUS_08_static_default_never_passes():
    feed = Feed(FusionSession())
    for _ in range(120):
        assert feed().status != 'passed'


def test_UT_FUS_01_all_action_orders():
    for pair in itertools.combinations((Action.TURN_LEFT, Action.TURN_RIGHT, Action.NOD), 2):
        for actions in itertools.permutations((Action.BLINK,) + pair):
            feed = Feed(FusionSession(actions))
            for action in actions:
                result = complete(feed, action)
            assert result.status == 'passed', (actions, result)
            assert result.completed == 3


def test_PT_FUS_02_static_never_passes():
    for actions in itertools.permutations(ACTIONS):
        feed = Feed(FusionSession(actions))
        for _ in range(120):
            assert feed().status != 'passed'


@pytest.mark.parametrize('kwargs,reason', [
    ({'feature': {'face_count': 2}}, 'need_one_face'),
    ({'feature': {'face_count': 0}}, 'need_one_face'),
    ({'quality_ok': False}, 'poor_quality'),
    ({'identity_distance': 0.81}, 'identity_changed'),
    ({'identity_distance': float('nan')}, 'identity_changed'),
    ({'feature': {'yaw_deg': float('nan')}}, 'invalid_feature'),
    ({'feature': {'ear': 2}}, 'invalid_feature'),
    ({'passive_status': 'bypass'}, 'invalid_passive'),
])
def test_UT_FUS_02_validation(kwargs, reason):
    assert Feed(FusionSession(ACTIONS))(**kwargs).reason == reason


def test_UT_FUS_03_trajectory_and_time():
    feed = Feed(FusionSession(ACTIONS))
    feed()
    assert feed(yaw=13).reason == 'trajectory_jump'
    feed = Feed(FusionSession(ACTIONS))
    feed()
    assert feed(timestamp=0.1).reason == 'invalid_time'
    feed = Feed(FusionSession(ACTIONS))
    feed()
    assert feed(timestamp=0.61).reason == 'frame_gap'
    feed = Feed(FusionSession(ACTIONS))
    for _ in range(102):
        result = feed()
    assert result.status == 'timeout'
    assert result.reason == 'action_timeout'


def test_UT_FUS_04_passive_rejection():
    assert Feed(FusionSession(ACTIONS))(passive_status='spoof_candidate').reason == 'passive_spoof'
    feed = Feed(FusionSession(ACTIONS))
    for action in ACTIONS:
        result = complete(feed, action, passive='low_confidence')
    assert result.status == 'failed'
    assert result.reason == 'passive_not_confirmed'


def test_PT_FUS_01_terminal_is_irreversible():
    passed = Feed(FusionSession(ACTIONS))
    for action in ACTIONS:
        complete(passed, action)
    failed = Feed(FusionSession(ACTIONS))
    failed(quality_ok=False)
    timeout = Feed(FusionSession(ACTIONS))
    for _ in range(103):
        timeout()
    for feed in (passed, failed, timeout):
        terminal = feed.session.terminal
        assert terminal.status in ('passed', 'failed', 'timeout')
        for _ in range(100):
            assert feed(feature={'face_count': 2}) == terminal


def test_UT_FUS_05_spatial_association_and_direction():
    points = dict(left_eye=(40, 30), right_eye=(60, 30), nose=(58, 40), chin=(50, 60))
    feature = build_action_feature(points)
    feature['face_box'] = (20, 10, 80, 90)
    adapted = adapt_feature(feature, (15, 5, 85, 95))
    assert feature['yaw_deg'] > 20
    assert adapted['yaw_deg'] < -20  # 原始图像右偏=人体左转。
    points['nose'] = (42, 40)
    feature['yaw_deg'] = build_action_feature(points)['yaw_deg']
    assert adapt_feature(feature, (15, 5, 85, 95))['yaw_deg'] > 20
    with pytest.raises(ValueError):
        adapt_feature(feature, (200, 200, 300, 300))
    with pytest.raises(ValueError):
        adapt_feature(feature, (0, 0, 0, 1))


def test_UT_FUS_06_off_center_not_baseline():
    feed = Feed(FusionSession(ACTIONS))
    for _ in range(8):
        result = feed(yaw=30)
    assert result.phase == 'baseline'
    assert not feed.session.baseline_samples


def test_UT_FUS_03_single_target_frame_not_enough():
    feed = Feed(FusionSession(ACTIONS))
    for _ in range(3):
        feed()
    feed(ear=0.2)
    for _ in range(5):
        result = feed()
    assert result.completed == 0
    assert result.phase == 'outbound'
