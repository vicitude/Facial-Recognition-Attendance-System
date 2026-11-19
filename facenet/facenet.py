import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.backends.cudnn as cudnn

from attendance.inference_device import resolve_device
from facenet.nets.facenet import Facenet as facenet
from facenet.utils.utils import preprocess_input, resize_image, show_config



class Facenet(object):
    _defaults = {
        "model_path"    : "./facenet/facenet_mobilenet.pth",
        "input_shape"   : [160, 160, 3],
        "backbone"      : "mobilenet",
        "letterbox_image"   : True,
        "cuda"              : None,
    }

    @classmethod
    def get_defaults(cls, n):
        if n in cls._defaults:
            return cls._defaults[n]
        else:
            return "Unrecognized attribute name '" + n + "'"

    def __init__(self, **kwargs):
        self.__dict__.update(self._defaults)
        for name, value in kwargs.items():
            setattr(self, name, value)

        self.generate()
        
        show_config(**self._defaults)
        
    def generate(self):
        print('Loading weights into state dict...')
        self.device = resolve_device("cpu" if self.cuda is False else None)
        self.cuda = self.device.type == "cuda"
        self.net = facenet(backbone=self.backbone, mode="predict")
        self.net.load_state_dict(torch.load(self.model_path, map_location="cpu", weights_only=True), strict=False)
        self.net.to(self.device).eval()
        print('{} model loaded.'.format(self.model_path))

    def extract_embedding(self, image):
        """提取单张人脸图像的 128 维 FaceNet 特征。"""
        with torch.no_grad():
            image = resize_image(image, [self.input_shape[1], self.input_shape[0]], letterbox_image=self.letterbox_image)
            photo = torch.from_numpy(np.expand_dims(np.transpose(preprocess_input(np.array(image, np.float32)), (2, 0, 1)), 0))
            return self.net(photo.to(self.device)).cpu().numpy()[0].astype(np.float32, copy=False)

    def detect_image(self, image_1, image_2):
        with torch.no_grad():
            image_1 = resize_image(image_1, [self.input_shape[1], self.input_shape[0]], letterbox_image=self.letterbox_image)
            image_2 = resize_image(image_2, [self.input_shape[1], self.input_shape[0]], letterbox_image=self.letterbox_image)
            
            photo_1 = torch.from_numpy(np.expand_dims(np.transpose(preprocess_input(np.array(image_1, np.float32)), (2, 0, 1)), 0))
            photo_2 = torch.from_numpy(np.expand_dims(np.transpose(preprocess_input(np.array(image_2, np.float32)), (2, 0, 1)), 0))
                
            output1 = self.net(photo_1.to(self.device)).cpu().numpy()
            output2 = self.net(photo_2.to(self.device)).cpu().numpy()
            
            l1 = np.linalg.norm(output1 - output2, axis=1)

        return l1