"""仅内存的本轮眼部校准；校准动作不计入随机挑战。"""
import math
from statistics import median


class EyePreparation:
    def __init__(self):
        self.reset()

    def reset(self):
        self.stage = 'open'
        self.samples = []
        self.open_ear = self.closed_threshold = self.open_threshold = None
        self.calibrated_at = None
        self.ready = self.failed = False
        self.started = self.last_timestamp = None
        self.reason = ''

    def metrics(self) -> dict:
        return dict(preparation_stage=self.stage, preparation_samples=len(self.samples),
                    preparation_ready=self.ready, preparation_reason=self.reason,
                    open_ear=self.open_ear, closed_threshold=self.closed_threshold,
                    open_threshold=self.open_threshold)

    def _invalidate(self, reason, *, clear_calibration=False):
        self.samples.clear()
        self.ready = False
        self.reason = reason
        if self.calibrated_at is None or clear_calibration:
            self.stage = 'open'
            self.open_ear = self.closed_threshold = self.open_threshold = None
            self.calibrated_at = None

    def _append(self, timestamp, yaw, pitch, ear):
        self.samples.append((timestamp, yaw, pitch, ear))
        self.samples = self.samples[-60:]

    def _stable(self, *, eyes=False):
        return all(max(p[axis] for p in self.samples) - min(p[axis] for p in self.samples)
                   <= limit for axis, limit in ((1, 4), (2, 4), (3, .04)) if eyes or axis != 3)

    def _enough(self, count, duration):
        return len(self.samples) >= count and self.samples[-1][0] - self.samples[0][0] >= duration - 1e-9

    def update(self, feature: dict, *, timestamp: float, quality_ok: bool) -> bool:
        if self.failed:
            return False
        try:
            timestamp = float(timestamp)
            if not math.isfinite(timestamp) or (self.last_timestamp is not None and timestamp <= self.last_timestamp):
                raise ValueError('time')
        except (TypeError, ValueError, OverflowError):
            self.failed, self.ready, self.reason = True, False, 'invalid_time'
            return False
        if self.started is None:
            self.started = timestamp
        if self.calibrated_at is None and timestamp - self.started > 20:
            self.failed, self.ready, self.reason = True, False, 'calibration_timeout'
            return False
        if self.last_timestamp is not None and timestamp - self.last_timestamp > .5:
            self._invalidate('frame_gap', clear_calibration=True)
        self.last_timestamp = timestamp
        try:
            if feature.get('face_count') != 1:
                self._invalidate('need_one_face')
                return False
            if quality_ok is not True:
                self._invalidate('poor_quality')
                return False
            yaw, pitch, ear = (float(feature[k]) for k in ('yaw_deg', 'pitch_deg', 'ear'))
            if not all(math.isfinite(v) for v in (yaw, pitch, ear)) or not 0 < ear <= 1:
                raise ValueError('feature')
        except (AttributeError, KeyError, TypeError, ValueError, OverflowError):
            self._invalidate('invalid_feature')
            return False
        if abs(yaw) > 8 or not 20 <= pitch <= 70:
            self._invalidate('center_face')
            return False
        self.reason = ''
        if self.stage == 'open':
            if not .12 <= ear <= .60:
                self._invalidate('open_eyes')
                return False
            self._append(timestamp, yaw, pitch, ear)
            if not self._stable(eyes=True):
                self.samples = [self.samples[-1]]
                self.reason = 'hold_still'
            if self._enough(15, .6):
                self.open_ear = median(p[3] for p in self.samples)
                self.stage, self.samples = 'close', []
        elif self.stage == 'close':
            if ear > self.open_ear * .65 or self.open_ear - ear < .05:
                self.samples.clear()
                self.reason = 'close_eyes'
                return False
            self._append(timestamp, yaw, pitch, ear)
            if self._enough(3, .08):
                closed = median(p[3] for p in self.samples)
                self.closed_threshold = closed + .25 * (self.open_ear - closed)
                self.open_threshold = closed + .75 * (self.open_ear - closed)
                self.stage, self.samples = 'reopen', []
        elif self.stage in ('reopen', 'ready'):
            if ear < self.open_threshold:
                self.samples.clear()
                self.ready = False
                self.reason = 'open_eyes'
                return False
            self._append(timestamp, yaw, pitch, ear)
            if not self._stable():
                self.samples = [self.samples[-1]]
                self.ready = False
                self.reason = 'hold_still'
            if self.stage == 'reopen' and self._enough(5, .15):
                self.calibrated_at = timestamp
                self.stage, self.samples = 'ready', []
            elif self.stage == 'ready':
                self.ready = self._enough(15, .6)
        return self.ready
