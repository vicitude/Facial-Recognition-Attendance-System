"""S1 ?????????????????"""

from collections import deque
from dataclasses import dataclass
import hashlib
import importlib.util
from pathlib import Path
from time import perf_counter

import cv2
import numpy as np
import torch

from attendance.inference_device import resolve_device


DEFAULT_ASSETS = Path(__file__).resolve().parents[1] / "research_assets" / "Silent-Face-Anti-Spoofing"
MODEL_FILES = (
    ("2.7_80x80_MiniFASNetV2.pth", "MiniFASNetV2", 2.7,
     "a5eb02e1843f19b5386b953cc4c9f011c3f985d0ee2bb9819eea9a142099bec0"),
    ("4_0_0_80x80_MiniFASNetV1SE.pth", "MiniFASNetV1SE", 4.0,
     "84ee1d37d96894d5e82de5a57df044ef80a58be2b218b5ed7cdfd875ec2f5990"),
)


@dataclass(frozen=True)
class LivenessResult:
    status: str
    probabilities: tuple
    elapsed_ms: float
    quality: tuple = ()


def assess_confidence(probabilities, min_live_prob=0.80, min_margin=0.15):
    """Apply a provisional conservative gate to averaged [spoof, live, ...] scores."""
    values = np.asarray(probabilities, dtype=np.float64)
    if values.shape != (3,) or not np.isfinite(values).all():
        raise ValueError("probabilities must have shape (3,)")
    order = np.sort(values)[::-1]
    if int(values.argmax()) != 1:
        return "spoof_candidate", float(values[1]), float(order[0] - order[1])
    margin = float(order[0] - order[1])
    if values[1] >= min_live_prob and margin >= min_margin:
        return "live_candidate", float(values[1]), margin
    return "low_confidence", float(values[1]), margin


def assess_quality(frame, bbox, min_face_size=60, min_brightness=20.0, max_brightness=240.0, min_sharpness=20.0):
    """Return (ok, (reason, brightness, sharpness)) using an xyxy face box."""
    left, top, right, bottom = [int(round(value)) for value in bbox]
    patch = frame[top:bottom, left:right]
    if patch.size == 0 or patch.shape[0] < min_face_size or patch.shape[1] < min_face_size:
        return False, ("face_too_small", 0.0, 0.0)
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    brightness = float(gray.mean())
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    ok = min_brightness <= brightness <= max_brightness and sharpness >= min_sharpness
    reason = "ok" if ok else "poor_quality"
    return ok, (reason, brightness, sharpness)


class MultiFrameConsistency:
    """Bounded, pixel-free provisional temporal confirmation for research."""
    def __init__(self, window=7, required_live=5, min_live_prob=0.80, max_score_std=0.10):
        self.window = window
        self.required_live = required_live
        self.min_live_prob = min_live_prob
        self.max_score_std = max_score_std
        self._results = deque(maxlen=window)

    def reset(self):
        self._results.clear()

    def update(self, result):
        if result.status not in {"live_candidate", "spoof_candidate"} or len(result.probabilities) != 3:
            self.reset()
            return "inconclusive"
        self._results.append(result)
        if len(self._results) < self.required_live:
            return "pending"
        live_scores = np.asarray([item.probabilities[1] for item in self._results], dtype=float)
        live_count = sum(item.status == "live_candidate" and item.probabilities[1] >= self.min_live_prob for item in self._results)
        if live_count >= self.required_live and float(live_scores.std()) <= self.max_score_std:
            return "consistent_live"
        if len(self._results) == self.window:
            return "inconsistent"
        return "pending"


def _load_source(path, digest, module_name):
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError(f"????????: {path.name}")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare_tensor(patch):
    return torch.from_numpy(np.ascontiguousarray(patch.transpose(2, 0, 1))).float().unsqueeze(0)


def summarize(probabilities):
    values = np.asarray(probabilities, dtype=np.float64)
    if values.shape != (2, 3) or not np.isfinite(values).all():
        raise ValueError("?????????????")
    if (values < 0).any() or (values > 1).any() or not np.allclose(values.sum(axis=1), 1, atol=1e-5):
        raise ValueError("????????????")
    average = values.mean(axis=0)
    status = "live_candidate" if int(average.argmax()) == 1 else "spoof_candidate"
    if np.count_nonzero(np.isclose(average, average.max(), rtol=0, atol=1e-8)) > 1:
        status = "inconclusive"
    return status, tuple(float(value) for value in average)


class LivenessResearch:
    def __init__(self, assets=DEFAULT_ASSETS, device=None):
        self.device = resolve_device(device)
        assets = Path(assets)
        network = _load_source(
            assets / "src/model_lib/MiniFASNet.py",
            "6c3159a459838b079c34e3656762549b7375444d994611fac92688259db e313f".replace(" ", ""),
            "s1_minifas_network",
        )
        crop = _load_source(
            assets / "src/generate_patches.py",
            "9fc03bc0da6b22455f93c589be77128b7dd592fed87aa5f843cfa06c6a02ee3c",
            "s1_minifas_crop",
        )
        self._cropper = crop.CropImage()
        self._models = []
        for filename, architecture, scale, digest in MODEL_FILES:
            path = assets / "resources/anti_spoof_models" / filename
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError(f"????????: {filename}")
            state = torch.load(path, map_location="cpu", weights_only=True)
            state = {key.removeprefix("module."): value for key, value in state.items()}
            model = getattr(network, architecture)(conv6_kernel=(5, 5))
            model.load_state_dict(state, strict=True)
            model.to(self.device).eval()
            self._models.append((model, scale))

    def evaluate(self, frame, boxes):
        started = perf_counter()
        if not isinstance(frame, np.ndarray) or frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3 or min(frame.shape[:2]) < 2:
            raise ValueError("??????? uint8 BGR ??")
        if len(boxes) != 1:
            status = "no_face" if len(boxes) == 0 else "multiple_faces"
            return LivenessResult(status, (), (perf_counter() - started) * 1000)
        coordinates = np.asarray(boxes[0][:4], dtype=np.float64)
        if coordinates.shape != (4,) or not np.isfinite(coordinates).all():
            raise ValueError("???????")
        left, top, right, bottom = coordinates
        height, width = frame.shape[:2]
        if not (0 <= left < right <= width and 0 <= top < bottom <= height):
            raise ValueError("??????????")
        bbox = [float(left), float(top), float(right-left), float(bottom-top)]
        probabilities = []
        with torch.inference_mode():
            for model, scale in self._models:
                patch = self._cropper.crop(frame, bbox, scale, 80, 80)
                logits = model(prepare_tensor(patch).to(self.device))
                probabilities.append(torch.softmax(logits, dim=1).cpu().numpy()[0])
        status, scores = summarize(probabilities)
        quality_ok, quality = assess_quality(frame, [left, top, right, bottom])
        if not quality_ok:
            status = "low_quality"
        else:
            status, _, _ = assess_confidence(scores)
        return LivenessResult(status, scores, (perf_counter() - started) * 1000, quality)
