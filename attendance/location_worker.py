"""在后台线程执行定位，避免阻塞 PyQt 主线程。"""
from __future__ import annotations
from PyQt5 import QtCore
from attendance.windows_location import WindowsLocationSource

class LocationWorker(QtCore.QObject):
    finished = QtCore.pyqtSignal(object)
    def __init__(self, source_factory=WindowsLocationSource):
        super().__init__()
        self.source_factory = source_factory
    @QtCore.pyqtSlot()
    def run(self):
        source = self.source_factory()
        self.finished.emit(source.probe())
