# 决策 020：登记采集、识别弹窗与员工删除修复

## 已修复
- 登记点击采集但无当前帧时显示明确状态，不再静默无响应。
- 加密模板识别失败时不再调用旧 `get_name` 照片回退；未知结果统一停止识别后只提示一次。
- EmployeeService.delete 在 UI 二次确认后删除员工的 FaceTemplate 与 CheckRecord 关联记录，再删除员工。
- 更新服务测试契约：确认后的删除允许删除有打卡记录员工。

## 数据边界
旧 `face_datasets` 文件此前已按用户授权删除；本次代码不再使用旧照片识别回退。未执行新的文件删除操作。

## 密钥故障补充
发现 pywin32 当前版本的 `CryptProtectData` 返回值是 `bytes`，旧代码误取 `[1]` 后写入空内容，导致 `data/face_templates.dpapi` 为 0 字节。现已兼容 bytes 与 tuple 两种 pywin32 返回格式，并增加空密文拒绝、flush/fsync 和空文件检测。经用户确认删除原 0 字节文件后，重新生成 296 字节 DPAPI 密文，AES-GCM 128 维模板往返解密成功。

## 验证
M2/M3、模板、服务、动作规则聚焦回归此前 `38 passed`；密钥生成与加密模板 roundtrip 已在实际 Windows 环境成功。完整 Qt 回归和真实摄像头现场验收仍待完成。
