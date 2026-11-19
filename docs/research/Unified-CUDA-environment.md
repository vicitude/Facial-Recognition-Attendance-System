# 统一推理环境验证结果

2026-11-17，本机运行验证；不是摄像头或攻击验收。

- 保留 opencv4 环境，torch 2.8.0+cu126 / torchvision 0.23.0+cu126，CUDA runtime 12.6，RTX 3050 Laptop GPU。
- 原环境其他包未升级；升级前后 freeze 比较只有 torch 与 torchvision 两项变化。记录见 opencv4-before-cuda-freeze.txt / opencv4-after-cuda-freeze.txt（本机审计，不作为可迁移安装清单；pip本地wheel来源路径只是历史元数据）。
- YOLO实际执行合成黑图，device=cuda:0；FaceNet和两MiniFASNet真实CPU/CUDA推理成功；MediaPipe FaceMesh独立进程初始化成功，仍CPU。
- 默认TF32最大FaceNet分量误差0.000571683；关闭TF32后最大误差3.948807716369629e-7；两模型平均概率最大误差1.1641532182693481e-8。统一CUDA选择器关闭TF32；不改变阈值/归一化/颜色输入。
- 活体、模型设备、管理员/签到UI、模板加密/识别、地点工作线程专项：143 passed / 14既有Matplotlib弃用warnings，23.23秒。不是全项目通过。
- 完整attendance_ui导入、Qt application与管理员页构造成功（刷新表替身，不访问业务库）；加密/DPAPI/Windows定位依赖导入通过。Qt离屏有字体目录警告，未宣称真实GUI视觉验收。
- 升级前原有四项pip check问题保持一致：chromadb缺onnxruntime；langchain-core与packaging26.3冲突；opencv-python-headless5与numpy1.26.4冲突；opentelemetry-proto与protobuf4.25.9冲突。没有擅自修复无关依赖，不能宣称pip check全绿。
- 安装曾因D盘空间不足失败并回滚torch，导致短暂torch/torchvision不匹配；将wheel移至C盘后完成安装并重新验证。
- 用户授权后，验证通过再删除独立opencv4_gpu；已核对venv配置、无运行进程、无链接，删除7,493,571,910字节，目录不存在。D盘剩余10,277,335,040字节（删除时读数）。

## 当前启动方式

```powershell
Set-Location -LiteralPath 'D:\yol\yolov8_facenet'
$env:PYTHONUTF8='1'
$env:YOLO_AUTOINSTALL='false'
# 仅对本项目已信任的本地旧完整YOLO权重使用
$env:TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD='1'
& 'D:\python\venvs\opencv4\Scripts\python.exe' -u '.\attendance_ui.py'
```

独立活体：将入口替换为 fused_liveness_research.py --camera 0 --category live。管理员活体试运行默认关闭。无CUDA时自动CPU；显存/驱动错误向上传播，不静默降级。未打开相机，未修改正式库，未修改旧三个入口主体，未commit/push/reset/clean。历史签到/签退矛盾不在本轮修复范围，照片现场验收仍未完成。
