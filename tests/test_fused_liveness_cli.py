"""CT-FUS-01：全替身入口测试，不启用设备或加载模型。"""
import importlib
import json
import sys
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest


def module(**attrs):
    value = ModuleType('fake')
    value.__dict__.update(attrs)
    return value


@pytest.fixture
def harness(monkeypatch):
    import fused_liveness_research as cli
    state = SimpleNamespace(released=False, closed=False, destroyed=False,
                            reads=0, evaluations=0, vectors=0, mismatch=False, crash=False,
                            keys=iter([27]))
    frame = np.ones((100, 100, 3), dtype=np.uint8)

    class Capture:
        def set(self, *args): pass
        def isOpened(self): return True
        def read(self):
            state.reads += 1
            return True, frame.copy()
        def release(self): state.released = True

    class Detector:
        def __init__(self, **kwargs): assert kwargs['max_faces'] == 2
        def close(self): state.closed = True
        def detect(self, frame):
            return dict(face_count=1, yaw_deg=0, pitch_deg=45, ear=0.3,
                        face_box=(200, 200, 300, 300) if state.mismatch else (0, 0, 100, 100))

    class Embedder:
        def extract_embedding(self, image):
            state.vectors += 1
            return np.full(128, state.vectors, dtype=np.float32)

    class Passive:
        def evaluate(self, *args):
            state.evaluations += 1
            if state.crash:
                raise RuntimeError('simulated inference failure')
            return SimpleNamespace(status='spoof_candidate')

    fake_cv = module(CAP_DSHOW=1, CAP_PROP_BUFFERSIZE=2, COLOR_BGR2RGB=3,
                     FONT_HERSHEY_SIMPLEX=4, WND_PROP_VISIBLE=5,
                     VideoCapture=lambda *args: Capture(), cvtColor=lambda f, *a: f,
                     flip=lambda f, *a: f, putText=lambda *a: None, imshow=lambda *a: None,
                     waitKey=lambda *a: next(state.keys), getWindowProperty=lambda *a: 1,
                     destroyAllWindows=lambda: setattr(state, 'destroyed', True))
    replacements = {
        'cv2': fake_cv,
        'recognition': module(recognition=lambda f: [(0, 0, 100, 100)]),
        'facenet.facenet': module(Facenet=Embedder),
        'attendance.active_liveness_landmarks': module(FaceLandmarkDetector=Detector),
        'attendance.liveness_research': module(LivenessResearch=Passive, assess_quality=lambda *a: (True, ())),
    }
    for name, replacement in replacements.items():
        monkeypatch.setitem(sys.modules, name, replacement)
    monkeypatch.delitem(sys.modules, 'attendance.liveness_backend', raising=False)
    from attendance.fused_liveness import FusionResult

    class Camera:
        error = None
        def __init__(self, capture): self.capture = capture
        def snapshot(self):
            ok, image = self.capture.read()
            return state.reads, 0.0, image
        def close(self): self.capture.release()

    class Pipeline:
        def __init__(self, landmarks, auxiliary, quality):
            self.landmarks, self.auxiliary = landmarks, auxiliary
            self.result = None
        def start(self): pass
        def submit(self, *args):
            if self.result is not None: return
            evaluated = self.auxiliary(args[2], None)
            reason = 'passive_spoof' if evaluated['quality_ok'] else 'need_one_face'
            self.result = FusionResult('failed', 'blink', 'baseline', 0, reason)
        def snapshot(self):
            return dict(result=self.result, metrics={}, warming=False)
        def reset(self): self.result = None
        def close(self):
            self.landmarks.close()
            self.auxiliary.close()

    monkeypatch.setattr(cli, 'LatestFrameCamera', Camera)
    monkeypatch.setattr(cli, 'AsyncFusionPipeline', Pipeline)
    monkeypatch.setattr(sys, 'argv', ['fused_liveness_research.py', '--category', 'paper'])
    return cli, state


def test_CT_FUS_01_terminal_count_and_retry(harness, capsys):
    cli, state = harness
    state.keys = iter([-1, ord('r'), 27])
    cli.main()
    output = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith('{')]
    results = [row for row in output if 'status' in row]
    totals = [row['counts'] for row in output if 'counts' in row]
    # 第二个终态若复用上轮anchor，会变identity_changed而不是passive_spoof。
    assert [r['reason'] for r in results] == ['passive_spoof', 'passive_spoof']
    assert [row['attempts'] for row in totals] == [1, 2]
    assert state.evaluations == state.vectors == 2
    assert state.reads == 3
    assert state.released and state.closed and state.destroyed


def test_CT_FUS_01_spatial_mismatch_rejected(harness, capsys):
    cli, state = harness
    state.mismatch = True
    cli.main()
    assert 'need_one_face' in capsys.readouterr().out
    assert state.evaluations == state.vectors == 0
    assert state.released and state.closed and state.destroyed


def test_CT_FUS_01_inference_error_releases(harness):
    cli, state = harness
    state.crash = True
    with pytest.raises(RuntimeError, match='simulated inference failure'):
        cli.main()
    assert state.released and state.closed and state.destroyed
