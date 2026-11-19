# SPEC-007：三动作融合活体验证

## 0. 元数据
状态：开发中；版本：v1.4.0。PO：用户；TL/QA：当前实施代理。
关联代码：attendance/fused_liveness.py、fused_liveness_research.py；测试：tests/test_fused_liveness.py；数据库迁移：无；HTTP API：无（本地 Python 契约）。
本规范场景映射 pytest；不声称存在 OpenAPI 生成或 Gherkin 执行器。门禁：设置隔离测试配置后执行 `python -m pytest tests/test_fused_liveness.py -q`，全部通过；现场测试不能用模拟测试替代。示例：静态照片即使 passive=live_candidate，动作未完成也不能通过。

## 1. 术语
|术语|英文名|类型|定义|代码映射|数据库|示例|
|---|---|---|---|---|---|---|
|挑战|challenge|值对象|三个不重复动作|FusionSession.actions|无|blink,turn_left,nod|
|动作|action|枚举|blink/turn_left/turn_right/nod|既有 Action|无|blink|
|阶段|phase|枚举|baseline/outbound/return|FusionSession.phase|无|baseline|
|结果|status|枚举|pending/passed/failed/timeout|FusionResult.status|无|failed|
|特征|feature|值对象|face_count/yaw_deg/pitch_deg/ear|update 输入字典|无|ear=0.30|
|身份|identity_distance|值对象|当前128维向量与本轮起始向量L2距离，不是关键点标记|update 参数|无|0.2|

## 2. 验收场景
```gherkin
Feature: 三动作融合
 Scenario: 高被动分数不能放行静态人像
  Given 三个挑战动作尚未完成
  When 连续输入相同正面特征和真人候选被动状态
  Then 结果不能是 passed
 Scenario: 三动作全部通过
  Given 单人、质量合格、身份距离不超过0.8
  When 按本轮顺序完成基准、目标、回中且最近7个被动结果全为live_candidate
  Then 返回 passed
 Scenario: 中断或身份变化
  Given 挑战执行中
  When 出现多脸、无脸、低质量、无效数值或身份距离超过0.8
  Then 本轮 failed 且不能继续复用
```
超时、跳帧、单帧跳角、眨眼必须先睁眼测试均映射 §7。

## 3. 本地接口契约
`choose_actions(rng=None) -> tuple[Action, ...]`：必含 BLINK，从 TURN_LEFT/TURN_RIGHT/NOD 不放回抽两个，再打乱顺序；默认 secrets.SystemRandom，rng 仅用于可复现测试。
`FusionSession(actions=None)`：actions 为 None 时调用 choose_actions；传入时必须恰好三个不同 Action 且含 BLINK，否则 ValueError。
`FusionSession.update(feature: dict, *, timestamp: float, quality_ok: bool, passive_status: str, identity_distance: float) -> FusionResult`。
`FusionResult` frozen dataclass：status:str、action:str（当前动作的枚举值）、phase:str、completed:int、reason:str。例：FusionResult('pending','blink','baseline',0,'')。
时间由调用方 monotonic 提供。每次代表一张新摄像头帧，不重复提交同一帧。terminal 状态重复调用返回原结果。失败重试必须创建新会话、随机新挑战、重建身份基准。不输出生产放行凭据。

## 4. 数据字段与校验
FusionSession 保留：actions tuple、index int=0、phase str=baseline、count int=0、baseline_yaw/pitch float=0、baseline_samples list（上限3）、last_timestamp/start_timestamp/action_timestamp/last_feature 为 None（首帧前）、passive deque(maxlen=7)、terminal 为 None（终态前）。内存状态不存库。
输入 feature 必须有 face_count=1、有限 yaw_deg/pitch_deg/ear，EAR在[0,1]；timestamp有限，严格递增，相邻帧间隔<=0.5秒；identity_distance有限且在[0,0.8]。quality_ok 必须为 True。passive_status 为 live_candidate/spoof_candidate/low_confidence/inconclusive/low_quality/no_face/multiple_faces；未知状态拒绝。其他键忽略，不接受 identity_continuous=True 作为身份依据。JSON等价示例：{"face_count":1,"yaw_deg":0,"pitch_deg":45,"ear":0.3}。

### 适配器补充契约（审查修订）
MediaPipe返回 face_box=(xmin,ymin,xmax,ymax)，由全部关键点像素坐标范围得到。新增 `adapt_feature(feature: dict, box) -> dict` 于 fused_liveness.py：要求框有限且面积>0，两框IoU>=0.3，否则 ValueError；将原始图像yaw取负变为人体方向yaw，保留其他特征。CLI在不一致时输入face_count=0拒绝本轮。UT-FUS-05覆盖框错位、原始关键点左右方向。
正面研究约束：基准必须abs(yaw)<=8且20<=pitch<=70；否则清空采样，保持baseline（仍计时）。回中也必须满足此范围；这些二维估计不是物理角度，必须现场校验。UT-FUS-06覆盖偏头不能建立基准。

## 5. 决策与状态迁移
研究阈值不是生产标定值：每动作10秒，总计35秒；每帧yaw/pitch跳变>12度或EAR跳变>0.18拒绝；两角绝对值<=90；每动作需连续3帧基准（EAR>=0.28，基准3帧每轴极差<=4度），取均值作相对零点；点头用相对pitch而非既有绝对pitch。
- baseline→outbound：完成3帧基准；之后仍为睁眼正面不累计目标。
- outbound→return：左yaw相对<=-20、右>=20、点头pitch相对>=20，连续3帧达标；眨眼EAR<=0.21连续2帧。非目标帧重置目标计数。
- return→下一动作baseline：两轴相对基准绝对值<=8且EAR>=0.28连续3帧，并距该动作开始>=0.6秒。非回中帧重置计数。清空基准样本，不重置全局被动窗口/时间。
- 三动作完成后：仅当最近7帧全为live_candidate才passed，否则failed(passive_not_confirmed)。
- 任一帧spoof_candidate立即failed(passive_spoof)；low_confidence/inconclusive只作为未确认，不作真人；低质量/无脸/多脸立即failed。
- 任一校验失败→failed；超时→timeout；所有终态不可逆。每个输入先校验，再判时限，再更新轨迹与动作。
边界：时间恰好10/35秒不超时，间隔恰好0.5不拒绝；动作阈值端点包含。

### Properties
|性质|回链|量化式|生成器|自动化|
|---|---|---|---|---|
|P-FUS-01|§5终态|∀ terminal,后续任意输入⇒结果不变|三种终态×100输入|PT-FUS-01|
|P-FUS-02|§5三动作|∀静止基准流⇒status≠passed|动作排列×静止帧|PT-FUS-02|
|P-FUS-03|§3随机|∀生成挑战⇒len=3且无重复且含blink|100随机种子|PT-FUS-03|

## 6. 错误与日志
无HTTP错误码。reason枚举：invalid_feature/need_one_face/poor_quality/identity_changed/invalid_time/frame_gap/trajectory_jump/passive_spoof/passive_not_confirmed/action_timeout/session_timeout/invalid_passive。成功reason=completed；pending reason为空。
后端缺失、模型加载/推理失败：CLI报环境错误并退出，不跳过检测。CLI不记录图像、视频、向量、关键点轨迹、密钥或精确身份；只输出研究状态、动作进度、失败原因、攻击类别和计数。示例：failed identity_changed。

## 7. 测试矩阵
|来源|需求|类型|测试ID|状态|
|---|---|---|---|---|
|§3生成|三动作|属性|PT-FUS-03|已自动化|
|§5终态|终态不可逆|属性|PT-FUS-01|已自动化|
|§5静止|照片不因高分放行|属性|PT-FUS-02|已自动化|
|§2成功|三动作融合|单元|UT-FUS-01|已自动化|
|§4校验|身份/质量/多脸/非有限|单元|UT-FUS-02|已自动化|
|§5轨迹|跳角/间隔/超时|单元|UT-FUS-03|已自动化|
|§5被动|spoof与未确认拒绝|单元|UT-FUS-04|已自动化|
|§4适配|方向与框关联|单元|UT-FUS-05|已自动化|
|§4适配|偏头不建基准|单元|UT-FUS-06|已自动化|
|§8入口|R重试清空anchor、终态统计一次、错位拒绝、异常释放|契约|CT-FUS-01|已自动化|
|§8现场|四类实机|验收|TC-FUS-01|未自动化（交付前现场执行，依赖用户设备与样本）|

## 8. 非功能与现场入口
独立 `fused_liveness_research.py`：Windows摄像头、MediaPipe max_faces=2、YOLO检测、FaceNet身份连续性、MiniFASNet、assess_quality；不修改签到放行入口。使用原始非镜像帧推理，镜像仅预览；左右动作以人体方向显示并现场校验符号。屏幕使用Pillow绘制中文研究状态、当前指令、进度和原因：baseline提示正视摄像头并睁眼；outbound显示当前中文动作；return提示回正并睁眼；终态优先显示通过/失败/超时和中文原因，不再提示继续动作。新增 attendance/liveness_overlay.py，preview_lines(result) -> list[str]、draw_chinese_overlay(frame, result) 返回新BGR图像，原帧不修改；使用Windows Fonts目录微软雅黑或黑体TrueType字体，缓存字体，缺字体明确报错而非显示乱码；字号按画面宽度缩放，中文长行自动折行，深色底提高可读性。UT-FUS-07覆盖阶段指令、终态、中文原因和实际绘制。Esc退出，R重开（重新随机并清空基准）。失败不自动重试；不使用预录文件冒充实时帧。
性能：推理期间不丢弃质量/身份判定；推理间隔>0.5秒拒绝并显示frame_gap，目标设备实测后才能调参；资源 finally 释放。摄像头编号仅CLI参数，不写配置。验证：模拟门禁+人工观察CPU/帧间隔+退出重复启动。
现场四类：真人、纸质照片、手机静态照片、手机视频回放，每类至少20轮，光照/距离至少两种组合，每轮新随机挑战；记录有效尝试、通过、拒绝、不可用原因。研究验收候选标准：真人>=18/20通过，三类攻击各0/20通过；小样本0次通过不代表零风险，任一攻击通过不得接正式签到。移动纸张/移动屏幕/已有眨眼转头视频必须覆盖。采集原图和视频需另行同意，本版本默认不留存。

### 异步性能修订 v1.1.0
新增 attendance/liveness_pipeline.py：LatestFrameCamera(capture)后台读取，仅保存最新(frame_id,timestamp,frame)，close()停止并释放；AsyncFusionPipeline(landmarks, auxiliary, quality)后台动作线程与单一辅助线程，start/reset/submit(frame_id,timestamp,frame)/snapshot/close。submit只保存最新帧，绝不积压；每张帧最多处理一次；输入帧时间使用monotonic采集时刻。snapshot返回result、metrics、warming、generation。reset递增generation，清空状态/身份/待处理数据；旧任务结果即使完成也不计入新挑战。
辅助回调 auxiliary(frame, anchor) -> dict：同帧YOLO单脸、质量、关键点空间关联、FaceNet身份距离、MiniFASNet状态；返回feature、quality_ok、identity_distance、passive_status、anchor、timings_ms。anchor只在本轮第一次质量合格时建立，后续保持。仅一个辅助任务运行，取最新帧；辅助工作间隔至少0.4秒。高频回调landmarks.detect与quality(frame,face_box)逐帧检查动作、质量；辅助结果不替代当前帧关键点。预览主线程不执行模型。
先完成首份辅助与一次关键点推理预热再创建会话、开始计时；预热后的新采集帧才进入挑战。采样间隔>0.5秒仍失败；trajectory_jump/frame_gap在画面解释为无法确认轨迹/性能不足，不断言作弊。
FusionSession(actions=None, defer_auxiliary=False)：默认原有同步行为。defer_auxiliary=True时三个动作结束进入verification/pending；动作通道不使用历史被动窗口放行。新增 finish_auxiliary(approved: bool, reason='passive_not_confirmed') -> FusionResult，仅verification可调用，approved=True终态passed，否则failed；其他阶段调用ValueError。终态不可逆。
异步最终放行：连续七份不同源帧的live_candidate辅助结果（保留原七次被动确认要求，不以两份替代）、每份身份距离<=0.8且质量合格；最后一份源采集时间>=动作完成时间、结果年龄<=2秒；任一辅助spoof/身份变化/低质量/多脸直接拒绝。unknown/low_confidence等待新结果，verification最多5秒，超过拒绝；辅助源帧年龄>2秒不得采信，显示辅助等待/过期；动作期间无新鲜辅助最长2秒则拒绝auxiliary_stale。预热仅用于准备，不计通过次数与动作时间；reset重新随机和建身份基准。
新增中文性能显示：动作FPS、关键点耗时、YOLO/FaceNet/被动耗时、辅助年龄、预热或等待辅助。新原因auxiliary_stale/verification_timeout/pipeline_error有中文说明。异常失败关闭通道，不降级放行；close等待工作线程结束并释放摄像头/关键点资源。采集设备read阻塞或本机模型不可中断不保证立即退出，不强杀线程。
补充约束：动作结果提交年龄>0.5秒拒绝frame_gap；verification持续检查单脸、质量、身份及时间，但不再累计动作，更新时间戳保持连续。每个任务异常在所属generation内拒绝，旧generation异常丢弃且线程继续等待；start重复调用抛RuntimeError。动作质量框裁剪至图像边界后评估。
P-FUS-04（回链异步门禁/CT-FUS-02）：∀generation不匹配或辅助源年龄>2秒的结果，不可促成passed；穷举旧正常/旧异常/过期/七份新鲜后置结果的mock测试作为自动化oracle。
测试CT-FUS-02：最新帧覆盖不积压、generation隔离、终态等待后置辅助、过期辅助拒绝、线程异常不放行；UT-FUS-08验证defer_auxiliary默认兼容和verification门禁。mock不加载真实模型。真实速度和四类验收仍未执行。

### 身份基准与诊断修订 v1.1.1
覆盖v1.1.0首张合格即建立anchor的规则。辅助预热后进入身份准备：连续3份不同源帧，单脸、质量合格、源年龄<=2秒、abs(yaw_deg)<=8、pitch_deg在[20,70]、ear>=0.28；三份yaw/pitch极差分别<=4；采用第三份的128维向量作为固定anchor，不平均、不滚动更新。任一姿态不合格清空准备窗口；姿态超极差保留本份为新窗口首份。准备阶段不创建动作session、不开始挑战时钟，不累计七份live。辅助spoof/质量/多脸仍拒绝；首次准备期间身份距离不作换人判定（无基准）。所有接受帧均须有效128维有限向量。reset清空样本和全部诊断。新增StableIdentityBaseline.observe(feature:dict, vector)->bool / reset()；samples只保留最多3个yaw/pitch二元组；vector不持久化。
辅助回调返回增加identity_vector（本帧128维向量）；没有anchor时identity_distance为None。辅助提交显示identity_distance（None显示未建立）、identity_threshold=0.8、baseline_samples=0..3、baseline_yaw/baseline_pitch（完成前None）、identity_yaw/identity_pitch/identity_ear。固定anchor建立后的identity_distance>0.8或非有限仍立即拒绝，不放宽阈值。动作线程只有anchor建立且aux有效后可启动。身份准备中文提示“正视、睁眼、保持稳定，身份基准 N/3”。每份接受的辅助采样产生内存有界pending_diagnostics最多32项，snapshot消费清空，CLI打印仅数值JSON（category/generation/metrics/research_only），不含图像、向量或anchor。
终态诊断：terminal_metrics首次终态时冻结；snapshot终态返回冻结值，不再随墙钟增长；失败辅助源年龄以触发失败本份timestamp计算，非上一份通过帧。动作update和辅助finish产生终态也冻结。reset后允许重新计时。中文标注“本轮结束时指标（已冻结）”，展示身份距离/阈值、基准与本帧yaw/pitch/EAR；诊断改变不改变放行语义。
CT-FUS-03：3份正视稳定才建基准；偏头/闭眼不建；极差超限重建；终态时间前移不改变冻结指标；身份>0.8诊断可见且拒绝；reset清空诊断。P-FUS-05：∀准备不足3份或不符合姿态稳定条件，不可创建动作挑战；CT-FUS-03穷举边界，既有56项回归继续执行。无设备性能或真人通过声明。

### 准备与眼部校准修订 v1.2.0（覆盖v1.1.1固定EAR准备规则）
本修订仅研究入口，保留身份距离0.8、三随机动作、七份辅助、源年龄和所有拒绝规则。FusionSession(actions=None, defer_auxiliary=False, eye_thresholds=None)：None保留旧0.21/0.28；传入(closed, opened)须有限且0<closed<opened<=1，否则ValueError。本轮动作baseline/return使用opened，blink使用closed；阈值固定至reset，绝不随动作滚动。
新增attendance/liveness_preparation.py EyePreparation()，update(feature:dict, *, timestamp:float, quality_ok:bool)->bool、reset()。内存字段：stage='open'|'close'|'reopen'|'ready'，samples列表最多60个(timestamp,yaw,pitch,ear)，open_ear/closed_threshold/open_threshold/calibrated_at默认None，ready=False，started/last_timestamp=None，reason=''，failed=False。metrics()->dict返回preparation_stage、preparation_samples、preparation_ready、preparation_reason、open_ear、closed_threshold、open_threshold，不包含轨迹或向量。每轮开始显示明确校准指令：正视自然睁眼→保持正视闭眼→重新睁眼。校准不是活体挑战完成次数。
输入须单脸、质量True、有限timestamp严格递增、有限abs(yaw)<=8、pitch在[20,70]、EAR在(0,1]。失效帧清空尚未完成校准并提示need_one_face/poor_quality/center_face/invalid_feature；完成校准后的失效帧仅撤销ready、清空稳定窗口，不重估阈值。间隔>0.5秒清空整个校准但保留起始时钟。准备从首个update开始20秒，未校准超时failed=True reason=calibration_timeout，经pipeline拒绝本轮；终态只能R重置。时间无效failed=True reason=invalid_time。
open阶段：EAR限定[0.12,0.60]，至少15个连续有效帧且首尾>=0.6秒，yaw/pitch极差各<=4、EAR极差<=0.04；极差超限以本份重开窗口。取EAR中位数open_ear，进入close。此阶段依据用户明确睁眼指令采集，不能仅凭固定数值声称已睁眼。
close阶段：EAR<=open_ear*0.65且open_ear-EAR>=0.05，至少3个连续帧且首尾>=0.08秒。取闭眼中位数c；closed_threshold=c+0.25*(open_ear-c)，open_threshold=c+0.75*(open_ear-c)，进入reopen。其他帧重置本阶段计数而不更新open_ear。
reopen阶段：EAR>=open_threshold至少5帧且首尾>=0.15秒，yaw/pitch极差各<=4，完成校准，calibrated_at为本帧采集时间，进入ready。未达标清本阶段窗口。ready阶段持续正视且EAR>=open_threshold，至少15帧且首尾>=0.6秒姿态极差<=4才preparation_ready=True；失稳立即撤销并以当前帧重建，不更新阈值。样本窗口有界最多60；示例open=.25、closed=.12，closed_threshold=.1525、open_threshold=.2175，不要求达到.28。
动作线程在未创建session前处理该准备状态，年龄>0.5秒的准备帧不采信并清校准；metrics逐帧更新，不等慢通道。辅助仍检查单脸/质量/被动，不因校准豁免；只有preparation_ready=True且辅助源timestamp>=calibrated_at才允许三份身份准备，StableIdentityBaseline.observe(feature,vector,min_open_ear=0.28)在研究pipeline传open_threshold；保留三份姿态极差限制和第三份固定anchor。准备ready失效时清尚未完成的身份样本。anchor建好且最新准备仍ready才创建带本轮eye_thresholds的session；此后不继续校准。reset清全部校准、身份和诊断；旧generation结果丢弃。
画面预热时替换笼统准备行：open“准备1/3：正视摄像头，自然睁眼保持片刻”；close“准备2/3：保持正视，请闭眼并保持片刻”；reopen“准备3/3：请重新睁眼并保持片刻”；ready显示“眼部校准完成，请正视睁眼，等待身份基准 N/3”。额外显示preparation_reason中文原因及校准EAR/闭眼与睁眼阈值。calibration_timeout中文“眼部校准超时，按R重新开始”；终态不显示继续校准。
CT-FUS-04覆盖低EAR完整校准、静止/闭眼不足不启动、质量/多脸/失稳/间隔撤销、20秒超时、无效时间、reset隔离、辅助源早于校准不建anchor、动作阈值衔接；UT-FUS-09覆盖中文阶段实际绘制和阈值显示。P-FUS-06：∀未完成open→close→reopen且稳定不足的准备流，不可创建session；CT-FUS-04穷举阶段与边界作为oracle。P-FUS-05中准备不充分含本修订校准门禁；CT-FUS-03更新注入已校准状态，不能绕过真实入口。本地门禁：隔离配置下运行tests/test_liveness_preparation.py及既有活体测试全部通过；不声称已配CI、真人通过或攻击验收。所有新状态只在内存，无新依赖、数据库或旧识别入口改动。

### 分阶段身份复核 v1.3.0（覆盖异步通道单次距离超限即失败规则）
仅研究异步入口启用。固定anchor与0.8阈值不变，不滚动更新。动作baseline/outbound/return期间有限非负距离超过0.8仅诊断，不累计身份确认；None/NaN/Inf/负距离仍identity_changed。单脸、质量、被动spoof、框IoU、逐帧轨迹/时间门禁始终保留；这些只能证明轨迹关联，不保证同一身份。
FusionSession新增参数identity_checkpoints=False；默认行为兼容旧同步测试。True且defer_auxiliary=True时，每动作回中完成后index加1，phase='identity_check'，不立即开始下一动作。新增resume_identity()->FusionResult，仅identity_check允许调用，否则ValueError；index<3进入baseline并清样本/count、action_timestamp置last_timestamp，index=3进入verification。辅助resume后pipeline将session.action_timestamp与ready_at置为复核提交时monotonic，下一动作只接收此后采集帧；动作线程开始detect前记录(session对象,index,phase)，提交时若已变则丢弃该在飞结果，不判失败。CT-FUS-05使用Event屏障覆盖复核推进期间在飞旧动作结果。identity_check逐帧继续输入/严格递增时间/0.5秒间隔/35秒总时限/跳变检查但不累计动作，不使用上一动作10秒时限；辅助被动状态校验必须先于resume_identity，spoof/非法状态不得推进阶段；pipeline进入该阶段记identity_check_at=monotonic()，5秒内无复核成功则identity_check_timeout，终态不可逆。
AsyncFusionPipeline新增identity_samples=[]（最多3个yaw/pitch）、identity_failures=0、identity_check_at=None，reset全清；进入每次identity_check重置这些字段及live_count。仅采集时间>=identity_check_at的辅助结果可用于本次复核。正视定义：abs(raw yaw)<=8、abs(raw yaw-baseline_yaw)<=8、abs(pitch-baseline_pitch)<=8、20<=pitch<=70、EAR>=本轮open_threshold（未校准替身用0.28），数值须有限。非正视清连续身份样本及超限计数；正视且距离>0.8清成功样本，连续三份正视超限才identity_changed；正视且距离<=0.8清超限计数并累计三份不同源帧，yaw/pitch极差各<=4，否则本份重开窗口。三份通过才resume_identity；不使用动作期间历史帧。等待期间单次超限不放行也不立即失败。
verification仍须最新正视且身份<=0.8，非正视/超限重置live_count，连续三份正视超限拒绝；每份计入七次live必须正视且身份合格。最后源时间>=completed_at，5秒验证时限与2秒新鲜度不变。无session但已有anchor时继续原严格身份检查。例：转头距离0.824保持动作中；回正三份0.3/0.4/0.35后下一动作；换人回正0.9/0.95/1.0拒绝，不更新anchor。
metrics增加identity_check_state='deferred'|'waiting'|'confirmed'，identity_check_samples=0..3、identity_failures=0..3；仅数值诊断。画面identity_check提示“动作完成，请回正睁眼，等待身份复核”，明确动作中距离仅诊断、等待复核N/3。新reason identity_check_timeout中文提示回正复核超时。
P-FUS-07：∀动作中超限但有限非负距离，不单独触发身份失败；∀未取得每动作三份动作后正视合格身份结果，不进入下一动作或passed；∀连续三份正视超限必拒绝。自动化PT-FUS-07/CT-FUS-05覆盖左右转头/点头、单异常恢复、换人/持续超限、旧源、失稳、NaN、reset、被动spoof与最终门禁。门禁为隔离配置下活体专项pytest，不新增依赖/CI/数据库，真实换人与四类现场验收另行执行，模拟不能证明防作弊。

### 三次眨眼修订 v1.4.0（当前默认，覆盖前文随机默认挑战）
用户确认仅针对完整纸质照片与手机静态照片开展本阶段研究。`choose_actions(rng=None) -> tuple[Action, ...]` 保留签名但不使用rng，固定返回 `(Action.BLINK, Action.BLINK, Action.BLINK)`；`FusionSession(actions=None, defer_auxiliary=False, eye_thresholds=None, identity_checkpoints=False)` 默认使用该序列。显式actions仅接受三次BLINK，或历史三个互异且包含BLINK的Action序列；其他情况ValueError，不新增字段、枚举或依赖。历史显式混合动作仅用于兼容回归，不在默认摄像头入口抽取。
校准open→close→reopen不计次数；校准和三份身份基准后才创建session。每次眨眼独立baseline（3帧稳定睁眼）→outbound（EAR<=本轮closed连续2帧）→return（EAR>=opened且回正连续3帧、该次开始>=0.6秒）才index加1。持续闭眼只能停留return，不能多计；单帧闭眼不能计数；每次完成仍须三份新源正视身份复核才开始下一次；第三次之后仍需原七份辅助门禁。阈值、10/35秒、身份0.8、准备20秒、复核/最终5秒、单脸/质量/轨迹/源新鲜度/reset/终态不变。
`preview_lines`默认blink结果显示“已完成 N/3 次眨眼”“第 N/3 次眨眼”，准备显示“三次眨眼尚未开始”，不提示随机挑战或要求转头点头；完成和等待语句使用“三次眨眼”。显式历史非blink动作仍显示其动作指令。R清校准/身份/次数重开三次眨眼，CLI参数不变。
P-FUS-08（回链本段）：∀持续静止或持续闭眼流，不能完成三次眨眼；∀已计一次眨眼，未经过新baseline和新闭眼/睁眼周期不能增加下一次。PT-FUS-08/CT-FUS-06在tests/test_fused_liveness.py自动化：固定默认、允许/拒绝序列、持续闭眼/单帧/静止、三次完成并仍等待身份/辅助、中文提示及reset；隔离配置下现有活体12文件全部通过作为本地门禁，无新增CI。
本阶段现场真人/完整纸照/手机静态照每类20轮、至少两种光照距离；候选标准真人>=18/20，攻击各0/20。移动/弯折造成眼部误判须记录；手机视频可记录但不在本阶段防护承诺中，视频/挖眼照片/深伪不保证阻断。旧四类现场记录保留为历史目标，不得声称已验收；减少动作不是安全效果证据。例：校准闭眼后次数0，第一次挑战闭眼保持2秒仍0，重新睁眼满足return后次数1。

## 9. 假设与约束
现有依赖已装；不新增依赖/不改数据库/不改ui.py、recognition.py、get_name.py主体；不commit/push/reset/clean。用户批准组合方案不等于批准未经现场验收的正式部署。RGB挑战仍不能保证抵御视频、深伪、面具、虚拟摄像头；身份距离检查不能证明真实在场。
Git变更日志由提交记录生成；当前不创建提交，因此无提交日志条目。开发日期2026-11-16不是验收日期。
