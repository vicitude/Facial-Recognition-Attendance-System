
from facenet.facenet import Facenet
from PIL import Image
import recognition
import cv2
import os


# 加载人脸识别模型
model = Facenet()


# 遍历人脸文件夹，将文件信息存放在列表中
face_datasets_list = []
names = []
face_datasets = os.listdir('./face_datasets/')
for file in face_datasets:
    if file.endswith('jpg') or file.endswith('png'):
        face_datasets_list.append('./face_datasets/' + file)
        names.append(file.split('.')[0])



# 加载视频，循环读取
cap = cv2.VideoCapture('./inference/videos/test_1.avi')
while True:

    
    # ret, frame = cap.read() --- 读取视频，有数据返回的时候ret参数为True，否则为False。第二个参数是视频数据
    ret, frame = cap.read()
    # ret为False的时候，跳出循环

    if not ret:
        break

    
    # recognition.recognition(frame) --- 调用yolov8模型对人类进行检测
    boxes = recognition.recognition(frame)

    
    #  遍历得到的人脸信息
    for box in boxes:

        #  人脸目标的置信度大于0.6的时候
        if box[4] > 0.6:

            #  框起来人脸
            cv2.rectangle(frame, (box[0], box[1]), (box[2], box[3]), (0, 255, 0), 1)
            #  得到人脸ROI区域，然后写入到目录
            face_roi = frame[box[1]:box[3], box[0]:box[2]]
            cv2.imwrite('./facenet/images/face.jpg', face_roi)

            #  读取目录的人脸图像。然后和人脸数据库中的人脸就行比对，得到识别的结果
            info = []
            image_1 = Image.open('./facenet/images/face.jpg')
            for path in face_datasets_list:
                image_2 = Image.open(path)
                distance = model.detect_image(image_1, image_2)
                info.append(distance)

            name = names[info.index(min(info))]
            #  将识别结果绘制在图像上
            if min(info) < 1:
                cv2.putText(frame, name, (box[0], box[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
            else:
                cv2.putText(frame, 'unknown', (box[0], box[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

    cv2.imshow('', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

