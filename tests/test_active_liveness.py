import random

from attendance.active_liveness import Action, ActiveLivenessSession, choose_instruction


def test_random_instruction_is_supported_and_explicit():
    instruction = choose_instruction(random.Random(2))
    assert instruction.action in tuple(Action)
    assert "3秒" in instruction.prompt


def test_action_requires_one_face_and_then_completes():
    session = ActiveLivenessSession(choose_instruction(random.Random(1)))
    assert session.update({"face_count": 0}).status == "pending"
    assert session.update({"face_count": 1, "action_started": True}).status == "pending"
    result = session.update({"face_count": 1, "action_completed": True})
    assert result.status == "passed"
    assert session.update({"face_count": 1}).status == "passed"


def test_identity_change_fails_and_frame_limit_times_out():
    failed = ActiveLivenessSession(choose_instruction(random.Random(1)), max_frames=3)
    result = failed.update({"face_count": 1, "identity_continuous": False})
    assert result.status == "failed"
    timed = ActiveLivenessSession(choose_instruction(random.Random(1)), max_frames=1)
    timed.update({"face_count": 1})
    assert timed.update({"face_count": 1}).status == "timeout"
