# SPEC-008 三次眨眼考勤试运行
## 0. 元数据
v1.0.0，已批准实施。PO用户/TL与QA当前Agent；代码attendance/ui_liveness.py、liveness_backend.py、ui_checkin.py、ui_main.py；无API路由和数据库迁移。本地门禁 pytest tests/test_liveness_checkin.py，随后既有活体与签到专项；不声明新增CI。Gherkin用pytest替身执行，无HTTP/OpenAPI生成。示例：默认关闭→管理员启用→员工验证。
## 1. 术语
|术语|英文名|类型|定义|代码映射|数据库映射|示例|
|试运行开关|liveness_enabled|bool|仅本次管理员会话，默认False|CheckInTab|无|重启关闭|
|当轮验证框|LivenessDialog|服务|每员工新实例、无共享通过令牌|ui_liveness|无|111111|
|绑定辅助|BoundAuxiliary|服务|用内存解密模板约束当前镜头身份|liveness_backend|无|三姿态最小L2<1.0|
## 2. 场景
```gherkin
Given 活体开启且员工A已识别
When A本轮三次眨眼通过且绑定A模板
Then 才打开A的打卡确认框
Given 验证失败、取消、超时、异常或员工不匹配
When 本轮结束
Then 不打开确认框且不写记录
Given 管理员关闭试运行
When 识别员工
Then 保留原确认流程并显示活体未启用
```
## 3. 接口
`LivenessDialog(employee_id: str, name: str, capture, parent=None)`；`_tick()`每30ms取最新原始帧、submit、snapshot并绘图；`reject()`及`done(result)`停timer并close流水线/采集适配器，等待线程退出；仅真实passed可设置verified=True后accept。总等待90秒包含预热，超时拒绝。无重试按钮，关闭后重新识别创建新轮。
`BoundAuxiliary(vectors)`：复用研究同帧YOLO/MediaPipe/FaceNet/MiniFASNet执行；vectors是三份有限128维float32副本，仅内存；每份提取向量到任一员工模板距离必须有限且<1.0，否则抛ValueError，pipeline失败。固定anchor的0.8检查仍保留。辅助线程不访问数据库。示例：A模板不能接受B向量。
`Landmarks`与`Auxiliary`从独立研究入口抽取至liveness_backend.py；CLI导入这些类保留行为。
## 4. 数据
CheckInTab新增liveness_enabled:bool=False；LivenessDialog.verified:bool=False，仅passed置True。每次从FaceTemplateService加载本员工模板（UI线程），传入BoundAuxiliary，无磁盘写入。摄像头沿用现有capture，不新开设备：暂停父timer，子框30ms GUI timer作为唯一read调用方，发布带monotonic时间及递增序号的原始帧；不新建采集线程，避免物理read阻塞导致采集线程join死锁。子框关闭停止timer并join两个推理线程后恢复父timer；exec异常外围finally仍显式幂等shutdown，关闭失败不恢复父timer。无数据库字段/密文变更。示例：取消后verified仍False。
## 5. 状态和决策
```yaml
initial: pending
pending: {passed: verified, failed: rejected, timeout: rejected, cancel: rejected, error: rejected}
verified: {finish: confirm_same_employee}
rejected: {finish: no_record}
```
识别结果处理前设置pending_dialog防重复；冻结识别flag防队列重入；先等待旧识别线程完全退出再使用模型，父相机timer暂停。开关在相机/识别/队列/弹窗活动时禁止变更。验证后重新读取当前员工在职状态，离职/已删/读取异常均不确认；验证后确认仅当前员工；多人按原顺序每人新验证框；下个人以singleShot调度，不递归；停止/关闭相机清空队列并作废generation。验证取消/失败继续下个人但该人无记录。程序关闭/相机错误不放行。示例：A通过不能为下一位B免验证。
### Properties
P-LCI-01：∀未verified结果，确认框创建数=0，CheckService调用数=0；PT-LCI-01参数化失败结果。P-LCI-02：∀员工队列，每次验证参数员工=随后确认员工；CT-LCI-02。P-LCI-03：∀错误向量/阈值边界，绑定不得通过；UT-LCI-03。
## 6. 错误
LIVENESS_REJECTED：失败/取消不写库；LIVENESS_UNAVAILABLE：初始化/模板/设备异常不回退；UI提示重启识别，不打印向量、图像、密钥或异常具体秘密。HTTP不适用。示例：模型缺失显示无法完成活体，不打开确认。
## 7. 测试
PT-LCI-01覆盖开关/拒绝/异常/当轮verified；CT-LCI-02覆盖多人身份参数及新轮；UT-LCI-03覆盖绑定有限向量与距离边界；CT-LCI-04覆盖对话框passed标记/取消/资源关闭/超时，均在tests/test_liveness_checkin.py；实现本轮自动化。设备现场由用户后续真人/纸照/手机静态照各20轮，未执行不得写已验收。
## 8. 非功能
UI轮询30ms、总等待90秒；模型后台两个线程；退出join而非强杀，模型卡住会延长关闭等待，不允许释放仍使用资源。测试替身验证关闭调用；性能仅以现场为准。零新依赖，零原图/向量持久化；管理员账户菜单复选Action，文案三次眨眼活体（试运行），默认False、不持久化；实时页badge可见开关。示例：开启缺依赖→拒绝而非跳过。
### v1.0.1 管理员页胶囊入口（覆盖账户菜单入口）
AdminsTab新增 `liveness_requested = QtCore.pyqtSignal(bool)`、`btn_liveness: QPushButton`，位于管理员页表格上方独立设置卡，checkable=True/default=False，圆角22px/min-height24px，文案“活体试运行：关闭”或“活体试运行：开启”，说明“三次眨眼验证；切换前请关闭相机，重启后默认关闭。”。`set_liveness_state(self, enabled: bool) -> None` 阻断按钮信号后同步checked和文字，不发请求；clicked(bool)发liveness_requested。MainWindow连接该信号至现有`_on_liveness_toggled(self, enabled: bool) -> None`，统一调用CheckInTab.set_liveness_enabled，成功/拒绝后均将真实状态同步按钮与兼容action_liveness。旧action_liveness保留属性但不加入账户菜单，避免双入口；不改既有拒切条件和默认关闭、不持久化语义。拒绝时状态栏明确提示关闭相机，按钮回滚。
CT-LCI-05（tests/test_liveness_checkin.py）：参数化requested/current/busy组合，真实AdminsTab按钮click经MainWindow槽→真实CheckInTab，断言文字/checked/业务bool一致；验证双击开关开→关、忙时拒绝回滚及程序同步不发请求。P-LCI-04：∀忙状态与请求，实际开关不变且按钮checked=实际值，回链本段与CT-LCI-05；本地门禁pytest tests/test_liveness_checkin.py tests/test_ui_admins.py。不新增依赖/数据库字段/HTTP接口/错误码。例：相机开且当前关闭→点击仍关闭，并显示先关闭相机。

## 9. 约束
不改ui.py/recognition.py/get_name.py主体、不动班次地点业务、不自动安装依赖、不执行正式库测试、不提交。试运行不是防作弊保证，视频/挖眼照片不在承诺范围。版本历史由Git生成；本次未提交，不虚构commit。
