import pytest

from attendance.active_liveness import Action
from attendance.active_liveness_rules import ActionRule


def test_left_turn_requires_return_to_center():
    rule = ActionRule(Action.TURN_LEFT)
    assert rule.evaluate({"face_count": 1, "yaw_deg": -25})["action_started"]
    assert not rule.evaluate({"face_count": 1, "yaw_deg": -20})["action_completed"]
    assert rule.evaluate({"face_count": 1, "yaw_deg": 2})["action_completed"]


def test_right_turn_and_nod():
    right = ActionRule(Action.TURN_RIGHT)
    right.evaluate({"face_count": 1, "yaw_deg": 25})
    assert right.evaluate({"face_count": 1, "yaw_deg": 0})["action_completed"]
    nod = ActionRule(Action.NOD)
    nod.evaluate({"face_count": 1, "pitch_deg": 25})
    assert nod.evaluate({"face_count": 1, "pitch_deg": 1})["action_completed"]


def test_blink_closed_then_open():
    rule = ActionRule(Action.BLINK)
    assert rule.evaluate({"face_count": 1, "ear": 0.18})["action_started"]
    assert rule.evaluate({"face_count": 1, "ear": 0.34})["action_completed"]


def test_missing_face_resets_rule():
    rule = ActionRule(Action.TURN_LEFT)
    rule.evaluate({"face_count": 1, "yaw_deg": -25})
    rule.evaluate({"face_count": 0})
    assert not rule.evaluate({"face_count": 1, "yaw_deg": 1})["action_completed"]
