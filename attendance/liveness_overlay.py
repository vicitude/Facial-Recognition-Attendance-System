"""研究摄像头中文提示；只修改预览副本，不修改推理帧。"""
from functools import lru_cache
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ACTIONS = {
    'blink': '请眨眼，然后睁眼',
    'turn_left': '请向您自己的左侧转头',
    'turn_right': '请向您自己的右侧转头',
    'nod': '请低头点头',
}
REASONS = {
    'invalid_feature': '关键点数据无效，请调整位置重试',
    'need_one_face': '请确保画面只有一张脸且正对摄像头',
    'poor_quality': '人脸不清晰、太小或光线不合适',
    'identity_changed': '人脸特征变化过大，请重新检测',
    'invalid_time': '帧时间异常，请重新检测',
    'frame_gap': '处理帧间隔过长，请检查电脑推理速度',
    'trajectory_jump': '采样轨迹不连续，无法确认动作；请查看动作FPS后重试',
    'auxiliary_stale': '辅助推理未及时完成，请检查下方耗时后重试',
    'verification_timeout': '动作已完成，但等待新鲜辅助结果超时',
    'identity_check_timeout': '回正身份复核超时，请正视睁眼后重新检测',
    'pipeline_error': '后台推理异常，本轮未放行；请重启并检查环境',
    'passive_spoof': '被动模型判定疑似照片或屏幕攻击',
    'passive_not_confirmed': '动作已完成，但被动活体未确认',
    'action_timeout': '当前动作超时',
    'session_timeout': '本轮检测超时',
    'invalid_passive': '被动检测结果异常',
    'completed': '三次眨眼与辅助检查通过（仅研究结果）',
    'calibration_timeout': '眼部校准超时，按R重新开始',
}


def preview_lines(result) -> list[str]:
    if result is None:
        return ['融合活体研究 · 准备开始', '请正视摄像头，保持睁眼', '按 R 重新检测  |  Esc 退出']
    status = {'pending': '检测中', 'passed': '本轮通过（研究验证）',
              'failed': '本轮失败', 'timeout': '检测超时'}[result.status]
    unit = '次眨眼' if result.action == 'blink' else '个动作'
    lines = [f'{status}  ·  已完成 {result.completed}/3 {unit}']
    if result.status != 'pending':
        lines.append(REASONS.get(result.reason, '检测未完成，请重试'))
        lines.append('按 R 开始新一轮眨眼挑战  |  Esc 退出')
    else:
        if result.phase == 'identity_check':
            return lines + ['动作完成，请回正睁眼，等待身份复核', '请保持稳定  |  R重新检测  |  Esc退出']
        if result.phase == 'verification':
            return lines + ['三次眨眼已完成，等待最新身份与被动活体检查', '请保持正视睁眼  |  R重新检测  |  Esc退出']
        if result.phase == 'baseline':
            instruction = '请正视摄像头，保持睁眼，等待建立基准'
        elif result.phase == 'return':
            instruction = '动作已达到，请回正并睁眼，保持片刻'
        else:
            instruction = ACTIONS[result.action]
        lines.extend([f'第 {result.completed + 1}/3 {unit}：{ACTIONS[result.action]}', instruction,
                      '请按提示操作  |  R 重新检测  |  Esc 退出'])
    return lines


@lru_cache(maxsize=8)
def _font(size):
    directory = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
    for name in ('msyh.ttc', 'simhei.ttf', 'simsun.ttc'):
        path = directory / name
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    raise RuntimeError('未找到中文字体：请检查Windows字体安装')


def draw_chinese_overlay(frame, result, metrics=None, warming=False):
    image = Image.fromarray(np.ascontiguousarray(frame[:, :, ::-1]))
    draw = ImageDraw.Draw(image)
    width, height = image.size
    size = max(12, min(28, width // 28, height // 16))
    font = _font(size)
    margin, spacing = 10, size + 8
    wrapped = []
    lines = preview_lines(result)
    if warming:
        progress = (metrics or {}).get('baseline_samples', 0)
        stage = (metrics or {}).get('preparation_stage', 'open')
        instructions = {
            'open': '准备1/3：正视摄像头，自然睁眼保持片刻',
            'close': '准备2/3：保持正视，请闭眼并保持片刻',
            'reopen': '准备3/3：请重新睁眼并保持片刻',
            'ready': f'眼部校准完成，请正视睁眼，等待身份基准 {progress}/3',
        }
        lines = ['融合活体研究 · 准备阶段（三次眨眼尚未开始）', instructions[stage]]
        reasons = {'need_one_face': '请确保画面只有一张脸', 'poor_quality': '请改善光线和清晰度',
                   'center_face': '请回正，正视摄像头', 'invalid_feature': '关键点无效，请调整位置',
                   'frame_gap': '采样间隔过长，重新校准', 'hold_still': '姿态或眼部数值不稳定，请保持片刻',
                   'open_eyes': '请自然睁眼', 'close_eyes': '请闭眼并保持片刻'}
        reason = (metrics or {}).get('preparation_reason')
        if reason in reasons:
            lines.append(reasons[reason])
        lines.append('按 R 重新校准  |  Esc 退出')
    if metrics:
        def number(key):
            value = metrics.get(key)
            precision = 3 if key in ('identity_distance', 'identity_ear') else 1
            return '--' if value is None else f'{value:.{precision}f}'
        lines.extend([f"动作FPS {number('action_fps')}  |  关键点 {number('landmarks_ms')} 毫秒",
                      f"YOLO {number('yolo_ms')} / 身份 {number('facenet_ms')} / 被动 {number('passive_ms')} 毫秒",
                      f"辅助结果年龄 {number('aux_age_ms')} 毫秒（上限2000）"])
        lines.extend([f"身份距离 {number('identity_distance')} / 阈值 0.8",
                      f"基准 yaw {number('baseline_yaw')} / pitch {number('baseline_pitch')}",
                      f"本帧 yaw {number('identity_yaw')} / pitch {number('identity_pitch')} / EAR {number('identity_ear')}"])
        if metrics.get('identity_check_state') == 'deferred':
            lines.append('动作中身份距离仅作诊断，回正后严格复核')
        elif metrics.get('identity_check_state') == 'waiting':
            lines.append(f"回正身份复核 {metrics.get('identity_check_samples', 0)}/3，连续超限 {metrics.get('identity_failures', 0)}/3")
        if metrics.get('open_threshold') is not None:
            lines.append(f"校准EAR {metrics['open_ear']:.3f} / 闭眼阈值 {metrics['closed_threshold']:.3f} / 睁眼阈值 {metrics['open_threshold']:.3f}")
        if metrics.get('frozen'):
            lines.append('本轮结束时指标（已冻结，不再随等待时间增长）')
        if metrics.get('aux_expired'):
            lines.append('辅助推理结果已过期，不计入通过；正在等待最新结果')
    for line in lines:
        current = ''
        for char in line:
            if current and draw.textbbox((0, 0), current + char, font=font)[2] > width - 2 * margin:
                wrapped.append(current)
                current = char
            else:
                current += char
        wrapped.append(current)
    draw.rectangle((0, 0, width, min(height, len(wrapped) * spacing + 2 * margin)), fill=(15, 15, 15))
    for index, line in enumerate(wrapped):
        draw.text((margin, margin + index * spacing), line, font=font, fill=(255, 235, 120))
    return np.asarray(image)[:, :, ::-1].copy()
