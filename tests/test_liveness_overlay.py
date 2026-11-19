"""UT-FUS-07 中文预览，不打开摄像头。"""
import numpy as np
import pytest
from attendance.fused_liveness import FusionResult
from attendance.liveness_overlay import preview_lines, draw_chinese_overlay


@pytest.mark.parametrize('phase,expected', [('baseline', '正视摄像头'), ('outbound', '请向您自己的左侧转头'), ('return', '请回正并睁眼')])
def test_UT_FUS_07_stage(phase, expected):
    lines = preview_lines(FusionResult('pending', 'turn_left', phase, 1, ''))
    assert expected in '\n'.join(lines)
    assert '2/3' in '\n'.join(lines)


def test_UT_FUS_07_failure_has_reason_not_action():
    lines = preview_lines(FusionResult('failed', 'turn_left', 'outbound', 0, 'passive_spoof'))
    assert '疑似照片或屏幕攻击' in '\n'.join(lines)
    assert not any('请向您' in line for line in lines)
    assert '按 R' in lines[-1]


def test_CT_FUS_03_identity_diagnostics_visible(monkeypatch):
    import attendance.liveness_overlay as overlay
    lines = []
    original = overlay.preview_lines
    # 捕获实际绘制文本，保留真实Pillow渲染验证。
    from PIL import ImageDraw
    original_text = ImageDraw.ImageDraw.text
    def record(draw, xy, text, **kwargs):
        lines.append(text)
        return original_text(draw, xy, text, **kwargs)
    monkeypatch.setattr(ImageDraw.ImageDraw, 'text', record)
    frame = np.zeros((960, 1280, 3), dtype=np.uint8)
    overlay.draw_chinese_overlay(frame, FusionResult('failed', 'blink', 'baseline', 0, 'identity_changed'),
                                 dict(identity_distance=.913, identity_ear=.287, baseline_yaw=1.2,
                                      baseline_pitch=45., frozen=True, aux_age_ms=900.))
    rendered = '\n'.join(lines)
    assert '0.913' in rendered and '0.287' in rendered
    assert '基准 yaw 1.2' in rendered and '已冻结' in rendered
    assert not frame.any()


def test_UT_FUS_07_chinese_pixels_do_not_modify_source():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    rendered = draw_chinese_overlay(frame, FusionResult('pending', 'blink', 'outbound', 0, ''))
    assert rendered.shape == frame.shape
    assert rendered.dtype == frame.dtype
    assert rendered.sum() > 0
    assert frame.sum() == 0
