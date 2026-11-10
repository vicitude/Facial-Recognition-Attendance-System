from ultralytics import YOLO

if __name__ == '__main__':
    model = YOLO("./runs/detect/train/weights/best.pt")
    model.val(data=r"D:\yolov8_facenet\mydata.yaml",
              batch=8,
              workers=0,
              imgsz=640)