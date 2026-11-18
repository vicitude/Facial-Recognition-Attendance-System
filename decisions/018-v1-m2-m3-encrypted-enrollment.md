# 决策 018：M2/M3 三姿态加密登记与模板识别适配层

## 状态
进行中：基础链路已实现，现场验收与完整 Qt 回归待完成。

## 范围
- M2：人员管理新增入口使用三姿态登记对话框；仅填写工号、姓名并手动同意隐私采集。
- M3：FaceNet 128 维向量使用 AES-GCM 加密模板，Windows DPAPI 保护本机密钥；签到识别优先使用加密模板。
- 不修改 `ui.py`、`recognition.py`、`get_name.py` 主体；不保存客户原始登记照片。

## 已落地
- `attendance/face_template_crypto.py`：AES-256-GCM、DPAPI LocalMachine、本机密钥初始化、认证失败拒绝。
- `attendance/face_template.py`：正面/左45°/右45°姿态提示与一脸、尺寸、亮度、清晰度质量门。
- `attendance/models.py` / `attendance/db.py`：`face_templates` 表，Employee 照片和班次可为空。
- `attendance/ui_enrollment.py`：摄像头三姿态采集、失败只重拍当前姿态、模板保存失败回滚员工。
- `attendance/ui_employees.py`：新增按钮打开 EnrollmentDialog。
- `attendance/face_recognition_templates.py`：模板解密、三姿态最小距离匹配、在职员工阈值识别。
- `attendance/ui_checkin.py`：识别线程优先调用加密模板适配层，未命中时保留旧照片路径兼容回退；确认窗口按工号查询员工。

## 验证
- 加密/质量/模板识别/服务层聚焦测试：31 passed。
- 新增模块 py_compile 通过。
- `tests/test_ui_employees.py` 在当前 Windows offscreen 环境曾长时间挂起，不能视为通过。
- 全量测试此前曾触发既有 Qt `access violation`，需单独修复测试环境后再宣称全量绿。

## 未完成
1. 真实摄像头三姿态现场验收。
2. 旧照片回退路径最终移除前的客户数据迁移策略。
3. Qt 对话框和签到线程的稳定集成测试。
4. M3 距离阈值需用客户现场样本标定，当前 `1.0` 仅为研究默认值，不是安全保证。
