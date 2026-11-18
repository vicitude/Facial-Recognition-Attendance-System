# DSH 项目交接文档

## 1. 项目与状态

- 项目目录：`D:\yol\yolov8_facenet`
- 系统是 Windows 本地人脸识别考勤系统，使用 YOLOv8、FaceNet、PyQt5 和 MySQL。
- 工作区存在未提交改动，不要 reset、clean 或覆盖现有改动。
- 原始基线：`882ac1afcd36e7477dc72cda1edf4156517b4bf8`。当前未要求 commit、push 或新建分支。

## 2. 当前目标

客户方案：`D:\SOLO\ddd\GPTwork\客户交付\Windows人脸识别考勤系统_主线与研究支线方案.md`

主线是现有考勤系统。研究支线包括：静默活体、加密人脸特征、多人识别、异常规则和 Windows 地点校验。当前进度是 S1 活体独立验证，尚未接入正式签到。

## 3. 已完成

- 完成动漫风 UI：登录、主窗口、管理页、弹窗、高 DPI 和摄像头水平翻转。
- 实时识别已移到 QThread；忙时丢帧；停止和关闭会等待任务结束。
- S0 已完成测试隔离：`pytest`、`pytest-qt`和独立 MySQL 测试库。
- S1 适配模块：`attendance/liveness_research.py`；入口：`liveness_research.py`。
- 活体模型和源码：`research_assets/Silent-Face-Anti-Spoofing`，上游提交 `b6d5f04ad78778917853b25c778acef6d5626d15`。

## 4. 验证结果

- 全量回归：`79 passed, 1 skipped`。跳过项是 Windows Qt 离屏环境的 QMessageBox 已知问题。
- 服务层 21 项通过；线程专项 3 项通过；S1 活体测试 5 项通过。
- 当前是 CPU 版 PyTorch；摄像头可读取 640x480。
- OpenCV 5.0 已移除 Caffe 导入，上游 RetinaFace 检测器不能直接使用；S1 复用项目 YOLO 人脸框。
- 上游样例已通过离线链路：`image_T1.jpg` 为 `live_candidate`，`image_F1.jpg` 和 `image_F2.jpg` 为 `spoof_candidate`。

## 5. 常用测试

```powershell
$env:ATTENDANCE_TEST_CONFIG = (Join-Path (Get-Location) "attendance_test_config.ini")
$env:QT_QPA_PLATFORM = "offscreen"
& "D:\python\venvs\opencv4\Scripts\python.exe" -m pytest tests -q --tb=short
& "D:\python\venvs\opencv4\Scripts\python.exe" tests/test_liveness_research.py
```

## 6. 未完成

- S0 仍需正式数据备份恢复、真人识别到签到查询现场闭环、异常路径和部署验收。
- S1 仍需真人、打印照片、手机屏幕照片、视频重放分组测试。
- 需要记录真人误拒、攻击误通过、无法判断和耗时，再决定是否进入 S2。
- `live_candidate` 只是模型倾向，不能解释为允许打卡。

## 7. 禁止事项

- 不要直接把活体接入 `attendance/ui_checkin.py`，除非 S1 现场测试已达到确认标准。
- 不要修改 `ui.py`、`recognition.py`、`get_name.py`，除非用户明确授权。
- 不要安装上游老版 `requirements.txt`，不要用测试配置连接或清理正式数据库。
- 不要删除 `research_assets` 或 `attendance_test_config.ini`，不要提交密码、照片、日志、绝对路径和模型二进制。

## 8. 接手顺序

1. 先运行 `git status --short`，确认未提交改动。
2. 阅读 `AGENTS.md`、`BACKLOG.md`、`docs/research/S0-baseline.md` 和本文档。
3. 设置隔离配置后运行全量测试和 S1 测试。
4. 采集四类现场样本并冻结验收标准。
5. 根据数据决定继续优化、进入 S2 或保留为研究结果。

## 9. 交接结论

主线自动化回归稳定，S0 自动化隔离部分完成，S1 模型适配和离线冒烟完成；现场活体数据、正式打卡集成和防伪效果尚未验收。
