"""屏幕彩光窗口的颜色状态控制。"""

COLORS = ("off", "white", "red", "green", "blue")


class ScreenColorController:
    def __init__(self):
        self._current = "off"

    def set_color(self, color: str) -> None:
        if color not in COLORS:
            raise ValueError("COLOR_INVALID_INPUT")
        self._current = color

    def current_color(self) -> str:
        return self._current
