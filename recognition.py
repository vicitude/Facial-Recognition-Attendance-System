
# 加载库


from ultralytics.utils.ops import non_max_suppression, scale_boxes
import numpy as np
import argparse
import torch
import cv2
import sys


# ----------------------------------------------------------------------------------------------------------------------

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



# 参数设置，权重位置，置信度筛选，nms
parser = argparse.ArgumentParser()
parser.add_argument('--weights', type=str, default='runs/detect/train/weights/best.pt', help='path to weights file')
parser.add_argument('--conf-thres', type=float, default=0.3, help='object confidence threshold')
parser.add_argument('--nms-thres', type=float, default=0.5, help='iou threshold for non-maximum suppression')
opt = parser.parse_args()
print(opt)




class Yolo():

   
    # 初始化
    def __init__(self):
        self.prepare()

   

    def prepare(self):
        global model, device, classes, names
        device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        model = torch.load(opt.weights, map_location=device)['model'].float()
        model.to(device).eval()
        names = model.names if hasattr(model, 'names') else model.modules.names

    
    
    def detect(self, frame):

       
        # 图像预处理
        
        im0 = frame
        img = letterbox(frame, new_shape=640)[0]
        img = img[:, :, ::-1].transpose(2, 0, 1)
        img = np.ascontiguousarray(img, dtype=np.float32)
        img /= 255.0

        img = torch.from_numpy(img).to(device)
        if img.ndimension() == 3:
            img = img.unsqueeze(0)

       
        # 识别，以及识别信息的筛选
        pred = model(img)[0]
        pred = non_max_suppression(pred, opt.conf_thres, opt.nms_thres)

        
        # 遍历检测结果，存放在列表中
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

# 调用检测函数
def recognition(image):
    boxes = yolo.detect(image)
    return boxes