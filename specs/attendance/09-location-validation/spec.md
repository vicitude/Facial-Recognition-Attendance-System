# SPEC-005: Windows 地点校验

> 状态：已闭环（自动化验证完成；真实目标设备验收待现场执行）；版本：v1.1.0；关联代码：`attendance/location_validation.py`、`attendance/services.py`、`attendance/ui_schedules.py`、`attendance/checkin_location.py`、`attendance/windows_location.py`、`attendance/location_worker.py`、`attendance/ui_checkin.py`；测试：`tests/test_location_validation.py`、`tests/test_schedule_location_config.py`、`tests/test_checkin_location.py`、`tests/test_checkin_async_location_contract.py`、`tests/test_location_worker.py`。本阶段已接入签到确认前的地点判定：地点通过后才允许写入，不通过不得写入。

## 1. 术语表
|术语|英文名|类型|定义|代码映射|数据库映射|示例|
|---|---|---|---|---|---|---|
|坐标|Coordinate|值对象|纬度、经度，单位度|`Coordinate`|无|`(39.9,116.4)`|
|地点|AllowedLocation|值对象|允许中心坐标和半径|`AllowedLocation`|schedules.location_*|半径100米|
|校验结果|LocationDecision|值对象|是否允许及原因|`LocationDecision`|无|`allowed`|

## 2. Gherkin 场景
```gherkin
功能: 班次签到地点校验
场景: 坐标在允许半径内
 假设班次配置地点总部(39.9000,116.4000)，半径100米
 当提交(39.9005,116.4000)
 那么结果为allowed
场景: 坐标越界
 假设班次配置地点半径100米
 当提交距离中心大于100米的坐标
 那么结果为outside_radius且不得继续打卡
场景: 定位不可用
 假设当前坐标为None
 当执行校验
 那么结果为location_unavailable
场景: 地点配置不完整
 假设班次只填写地点名称
 当保存班次
 那么抛出LOCATION_CONFIG_INVALID
```

## 3. 接口契约
- `Coordinate(latitude: float, longitude: float)`。
- `AllowedLocation(name: str, latitude: float, longitude: float, radius_m: float)`。
- `haversine_meters(left: Coordinate, right: Coordinate) -> float`。
- `validate_location(current: Coordinate|None, allowed: list[AllowedLocation]) -> LocationDecision`。
- `schedule_allowed_location(schedule) -> AllowedLocation|None`：四个地点字段全为空返回None，部分为空抛LOCATION_CONFIG_INVALID。
- `ScheduleService.create(..., location_name=None, location_latitude=None, location_longitude=None, location_radius_m=None, ...)`：四字段全为空表示该班次不启用地点限制；部分填写或参数非法抛LOCATION_CONFIG_INVALID。

## 4. 数据模型与校验
地点字段为 `location_name VARCHAR(100) NULL`、`location_latitude DOUBLE NULL`、`location_longitude DOUBLE NULL`、`location_radius_m DOUBLE NULL`。全空合法；部分为空非法。纬度[-90,90]、经度[-180,180]、半径(0,100000]。

## 5. 业务规则与状态
对每个允许地点计算 Haversine 距离；距离小于等于半径允许；多个地点取最近者；当前坐标None拒绝；班次无地点配置时返回None，由调用方决定是否启用校验。本阶段不写打卡记录。

## 6. 错误处理
`INVALID_COORDINATE`、`INVALID_LOCATION`、`LOCATION_CONFIG_INVALID`；非法配置不得保存；运行时定位不可用不得放行。

## 7. 测试矩阵
|需求|ID|类型|测试|
|---|---|---|---|
|距离计算|REQ-LOC-01|单元|UT-LOC-001|
|半径边界|REQ-LOC-02|契约|CT-LOC-001|
|越界拒绝|REQ-LOC-03|契约|CT-LOC-002|
|不可用定位|REQ-LOC-04|契约|CT-LOC-003|
|地点配置完整性|REQ-LOC-05|契约|CT-LOC-004|

## 8. 非功能需求
100个地点的模拟校验小于10ms；不访问网络、不记录精确坐标日志；以自动化测试计时和日志断言验证。

## 9. 假设、约束与变更日志
Windows 定位适配器使用可选 WinRT 包；缺少 `winrt-Windows.Foundation` 或 Geolocation 运行时返回 `runtime_unavailable`，权限/服务/超时返回对应不可用状态。旧识别入口主体不改，活体不接入，不执行数据库破坏性操作。2026-11-15 v1.0.0 初始版本；2026-11-15 增加班次地点配置契约。

## 10. 签到接入规则
`CheckConfirmDialog` 在调用 `CheckService.create_record` 前执行 `decide_checkin_location`。已配置地点时：范围内才继续；越界、定位不可用或配置无效均拒绝且不写记录。未配置地点时返回 `location_not_configured` 并保持原时间规则。地点判定优先于早退确认，地点拒绝不会弹早退确认。

默认定位来源为 `WindowsLocationSource`；测试可通过 `CheckConfirmDialog.LOCATION_SOURCE_FACTORY` 注入 `StaticLocationSource`，不修改旧识别入口。

## 11. 验收门禁
必须通过三件套、模拟坐标测试、班次配置契约测试和py_compile；真实Windows定位及签到强制接入另行验收。
