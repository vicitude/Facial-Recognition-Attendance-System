
# 导入库
from facenet.facenet import Facenet
from PIL import Image
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


def rec(image, box):


       
        #  得到人脸ROI区域，然后写入到目录
        face_roi = image[box[1]:box[3], box[0]:box[2]]
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
            return name
        else:
            return 'unknown'


