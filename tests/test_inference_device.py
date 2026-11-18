"""SPEC-009 PT-DEV-01 / CT-DEV-02，真实模型不读取人脸或业务库。"""
import numpy as np
import pytest
import torch
from PIL import Image

from attendance.inference_device import resolve_device


@pytest.mark.parametrize("available", [False, True])
def test_PT_DEV_01(monkeypatch, available):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: available)
    assert resolve_device().type == ("cuda" if available else "cpu")
    assert resolve_device("cpu").type == "cpu"
    if available:
        assert torch.backends.cudnn.allow_tf32 is False
        assert torch.backends.cuda.matmul.allow_tf32 is False
    assert resolve_device("cuda:0").type == "cuda"


def _outputs(cuda):
    from facenet.facenet import Facenet
    from attendance.liveness_research import LivenessResearch
    image = Image.fromarray(np.random.default_rng(9).integers(0, 256, (160, 160, 3), dtype=np.uint8))
    face = Facenet(cuda=cuda)
    expected = "cuda" if cuda else "cpu"
    assert face.device.type == next(face.net.parameters()).device.type == expected
    vector = face.extract_embedding(image)
    assert vector.shape == (128,) and vector.dtype == np.float32
    assert np.isfinite(vector).all()
    assert np.allclose(face.detect_image(image, image), 0, atol=1e-6)
    passive = LivenessResearch(device="cuda:0" if cuda else "cpu")
    assert all(next(model.parameters()).device.type == expected for model, _ in passive._models)
    frame = np.random.default_rng(17).integers(0, 256, (240, 320, 3), dtype=np.uint8)
    result = passive.evaluate(frame, [[80, 50, 220, 210]])
    probabilities = np.array(result.probabilities)
    assert np.isfinite(probabilities).all() and np.isclose(probabilities.sum(), 1)
    return vector, probabilities


def test_CT_DEV_02_cpu():
    _outputs(False)


@pytest.mark.skipif(not torch.cuda.is_available(), reason="需要真实CUDA设备")
def test_CT_DEV_02_cuda_parity():
    cpu_vector, cpu_probs = _outputs(False)
    gpu_vector, gpu_probs = _outputs(True)
    assert np.max(np.abs(cpu_vector - gpu_vector)) <= 1e-4
    assert np.max(np.abs(cpu_probs - gpu_probs)) <= 1e-4
