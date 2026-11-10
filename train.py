from ultralytics import YOLO

if __name__ == '__main__':
    model = YOLO("yolov8s.pt")
    model.train(data=r"D:\yolov8_facenet\mydata.yaml",
                epochs=150,
                batch=1,
                workers=0,
                imgsz=640)
