"""S1.5 主动动作活体研究模块。

只接收调用方提取的人脸关键点/姿态特征，不保存视频或原始帧。
该模块只输出动作状态，未经现场验收不得作为正式放行保证。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import random
from typing import Optional


class Action(str, Enum):
    TURN_LEFT = "turn_left"
    TURN_RIGHT = "turn_right"
    NOD = "nod"
    BLINK = "blink"


@dataclass(frozen=True)
class ActionInstruction:
    action: Action
    prompt: str
    duration_s: float = 3.0
    min_angle_deg: float = 20.0
    max_angle_deg: float = 35.0


@dataclass(frozen=True)
class ActionResult:
    status: str
    action: Action
    frames: int
    reason: str = ""


_PROMPTS = {
    Action.TURN_LEFT: "请在3秒内向左转头约20°至35°",
    Action.TURN_RIGHT: "请在3秒内向右转头约20°至35°",
    Action.NOD: "请在3秒内点头一次",
    Action.BLINK: "请在3秒内自然眨眼一次",
}


def choose_instruction(rng: Optional[random.Random] = None) -> ActionInstruction:
    rng = rng or random
    action = rng.choice(tuple(Action))
    return ActionInstruction(action=action, prompt=_PROMPTS[action])


class ActiveLivenessSession:
    """有限状态动作会话；输入为已提取的单帧动作特征。"""

    def __init__(self, instruction: ActionInstruction, max_frames: int = 90):
        self.instruction = instruction
        self.max_frames = max_frames
        self.frames = 0
        self._started = False
        self._completed = False

    def reset(self) -> None:
        self.frames = 0
        self._started = False
        self._completed = False

    def update(self, feature: dict) -> ActionResult:
        if self._completed:
            return ActionResult("passed", self.instruction.action, self.frames, "already_completed")
        self.frames += 1
        if self.frames > self.max_frames:
            self._completed = True
            return ActionResult("timeout", self.instruction.action, self.frames, "frame_limit")
        if not isinstance(feature, dict) or feature.get("face_count") != 1:
            self._started = False
            return ActionResult("pending", self.instruction.action, self.frames, "need_one_face")
        if feature.get("identity_continuous") is False:
            self._completed = True
            return ActionResult("failed", self.instruction.action, self.frames, "identity_changed")
        if feature.get("action_started"):
            self._started = True
        if self._started and feature.get("action_completed"):
            self._completed = True
            return ActionResult("passed", self.instruction.action, self.frames, "action_completed")
        return ActionResult("pending", self.instruction.action, self.frames)
