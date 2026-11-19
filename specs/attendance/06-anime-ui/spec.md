# SPEC-003：清爽动漫风界面，第一阶段

## 0. 文档头与元数据
- 状态：已批准；版本：v1.0.0；日期：2026-11-10。
- 授权：用户确认浅色清新动漫风，并要求 GitHub 备份成功后实施第一阶段。
- 代码：attendance/ui_theme.py、attendance/ui_main.py、attendance/ui_checkin.py。
- 门禁：不修改数据库、服务层、ui.py、recognition.py、get_name.py；不新增依赖。

## 1. 术语表与统一语言
| 术语 | 英文名 | 类型 | 定义 | 代码映射 | 数据库映射 | 示例 |
|---|---|---|---|---|---|---|
| 主题 | Theme | UI | 雾蓝淡紫、圆角卡片、星月装饰 | ui_theme | 无 | 主窗口 |
| 导航 | Navigation | UI | 四项侧边导航，同步现有 tabs | MainWindow.navigation | 无 | 实时签到 |
| 结果卡 | ResultCard | UI | 最近识别对象和真实操作反馈 | CheckInTab.result_name | 无 | 张三 |

## 2. 用户故事与验收场景
- U01：打开主窗口，显示侧边导航、管理员名称、四个原有页面，默认实时签到。
- U02：导航选择与账户菜单切换均同步页面标题、导航选中项和 tabs 当前页。
- U03：相机未打开时显示提示；打开、开始、停止、关闭操作保留原有状态转换。
- U04：识别到员工后显示姓名、工号；打卡成功才显示类型与时间，取消不得显示成功。
- U05：窗口 1100×720 和 1440×900 下导航、视频和操作区无重叠。

## 3. 接口契约
- ui_theme.apply_theme(widget: QWidget) -> None：设置窗口主题；不修改 QApplication 全局样式。
- ui_theme.StarBanner(parent: QWidget | None = None)：原生 QPainter 星月装饰，无外部素材及网络请求。
- MainWindow 保留 tabs、四个 *_tab、所有 action 与原槽函数；隐藏 tabBar，增加 QListWidget navigation。
- CheckInTab 保留 btn_open/start/stop、video_label、原识别与相机接口；新增 result_name、result_detail、activity_label、device_status。
- 无 HTTP API，无数据库迁移。

## 4. 数据模型与校验规则
- 不新增持久化字段；结果卡只持有本次会话的显示文本。
- 主色 #7c83e8，背景 #f5f6fc，正文 #303650，次级文字 #66708c，危险色 #bd456a。
- 字体 Microsoft YaHei UI，正文 10pt；主窗口默认 1440×900，最小 1100×720；视频最小 480×320。
- 侧栏宽 206；结果栏宽 260；布局间距 16；主内容外边距 24。

## 5. 业务规则与状态流转
- 相机关闭 → 打开：开始按钮可用；打开 → 识别中：停止按钮可用；识别中 → 停止：恢复开始按钮。
- 相机任意状态 → 关闭：清空视频显示，开始和停止不可用。
- 未识别仍使用既有警告和停止规则；不调整阈值、识别频率和员工绑定规则。
- 成功打卡由 CheckConfirmDialog.recorded 信号更新卡片；取消仅结束识别。
- 切换页面不新增摄像头自动开启/停止行为。

## 6. 错误处理与日志规范
- 沿用既有错误码、弹窗、日志，不增加日志中的个人资料。
- 无图库、数据库或摄像头的预览必须使用显式假数据，不声称实际识别成功。

## 7. 测试策略与覆盖矩阵
| 场景 | 测试 | 方法 |
|---|---|---|
| U01/U02 | test_navigation | mock 服务后实例化真实 MainWindow，检查双向切换 |
| U03 | test_camera_states | 假摄像头驱动真实槽函数 |
| U04 | test_result_feedback | 发射真实 recorded 信号并验证卡片 |
| U05 | test_layout | 两种尺寸检查布局几何并保存离屏预览 |
- 验证文件 tests/test_anime_ui.py 用 unittest 独立运行，不加载 pytest conftest，不连接数据库、不加载模型。

## 8. 非功能性需求
- 零新增依赖、零网络素材请求、零新增后台动画定时器。
- 不运行会清业务表的既有 pytest fixture；不为验证读取真实数据库凭证。
- 新增装饰仅原生绘图；无持续闪烁、背景音乐或人物壁纸。

## 9. 假设、约束与变更日志
- 本阶段是动漫风视觉基础，不含人物插画、登录重排、人脸库整合或识别引擎重构。
- 后续阶段另行确认；本次 GitHub 远程基线为 882ac1a。
- 2026-11-10：创建第一阶段范围，用户已授权实施。
