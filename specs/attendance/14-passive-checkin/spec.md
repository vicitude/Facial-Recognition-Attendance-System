# SPEC-011：普通签到默认被动活体

## 0. 元数据
v1.0.0，已批准（2026-11-18）。PO：用户；TL/QA：当前代理。生产路径：`attendance/ui_checkin.py`，复用 `attendance/recognition_results.py` 与 `attendance/liveness_research.py`。无 HTTP 路由、网络契约或数据库迁移。§2 的场景由 §7 的 Python 测试执行，不需要引入 Gherkin 运行器。门禁：§8 本地命令退出码须为 0；无新增 CI。例：关闭两个试运行开关，实时签到显示普通活体门禁。

## 1. 术语
| 术语 | 英文名 | 类型 | 定义 | 代码映射 | 数据库映射 | 示例 |
|---|---|---|---|---|---|---|
| 身份命中 | matched | 状态 | 原加密模板匹配成功，尚不是普通模式放行依据 | `RecognitionResult.status` | 不写入 | `matched` |
| 普通活体结果 | passive result | 状态 | 顺序：`live_candidate`、`spoof_candidate`、`low_confidence`、`low_quality`、`inconclusive`、`liveness_unavailable` | 复用 `RecognitionResult.status` | 不写入 | `low_quality` |
| 试运行 | trial | 模式 | 彩光或眨眼开关启用，走其自己的门禁 | `color_liveness_enabled`、`liveness_enabled` | 不持久化 | 彩光开启 |

## 2. 验收场景
```gherkin
Feature: 普通打卡前检查活体
  Scenario: REQ-PAS-01 同帧通过
    Given 普通模式加密模板命中员工A
    When 原识别帧中对应的人脸框返回 live_candidate
    Then 允许创建员工A的确认框但不自动写记录
  Scenario: REQ-PAS-02 拒绝与重试
    Given 普通模式加密模板命中员工A
    When 活体结果不是 live_candidate 或加载或推理抛出异常
    Then 不创建员工A的确认框且提示失败原因与重新识别
  Scenario: REQ-PAS-03 多人与试运行
    Given 两个不同员工命中
    When 普通模式中首人拒绝且次人通过，或进入任一种试运行
    Then 普通模式仅确认次人，试运行仅执行自身验证
  Scenario: REQ-PAS-04 防止仅凭工号确认
    Given 普通模式接收无活体证据的工号或已作废的后台结果
    When 消费该结果
    Then 不创建确认框
```

## 3. 本地接口
`CheckInTab._identify_frame_boxes(self, frame, boxes)` 返回 `RecognitionResult` 列表，模板算法不变，在尾部调用 `_apply_passive_liveness(self, frame, results: list[RecognitionResult]) -> list[RecognitionResult]`。`_handle_recognition_results(self, results: list[RecognitionResult]) -> None` 是同步与后台批量结果共用的消费入口。`_do_recognition(self, frame: np.ndarray) -> None` 保留签名，只处理首个框；后台全部框由现有 `RecognitionWorker` 批量回调处理（未使用的单框 identify 参数传 `None`），不改 worker 通用接口。删除不再使用的 `_recognize_name`/`_identify_frame_box` 及该模块的 `get_name`/`identify_template` 导入；不要恢复照片匹配回退。例：检测不到框仍走原 `unknown` 路径。

## 4. 数据模型及校验
`_passive_liveness: Optional[LivenessResearch]` 实例字段，初值 `None`＝尚未成功构建。成功后缓存于同一实时签到页，异常不缓存构建对象。`_multi_queue` 内容从工号变为 `RecognitionResult`，缺省空列表；队列仍只收当前模式可继续处理的结果。`RecognitionResult` 不新增字段：`status: str`、`employee_id: Optional[str]`、`distance: Optional[float]`、`pose: Optional[str]`、`box: tuple` 均为构造必填，无默认值；无员工的结果三项 Optional 为 `None`。有员工的试运行命中和普通通过保留其三项原值；普通拒绝用 `dataclasses.replace` 清空三项、保留框；非 `matched` 结果不改写。例：`RecognitionResult('low_quality', None, None, None, (0, 0, 80, 80))`。内部 Python 类型，无 JSON 或数据库实体序列化。

## 5. 业务规则与状态流转
```yaml
matched:
  trial: trial_verify
  ordinary_live_candidate: confirm_eligible
  ordinary_other_or_exception: rejected
trial_verify: {existing_pass: confirm_eligible, existing_reject: rejected}
```
- `_apply_passive_liveness` 在任一试运行开启或无 `matched` 时原样返回，不导入/加载模型。普通模式首次有 `matched` 时局部导入并实例化 `LivenessResearch()`；构建失败将本批次命中全标 `liveness_unavailable`。每个命中的框用 `evaluate(frame, [result.box])`，与模板使用同一 BGR 帧及同一组整数坐标；单框异常只封闭该框。原有模型分数、质量规则与阈值不改：真人类索引 1 必须最高、≥0.80、领先第二类≥0.15；质量不合格不通过。模型状态若不在 `live_candidate`、`spoof_candidate`、`low_confidence`、`low_quality`，归 `inconclusive`。
- `_handle_recognition_results` 在普通模式只保留 `live_candidate`，试运行只保留 `matched`；按原检测顺序处理，不新增去重。单人/队列通过 `_handle_recognition_result(self, result: RecognitionResult) -> None` 调用 `_handle_recognition_name(self, name: str, *, passive_verified: bool = False) -> None`，仅 `live_candidate` 设置此参数为真；普通模式没有此结果不能确认。无可处理项但有普通活体失败时按不可用 > 疑似非真人 > 重试的优先级显示一条提示；若有可处理项，仅处理通过者，不为拒绝项弹窗；无活体结果则沿用身份未识别提示。队列、generation 作废和相机生命周期沿用原入口。
- `_do_recognition` 若识别线程、确认弹窗或多人队列活动则无操作；否则检测首框并调用批量识别。检测/模板异常仍走原同步“未能完成加密模板识别”分支；普通活体异常在批量适配器处理。普通模式最终仍只进入手动确认，不自动打卡；试运行门禁和确认后业务不变。
- 初始徽标及两个试运行关闭后的徽标均使用 `_PASSIVE_LIVENESS_LABEL = '普通模式：被动活体检测'`；试运行开启的原文案不动。

### Properties
- P-PAS-01（REQ-PAS-01/02/04）：∀普通模式命中框和返回状态/异常，确认资格只来自同帧同框 `live_candidate`；有限生成器枚举上述模型状态、无脸/多脸、未知状态、加载与推理异常、旧 generation、裸工号。PT-PAS-01、TC-PAS-04。
- P-PAS-02（REQ-PAS-03）：∀通过/拒绝混合组，队列只含通过者且保留相对顺序；∀启用试运行的模式，额外被动调用数=0。有限生成器用 3 框 `[通过, 拒绝, 通过]` 与两种互斥试运行。PT-PAS-02、TC-PAS-03。

## 6. 错误与 UI
无 HTTP 状态、无新增持久化日志。`_show_passive_liveness_failure(self, status: str) -> None` 调用现有停止识别辅助方法，设置 `result_name='活体未通过'`，将下列消息同时用于 `result_detail` 与状态栏；不显示分数、图像、密钥或异常原文，不弹模态窗。
| 状态 | 条件 | 消息 |
|---|---|---|
| `liveness_unavailable` | 模型加载或单框推理异常 | 活体检测暂不可用，未放行，请重新开始识别。 |
| `spoof_candidate` | 模型倾向非真人 | 未通过真人检测，请本人面向镜头后重新开始识别。 |
| `low_quality` / `low_confidence` / `inconclusive` | 质量或置信不足、其他输出或缺少普通活体资格 | 未能确认活体，请正对镜头、调整光线后重新开始识别。 |

## 7. 需求覆盖
| 需求来源 | 需求 | 类型 | 用例 | 状态 |
|---|---|---|---|---|
| §5、P-PAS-01 | REQ-PAS-01/02 | 参数化 | PT-PAS-01 `test_PT_PAS_01_*` | 实现随代码交付 |
| §5、P-PAS-02 | REQ-PAS-03 | 队列 | PT-PAS-02 `test_PT_PAS_02_*` | 实现随代码交付 |
| §2 试运行 | REQ-PAS-03 | 回归 | TC-PAS-03 `test_TC_PAS_03_*` | 实现随代码交付 |
| §5 后台/消费 | REQ-PAS-04 | 线程及 UI | TC-PAS-04 `test_TC_PAS_04_*` | 实现随代码交付 |
| §9 现场效果 | REQ-PAS-02 | 人工 | TC-PAS-05 | 未自动化：目标相机上部署前执行 |

## 8. 非功能与验证命令
现有工作线程完成模板和活体推理；UI 线程消费结果。单实例成功模型初始化最多一次；无匹配或试运行时新增加载次数为零；无新增文件或数据库写入。例：首个任务构建后，下一任务只调用 `evaluate`。以线程及调用次数断言验证，不虚设推理耗时目标。PowerShell 本地门禁（`$env:PYTHON` 设为已配置的项目解释器；跳过全局数据库 fixture）：
```powershell
$env:QT_QPA_PLATFORM='offscreen'
& $env:PYTHON -B -m pytest --noconftest -p no:cacheprovider tests/test_passive_checkin.py tests/test_recognition_lifecycle.py tests/test_anime_ui.py tests/test_multi_face_ui_contract.py tests/test_liveness_checkin.py tests/test_color_liveness_ui.py tests/test_m2_m3_contracts.py tests/test_color_light_liveness.py tests/test_color_liveness_worker.py -k 'not test_preview_horizontal_flip'
```
预览方向用例单独记录：当前预览代码在未勾选时翻转，与决策 013 和原测试断言相反；不属于本规格，不为取得全绿而改动预览行为或断言。

## 9. 假设、约束、版本
使用环境现有 PyQt5、OpenCV、NumPy、Pillow、PyTorch 与本地哈希校验通过的 MiniFASNet 定义和权重。例：删除或损坏权重不会让普通模式退回仅身份比对。本机开发不访问业务库、真实相机或密钥；不改旧入口主体，不改彩光或眨眼判定，不新增开关、依赖或阈值。现场建议真人与纸质照片各 20 次，记录通过/拒绝数，不把模型结果当防作弊保证。v1.0.0（2026-11-18）为首次批准的本地规格；无 Git 提交记录可生成版本日志。
