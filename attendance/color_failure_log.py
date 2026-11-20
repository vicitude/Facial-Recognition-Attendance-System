"""追加彩光失败的本地诊断统计。"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from attendance.color_light_liveness import ColorLightConfig, QUALITY_ISSUES

_LOG_PATH = Path(__file__).resolve().parent.parent / 'color_liveness_failures.jsonl'
_ROW_FIELDS = ('cycle', 'color', 'samples', 'hits', 'motion_skips', 'delta_median', 'delta_peak')


def append_color_failure(reason: str, *, min_color_ratio: float, snapshot: Optional[dict] = None,
                         config: Optional[ColorLightConfig] = None) -> bool:
    snapshot = snapshot or {}
    result = snapshot.get('result')
    metrics = result.metrics if result is not None else {}
    rows = []
    for row in metrics.get('color_diagnostics', []):
        fields = {key: row[key] for key in _ROW_FIELDS}
        fields['quality_skips'] = {key: row['quality_skips'][key] for key in QUALITY_ISSUES
                                   if key in row['quality_skips']}
        rows.append(fields)
    entry = dict(timestamp=datetime.now().astimezone().isoformat(timespec='seconds'),
                 reason=reason, min_color_ratio=min_color_ratio,
                 color=result.color if result is not None else None,
                 baseline_samples=metrics.get('baseline_samples'),
                 baseline_frames=config.baseline_frames if config is not None else None,
                 chroma_delta_threshold=config.chroma_delta_threshold if config is not None else None,
                 baseline_luma=metrics.get('baseline_luma'),
                 baseline_luma_variance=metrics.get('baseline_luma_variance'),
                 baseline_chroma=metrics.get('baseline_chroma'), color_diagnostics=rows)
    entry.update({key: snapshot.get(key) for key in ('frame_count', 'processed_count', 'valid_count')})
    try:
        line = json.dumps(entry, ensure_ascii=False, allow_nan=False)
        with _LOG_PATH.open('a', encoding='utf-8') as stream:
            stream.write(line + '\n')
    except (OSError, ValueError, TypeError):
        return False
    return True
