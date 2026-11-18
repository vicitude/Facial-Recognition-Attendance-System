# 决策 025：屏幕彩光活体试运行开发中

- 日期：2026-11-18
- 状态：开发中；自动化专项已通过，现场验收未执行。
- 用户已批准按屏幕彩光方案实施：独立窗口四周显示白/红/绿/蓝变化，中央保留较小摄像头预览。
- 彩光开关默认关闭，与旧三次眨眼开关互斥；失败、取消、超时均不进入既有 CheckConfirmDialog，不调用 CheckService。
- 代码边界：新增 `attendance/color_light_controller.py`、`color_light_liveness.py`、`color_light_backend.py`、`ui_color_liveness.py`；仅在 `attendance/ui_checkin.py`、`ui_admins.py`、`ui_main.py` 增加试运行开关及门禁，不修改旧 `ui.py`、`recognition.py`、`get_name.py` 主体，不写数据库。
- 自动化证据：`tests/test_color_light_liveness.py`、`tests/test_color_light_backend.py`、`tests/test_liveness_checkin.py`、`tests/test_ui_admins.py` 合计 26 passed，14 个既有弃用警告；相关模块 py_compile 通过。
- v1.1.0 彩光白光卡顿修复：采集和推理分别移到后台，Qt 只显示最新预览与采集/分析/有效计数；白光和挑战样本分别计数。色序必须经过绘制确认及稳定期；同一检测框实际执行质量、模板、被动门禁，不使用常量模拟成功。取消异步归还相机，归还前不读取或释放。
- v1.1.0 专项证据：彩光、签到、相机生命周期、多人和管理员开关 55 passed，14 个既有弃用警告；相关模块编译通过。彩光用模拟相机、模型输出与离屏 Qt 验证，不代表实机性能或物理颜色响应已通过。
- 未完成：真实摄像头性能、识别框稳定性、模板距离、屏幕反射与环境光照，以及真人/纸照/手机静态照现场各 20 轮。不能据此宣称防作弊能力或正式生产可用。