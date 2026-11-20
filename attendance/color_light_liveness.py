"""低负载屏幕彩光响应状态机；仅保存有界数值，不保存图像。"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from statistics import median
import math
import numpy as np

QUALITY_ISSUES = ("face_too_small", "too_dark", "too_bright", "blurry", "other_quality")


class ColorStatus(str, Enum):
    PENDING = "pending"
    PASSED = "passed"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    ERROR = "error"


class ColorPhase(str, Enum):
    DISABLED = "disabled"
    WARMING = "warming"
    BASELINE = "baseline"
    COLOR_CHALLENGE = "color_challenge"
    VERIFYING = "verifying"
    PASSED = "passed"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass(frozen=True)
class ColorLightConfig:
    enabled: bool = False
    sequence: tuple = ("red", "green", "blue")
    color_duration_ms: int = 2000
    settle_ms: int = 80
    cycles: int = 1
    baseline_frames: int = 3
    sample_frames_per_color: int = 3
    max_session_ms: int = 25000
    min_fps: float = 8.0
    max_frame_age_ms: int = 250
    identity_threshold: float = 0.8
    chroma_delta_threshold: float = 0.08
    motion_threshold: float = 0.015
    min_color_ratio: float = 0.85

    def __post_init__(self):
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be bool")
        if len(self.sequence) != 3 or set(self.sequence) != {"red", "green", "blue"}:
            raise ValueError("invalid sequence")
        if not (80 <= self.color_duration_ms <= 2000 and 30 <= self.settle_ms <= 200
                and self.settle_ms < self.color_duration_ms):
            raise ValueError("invalid timing")
        if self.cycles not in (1, 2) or not 1 <= self.baseline_frames <= 10 or not 1 <= self.sample_frames_per_color <= 10:
            raise ValueError("invalid frame count")
        if not 5000 <= self.max_session_ms <= 30000 or not 5.0 <= self.min_fps <= 15.0 or not 50 <= self.max_frame_age_ms <= 500:
            raise ValueError("invalid session limits")
        if any(not 0.0 <= value <= 1.0 for value in (self.identity_threshold, self.chroma_delta_threshold, self.motion_threshold)):
            raise ValueError("invalid threshold")
        if not 0.5 <= self.min_color_ratio <= 1.0:
            raise ValueError("invalid min_color_ratio")


@dataclass(frozen=True)
class ColorResult:
    status: str
    phase: str
    color: str | None
    cycle: int
    accepted_samples: int
    reason: str | None
    metrics: dict = field(default_factory=dict)


class ColorLivenessSession:
    def __init__(self, employee_id: str, config: ColorLightConfig, auxiliary=None):
        self.employee_id = employee_id
        self.config = config
        self.auxiliary = auxiliary
        self._status = ColorStatus.PENDING.value
        self._phase = ColorPhase.DISABLED.value
        self._color = None
        self._cycle = 0
        self._accepted = 0
        self._reason = None
        self._metrics = {"baseline_samples": 0}
        self._started = None
        self._last_frame = -1
        self._last_timestamp = None
        self._color_samples = self._color_hits = self._color_motion_skips = 0
        self._baseline = []
        self._baseline_chroma = None
        self._quality_issue = None
        self._quality_skips = {}
        self._color_deltas = []
        self._color_diagnostics = []

    def _color_row(self):
        return dict(cycle=self._cycle + 1, color=self._color, samples=self._color_samples,
                    hits=self._color_hits, motion_skips=self._color_motion_skips,
                    quality_skips=self._quality_skips.copy(),
                    delta_median=median(self._color_deltas) if self._color_deltas else None,
                    delta_peak=max(self._color_deltas) if self._color_deltas else None)

    def _result(self):
        rows = [dict(row, quality_skips=row['quality_skips'].copy()) for row in self._color_diagnostics]
        if self._phase == ColorPhase.COLOR_CHALLENGE.value:
            rows.append(self._color_row())
        ratio = (self._color_hits / self._color_samples) if self._color_samples else 0.0
        metrics = dict(self._metrics, color_samples=self._color_samples,
                       color_hits=self._color_hits, color_motion_skips=self._color_motion_skips,
                       color_ratio=ratio, min_color_ratio=self.config.min_color_ratio,
                       quality_issue=self._quality_issue, color_diagnostics=rows)
        return ColorResult(self._status, self._phase, self._color, self._cycle, self._accepted, self._reason, metrics)

    def start(self, timestamp: float) -> ColorResult:
        if self._status != ColorStatus.PENDING.value or self._started is not None or not math.isfinite(timestamp):
            return self._result()
        self._started = timestamp
        self._last_timestamp = timestamp
        self._phase = ColorPhase.BASELINE.value
        self._color = "white"
        return self._result()

    def _reject(self, reason: str, status=ColorStatus.REJECTED.value, phase=ColorPhase.REJECTED.value):
        if self._phase == ColorPhase.COLOR_CHALLENGE.value:
            self._color_diagnostics.append(self._color_row())
            self._color_deltas.clear()
        self._status, self._phase, self._reason = status, phase, reason
        return self._result()

    def submit(self, frame_id: int, timestamp: float, frame, light_state: str) -> ColorResult:
        if self._status != ColorStatus.PENDING.value:
            return self._result()
        if self._started is None or not isinstance(frame, dict):
            return self._reject("COLOR_INVALID_INPUT")
        if not math.isfinite(timestamp) or frame_id <= self._last_frame or timestamp <= self._last_timestamp:
            return self._reject("COLOR_PERFORMANCE_INSUFFICIENT")
        if (timestamp - self._started) * 1000 >= self.config.max_session_ms:
            return self._reject("COLOR_TIMEOUT", ColorStatus.TIMEOUT.value, ColorPhase.TIMEOUT.value)
        self._last_frame, self._last_timestamp = frame_id, timestamp
        if light_state != self._color:
            return self._reject("COLOR_SEQUENCE_MISMATCH")
        baseline = self._phase == ColorPhase.BASELINE.value
        face_count = frame.get("face_count")
        if face_count != 1:
            return self._wait_or_reject("COLOR_WAITING_FACE" if face_count == 0 else "COLOR_QUALITY_REJECTED",
                                        baseline and face_count == 0)
        motion = frame.get("motion_score")
        quality_ok = frame.get("quality_ok")
        motion_valid = isinstance(motion, (int, float)) and 0 <= motion <= 1
        if (self._phase == ColorPhase.COLOR_CHALLENGE.value and quality_ok is False
                and motion_valid):
            issue = frame.get("quality_issue")
            self._quality_issue = issue if isinstance(issue, str) and issue in QUALITY_ISSUES else "other_quality"
            self._quality_skips[self._quality_issue] = self._quality_skips.get(self._quality_issue, 0) + 1
            self._reason = "COLOR_QUALITY_SKIPPED"
            return self._result()
        if quality_ok is not True or not motion_valid:
            return self._wait_or_reject("COLOR_QUALITY_REJECTED", baseline)
        vector, distance = frame.get("identity_vector"), frame.get("identity_distance")
        if (not isinstance(vector, np.ndarray) or vector.shape != (128,) or vector.dtype != np.float32
                or not np.isfinite(vector).all() or not isinstance(distance, (int, float))
                or not 0 <= distance <= self.config.identity_threshold):
            return self._reject("COLOR_IDENTITY_REJECTED")
        passive = frame.get("passive_status")
        if passive != "live_candidate":
            return self._wait_or_reject("COLOR_PASSIVE_REJECTED", baseline and passive == "low_confidence")
        rgb = frame.get("mean_rgb")
        if (not isinstance(rgb, (tuple, list)) or len(rgb) != 3
                or any(not isinstance(v, (int, float)) or not 0 <= v <= 255 for v in rgb) or sum(rgb) <= 0):
            return self._reject("COLOR_INVALID_INPUT")
        if motion > self.config.motion_threshold:
            if baseline:
                return self._wait_or_reject("COLOR_MOTION_SKIPPED", True)
            if self._phase == ColorPhase.COLOR_CHALLENGE.value:
                self._color_motion_skips += 1
            self._reason = "COLOR_MOTION_SKIPPED"
            return self._result()
        self._reason = None
        chroma = np.asarray(rgb, dtype=np.float64) / sum(rgb)
        if baseline:
            self._baseline.append((sum(rgb) / 765.0, chroma))
            self._metrics["baseline_samples"] = len(self._baseline)
            if len(self._baseline) == self.config.baseline_frames:
                lumas = [luma for luma, _ in self._baseline]
                variance = float(np.var(lumas))
                self._metrics["baseline_luma"] = float(np.mean(lumas))
                self._metrics["baseline_luma_variance"] = variance
                self._baseline_chroma = np.mean([value for _, value in self._baseline], axis=0)
                self._metrics["baseline_chroma"] = tuple(float(v) for v in self._baseline_chroma)
                if variance > .04:
                    return self._reject("COLOR_UNRESPONSIVE")
                self._baseline.clear()
                self._phase, self._color = ColorPhase.COLOR_CHALLENGE.value, self.config.sequence[0]
        elif self._phase == ColorPhase.COLOR_CHALLENGE.value:
            self._accept_color(chroma)
        elif self._phase == ColorPhase.VERIFYING.value:
            self._status, self._phase = ColorStatus.PASSED.value, ColorPhase.PASSED.value
        return self._result()

    def _wait_or_reject(self, reason, wait):
        if not wait:
            return self._reject(reason)
        self._reason = reason
        self._baseline.clear()
        self._metrics["baseline_samples"] = 0
        return self._result()

    def _accept_color(self, chroma):
        delta = chroma - self._baseline_chroma
        channel = ("red", "green", "blue").index(self._color)
        score = float(delta[channel])
        self._color_deltas.append(score)
        self._color_samples += 1
        if score >= self.config.chroma_delta_threshold and score == float(np.max(delta)):
            self._color_hits += 1
        self._accepted += 1
        self._metrics[f"{self._color}_delta"] = score

    def finish_color(self) -> ColorResult:
        if self._status != ColorStatus.PENDING.value or self._phase != ColorPhase.COLOR_CHALLENGE.value:
            return self._result()
        if self._color_samples < self.config.sample_frames_per_color:
            return self._reject("COLOR_SAMPLES_INSUFFICIENT")
        if self._color_hits / self._color_samples < self.config.min_color_ratio:
            return self._reject("COLOR_UNRESPONSIVE")
        self._color_diagnostics.append(self._color_row())
        self._color_deltas.clear()
        self._quality_skips.clear()
        self._quality_issue = None
        self._color_samples = self._color_hits = self._color_motion_skips = 0
        self._reason = None
        index = self.config.sequence.index(self._color)
        if index < 2:
            self._color = self.config.sequence[index + 1]
        elif self._cycle + 1 < self.config.cycles:
            self._cycle += 1
            self._color = self.config.sequence[0]
        else:
            self._phase, self._color = ColorPhase.VERIFYING.value, "white"
        return self._result()

    def cancel(self, reason: str = "cancel") -> ColorResult:
        if self._status == ColorStatus.PENDING.value:
            return self._reject("COLOR_CANCELLED" if reason == "cancel" else reason)
        return self._result()

    def snapshot(self) -> ColorResult:
        return self._result()

    def close(self) -> None:
        self.cancel("COLOR_CANCELLED")
