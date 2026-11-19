"""彩光采集和分析各使用一条线程；Qt 不读相机、不等待 join。"""
from __future__ import annotations

import threading
from time import monotonic

import cv2

from attendance.color_light_backend import ColorLightBackend
from attendance.color_light_liveness import ColorLightConfig, ColorLivenessSession, ColorPhase, ColorStatus


class ColorLivenessWorker:
    def __init__(self, employee_id, capture, templates, *, config=None, backend_factory=ColorLightBackend):
        self.config = config or ColorLightConfig(enabled=True)
        self._capture = capture
        self._templates = tuple(templates)
        self._backend_factory = backend_factory
        self._session = ColorLivenessSession(employee_id, self.config)
        self._condition = threading.Condition()
        self._threads = []
        self._stop = False
        self._started = None
        self._epoch = 0
        self._displayed = None
        self._painted_at = None
        self._latest = None
        self._last_capture = None
        self._frame_count = self._processed_count = self._valid_count = 0
        self._result = self._session.snapshot()
        self._error = None

    def start(self) -> None:
        with self._condition:
            if self._started is not None or self._stop:
                return
            self._started = monotonic()
            self._result = self._session.start(self._started)
            try:
                for target, name in ((self._read_camera, "color-camera"), (self._analyze, "color-inference")):
                    thread = threading.Thread(target=target, name=name, daemon=True)
                    thread.start()
                    self._threads.append(thread)
            except Exception:
                self._fail_locked("COLOR_INTERNAL_ERROR")

    def _finish_due_color_locked(self):
        if (self._stop or self._result.phase != ColorPhase.COLOR_CHALLENGE.value
                or self._displayed != self._result.color or self._painted_at is None
                or monotonic() < self._painted_at + self.config.color_duration_ms / 1000):
            return False
        self._result = self._session.finish_color()
        self._error = None
        if self._result.status != ColorStatus.PENDING.value:
            self._stop = True
        self._condition.notify_all()
        return True

    def acknowledge_color(self, color: str) -> bool:
        with self._condition:
            if self._stop or color != self._result.color:
                return False
            if color != self._displayed:
                self._epoch += 1
                self._displayed = color
                self._painted_at = monotonic()
                self._condition.notify_all()
            return True

    def _read_camera(self):
        try:
            while True:
                with self._condition:
                    if self._stop:
                        return
                    began, epoch = monotonic(), self._epoch
                ok, frame = self._capture.read()
                captured = monotonic()
                if not ok or frame is None:
                    with self._condition:
                        self._fail_locked("COLOR_CAMERA_READ_FAILED")
                    return
                frame = cv2.flip(frame, 1)
                if frame.ndim != 3 or frame.shape[2] != 3:
                    raise ValueError("COLOR_CAMERA_READ_FAILED")
                frame.setflags(write=False)
                with self._condition:
                    if self._stop:
                        return
                    if self._expired_locked():
                        return
                    previous = self._last_capture
                    self._last_capture = captured
                    self._frame_count += 1
                    cadence_ok = previous is None or 0 < captured - previous <= 1 / self.config.min_fps
                    self._latest = (self._frame_count, began, captured, epoch, cadence_ok, frame)
                    self._condition.notify_all()
        except Exception:
            with self._condition:
                self._fail_locked("COLOR_CAMERA_READ_FAILED")

    def _analyze(self):
        try:
            backend = self._backend_factory(self._templates)
        except Exception:
            with self._condition:
                self._fail_locked("COLOR_MODEL_UNAVAILABLE")
            return
        try:
            seen = 0
            while True:
                with self._condition:
                    self._condition.wait_for(lambda: self._stop or (
                        self._latest is not None and self._latest[0] > seen))
                    if self._stop:
                        return
                    if self._expired_locked():
                        return
                    if self._finish_due_color_locked():
                        continue
                    seen, began, captured, epoch, cadence_ok, frame = self._latest
                    if (epoch != self._epoch or self._displayed != self._result.color
                            or self._painted_at is None
                            or began < self._painted_at + self.config.settle_ms / 1000):
                        continue
                    color = self._displayed
                    if not cadence_ok or monotonic() - captured > self.config.max_frame_age_ms / 1000:
                        self._error = "COLOR_PERFORMANCE_INSUFFICIENT"
                        continue
                facts = backend(frame)
                with self._condition:
                    if self._stop:
                        return
                    self._processed_count += 1
                    if epoch != self._epoch or color != self._result.color:
                        continue
                    if self._expired_locked():
                        return
                    if self._finish_due_color_locked():
                        continue
                    if monotonic() - captured > self.config.max_frame_age_ms / 1000:
                        self._error = "COLOR_PERFORMANCE_INSUFFICIENT"
                        continue
                    self._error = None
                    result = self._session.submit(seen, captured, facts, color)
                    if result.reason is None:
                        self._valid_count += 1
                    self._result = result
                    if result.status != "pending":
                        self._stop = True
                        self._condition.notify_all()
                        return
        except Exception:
            with self._condition:
                self._fail_locked("COLOR_INTERNAL_ERROR")

    def _expired_locked(self):
        if self._started is None or monotonic() - self._started < self.config.max_session_ms / 1000:
            return False
        self._fail_locked("COLOR_TIMEOUT")
        return True

    def _fail_locked(self, reason):
        if self._stop:
            return
        self._error = reason
        if reason == "COLOR_TIMEOUT":
            self._result = self._session._reject(reason, ColorStatus.TIMEOUT.value, ColorPhase.TIMEOUT.value)
        else:
            self._result = self._session._reject(reason, ColorStatus.ERROR.value, ColorPhase.ERROR.value)
        self._stop = True
        self._condition.notify_all()

    def snapshot(self) -> dict:
        with self._condition:
            if not self._expired_locked():
                self._finish_due_color_locked()
            return dict(frame=None if self._latest is None else self._latest[-1], result=self._session.snapshot(),
                        error=self._error, frame_count=self._frame_count,
                        processed_count=self._processed_count, valid_count=self._valid_count,
                        desired_color=self._result.color)

    def stop(self) -> bool:
        with self._condition:
            self._result = self._session.cancel()
            self._stop = True
            self._latest = None
            self._condition.notify_all()
        return self.stopped()

    def stopped(self) -> bool:
        with self._condition:
            return not any(thread.is_alive() for thread in self._threads)
