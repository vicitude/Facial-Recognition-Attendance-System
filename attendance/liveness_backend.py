"""活体模型线程适配器；仅内存处理。"""
from time import monotonic
import cv2
import numpy as np
from PIL import Image
import recognition
from facenet.facenet import Facenet
from attendance.fused_liveness import adapt_feature
from attendance.active_liveness_landmarks import FaceLandmarkDetector
from attendance.liveness_research import LivenessResearch, assess_quality

class Auxiliary:
    def __init__(self):
        self.detector = None
        self.passive = self.embedder = None

    def __call__(self, frame, anchor):
        # 各模型只由单一所属线程初始化和使用，避免跨线程共享MediaPipe graph。
        if self.detector is None:
            self.detector = FaceLandmarkDetector(max_faces=2)
            self.passive = LivenessResearch()
            self.embedder = Facenet()
        start = monotonic()
        boxes = recognition.recognition(frame)
        detected = monotonic()
        feature = self.detector.detect(frame)
        output = dict(feature=feature, quality_ok=False, identity_distance=float('inf'),
                      passive_status='no_face', anchor=anchor,
                      timings_ms={'yolo_ms': (detected - start) * 1000})
        if len(boxes) != 1 or feature.get('face_count') != 1:
            output['feature'] = {'face_count': 0}
            return output
        height, width = frame.shape[:2]
        x1, y1, x2, y2 = [int(float(v)) for v in boxes[0][:4]]
        box = (max(0, x1), max(0, y1), min(width, x2), min(height, y2))
        try:
            adapt_feature(feature, box)  # 验证同帧模型关注同一张脸，不改变原始方向。
        except ValueError:
            output['feature'] = {'face_count': 0}
            return output
        output['quality_ok'], _ = assess_quality(frame, box)
        if not output['quality_ok']:
            return output
        x1, y1, x2, y2 = box
        start = monotonic()
        vector = self.embedder.extract_embedding(Image.fromarray(cv2.cvtColor(frame[y1:y2, x1:x2], cv2.COLOR_BGR2RGB)))
        if vector.shape != (128,) or not np.isfinite(vector).all():
            raise RuntimeError('无效身份特征')
        output['timings_ms']['facenet_ms'] = (monotonic() - start) * 1000
        output['identity_vector'] = vector
        output['identity_distance'] = None if anchor is None else float(np.linalg.norm(vector - anchor))
        start = monotonic()
        output['passive_status'] = self.passive.evaluate(frame, [box]).status
        output['timings_ms']['passive_ms'] = (monotonic() - start) * 1000
        return output

    def close(self):
        if self.detector is not None:
            self.detector.close()

class BoundAuxiliary(Auxiliary):
    def __init__(self, vectors):
        super().__init__()
        self.vectors = [np.asarray(v, dtype=np.float32).copy() for v in vectors]
        if len(self.vectors) != 3 or any(v.shape != (128,) or not np.isfinite(v).all() for v in self.vectors):
            raise ValueError('员工模板无效')

    def __call__(self, frame, anchor):
        output = super().__call__(frame, anchor)
        if output.get('quality_ok'):
            vector = output.get('identity_vector')
            if vector is None or not self.matches(vector):
                raise ValueError('当前人员与目标员工不匹配')
        return output

    def matches(self, vector):
        vector = np.asarray(vector, dtype=np.float32)
        return (vector.shape == (128,) and np.isfinite(vector).all()
                and min(float(np.linalg.norm(vector - v)) for v in self.vectors) < 1.0)


class Landmarks:
    def __init__(self):
        self.detector = None
    def detect(self, frame):
        if self.detector is None:
            self.detector = FaceLandmarkDetector(max_faces=2)
        return self.detector.detect(frame)
    def close(self):
        if self.detector is not None:
            self.detector.close()

