# SPEC-004: 多人识别与结果稳定化

> 状态：开发中；版本：v1.0.0；负责人：TL: DSH；关联代码：`attendance/face_recognition_templates.py`、`attendance/ui_checkin.py`、`attendance/recognition_results.py`；测试：`tests/test_multi_face_recognition.py`；活体不接入。

## 1. 术语表
|术语|英文名|类型|定义|代码映射|数据库映射|示例|
|---|---|---|---|---|---|---|
|检测框|FaceBox|值对象|单张脸的[x1,y1,x2,y2]整数框|`normalize_box`|无|`(1,2,100,120)`|
|识别结果|RecognitionResult|值对象|单脸匹配状态、员工、距离|`RecognitionResult`|无|`matched`|
|批次结果|RecognitionBatch|值对象|同一帧全部人脸结果|`recognize_faces`|无|2人|
|状态|RecognitionStatus|枚举|`matched`,`unknown`,`ambiguous`,`invalid`|`RecognitionResult.status`|无|`matched`|

## 2. Gherkin 场景
```gherkin
功能: 多人脸识别
场景: 同帧逐人匹配
 假设检测器返回两个互不重叠的人脸框
 当对每个框提取128维向量并匹配模板
 那么批次结果包含两个结果且框顺序保持
场景: 未知人与低置信度
 假设最小距离大于等于阈值
 当执行匹配
 那么状态为 unknown 且不得生成打卡请求
场景: 重叠框去重
 假设两个框 IoU 大于等于0.5
 当执行批次识别
 那么只保留一个结果
```

## 3. 接口契约
- `normalize_box(box: object) -> tuple[int,int,int,int]`：仅接受至少4个数值，坐标截断为整数。
- `iou(left: tuple[int,int,int,int], right: tuple[int,int,int,int]) -> float`。
- `RecognitionResult(status: str, employee_id: str|None, distance: float|None, pose: str|None, box: tuple[int,int,int,int])`。
- `recognize_faces(queries: list[tuple[box,vector]], employee_ids: list[str], threshold: float=1.0, overlap_threshold: float=0.5, key: bytes|None=None) -> list[RecognitionResult]`。

## 4. 数据模型与校验
RecognitionStatus 枚举恰为四值。box 为4元非负整数；matched 必须有 employee_id/distance/pose；unknown/invalid 的 employee_id 为 None；distance 必须为有限非负数。

## 5. 业务规则与状态
每帧先按输入顺序去除 IoU>=0.5 的后续框，再逐框调用现有 `identify`。距离 `< threshold` 为 matched，否则 unknown。识别异常或向量形状错误为 invalid。批次不得写数据库；打卡由用户对单个 matched 结果确认。

Properties：
- P-MFR-01：任意输出结果的 box 数量等于去重后输入框数量。
- P-MFR-02：任意 matched 结果距离严格小于 threshold。
- P-MFR-03：unknown/invalid 结果 employee_id 必为 None。

## 6. 错误处理
`INVALID_FACE_BOX`：框无效；`INVALID_EMBEDDING`：向量无效；`RECOGNITION_ERROR`：模板读取/匹配异常；错误只转为 invalid 结果，不写数据库，日志记录 warning。

## 7. 测试矩阵
|需求|ID|类型|测试|
|---|---|---|---|
|框校验|REQ-MFR-01|单元|UT-MFR-001|
|IoU去重|REQ-MFR-02|单元|UT-MFR-002|
|逐人匹配|REQ-MFR-03|契约|CT-MFR-001|
|未知拒绝|REQ-MFR-04|契约|CT-MFR-002|
|Properties|REQ-MFR-05|属性|PT-MFR-001~003|

## 8. 非功能需求
批次纯内存处理；100个输入框的去重与结果组装耗时小于100ms（使用模拟向量和 monkeypatch 测试）；不保存原图、向量或密钥。

## 9. 假设、约束与变更日志
假设现有 `identify` 提供单员工最佳匹配；约束不改旧识别入口主体、不接入活体、不执行数据库破坏性操作。变更日志：2026-11-15 v1.0.0 初始规范。

## 10. 验收门禁
必须通过本目录 `tasks.md`、`checklist.md`、`self-check.md`，并通过模拟契约测试；完整摄像头现场验收不作为本阶段自动测试前提。
