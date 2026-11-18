# 决策 019：S1.5 主动动作活体研究

## 状态
研究模块已实现，尚未接入正式签到，现场验收待完成。

## 方案
签到前随机选择一个动作：左转头、右转头、点头或眨眼。客户端连续采集短时特征，只在内存处理，不保存视频、截图或动作细节。必须保持单人脸和身份连续；动作完成返回 `passed`，身份变化返回 `failed`，超过帧数返回 `timeout`。

## 已实现
- `attendance/active_liveness.py`：随机指令与会话状态机。
- `attendance/active_liveness_features.py`：yaw/pitch/EAR 特征计算。
- `attendance/active_liveness_rules.py`：特征到动作开始/完成事件的规则。
- `attendance/active_liveness_landmarks.py`：可选 MediaPipe Face Mesh 真实关键点适配器；缺少 mediapipe 时明确报告环境不可用，不自动安装依赖。

## 边界
主动动作可降低纸质照片、静态手机照片和静态屏幕照片的攻击成功率，但不能保证抵御预录视频回放、实时换脸或高质量面具。关键点适配器只提供真实特征，不能替代现场标定和攻击样本验收。当前已获许可在 `D:\python\venvs\opencv4` 安装 `mediapipe==0.10.21`；该版本同时调整了环境中的 NumPy/OpenCV 依赖，完整项目回归需重新核对兼容性。

## 验证
关键点适配器、动作规则、主动状态机和特征测试聚焦回归通过（8 passed）。当前环境检测到 `mediapipe` 未安装，因此未执行真实摄像头关键点推理；未新增依赖，也未接入正式签到。需先确认依赖安装许可，再进行真实摄像头验证。
