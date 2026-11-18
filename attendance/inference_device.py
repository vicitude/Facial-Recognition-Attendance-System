"""统一模型推理设备，不在推理异常时静默降级。"""
import torch


def resolve_device(device=None):
    selected = torch.device("cuda:0" if torch.cuda.is_available() else "cpu") if device is None else torch.device(device)
    if selected.type == "cuda":
        # 固定FP32精度，避免TF32导致与既有CPU模板产生额外数值偏差。
        torch.backends.cudnn.allow_tf32 = False
        torch.backends.cuda.matmul.allow_tf32 = False
    return selected
