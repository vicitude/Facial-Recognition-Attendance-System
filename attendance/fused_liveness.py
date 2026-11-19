"""三动作融合研究会话；结果不是生产放行凭据，不保留图像。"""
from collections import deque
from dataclasses import dataclass
import math

from attendance.active_liveness import Action


def choose_actions(rng=None) -> tuple[Action, ...]:
    return (Action.BLINK, Action.BLINK, Action.BLINK)


def adapt_feature(feature: dict, box) -> dict:
    """关联同一空间人脸，统一为人体左右方向。"""
    try:
        a = tuple(float(v) for v in feature['face_box'])
        b = tuple(float(v) for v in box)
        if len(a) != 4 or len(b) != 4 or not all(math.isfinite(v) for v in a + b):
            raise ValueError('无效人脸框')
        areas = [(r[2] - r[0]) * (r[3] - r[1]) for r in (a, b)]
        if any(r[2] <= r[0] or r[3] <= r[1] for r in (a, b)):
            raise ValueError('无效人脸框')
        intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
        if intersection / (sum(areas) - intersection) < 0.3:
            raise ValueError('检测人脸不一致')
        return dict(feature, yaw_deg=-float(feature['yaw_deg']))
    except (KeyError, TypeError, OverflowError) as exc:
        raise ValueError('无效关键点关联') from exc


@dataclass(frozen=True)
class FusionResult:
    status: str
    action: str
    phase: str
    completed: int
    reason: str


class FusionSession:
    def __init__(self, actions=None, defer_auxiliary=False, eye_thresholds=None, identity_checkpoints=False):
        self.closed_threshold, self.open_threshold = (0.21, 0.28) if eye_thresholds is None else eye_thresholds
        if not (math.isfinite(self.closed_threshold) and math.isfinite(self.open_threshold)
                and 0 < self.closed_threshold < self.open_threshold <= 1):
            raise ValueError('无效眼部阈值')
        self.actions = choose_actions() if actions is None else tuple(actions)
        if (len(self.actions) != 3
                or any(not isinstance(a, Action) for a in self.actions)
                or (self.actions != (Action.BLINK,) * 3
                    and (len(set(self.actions)) != 3 or Action.BLINK not in self.actions))):
            raise ValueError("需要三次眨眼或三个不同且包含眨眼的历史动作")
        self.index = 0
        self.phase = "baseline"
        self.count = 0
        self.baseline_yaw = self.baseline_pitch = 0.0
        self.baseline_samples = []
        self.last_timestamp = self.start_timestamp = self.action_timestamp = None
        self.last_feature = None
        self.passive = deque(maxlen=7)
        self.terminal = None
        self.defer_auxiliary = defer_auxiliary
        self.identity_checkpoints = identity_checkpoints

    def resume_identity(self) -> FusionResult:
        if self.terminal is not None:
            return self.terminal
        if self.phase != 'identity_check':
            raise ValueError('当前不在身份复核阶段')
        self.phase = 'verification' if self.index == 3 else 'baseline'
        self.count = 0
        self.baseline_samples.clear()
        self.action_timestamp = self.last_timestamp
        return self._result()

    def finish_auxiliary(self, approved: bool, reason='passive_not_confirmed') -> FusionResult:
        if self.terminal is not None:
            return self.terminal
        if self.phase != 'verification':
            raise ValueError('动作尚未完成')
        return self._result('passed' if approved else 'failed', 'completed' if approved else reason)

    def _result(self, status="pending", reason=""):
        result = FusionResult(status, self.actions[min(self.index, 2)].value,
                              self.phase, self.index, reason)
        if status != "pending":
            self.terminal = result
        return result

    def update(self, feature: dict, *, timestamp: float, quality_ok: bool,
               passive_status: str, identity_distance: float) -> FusionResult:
        if self.terminal is not None:
            return self.terminal
        try:
            if not isinstance(feature, dict):
                return self._result("failed", "invalid_feature")
            if feature.get("face_count") != 1:
                return self._result("failed", "need_one_face")
            yaw, pitch, ear = (float(feature[k]) for k in ("yaw_deg", "pitch_deg", "ear"))
            if not all(math.isfinite(x) for x in (yaw, pitch, ear)) or not 0 <= ear <= 1 or max(abs(yaw), abs(pitch)) > 90:
                return self._result("failed", "invalid_feature")
            if quality_ok is not True:
                return self._result("failed", "poor_quality")
            distance = float(identity_distance)
            if not math.isfinite(distance) or not 0 <= distance <= 0.8:
                return self._result("failed", "identity_changed")
            timestamp = float(timestamp)
            if not math.isfinite(timestamp) or (self.last_timestamp is not None and timestamp <= self.last_timestamp):
                return self._result("failed", "invalid_time")
        except (ValueError, TypeError, KeyError, OverflowError):
            return self._result("failed", "invalid_feature")
        if self.last_timestamp is not None and timestamp - self.last_timestamp > 0.5:
            return self._result("failed", "frame_gap")
        if passive_status not in {"live_candidate", "spoof_candidate", "low_confidence", "inconclusive", "low_quality", "no_face", "multiple_faces"}:
            return self._result("failed", "invalid_passive")
        if passive_status in {"no_face", "multiple_faces"}:
            return self._result("failed", "need_one_face")
        if passive_status == "low_quality":
            return self._result("failed", "poor_quality")
        if passive_status == "spoof_candidate":
            return self._result("failed", "passive_spoof")
        if self.phase == 'verification':
            self.last_timestamp = timestamp
            return self._result()
        if self.start_timestamp is None:
            self.start_timestamp = self.action_timestamp = timestamp
        if timestamp - self.start_timestamp > 35:
            return self._result("timeout", "session_timeout")
        if self.phase != 'identity_check' and timestamp - self.action_timestamp > 10:
            return self._result("timeout", "action_timeout")
        if self.last_feature is not None:
            previous_yaw, previous_pitch, previous_ear = self.last_feature
            if abs(yaw - previous_yaw) > 12 or abs(pitch - previous_pitch) > 12 or abs(ear - previous_ear) > 0.18:
                return self._result("failed", "trajectory_jump")
        self.last_timestamp = timestamp
        self.last_feature = (yaw, pitch, ear)
        self.passive.append(passive_status)
        if self.phase == 'identity_check':
            return self._result()
        if self.phase == "baseline":
            if ear < self.open_threshold or abs(yaw) > 8 or not 20 <= pitch <= 70:
                self.baseline_samples.clear()
                return self._result()
            self.baseline_samples.append((yaw, pitch))
            if len(self.baseline_samples) > 3:
                self.baseline_samples.pop(0)
            if len(self.baseline_samples) == 3:
                if any(max(p[axis] for p in self.baseline_samples) - min(p[axis] for p in self.baseline_samples) > 4 for axis in (0, 1)):
                    self.baseline_samples = [(yaw, pitch)]
                else:
                    self.baseline_yaw = sum(p[0] for p in self.baseline_samples) / 3
                    self.baseline_pitch = sum(p[1] for p in self.baseline_samples) / 3
                    self.phase, self.count = "outbound", 0
            return self._result()
        dy, dp = yaw - self.baseline_yaw, pitch - self.baseline_pitch
        action = self.actions[self.index]
        if self.phase == "outbound":
            target = {Action.TURN_LEFT: dy <= -20, Action.TURN_RIGHT: dy >= 20,
                      Action.NOD: dp >= 20, Action.BLINK: ear <= self.closed_threshold}[action]
            self.count = self.count + 1 if target else 0
            if self.count >= (2 if action == Action.BLINK else 3):
                self.phase, self.count = "return", 0
        else:
            centered = abs(dy) <= 8 and abs(dp) <= 8 and ear >= self.open_threshold and abs(yaw) <= 8 and 20 <= pitch <= 70
            self.count = self.count + 1 if centered else 0
            if self.count >= 3 and timestamp - self.action_timestamp >= 0.6:
                self.index += 1
                if self.defer_auxiliary and self.identity_checkpoints:
                    self.phase = 'identity_check'
                    return self._result()
                if self.index == 3:
                    if self.defer_auxiliary:
                        self.phase = 'verification'
                        return self._result()
                    if len(self.passive) == 7 and all(p == "live_candidate" for p in self.passive):
                        return self._result("passed", "completed")
                    return self._result("failed", "passive_not_confirmed")
                self.phase, self.count = "baseline", 0
                self.baseline_samples.clear()
                self.action_timestamp = timestamp
        return self._result()
