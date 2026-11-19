# 人脸识别签到系统

Windows 桌面应用：通过摄像头做人脸签到/签退，在管理员界面维护员工、班次和记录。主入口是 [`attendance_ui.py`](attendance_ui.py)；旧版识别演示不是正式签到入口。

## 1. 准备环境

- Windows 10/11 x64、64 位 CPython 3.9（本项目验证环境为 3.9.25）、PowerShell 5.1 或 7、正在运行的 MySQL Server 8.x 和可用摄像头。模板加密依赖 Windows DPAPI；班次配置了位置校验时，还要开启 Windows 定位服务及桌面应用的定位权限。
- 以下命令在克隆后的项目根目录执行。若 Python 3.9 未加入 `py` 启动器，用对应的 64 位 `python.exe` 创建虚拟环境。Python 3.9 已停止上游安全维护，此处用于复现现有依赖环境。

```powershell
py -3.9 -m venv .venv
$python = '.\.venv\Scripts\python.exe'
& $python -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.8.0 torchvision==0.23.0
& $python -m pip install -r requirements.txt
& $python -m pip check
```

有 NVIDIA 显卡和支持 CUDA 12.6 的驱动时，可在新环境中将第一条 pip 命令的索引换成 `https://download.pytorch.org/whl/cu126`，仍使用相同版本配对。不另装 `ultralytics`（项目自带 8.2.103 源码）；不要并装其它 OpenCV wheel，以免覆盖 `cv2`。

## 2. 获取模型

**自训 YOLO 权重没有公开下载链接。** 先向项目维护者取得原始 `best.pt`，再执行下列命令。普通 COCO 版 `yolov8s.pt` 不能代替此人脸专用模型。脚本下载上游 FaceNet 和 MiniFASNet 依赖并检查 SHA-256，不覆盖已有文件；不会安装 Python 包、打开相机或连库。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup-models.ps1 -YoloWeights 'C:\path\to\best.pt'
```

| 依赖 | 放置路径 / 来源 |
| --- | --- |
| 自训 YOLOv8 人脸检测权重 | `runs/detect/train/weights/best.pt`，来自维护者；SHA-256：`39b18262cd6f6b259790fed3b6421c11f17ced29a8633c899bab2445a1d73ae7` |
| FaceNet MobileNet | `facenet/facenet_mobilenet.pth`，来自 [FaceNet PyTorch v1.0](https://github.com/bubbliiiing/facenet-pytorch/releases/tag/v1.0) |
| 默认被动活体 | `research_assets/Silent-Face-Anti-Spoofing/` 下的两份 Python 源文件和两份权重，来自 [固定上游提交](https://github.com/minivision-ai/Silent-Face-Anti-Spoofing/tree/b6d5f04ad78778917853b25c778acef6d5626d15)；准确路径及哈希见 [`setup-models.ps1`](setup-models.ps1) |

如果 `best.pt` 已在目标路径，可以省略 `-YoloWeights`。只有上游依赖而没有自训权重时，脚本会报错，应用也不能启动。不要用未知来源的 `.pt`：现有加载器会反序列化完整 PyTorch 模型。

## 3. 配置 MySQL 并启动

复制示例 INI，填写本机专用的 MySQL 用户、密码和初始管理员密码。建议使用项目专用账号，仅对目标库授予创建库/表、迁移所需的 ALTER、查询及写入权限，不用 MySQL root。管理员密码长度为 6–50，使用独立强密码；若密码带 `%`，在 INI 中写成 `%%`（ConfigParser 转义）。管理员配置只用于首次建号，不会重置已有账号密码。

```powershell
Copy-Item -LiteralPath .\attendance_config.example.ini -Destination .\attendance_config.ini
# 先编辑 attendance_config.ini，然后执行：
$env:PYTHONUTF8 = '1'
$env:YOLO_AUTOINSTALL = 'false'
# 只在此启动进程中兼容已经校验且信任的旧版完整 YOLO 权重。
$env:TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD = '1'
try {
    # 在 Qt 加载前导入 MediaPipe，避免 Windows 上的 DLL 初始化冲突。
    & $python -c "import mediapipe, runpy; runpy.run_path('attendance_ui.py', run_name='__main__')"
} finally {
    Remove-Item Env:TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD -ErrorAction SilentlyContinue
}
```

首次启动创建所需表和默认班次。进入「实时签到」后，点齿轮登录管理员页面，新增员工、确认班次并在本机采集人脸模板，再返回签到。仓库不分发人脸照片、模板、密钥、数据库、配置凭证或模型权重。现有数据库升级前先备份；换机不要复制旧 DPAPI 密钥来代替重新登记。

## 4. 验证与边界

- 使用 [`requirements-dev.txt`](requirements-dev.txt) 安装测试包。完整测试需要独立本机 MySQL 测试库：另建 INI，数据库名使用 `attendance_test_` 开头，设置 `ATTENDANCE_TEST_CONFIG` 为该文件路径。测试会清理测试库的数据，禁止指向业务库。
- 旧版 [`ui.py`](ui.py) 使用照片库模式：需自行创建 `face_datasets/` 和 `facenet/images/`，并准备有权使用的登记照片；它不是运行主入口的前置条件。可选训练和研究示例不属于首次部署流程。
- 默认被动活体和可选的主动活体仍不能当作已验证的防作弊保证。
- 第三方代码保留原有许可：[`ultralytics/`](ultralytics/) 使用 AGPL-3.0，FaceNet 上游使用 MIT。对应许可证见 [`ultralytics/LICENSE`](ultralytics/LICENSE) 和 [`facenet/LICENSE`](facenet/LICENSE)。
