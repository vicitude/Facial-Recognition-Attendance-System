# SPEC-010：屏幕彩光响应辅助活体

## 0. 元数据

开发中 · v1.1.0 · PO 用户 / TL、QA DSH。关联：`attendance/color_light_liveness.py`、`color_light_backend.py`、`color_liveness_worker.py`、`ui_color_liveness.py`、`ui_checkin.py`（均在 `attendance/`）。无 HTTP 端点和数据库迁移。门禁：在项目根用隔离测试配置执行 `python -m pytest tests/test_color_light_liveness.py tests/test_color_light_backend.py tests/test_color_liveness_worker.py tests/test_color_liveness_ui.py -q`；不修改旧三入口。Gherkin 场景由 §7 的 pytest 用例验证，独立 YAML 描述本地状态，无网络服务。

## 1. 术语

| 术语 | 英文名 | 类型 | 定义 | 代码映射 | DB | 示例 |
|---|---|---|---|---|---|---|
| 实际绘制代次 | epoch | 整数 | 窗口同步重绘后确认的颜色代次 | worker | 无 | white→red 为不同代次 |
| 颜色 | color | 枚举 | off/white/red/green/blue | ScreenColorController | 无 | white |
| 会话结果 | ColorResult | 值对象 | 数值计数与状态 | frozen dataclass | 无 | baseline 尚未满足 |
| 相机借用 | camera ownership | 生命周期 | 子窗口后台为唯一读取方，父窗口为唯一释放方 | CheckInTab / ColorLivenessWorker | 无 | 取消后等待在途读取返回 |

## 2. 验收场景

```gherkin
Feature: 彩光预览与采样隔离
  Scenario: 模型尚未完成
    Given 彩光窗口已经重绘为白色
    When 后台分析阻塞但摄像头仍在出帧
    Then 预览和采集计数继续更新
    And 有效白光计数只反映已通过门禁的帧
  Scenario: 取消发生在相机读取中
    Given 后台读取未返回
    When 用户取消彩光窗口
    Then 彩光窗口立即拒绝并关闭
    And 父窗口不读取或释放该相机直到后台退出
```

## 3. 本地接口

[本地对象契约](openapi.yaml)没有 HTTP 路径。`ColorLivenessSession(employee_id: str, config: ColorLightConfig, auxiliary=None)`；`start(timestamp: float) -> ColorResult`；`submit(frame_id: int, timestamp: float, frame, light_state: str) -> ColorResult`（`frame` 为单帧事实字典）；`snapshot() -> ColorResult`；`cancel(reason: str = 'cancel') -> ColorResult`；`close() -> None`。`ColorLightBackend(templates, *, detect=None, embed=None, passive=None, quality=None)`，`__call__(frame) -> dict`；四个可选参数为 None 时用现有 YOLO、FaceNet、MiniFASNet 和 assess_quality，否则使用测试替身。`ColorLivenessWorker(employee_id, capture, templates, *, config=None, backend_factory=ColorLightBackend)`；`start() -> None`、`stop() -> bool`（仅请求停止并报告是否已退出，不 join）、`stopped() -> bool`、`acknowledge_color(color: str) -> bool`、`snapshot() -> dict`。`ColorLivenessDialog(employee_id: str, name: str, capture, parent=None)`；`_shutdown() -> bool`。`ScreenColorController.set_color(color: str) -> None`、`current_color() -> str`，只用于本窗口。

## 4. 数据

- `ColorLightConfig`：`enabled=False, sequence=('red','green','blue'), color_duration_ms=2000, settle_ms=80, cycles=1, baseline_frames=3, sample_frames_per_color=3, min_color_ratio=0.85, max_session_ms=25000, min_fps=8.0, max_frame_age_ms=250, identity_threshold=0.8, chroma_delta_threshold=0.08, motion_threshold=0.015`。`min_color_ratio` 是合格颜色帧比例，范围 `[0.50, 1.00]`，步进 `0.05`，默认 `0.85`；UI 用 `QDoubleSpinBox` 设置，步进0.05，显示百分比，创建会话时传入，不持久化。RGB 序列须为三色排列；持色须大于稳定期且为 80–2000 ms；稳定期、总时限、帧龄分别为 30–200、5000–30000、50–500 ms；轮数 1–2；白光帧数及每色最低样本数 1–10；帧率 5–15；三个阈值各 0–1，违规抛 ValueError。worker 省略配置时启用试运行配置。内部整数 `_color_samples`、`_color_hits`、`_color_motion_skips` 从 0 起，每色清零，分别累计该色有效样本、色差达标样本和位移丢弃帧；不保存样本列表。
- `ColorResult(status, phase, color, cycle, accepted_samples, reason, metrics)`：`status` 为 pending/passed/rejected/timeout/error，`phase` 见 [YAML](color_liveness_states.yaml)；`color=None` 仅尚未开始，`cycle` 从 0 开始；`accepted_samples` 只统计彩光样本；`metrics.baseline_samples` 独立计数，`metrics.baseline_luma` 是白光归一平均亮度，`{red,green,blue}_delta` 为最近对应色响应；无诊断时键不存在。`reason=None` 表示没有错误或等待原因；快照复制指标字典。[JSON Schema](color_result.schema.json)约束结构。
- 单帧事实字段：`face_count: int`、`quality_ok: bool`、`identity_vector`（有限 128 维 float32；无有效单脸或质量不合格为 None）、`identity_distance`（对应模板最小 L2，同条件可为 None）、`passive_status: str`（未推理为 `not_evaluated`）、`mean_rgb`（RGB 0–255 三元组，无可用 ROI 为三个 0）、`motion_score: float`（连续有效框左上、右下坐标按画幅分别归一后的最大绝对差；首框为 0）、`timings_ms` 字典含 `color_stats_ms`。不保存原图、ROI、模板、向量或密钥。
- worker 快照 `frame`（未出帧时 None；其余只读 BGR 副本引用）、`result`（ColorResult）、`error`（无异常时 None）、`frame_count`、`processed_count`、`valid_count`（相机成功帧、完成分析帧、真正满足门禁且参与会话的帧）、`desired_color`（白光→三色→白光）。计数与结果同一把锁发布。

## 5. 规则与状态

1. `start` 启动白光基线，绝对 25 秒预算覆盖加载、采集、切色、验证。相机独占线程读帧并镜像，推理线程只消费最新帧；每样本带采集 ID、读开始和读完成时钟。切色后窗口调用 `repaint()`，读回软件颜色再确认代次。白光不强制持色；每个挑战色从绘制确认时起保持 2000 ms（配置可覆盖），未到期不能因色差切色或熄灯。取消、超时、设备异常和原有身份、质量、被动等门禁拒绝仍可立即终止。下一个有效帧必须在新色确认后 `settle_ms` 才**开始读取**；跨切色在途帧和旧代次结果丢弃。软件重绘确认不是物理显示器光学时间。取消、超时和相机异常不得被在途结果覆盖。worker 请求停止时将仍 pending 的结果置为 rejected/COLOR_CANCELLED；绝对期限置为 timeout/COLOR_TIMEOUT，其他后台失败置为 error/对应错误码。已发布终态不变。
2. ID 和采集时间严格递增；推理提交时帧龄最多 `max_frame_age_ms`，相邻采集间隔最多 `1/min_fps`（检查相机源帧，不将丢弃的分析帧或切色等待算作相机掉帧）。过期或相机供帧慢显示 `COLOR_PERFORMANCE_INSUFFICIENT` 并跳过，不归因为攻击；没有足够有效帧到绝对期限则超时。稳定等待不得阻塞界面。
3. 单脸尺寸≥60px、亮度 20–240、清晰度≥20；身份锚定当前员工三份模板，距离≤0.8；同一框用 MiniFASNet，真人类概率≥0.80 且领先≥0.15。白光基线的无脸、低质量、低置信等待有效帧并清基线连续计数；显式 spoof、多脸、无效/超限身份拒绝。彩色阶段与最终白光复核同样执行门禁。运动值必须是 0–1 范围内的数值，否则按质量不合格处理。质量、身份、被动与 RGB 校验通过后，运动值大于 0.015 的帧只丢弃，原因 `COLOR_MOTION_SKIPPED`，保持原阶段、颜色及截止时间；基线重置连续计数，彩色挑战与最终白光继续等待。运动帧不进入有效样本或达标比例，不能掩盖显式身份或被动拒绝。仅良好样本导致进度增加，身份或被动不能用常量代替。`ColorResult.metrics` 必含三项非负整数 `color_samples`（本色有效数）、`color_hits`（本色色差达标数）、`color_motion_skips`（仅因位移丢弃数），初始化为 0；进入下一色或最终白光时归零，拒绝或超时保留当前值。失败界面若结果颜色为红、绿、蓝，则显示失败颜色及三个计数；白光不展示彩色统计。示例：红光 3 帧有效、2 帧色差达标、1 帧位移丢弃，仍可通过该色。
4. 白光须收满 3 帧（配置可覆盖），每帧 RGB 均值的归一亮度方差≤0.04；基准为这些样本的逐通道色度均值。彩色帧先计算 RGB 各通道占比，再减白光基准；目标通道差须是三通道最大值且≥0.08。每个挑战色在整个 2 秒窗口持续累计所有通过硬门禁（单脸、尺寸/亮度/清晰度、身份、被动活体、数据有效）的样本；不因单个低色差帧或运动帧立刻失败。硬门禁的显式身份不匹配、spoof、多脸、非法数据仍立即拒绝。worker 在刷新快照、取帧分析前及提交分析结果前，持锁调用 `_finish_due_color_locked()`：仅当前挑战色已经绘制确认且单调时钟达到其结束时间时调用 `finish_color() -> ColorResult` 结算。到期的在途结果不计入原色或新色；结算不依赖新帧到达，绝对超时优先。`finish_color()` 非 pending/color_challenge 时不改变状态；有效样本少于配置下限（默认 3）拒绝 `COLOR_SAMPLES_INSUFFICIENT`，否则按 `color_hits / color_samples >= min_color_ratio` 判定（等于通过，不用 ceil 整数比例）；比例不足拒绝 `COLOR_UNRESPONSIVE`；通过才推进并清零本色计数。若未有任何有效样本、或有效样本低于下限，仍优先报样本不足。默认红绿蓝一轮，累计 6 秒持色；保留显式配置两轮的研究兼容性，总预算仍为 25 秒。最后切白并再采一帧走真实门禁才 passed。例：3 份内 1 份弱、2 份达标，在结束时通过本色；2 份达标但总数只有 2，结束时仍拒绝。静态固有偏色不得作为响应。
5. 取消立刻停轮询、复原颜色并请求后台停止，不在 Qt 线程 join。父窗口若检测线程尚未退出，停住预览，轮询退出；在此期间不允许重新开始、读取、释放或再借用相机；批次终止。主窗口关闭时若相机仍被借用则拒绝本次关闭，显示等待状态。正常归还后若相机及定时器仍是原对象才恢复。只有观察到 passed 且后台已停止后 Dialog 才能 Accepted；父窗口仍需复核同一员工在职。彩光失败不调用打卡确认或 CheckService。两开关默认关、会话内互斥，关闭时走原路径。

**Properties：** P-CLR-01：∀终态、后续输入，结果不变（UT-CLR-08）；P-CLR-02：∀旧色代次或不满足硬门禁的帧，不得计为有效（UT-CLR-07、CT-CLR-06）；P-CLR-06：∀后台尚存活，父相机读取及释放调用次数不变（CT-CLR-07）；P-CLR-09：∀有效样本数 n≥3，∀命中数 h∈[0,n]，本色通过当且仅当 h/n≥min_color_ratio（PT-CLR-07）；P-CLR-10：∀颜色，本色统计在持色窗内完整累计，运动丢弃不入n，颜色结算时若有效样本不足下限则失败样本不足，否则仅按比例失败/通过（CT-CLR-10）。生成器：时序与门禁用合成颜色、受控 Event 或确定状态序列，不增加属性测试依赖。

## 6. 反馈

| 错误码 | 条件 | 级别 |
|---|---|---|
| COLOR_PERFORMANCE_INSUFFICIENT | 采集慢、陈旧或输入顺序不合法 | WARN |
| COLOR_INVALID_INPUT / COLOR_SEQUENCE_MISMATCH | 错误阶段或颜色 | WARN |
| COLOR_WAITING_FACE / COLOR_QUALITY_REJECTED | 无脸等待，或多人、质量、运动值无效 | INFO / WARN |
| COLOR_MOTION_SKIPPED | 其余校验通过但运动超过阈值；仅丢帧 | 界面提示，不落盘 |
| COLOR_IDENTITY_REJECTED / COLOR_PASSIVE_REJECTED | 身份或被动门禁未满足；基线低置信等待 | WARN |
| COLOR_UNRESPONSIVE | 基线亮度不稳定或持色期结束、样本数足够但达标比例不足 | INFO |
| COLOR_SAMPLES_INSUFFICIENT | 持色期结束仍未收足有效样本 | INFO |
| COLOR_UNRESPONSIVE | 持色期结束且样本数达标，但色差达标比例低于用户设置 | INFO |
| COLOR_DEVICE_ERROR / COLOR_CAMERA_READ_FAILED / COLOR_MODEL_UNAVAILABLE / COLOR_INTERNAL_ERROR | 显示读回、相机、模型加载、运行异常 | ERROR |
| COLOR_TIMEOUT / COLOR_CANCELLED | 绝对期限或用户取消 | INFO |
| COLOR_LIVENESS_CONFLICT / COLOR_LIVENESS_UNAVAILABLE | 开关冲突或创建试运行失败 | WARN |

只在界面显示中文原因和错误码、采集/分析/有效数值，不新增长期日志。例：`白光有效 1/3 · 摄像头 12 · 已分析 3`。

## 7. 覆盖矩阵

| 需求来源 | 需求 ID | 类型 | 测试 ID | 自动化状态 |
|---|---|---|---|---|
| §5 色响应与色序 | REQ-CLR-005 | 单元 | UT-CLR-04/05 | 已自动化 |
| §5 真实门禁和终态 | REQ-CLR-008 | 性质 | UT-CLR-07/08 | 已自动化 |
| §5 后台、代次、采集与预览 | REQ-CLR-014 | 契约 | CT-CLR-04/06 | 已自动化 |
| §5 生命周期与确认 | REQ-CLR-015 | 契约 | CT-CLR-07 | 已自动化 |
| §5 P-CLR-08：∀其余校验合格且运动超阈值的帧，阶段和颜色不变、有效与达标数不增；终态显示当前颜色及冻结计数。 | REQ-CLR-017 | 属性与界面契约 | PT-CLR-06 / CT-CLR-09 | 已自动化 |
| §5 P-CLR-09 比例 oracle 与采样全窗结算 | REQ-CLR-018 | 性质/契约 | PT-CLR-07 / CT-CLR-10 | 未自动化（本次实施） |
| §4 UI运行时比例范围与应用行为 | REQ-CLR-019 | UI契约 | CT-CLR-11 | 未自动化（本次实施） |
| §5 P-CLR-07 固定持色：∀已绘制的挑战色、时钟早于截止、无其他拒绝或取消 ⇒ 保持当前色；到期按有效样本数与比例分类。受控时钟和合成 RGB。 | REQ-CLR-016 | 契约 | CT-CLR-08 | 已自动化 |
| 真实设备诊断与三类验收 | REQ-CLR-013 | 现场 | TC-CLR-01 | 未自动化（交付前现场执行） |

## 8. 非功能性需求

GUI 轮询 80ms，不调用相机读取、模型推理或 join；后台仅一条采集线程、一条推理线程，最新帧单槽覆盖（分析可能同时持有一帧）；阻塞替身验证 GUI 心跳、取消和安全归还，不能承诺驱动阻塞时后台在固定时限内退出。容量、过期和颜色证据用 CT-CLR-04/06/07 验证。真实摄像头试运行记录真人、纸照、手机静态照各 20 轮、设备、距离、两种光照；候选目标≥18、0、0，未执行不声称达标。

## 9. 假设与约束

Windows、PyQt5、OpenCV、既有 YOLO/FaceNet/MiniFASNet 资产；无新依赖、不调用 MediaPipe 和三眨眼 pipeline；不改旧 `ui.py`、`recognition.py`、`get_name.py`、不操作正式数据库、不承诺视频重放或纸照防护已验收。设备异常必须拒绝，不能替换为成功。v1.1.0 修复白光统计、采集/推理解耦和镜头归还；日期与提交绑定以 Git 记录为准，本次无提交。
