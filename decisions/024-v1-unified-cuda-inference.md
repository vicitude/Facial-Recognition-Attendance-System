# 024 统一CUDA推理环境

用户批准保留opencv4、升级CUDA版，验证后删除独立GPU环境。

实现：共享resolve_device，FaceNet/MiniFASNet模型与输入同设备；CUDA关闭TF32保持与CPU模板FP32数值一致。默认CUDA不可用则CPU，推理异常不静默重试。不改变活体阈值/特征预处理，不修改旧ui.py/recognition.py/get_name.py主体。

结果：torch2.8.0+cu126/torchvision0.23.0+cu126；真实CUDA矩阵、YOLO/FaceNet/MiniFASNet推理通过；MediaPipe初始化通过；143项专项通过。UI导入与无业务库构造通过。原四项pip check冲突保持不变。验证后删除独立GPU环境7,493,571,910字节。详细证据及当前命令见 docs/research/Unified-CUDA-environment.md；规范 specs/attendance/12-inference-device/spec.md。

边界：无相机现场/攻击验收，不宣称全项目或全部依赖健康。不涉及历史签到/签退矛盾修复。
