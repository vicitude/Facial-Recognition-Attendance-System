"""最新帧双通道研究流水线；模型线程之外只发布有界快照。"""
from collections import deque
import math

from threading import Condition, Event, Thread
from time import monotonic

from attendance.fused_liveness import FusionSession, adapt_feature
from attendance.liveness_preparation import EyePreparation


class LatestFrameCamera:
    def __init__(self, capture):
        self.capture = capture
        self.stop = Event()
        self.condition = Condition()
        self.latest = None
        self.error = None
        self.thread = Thread(target=self._run, name='liveness-camera', daemon=True)
        self.thread.start()

    def _run(self):
        sequence = 0
        try:
            while not self.stop.is_set():
                ok, frame = self.capture.read()
                if not ok:
                    raise RuntimeError('摄像头读取失败')
                sequence += 1
                with self.condition:
                    self.latest = (sequence, monotonic(), frame)
                    self.condition.notify_all()
        except Exception:
            self.error = 'camera_error'
        finally:
            self.capture.release()

    def snapshot(self):
        with self.condition:
            return self.latest

    def close(self):
        self.stop.set()
        self.thread.join()


class StableIdentityBaseline:
    """只保存姿态数值；调用方在第三份稳定采样上固定身份向量。"""
    def __init__(self):
        self.samples = []

    def reset(self):
        self.samples.clear()

    def observe(self, feature: dict, vector, min_open_ear=0.28) -> bool:
        import numpy as np
        values = np.asarray(vector)
        if values.shape != (128,) or not np.isfinite(values).all():
            raise ValueError('无效身份向量')
        yaw, pitch, ear = (float(feature[name]) for name in ('yaw_deg', 'pitch_deg', 'ear'))
        if (feature.get('face_count') != 1 or not all(math.isfinite(v) for v in (yaw, pitch, ear))
                or abs(yaw) > 8 or not 20 <= pitch <= 70 or not min_open_ear <= ear <= 1):
            self.reset()
            return False
        self.samples.append((yaw, pitch))
        self.samples = self.samples[-3:]
        if any(max(p[axis] for p in self.samples) - min(p[axis] for p in self.samples) > 4 for axis in (0, 1)):
            self.samples = [(yaw, pitch)]
        return len(self.samples) == 3


class AsyncFusionPipeline:
    def __init__(self, landmarks, auxiliary, quality):
        self.landmarks, self.auxiliary, self.quality = landmarks, auxiliary, quality
        self.condition = Condition()
        self.stopping = False
        self.generation = 0
        self.latest = None
        self.session = None
        self.result = None
        self.anchor = None
        self.aux = None
        self.aux_box = None
        self.aux_time = None
        self.live_count = 0
        self.completed_at = None
        self.ready_at = None
        self.last_submit = -1
        self.metrics = {}
        self.terminal_metrics = None
        self.baseline = StableIdentityBaseline()
        self.preparation = EyePreparation()
        self.identity_samples = []
        self.identity_failures = 0
        self.identity_check_at = None
        self.pending_diagnostics = deque(maxlen=32)
        self.threads = []

    def start(self):
        if self.threads:
            raise RuntimeError('流水线不可重复启动')
        for target, name in ((self._actions, 'liveness-actions'), (self._auxiliary, 'liveness-auxiliary')):
            thread = Thread(target=target, name=name, daemon=True)
            self.threads.append(thread)
            thread.start()

    def reset(self):
        with self.condition:
            self.generation += 1
            self.session = self.result = self.anchor = self.aux = self.aux_box = None
            self.aux_time = self.ready_at = self.completed_at = None
            self.live_count = 0
            self.latest = None
            self.metrics = {}
            self.terminal_metrics = None
            self.baseline.reset()
            self.identity_samples.clear()
            self.identity_failures = 0
            self.identity_check_at = None
            self.preparation.reset()
            self.pending_diagnostics.clear()
            self.condition.notify_all()

    def submit(self, frame_id, timestamp, frame):
        with self.condition:
            if frame_id <= self.last_submit:
                return
            self.last_submit = frame_id
            self.latest = (self.generation, frame_id, timestamp, frame.copy())
            self.condition.notify_all()

    def snapshot(self):
        with self.condition:
            self._freeze_terminal()
            metrics = dict(self.terminal_metrics if self.terminal_metrics is not None else self.metrics)
            if self.terminal_metrics is None:
                metrics['aux_age_ms'] = None if self.aux_time is None else (monotonic() - self.aux_time) * 1000
            diagnostics = list(self.pending_diagnostics)
            self.pending_diagnostics.clear()
            return dict(result=self.result, metrics=metrics, warming=self.session is None,
                        generation=self.generation, diagnostics=diagnostics)

    def _freeze_terminal(self, source_timestamp=None):
        if self.result is not None and self.result.status != 'pending' and self.terminal_metrics is None:
            self.terminal_metrics = dict(self.metrics)
            timestamp = self.aux_time if source_timestamp is None else source_timestamp
            self.terminal_metrics['aux_age_ms'] = None if timestamp is None else (monotonic() - timestamp) * 1000
            self.terminal_metrics['frozen'] = True

    def _fail(self, reason, source_timestamp=None):
        if self.session is None:
            self.session = FusionSession(defer_auxiliary=True)
        if self.session.terminal is None:
            self.result = self.session._result('failed', reason)
            self._freeze_terminal(source_timestamp)
            self.condition.notify_all()

    def _freshness(self):
        if self.session is None or self.session.terminal is not None:
            return
        now = monotonic()
        if (self.session.phase == 'identity_check' and self.identity_check_at is not None
                and now - self.identity_check_at > 5):
            self._fail('identity_check_timeout')
        elif self.completed_at is not None:
            if now - self.completed_at > 5:
                self._fail('verification_timeout')
        elif self.aux_time is None or now - self.aux_time > 2:
            self._fail('auxiliary_stale')

    def _actions(self):
        seen = None
        try:
            while True:
                with self.condition:
                    self.condition.wait_for(lambda: self.stopping or (self.latest is not None and self.latest[:2] != seen), timeout=0.05)
                    if self.stopping:
                        return
                    self._freshness()
                    item = self.latest
                    if item is None or item[:2] == seen:
                        continue
                    generation, frame_id, timestamp, frame = item
                    seen = item[:2]
                    if self.session is not None and self.session.terminal is not None:
                        continue
                    action_epoch = None if self.session is None else (self.session, self.session.index, self.session.phase)
                started = monotonic()
                try:
                    feature = self.landmarks.detect(frame)
                    quality_ok = False
                    if feature.get('face_count') == 1:
                        box = feature.get('face_box')
                        if box is not None:
                            height, width = frame.shape[:2]
                            clipped = (max(0, box[0]), max(0, box[1]), min(width, box[2]), min(height, box[3]))
                            quality_ok, _ = self.quality(frame, clipped)
                except Exception:
                    with self.condition:
                        if generation == self.generation:
                            self._fail('pipeline_error')
                    continue
                with self.condition:
                    if generation != self.generation:
                        continue
                    current_epoch = None if self.session is None else (self.session, self.session.index, self.session.phase)
                    if action_epoch != current_epoch:
                        continue
                    self.metrics['landmarks_ms'] = (monotonic() - started) * 1000
                    if self.session is None:
                        if monotonic() - timestamp > .5:
                            self.preparation._invalidate('frame_gap', clear_calibration=True)
                        else:
                            self.preparation.update(feature, timestamp=timestamp, quality_ok=quality_ok)
                        self.metrics.update(self.preparation.metrics())
                        if self.preparation.failed:
                            self._fail(self.preparation.reason)
                            continue
                        if not self.preparation.ready:
                            if self.anchor is None:
                                self.baseline.reset()
                                self.metrics['baseline_samples'] = 0
                            continue
                        if self.aux is None or self.anchor is None:
                            continue  # 校准、身份准备均不计挑战时间。
                        self.session = FusionSession(defer_auxiliary=True, eye_thresholds=(
                            self.preparation.closed_threshold, self.preparation.open_threshold), identity_checkpoints=True)
                        self.ready_at = monotonic()
                        self.condition.notify_all()
                        continue
                    if timestamp <= self.ready_at or self.session.terminal is not None:
                        continue
                    self._freshness()
                    if self.session.terminal is not None:
                        continue
                    if monotonic() - timestamp > 0.5:
                        self._fail('frame_gap')
                        continue
                    if feature.get('face_count') == 1:
                        try:
                            feature = adapt_feature(feature, self.aux_box)
                        except ValueError:
                            feature = {'face_count': 0}
                    previous = self.session.last_timestamp
                    previous_phase = self.session.phase
                    self.result = self.session.update(feature, timestamp=timestamp, quality_ok=quality_ok,
                                                      passive_status='inconclusive', identity_distance=0.0)
                    if previous is not None and timestamp > previous:
                        self.metrics['action_fps'] = 1 / (timestamp - previous)
                    self._freeze_terminal()
                    if self.result.phase == 'identity_check' and previous_phase != 'identity_check':
                        self.identity_check_at = monotonic()
                        self.identity_samples.clear()
                        self.identity_failures = self.live_count = 0
                        self.metrics.update(identity_check_state='waiting', identity_check_samples=0, identity_failures=0)
                    if self.result.phase == 'verification' and self.completed_at is None:
                        self.completed_at = monotonic()
        except Exception:
            with self.condition:
                self._fail('pipeline_error')
        finally:
            self.landmarks.close()

    def _check_identity(self, feature, distance, timestamp):
        """动作距离仅诊断；回正后使用新源连续采样复核固定身份。"""
        if self.anchor is None:
            return False
        if distance is None or not math.isfinite(distance) or distance < 0:
            self._fail('identity_changed', timestamp)
            return False
        phase = None if self.session is None else self.session.phase
        if phase in ('baseline', 'outbound', 'return'):
            self.metrics.update(identity_check_state='deferred', identity_check_samples=0)
            return False
        if phase not in ('identity_check', 'verification'):
            if distance > .8:
                self._fail('identity_changed', timestamp)
            return distance <= .8
        if phase == 'identity_check' and (self.identity_check_at is None or timestamp < self.identity_check_at):
            return False
        yaw, pitch, ear = (float(feature[k]) for k in ('yaw_deg', 'pitch_deg', 'ear'))
        centered = (all(math.isfinite(v) for v in (yaw, pitch, ear))
                    and abs(yaw) <= 8 and abs(yaw - self.metrics.get('baseline_yaw', 0)) <= 8
                    and abs(pitch - self.metrics.get('baseline_pitch', 45)) <= 8
                    and 20 <= pitch <= 70 and ear >= (self.preparation.open_threshold or .28))
        self.metrics['identity_check_state'] = 'waiting'
        if not centered:
            self.identity_samples.clear()
            self.identity_failures = 0
        elif distance > .8:
            self.identity_samples.clear()
            self.identity_failures += 1
        else:
            self.identity_failures = 0
            self.identity_samples.append((yaw, pitch))
            self.identity_samples = self.identity_samples[-3:]
            if any(max(p[a] for p in self.identity_samples) - min(p[a] for p in self.identity_samples) > 4 for a in (0, 1)):
                self.identity_samples = [(yaw, pitch)]
        self.metrics.update(identity_check_samples=len(self.identity_samples), identity_failures=self.identity_failures)
        if self.identity_failures >= 3:
            self._fail('identity_changed', timestamp)
            return False
        if centered and distance <= .8:
            if phase == 'identity_check' and len(self.identity_samples) == 3:
                self.result = self.session.resume_identity()
                self.ready_at = monotonic()
                self.session.action_timestamp = self.ready_at
                self.identity_check_at = None
                self.metrics['identity_check_state'] = 'confirmed'
                if self.session.phase == 'verification':
                    self.completed_at = monotonic()
            return True
        return False

    def _auxiliary(self):
        seen = None
        last_started = 0.0
        try:
            while True:
                with self.condition:
                    self.condition.wait(timeout=0.02)
                    if self.stopping:
                        return
                    item = self.latest
                    if item is None or item[:2] == seen or monotonic() - last_started < 0.4:
                        continue
                    if self.session is not None and self.session.terminal is not None:
                        continue
                    generation, frame_id, timestamp, frame = item
                    seen = item[:2]
                    anchor = self.anchor
                last_started = monotonic()
                try:
                    evaluated = self.auxiliary(frame, anchor)
                except Exception:
                    with self.condition:
                        if generation == self.generation:
                            self._fail('pipeline_error')
                    continue
                with self.condition:
                    if generation != self.generation:
                        continue
                    if self.session is not None and self.session.terminal is not None:
                        continue
                    self._freshness()
                    if self.session is not None and self.session.terminal is not None:
                        continue
                    self.metrics.update(evaluated.get('timings_ms', {}))
                    if monotonic() - timestamp > 2:
                        self.metrics['aux_expired'] = True
                        self._freshness()
                        continue
                    self.metrics['aux_expired'] = False
                    if not evaluated['quality_ok'] or evaluated['feature'].get('face_count') != 1:
                        self._fail('poor_quality' if evaluated['feature'].get('face_count') == 1 else 'need_one_face')
                        continue
                    feature = evaluated['feature']
                    self.metrics.update(identity_distance=evaluated['identity_distance'], identity_threshold=0.8,
                                        identity_yaw=feature.get('yaw_deg'), identity_pitch=feature.get('pitch_deg'),
                                        identity_ear=feature.get('ear'))
                    distance = evaluated['identity_distance']
                    status = evaluated['passive_status']
                    if status == 'spoof_candidate':
                        self._fail('passive_spoof')
                        continue
                    if status not in ('live_candidate', 'low_confidence', 'inconclusive'):
                        self._fail('poor_quality' if status == 'low_quality' else 'invalid_passive')
                        continue
                    identity_ok = self._check_identity(feature, distance, timestamp)
                    if self.session is not None and self.session.terminal is not None:
                        self.pending_diagnostics.append(dict(self.terminal_metrics))
                        continue
                    if self.anchor is None:
                        if (not self.preparation.ready or self.preparation.calibrated_at is None
                                or timestamp < self.preparation.calibrated_at):
                            self.baseline.reset()
                            self.metrics['baseline_samples'] = 0
                            self.pending_diagnostics.append(dict(self.metrics, aux_age_ms=(monotonic() - timestamp) * 1000))
                            self.condition.notify_all()
                            continue
                        ready = self.baseline.observe(feature, evaluated['identity_vector'],
                                                      min_open_ear=self.preparation.open_threshold)
                        self.metrics['baseline_samples'] = len(self.baseline.samples)
                        self.metrics.setdefault('baseline_yaw', None)
                        self.metrics.setdefault('baseline_pitch', None)
                        if not ready:
                            self.pending_diagnostics.append(dict(self.metrics, aux_age_ms=(monotonic() - timestamp) * 1000))
                            self.condition.notify_all()
                            continue
                        self.anchor = evaluated['identity_vector'].copy()
                        self.metrics.update(baseline_yaw=feature['yaw_deg'], baseline_pitch=feature['pitch_deg'])
                    self.pending_diagnostics.append(dict(self.metrics, aux_age_ms=(monotonic() - timestamp) * 1000))
                    self.aux = evaluated
                    self.aux_box = evaluated['feature']['face_box']
                    self.aux_time = timestamp
                    if self.session is not None:
                        self.live_count = self.live_count + 1 if status == 'live_candidate' and identity_ok else 0
                        if (self.session.phase == 'verification' and self.live_count >= 7
                                and timestamp >= self.completed_at and status == 'live_candidate'):
                            self.result = self.session.finish_auxiliary(True)
                            self._freeze_terminal(timestamp)
                    self.condition.notify_all()
        except Exception:
            with self.condition:
                self._fail('pipeline_error')
        finally:
            close = getattr(self.auxiliary, 'close', None)
            if close is not None:
                close()

    def close(self):
        with self.condition:
            self.stopping = True
            self.condition.notify_all()
        for thread in self.threads:
            thread.join()
