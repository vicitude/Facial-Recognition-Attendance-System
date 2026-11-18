from PyQt5 import QtCore


class RecognitionWorker(QtCore.QObject):
    finished = QtCore.pyqtSignal(object)
    failed = QtCore.pyqtSignal(str)
    completed = QtCore.pyqtSignal(int, object)
    errored = QtCore.pyqtSignal(int, str)

    def __init__(self, frame, recognize, identify, generation=0, batch_identify=None):
        super().__init__()
        self._frame = frame
        self._recognize = recognize
        self._identify = identify
        self._batch_identify = batch_identify
        self._generation = generation

    @QtCore.pyqtSlot()
    def run(self):
        try:
            boxes = self._recognize(self._frame)
            if not boxes:
                self.completed.emit(self._generation, 'unknown')
                self.finished.emit('unknown')
                return
            if self._batch_identify is not None:
                names = self._batch_identify(self._frame, boxes)
                self.completed.emit(self._generation, names)
                self.finished.emit(names)
                return
            name = self._identify(self._frame, boxes[0][:4])
            self.completed.emit(self._generation, name or 'unknown')
            self.finished.emit(name or 'unknown')
        except Exception as error:
            self.errored.emit(self._generation, str(error))
            self.failed.emit(str(error))
