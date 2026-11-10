"""签到/签退人员管理系统 - UI 工具 (SPEC-001-C).

提供统一的 QMessageBox.warning 弹窗辅助, 按错误码决定弹窗标题.
与 attendance/utils.py (A 层) 严格分离, 不修改 A 层代码.
"""

from typing import Optional

from PyQt5 import QtWidgets


# 错误码 → 弹窗标题 映射 (SPEC-001-C §6.1)
_TITLE_MAP: dict[str, str] = {
    "AUTH_FAILED": "登录失败",
    "EMPLOYEE_ID_INVALID": "保存失败",
    "EMPLOYEE_ID_EXISTS": "保存失败",
    "EMPLOYEE_NOT_FOUND": "操作失败",
    "EMPLOYEE_HAS_RECORDS": "删除失败",
    "EMPLOYEE_INACTIVE": "打卡失败",
    "FACE_IMAGE_NOT_FOUND": "保存失败",
    "SCHEDULE_NOT_FOUND": "保存失败",
    "CHECK_TYPE_INVALID": "打卡失败",
    "DATE_RANGE_INVALID": "查询失败",
    "CAMERA_OPEN_FAILED": "相机打开失败",
}


def show_error(
    parent: Optional[QtWidgets.QWidget],
    error_code: str,
    message: str,
) -> None:
    """弹 QMessageBox.warning, 标题按 _TITLE_MAP 决定.

    参数:
        parent: 父窗口 (可为 None).
        error_code: 错误码, 用于决定弹窗标题.
        message: 弹窗正文 (按 §6.1 表格的"内容"列组装, 含错误码后缀).
    """
    title = _TITLE_MAP.get(error_code, "操作失败")
    QtWidgets.QMessageBox.warning(parent, title, message)
