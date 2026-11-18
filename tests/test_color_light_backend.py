from types import SimpleNamespace
import numpy as np
from attendance.color_light_backend import ColorLightBackend


def test_backend_same_face_identity_quality_and_passive():
    boxes, calls = [], []
    def quality(frame, box):
        calls.append(('quality', box))
        return True, ()
    def embed(image):
        calls.append(('embed', image.size))
        query = np.zeros(128, np.float32)
        query[0] = .9
        return query
    def passive(frame, face_boxes):
        calls.append(('passive', face_boxes))
        return SimpleNamespace(status='spoof_candidate')
    backend = ColorLightBackend([np.zeros(128, np.float32)] * 3,
                               detect=lambda frame: boxes, quality=quality, embed=embed, passive=passive)
    frame = np.zeros((80, 100, 3), dtype=np.uint8)
    frame[:, :, 2] = 255
    assert backend(frame)['face_count'] == 0
    assert not calls
    boxes.append((0, 0, 80, 80, .9, 0, 'face'))
    facts = backend(frame)
    assert calls == [('quality', (0,0,80,80)), ('embed', (80,80)), ('passive', [(0,0,80,80)])]
    assert facts['mean_rgb'] == (255,0,0)
    assert facts['identity_distance'] > .8 and facts['passive_status'] == 'spoof_candidate'
    boxes[0] = (4, 0, 90, 80)
    assert backend(frame)['motion_score'] > .015
