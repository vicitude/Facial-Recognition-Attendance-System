from ultralytics.utils.ops import non_max_suppression, scale_boxes
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtGui import QPainter, QPixmap, QImage
import numpy as np
import get_name
import argparse
import torch
import cv2
import sys
import face_library
from face_manager_ui import open_face_manager_window


def letterbox(im, new_shape=(640, 640), color=(114, 114, 114), auto=True, scaleFill=False, scaleup=True, stride=32):
    shape = im.shape[:2]
    if isinstance(new_shape, int):
        new_shape = (new_shape, new_shape)
    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
    if not scaleup:
        r = min(r, 1.0)

    ratio = r, r
    new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
    dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]
    if auto:
        dw, dh = np.mod(dw, stride), np.mod(dh, stride)
    elif scaleFill:
        dw, dh = 0.0, 0.0
        new_unpad = (new_shape[1], new_shape[0])
        ratio = new_shape[1] / shape[1], new_shape[0] / shape[0]

    dw /= 2
    dh /= 2

    if shape[::-1] != new_unpad:
        im = cv2.resize(im, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    im = cv2.copyMakeBorder(im, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)
    return im, ratio, (dw, dh)


parser = argparse.ArgumentParser()
parser.add_argument('--weights', type=str, default='runs/detect/train/weights/best.pt', help='path to weights file')
parser.add_argument('--conf-thres', type=float, default=0.3, help='object confidence threshold')
parser.add_argument('--nms-thres', type=float, default=0.5, help='iou threshold for non-maximum suppression')
opt = parser.parse_args()
print(opt)


class Yolo():
    def __init__(self):
        self.prepare()

    def prepare(self):
        global model, device, classes, names
        device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        model = torch.load(opt.weights, map_location=device)['model'].float()
        model.to(device).eval()
        names = model.names if hasattr(model, 'names') else model.modules.names

    def detect(self, frame):
        im0 = frame
        img = letterbox(frame, new_shape=640)[0]
        img = img[:, :, ::-1].transpose(2, 0, 1)
        img = np.ascontiguousarray(img, dtype=np.float32)
        img /= 255.0

        img = torch.from_numpy(img).to(device)
        if img.ndimension() == 3:
            img = img.unsqueeze(0)

        pred = model(img)[0]
        pred = non_max_suppression(pred, opt.conf_thres, opt.nms_thres)

        boxes = []
        for i, det in enumerate(pred):
            if det is not None and len(det):
                det[:, :4] = scale_boxes(img.shape[2:], det[:, :4], im0.shape).round()

                for *xyxy, score, cls in det:
                    label = names[int(cls)]
                    boxes.append([int(xyxy[0]),
                                  int(xyxy[1]),
                                  int(xyxy[2]),
                                  int(xyxy[3]),
                                  float(score),
                                  int(cls),
                                  label
                                  ])
        return boxes


yolo = Yolo()


def recognition(image):
    boxes = yolo.detect(image)
    return boxes


class UiMainWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.timer_camera = QtCore.QTimer()
        self.cap = cv2.VideoCapture()
        self.CAM_NUM = 0
        self.flag_recognition = False
        self.myFileStr = ''
        self.current_pixmap = None
        recognition(cv2.imread('./ultralytics/assets/bus.jpg'))
        print('---------------加载模型-----------------')
        # 启动时重载人脸库并同步到 get_name 缓存 (与 face_manager 联动)
        try:
            reload_paths, reload_names = face_library.reload_face_library()
            import get_name
            get_name.face_datasets_list = reload_paths
            get_name.names = reload_names
            print(f'[启动] 人脸库已重载, 当前 {len(reload_names)} 人')
        except Exception as e:
            print(f'[启动] 人脸库重载失败 (非致命): {e}')
        self.set_ui()
        self.slot_init()

    def set_ui(self):
        self.__layout_main_1 = QtWidgets.QHBoxLayout()
        self.__layout_fun_button = QtWidgets.QHBoxLayout()
        self.__layout_main_2 = QtWidgets.QVBoxLayout()

        self.button_open_camera = QtWidgets.QPushButton('打开相机')
        self.button_open_camera.setFixedSize(120, 60)
        self.button_open_camera.setStyleSheet("QPushButton{color:white}"
                                             "QPushButton:hover{background-color: rgb(2,110,180);}"
                                             "QPushButton{background-color:rgb(48,124,208)}"
                                             "QPushButton{border:2px}"
                                             "QPushButton{border-radius:5px}"
                                             "QPushButton{padding:5px 5px}"
                                             "QPushButton{margin:5px 5px}")
        self.button_open_video       = QtWidgets.QPushButton('打开视频')
        self.button_open_video.setFixedSize(120, 60)
        self.button_open_video.setStyleSheet("QPushButton{color:white}"
                                              "QPushButton:hover{background-color: rgb(2,110,180);}"
                                              "QPushButton{background-color:rgb(48,124,208)}"
                                              "QPushButton{border:2px}"
                                              "QPushButton{border-radius:5px}"
                                              "QPushButton{padding:5px 5px}"
                                              "QPushButton{margin:5px 5px}")
        self.button_play_video       = QtWidgets.QPushButton('播放视频')
        self.button_play_video.setFixedSize(120, 60)
        self.button_play_video.setStyleSheet("QPushButton{color:white}"
                                              "QPushButton:hover{background-color: rgb(2,110,180);}"
                                              "QPushButton{background-color:rgb(48,124,208)}"
                                              "QPushButton{border:2px}"
                                              "QPushButton{border-radius:5px}"
                                              "QPushButton{padding:5px 5px}"
                                              "QPushButton{margin:5px 5px}")
        self.button_close_video      = QtWidgets.QPushButton('清屏')
        self.button_close_video.setFixedSize(120, 60)
        self.button_close_video.setStyleSheet("QPushButton{color:white}"
                                              "QPushButton:hover{background-color: rgb(2,110,180);}"
                                              "QPushButton{background-color:rgb(48,124,208)}"
                                              "QPushButton{border:2px}"
                                              "QPushButton{border-radius:5px}"
                                              "QPushButton{padding:5px 5px}"
                                              "QPushButton{margin:5px 5px}")
        self.button_open_image       = QtWidgets.QPushButton('打开图像')
        self.button_open_image.setFixedSize(120, 60)
        self.button_open_image.setStyleSheet("QPushButton{color:white}"
                                              "QPushButton:hover{background-color: rgb(2,110,180);}"
                                              "QPushButton{background-color:rgb(48,124,208)}"
                                              "QPushButton{border:2px}"
                                              "QPushButton{border-radius:5px}"
                                              "QPushButton{padding:5px 5px}"
                                              "QPushButton{margin:5px 5px}")
        self.button_recognition      = QtWidgets.QPushButton('开始识别')
        self.button_recognition.setFixedSize(120, 60)
        self.button_recognition.setStyleSheet("QPushButton{color:white}"
                                              "QPushButton:hover{background-color: rgb(2,110,180);}"
                                              "QPushButton{background-color:rgb(48,124,208)}"
                                              "QPushButton{border:2px}"
                                              "QPushButton{border-radius:5px}"
                                              "QPushButton{padding:5px 5px}"
                                              "QPushButton{margin:5px 5px}")
        self.button_stop_recognition = QtWidgets.QPushButton('停止识别')
        self.button_stop_recognition.setFixedSize(120, 60)
        self.button_stop_recognition.setStyleSheet("QPushButton{color:white}"
                                              "QPushButton:hover{background-color: rgb(2,110,180);}"
                                              "QPushButton{background-color:rgb(48,124,208)}"
                                              "QPushButton{border:2px}"
                                              "QPushButton{border-radius:5px}"
                                              "QPushButton{padding:5px 5px}"
                                              "QPushButton{margin:5px 5px}")
        self.button_close            = QtWidgets.QPushButton('退出程序')
        self.button_face_manager     = QtWidgets.QPushButton('人脸库管理')
        self.button_face_manager.setFixedSize(120, 60)
        self.button_face_manager.setStyleSheet("QPushButton{color:white}"
                                              "QPushButton:hover{background-color: rgb(2,110,180);}"
                                              "QPushButton{background-color:rgb(48,124,208)}"
                                              "QPushButton{border:2px}"
                                              "QPushButton{border-radius:5px}"
                                              "QPushButton{padding:5px 5px}"
                                              "QPushButton{margin:5px 5px}")
        self.button_close.setFixedSize(120, 60)
        self.button_close.setStyleSheet("QPushButton{color:white}"
                                              "QPushButton:hover{background-color: rgb(2,110,180);}"
                                              "QPushButton{background-color:rgb(48,124,208)}"
                                              "QPushButton{border:2px}"
                                              "QPushButton{border-radius:5px}"
                                              "QPushButton{padding:5px 5px}"
                                              "QPushButton{margin:5px 5px}")

        self.button_close.setMinimumHeight(50)
        self.button_stop_recognition.setMinimumHeight(50)
        self.button_recognition.setMinimumHeight(50)
        self.button_open_video.setMinimumHeight(50)
        self.button_play_video.setMinimumHeight(50)
        self.button_close_video.setMinimumHeight(50)
        self.button_open_image.setMinimumHeight(50)
        self.button_open_camera.setMinimumHeight(50)
        self.button_face_manager.setMinimumHeight(50)

        self.label_show_camera = QtWidgets.QLabel()
        self.label_show_camera.setAlignment(QtCore.Qt.AlignCenter)
        self.label_show_camera.setScaledContents(False)

        # 右侧信息栏文字设置
        self.label_show_info = QtWidgets.QLabel()
        self.label_show_info.setFixedWidth(300)
        font = QtGui.QFont()
        font.setPointSize(16)
        self.label_show_info.setFont(font)
        self.label_show_info.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        self.label_show_info.setWordWrap(True)

        self.__layout_main_1.addWidget(self.label_show_camera)
        self.__layout_main_1.addWidget(self.label_show_info)
        self.__layout_main_1.setStretchFactor(self.label_show_camera, 8)
        self.__layout_main_1.setStretchFactor(self.label_show_info, 1)

        self.__layout_fun_button.addWidget(self.button_open_camera)
        self.__layout_fun_button.addWidget(self.button_open_video)
        self.__layout_fun_button.addWidget(self.button_play_video)
        self.__layout_fun_button.addWidget(self.button_close_video)
        self.__layout_fun_button.addWidget(self.button_open_image)
        self.__layout_fun_button.addWidget(self.button_recognition)
        self.__layout_fun_button.addWidget(self.button_stop_recognition)
        self.__layout_fun_button.addWidget(self.button_face_manager)
        self.__layout_fun_button.addWidget(self.button_close)

        self.__layout_main_2.addLayout(self.__layout_main_1)
        self.__layout_main_2.addLayout(self.__layout_fun_button)
        self.setLayout(self.__layout_main_2)

        self.setWindowTitle("基于人脸图像的识别系统")
        self.resize(1300, 700)

    def slot_init(self):
        self.button_close.clicked.connect(self.close)
        self.button_recognition.clicked.connect(self.recognition)
        self.button_stop_recognition.clicked.connect(self.stop_recognition)
        self.button_open_video.clicked.connect(self.open_video)
        self.button_play_video.clicked.connect(self.play_video)
        self.button_close_video.clicked.connect(self.close_video)
        self.button_open_image.clicked.connect(self.open_image)
        self.timer_camera.timeout.connect(self.show_camera)
        self.button_open_camera.clicked.connect(self.button_open_camera_clicked)
        self.button_face_manager.clicked.connect(self.open_face_manager)

    def open_face_manager(self):
        """「人脸库管理」按钮槽函数: 弹独立的 FaceManagerDialog。

        注意: get_name.rec() 内部仍直接读模块级 face_datasets_list/names,
        不能热生效。修复方式 (临时): 让 get_name.py 的模块级变量指向 face_library 缓存。
        此处通过 patch get_name 模块属性实现 (侵入性小, 不改 get_name 源文件)。
        """
        reload_paths, reload_names = face_library.reload_face_library()
        # 同步 get_name 模块的全局缓存 (热生效)
        import get_name
        get_name.face_datasets_list = reload_paths
        get_name.names = reload_names
        # 弹窗
        dlg = open_face_manager_window(self)
        # 弹窗内点「重载 / 删除 / 保存」时同步刷新 ui.py 这边的缓存
        dlg.library_reloaded.connect(self._on_library_reloaded)
        # 保留引用避免被 GC 提前回收
        self._face_manager_dlg = dlg

    def _on_library_reloaded(self):
        """接 FaceManagerDialog 信号, 同步刷新本窗口的识别缓存。"""
        import get_name
        reload_paths, reload_names = face_library.reload_face_library()
        get_name.face_datasets_list = reload_paths
        get_name.names = reload_names
        # 顺手更新一次 info 栏 (若摄像头开着) 让用户立刻看到重载生效
        if hasattr(self, "label_show_info"):
            self.label_show_info.setText(
                f"(已重载人脸库, 当前 {len(reload_names)} 人)"
            )

    def cv_to_pixmap(self, cv_img):
        rgb_img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_img.shape
        bytes_per_line = ch * w
        q_img = QImage(rgb_img.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pix = QPixmap.fromImage(q_img)
        label_size = self.label_show_camera.size()
        pix = pix.scaled(label_size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        self.current_pixmap = pix
        return pix

    def open_image(self):
        self.close_video()
        fname = QtWidgets.QFileDialog.getOpenFileName(self, 'Open file', './inference/images/')
        if fname[0]:
            self.label_show_info.setText('')
            self.myFileStr = fname[0]
            image = cv2.imread(self.myFileStr)
            pix = self.cv_to_pixmap(image)
            self.label_show_camera.setPixmap(pix)

    def button_open_camera_clicked(self):
        self.close_video()
        if not self.timer_camera.isActive():
            flag = self.cap.open(self.CAM_NUM, cv2.CAP_DSHOW)
            self.flag_recognition = False
            if not flag:
                QtWidgets.QMessageBox.warning(self, 'warning', "请检查相机于电脑是否连接正确", buttons=QtWidgets.QMessageBox.Ok)
            else:
                self.timer_camera.start(30)
                self.button_open_camera.setText('关闭相机')
        else:
            self.timer_camera.stop()
            self.cap.release()
            self.label_show_camera.clear()
            self.current_pixmap = None
            self.button_open_camera.setText('打开相机')

    def open_video(self):
        self.close_video()
        self.fname_video = QtWidgets.QFileDialog.getOpenFileName(self, 'Open file', './inference/videos/')
        self.myFileStr = self.fname_video[0]
        file_name = self.fname_video[0].split('/')[-1].split('.')[-1]
        self.flag_recognition = False
        if file_name in ['mp4', 'avi']:
            self.CAM_NUM = self.fname_video[0]
            self.cap.open(self.CAM_NUM)
            ret, frame = self.cap.read()
            if ret:
                pix = self.cv_to_pixmap(frame)
                self.label_show_camera.setPixmap(pix)

    def recognition(self):
        if self.myFileStr.split('.')[-1] in ['mp4', 'avi']:
            self.flag_recognition = True
        if self.CAM_NUM == 0:
            self.flag_recognition = True
        if self.myFileStr.split('.')[-1] in ['jpg', 'png', 'jpeg']:
            img = cv2.imread(self.myFileStr)
            bboxes = recognition(img)
            ss = ''
            for box in bboxes:
                cv2.rectangle(img, (box[0], box[1]), (box[2], box[3]), (0, 255, 0), 2)
                text = "{}: {:.4f}".format(box[6], box[4])
                name = get_name.rec(img, box)
                cv2.putText(img, name, (box[0], box[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 1)
                label = box[-1]
                ss += label + ': \n' + str(box[:4]) + '\n' + name + '\n\n'
            self.label_show_info.setText(ss)
            pix = self.cv_to_pixmap(img)
            self.label_show_camera.setPixmap(pix)

    def stop_recognition(self):
        self.flag_recognition = False

    def show_camera(self):
        ret, frame = self.cap.read()
        if ret:
            ss = ''
            if self.flag_recognition:
                bboxes = recognition(frame)
                for box in bboxes:
                    label = box[-1]
                    cv2.rectangle(frame, (box[0], box[1]), (box[2], box[3]), (0, 255, 0), 2)
                    text = "{}: {:.4f}".format(box[6], box[4])
                    cv2.putText(frame, text, (box[0], box[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                    name = get_name.rec(frame, box)
                    ss += label + ': \n' + str(box[:4]) + '\n' + name + '\n\n'
            self.label_show_info.setText(ss)
            pix = self.cv_to_pixmap(frame)
            self.label_show_camera.setPixmap(pix)
        else:
            self.cap.release()
            self.label_show_camera.clear()
            self.label_show_info.setText('')
            self.CAM_NUM = 0
            self.current_pixmap = None

    def play_video(self):
        self.timer_camera.start(30)

    def close_video(self):
        self.timer_camera.stop()
        self.cap.release()
        self.label_show_camera.clear()
        self.button_open_camera.setText('打开相机')
        self.CAM_NUM = 0
        self.label_show_info.setText('')
        self.myFileStr = ''
        self.current_pixmap = None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.current_pixmap is not None:
            new_pix = self.current_pixmap.scaled(
                self.label_show_camera.size(),
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation
            )
            self.label_show_camera.setPixmap(new_pix)

    def paintEvent(self, event):
        painter = QPainter(self)
        pixmap = QPixmap(r"C:\Users\WJ\Desktop\yol\OIP-C.webp")
        pixmap = pixmap.scaled(self.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        painter.drawPixmap(self.rect(), pixmap)


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    ui = UiMainWindow()
    ui.show()
    sys.exit(app.exec_())