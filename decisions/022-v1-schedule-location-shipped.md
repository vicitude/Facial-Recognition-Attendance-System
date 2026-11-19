# 决策 022：SPEC-006 班次签到地点配置闭环

- 日期：2026-11-15
- 状态：已闭环（自动化验证完成；真实目标设备验收另列）
- 关联排期：班次签到地点配置与 Windows 定位接入

## 结论

班次签到地点配置已完成自动化闭环。管理员可为班次配置地点名称、经纬度和允许半径；四项全部为空表示不启用地点限制，部分填写或非法值拒绝保存。

签到确认流程在调用 `CheckService.create_record` 前执行地点判定：

1. 后台获取 Windows 定位；
2. 判断是否在班次允许半径内；
3. 地点通过后进入时间、重复和早退规则；
4. 地点失败时不写入考勤记录。

未配置地点限制的班次保持原有时间规则，不启动无必要的定位线程。

## 实现范围

- `attendance/location_validation.py`：坐标、允许地点、Haversine 距离和边界判定。
- `attendance/location_source.py`：静态与不可用定位来源。
- `attendance/windows_location.py`：可选 WinRT Windows 定位适配器，失败时安全降级，不在错误详情中记录精确坐标。
- `attendance/location_worker.py`：后台定位工作器。
- `attendance/checkin_location.py`：签到前地点判定。
- `attendance/models.py` / `attendance/db.py`：班次地点字段及兼容迁移。
- `attendance/services.py` / `attendance/ui_schedules.py`：管理员班次地点配置。
- `attendance/ui_checkin.py`：地点判定后才进入考勤写入流程。

## 验证证据

正确项目根目录：`D:\yol\yolov8_facenet`。

核心回归命令使用专用测试配置 `D:\yol\yolov8_facenet\attendance_test_config.ini`，结果：

- 地点、定位来源、异步定位契约：7 passed；
- 签到 UI：4 passed；
- 服务、班次、地点及签到相关合计：45 passed，14 warnings。

## 未覆盖范围

- 真实客户电脑的 Windows 定位权限、无定位服务、GPS 精度和网络环境仍需现场验收。
- S0 完整实机闭环仍未完成。
- 活体检测保持独立研究，不接入正式签到。
- 未执行 commit、push、reset、clean 或数据库破坏性清理；未修改旧 `ui.py`、`recognition.py`、`get_name.py` 主体。
