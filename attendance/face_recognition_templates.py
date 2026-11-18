"""加密人脸模板识别适配层（M3）。"""
from __future__ import annotations

from typing import Iterable

import numpy as np

from attendance.face_template_crypto import default_key_path, load_or_create_key
from attendance.services import EmployeeService, FaceTemplateService


def l2_distance(left: np.ndarray, right: np.ndarray) -> float:
    left = np.asarray(left, dtype=np.float32)
    right = np.asarray(right, dtype=np.float32)
    if left.shape != (128,) or right.shape != (128,):
        raise ValueError("识别向量必须是128维")
    return float(np.linalg.norm(left - right))


def match_employee(query: np.ndarray, employee_id: str, key: bytes | None = None) -> tuple[float, str]:
    """在内存中解密一个员工的三个模板，返回最小距离和姿态。"""
    if key is None:
        key = load_or_create_key(default_key_path())
    templates = FaceTemplateService.load_employee_vectors(employee_id, key)
    best = min((l2_distance(query, vector), pose) for pose, vector in templates.items())
    return best


def identify(query: np.ndarray, employee_ids: Iterable[str], threshold: float = 1.0, key: bytes | None = None):
    """遍历在职员工模板，返回 (employee, distance, pose) 或 None。"""
    best = None
    for employee_id in employee_ids:
        employee = EmployeeService.get(employee_id)
        if not employee.is_active:
            continue
        try:
            distance, pose = match_employee(query, employee_id, key)
        except (ValueError, KeyError):
            continue
        if best is None or distance < best[1]:
            best = (employee, distance, pose)
    if best is None or best[1] >= threshold:
        return None
    return best
