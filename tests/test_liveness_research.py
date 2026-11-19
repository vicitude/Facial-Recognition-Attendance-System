import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from attendance.liveness_research import (
    LivenessResearch,
    LivenessResult,
    MultiFrameConsistency,
    assess_confidence,
    assess_quality,
    prepare_tensor,
    summarize,
)


class LivenessResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = LivenessResearch()
        cls.frame = np.zeros((240, 320, 3), dtype=np.uint8)

    def test_prepare_tensor_preserves_upstream_byte_scale(self):
        patch = np.full((80, 80, 3), 255, dtype=np.uint8)
        tensor = prepare_tensor(patch)
        self.assertEqual(tuple(tensor.shape), (1, 3, 80, 80))
        self.assertEqual(float(tensor.max()), 255.0)

    def test_no_face_and_multiple_faces_are_not_pass(self):
        self.assertEqual(self.engine.evaluate(self.frame, []).status, 'no_face')
        self.assertEqual(
            self.engine.evaluate(self.frame, [[0, 0, 10, 10], [20, 20, 30, 30]]).status,
            'multiple_faces',
        )

    def test_invalid_box_is_rejected(self):
        with self.assertRaises(ValueError):
            self.engine.evaluate(self.frame, [[-1, 0, 10, 10]])

    def test_synthetic_face_returns_candidate_without_pass_threshold(self):
        result = self.engine.evaluate(self.frame, [[40, 30, 180, 210]])
        self.assertIn(result.status, {'live_candidate', 'spoof_candidate', 'low_confidence', 'low_quality', 'inconclusive'})
        self.assertEqual(len(result.probabilities), 3)
        self.assertAlmostEqual(sum(result.probabilities), 1.0, places=5)

    def test_confidence_gate_requires_probability_and_margin(self):
        self.assertEqual(assess_confidence([0.05, 0.9, 0.05])[0], 'live_candidate')
        self.assertEqual(assess_confidence([0.1, 0.7, 0.2])[0], 'low_confidence')
        self.assertEqual(assess_confidence([0.1, 0.46, 0.44])[0], 'low_confidence')

    def test_quality_rejects_tiny_dark_and_blurred_faces(self):
        frame = np.zeros((160, 160, 3), dtype=np.uint8)
        self.assertFalse(assess_quality(frame, [0, 0, 20, 20])[0])
        self.assertFalse(assess_quality(frame, [20, 20, 120, 120])[0])
        sharp = np.zeros_like(frame)
        sharp[::2, :, :] = 255
        self.assertTrue(assess_quality(sharp, [20, 20, 120, 120])[0])

    def test_multiframe_consistency_requires_stable_live_sequence(self):
        gate = MultiFrameConsistency()
        live = LivenessResult('live_candidate', (0.05, 0.9, 0.05), 1.0)
        spoof = LivenessResult('spoof_candidate', (0.9, 0.05, 0.05), 1.0)
        for _ in range(4):
            self.assertEqual(gate.update(live), 'pending')
        self.assertEqual(gate.update(live), 'consistent_live')
        gate.reset()
        for result in [live, live, spoof, spoof, spoof]:
            status = gate.update(result)
        self.assertIn(status, {'pending', 'inconsistent'})

    def test_summary_validates_shape_and_probabilities(self):
        status, scores = summarize([[0.1, 0.8, 0.1], [0.2, 0.7, 0.1]])
        self.assertEqual(status, 'live_candidate')
        self.assertAlmostEqual(sum(scores), 1.0, places=5)
        with self.assertRaises(ValueError):
            summarize([[0.5, 0.5]])


if __name__ == '__main__':
    unittest.main(verbosity=2)
