"""S1.5 主动动作特征规则层（方案2）。"""
from __future__ import annotations

from attendance.active_liveness import Action


class ActionRule:
    def __init__(self, action: Action, start_threshold: float = 20.0, complete_threshold: float = 8.0, blink_closed: float = 0.21, blink_open: float = 0.28):
        self.action = action
        self.start_threshold = start_threshold
        self.complete_threshold = complete_threshold
        self.blink_closed = blink_closed
        self.blink_open = blink_open
        self.started = False
        self.closed = False

    def reset(self):
        self.started = False
        self.closed = False

    def evaluate(self, feature: dict) -> dict:
        if feature.get("face_count") != 1:
            self.reset()
            return {"action_started": False, "action_completed": False}
        yaw = float(feature.get("yaw_deg", 0.0))
        pitch = float(feature.get("pitch_deg", 0.0))
        ear = feature.get("ear")
        started = completed = False
        if self.action == Action.TURN_LEFT:
            started = yaw <= -self.start_threshold
            completed = self.started and abs(yaw) <= self.complete_threshold
        elif self.action == Action.TURN_RIGHT:
            started = yaw >= self.start_threshold
            completed = self.started and abs(yaw) <= self.complete_threshold
        elif self.action == Action.NOD:
            started = pitch >= self.start_threshold
            completed = self.started and abs(pitch) <= self.complete_threshold
        elif self.action == Action.BLINK:
            if ear is None:
                return {"action_started": False, "action_completed": False}
            if float(ear) <= self.blink_closed:
                self.closed = True
            started = self.closed
            completed = self.closed and float(ear) >= self.blink_open
        if started:
            self.started = True
        if completed:
            self.started = False
            self.closed = False
        return {"action_started": started, "action_completed": completed}
