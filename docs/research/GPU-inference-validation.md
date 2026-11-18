# GPU 推理独立验证

日期：2026-11-16。状态：独立 CUDA 环境、真实 GPU 运算及静态单图 CPU/GPU 对照已完成；摄像头并发流水线与活体现场效果未验收。

## 授权与边界

用户确认建立独立 GPU 测试环境。不修改原 CPU 环境及旧 recognition.py/ui.py/get_name.py；不访问考勤数据库、不打开摄像头、不下载新模型、不改变识别或活体阈值。

## 已核对环境

- NVIDIA GeForce RTX 3050 Laptop GPU，显存 4096 MiB。
- NVIDIA 驱动 591.74；nvidia-smi 显示 CUDA 13.1，这是驱动能力，不代表 PyTorch 已能使用 CUDA。
- 原环境 Python 3.9.25、torch 2.8.0+cpu、torchvision 0.23.0+cpu。
- 独立环境选择同版本 torch 2.8.0 / torchvision 0.23.0 的 CUDA 12.6 构建，保留 numpy 1.26.4。
- 首次安装因旧 pip 对包名规范化和专用索引缺少构建依赖失败；仅升级独立环境 pip，从 PyPI 安装通用依赖，再从 PyTorch 官方索引安装 CUDA 包。不更改 NVIDIA 驱动，不需另装完整 CUDA Toolkit。

## 测试方法

- 使用现有人脸检测权重和用户此前授权测试的同一张静态人脸图；不复制照片或保存人脸向量。
- CPU/GPU 均 float32、letterbox 640、相同置信度和 NMS、5 次预热和 20 次测量。
- 测量覆盖预处理、数据传输、模型、NMS、框输出；CUDA 计时前后 synchronize。
- 原 detect 行为与额外 inference_mode 分开记录，不修改原识别文件。
- 比较图像/权重 SHA-256、框数、类别、框坐标和置信度。
- 静态单图测试不是摄像头整体 FPS 或活体效果验收。

## CPU 初步实测

原 CPU 环境，同一张 1440×810 BGR 图片，5 次预热、20 次测量：

- 原 detect：中位 94.150 ms，P95 95.984 ms。
- inference_mode：中位 106.657 ms，P95 147.011 ms；本次并未加速，不据此修改生产代码。
- 两种路径均检测到 1 张人脸，坐标 [390,724,523,907]，置信度 0.9183657。
- 原图 SHA-256：782eabe7f7c821b2fc3b8f93ef8eedbb71980bff3aa74b016dfe4d72dc0b303c。
- 权重 SHA-256：39b18262cd6f6b259790fed3b6421c11f17ced29a8633c899bab2445a1d73ae7。
- 静态输入是纵向图，经 letterbox 后尺寸与现场横向摄像头输入可能不同；现场约 922 ms 不能与此值直接算加速比。现场还存在模型并发、资源竞争等待排查因素。

## GPU 实测与结论

- torch 2.8.0+cu126 / torchvision 0.23.0+cu126，CUDA available=True；真实矩阵乘法通过，YOLO 参数设备为 cuda:0。
- GPU 原 detect：中位 22.263 ms，P95 25.648 ms；对照原 CPU 94.150 ms，中位约 4.23 倍加速。
- GPU inference_mode：中位 18.569 ms，P95 20.581 ms。仅基准测试使用，不改原入口。
- CPU/GPU 图像和权重哈希相同；均 1 张脸，类别相同、整数坐标完全相同，置信度分别 0.9183657169 / 0.9183664322，差约 7.15e-7。单图输出一致性不代表整个数据集精度验证。
- 独立环境 pip check 通过；YOLO/FaceNet/双 MiniFASNet 均可加载，MediaPipe Face Mesh 可初始化。
- FaceNet 代码固定 CPU，MiniFASNet 默认设备策略未改；不能宣称所有模型都迁移到 GPU。
- 两次 pip 大文件下载无进展，已停止并收集任务；改 curl 从同一官方地址完整下载 2915338284 字节后本地安装成功。未使用第三方模型或更改原环境。

## 本机研究启动方式

独立环境位于项目外，不将个人路径写入应用配置；下述仅本机运行记录，不用于客户交付。

```powershell
Set-Location -LiteralPath 'D:\yol\yolov8_facenet'
$env:PYTHONUTF8 = '1'
$env:YOLO_AUTOINSTALL = 'false'
# 仅对本项目已信任的旧式完整模型权重启用；不得用于不可信下载文件。
$env:TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD = '1'
& 'D:\python\venvs\opencv4_gpu\Scripts\python.exe' -u '.\fused_liveness_research.py' --camera 0 --category live
```

此命令仍是原三动作研究入口，并非新建无动作/炫光算法。未自动打开摄像头。需用户后续观察现场 YOLO 耗时、辅助结果年龄和整体稳定性；本次不承诺消除所有超时或提升防伪准确率。
