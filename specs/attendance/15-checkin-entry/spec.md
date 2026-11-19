# SPEC-012：员工签到与管理员入口分离

## 0. 元数据

状态：已批准；版本：v1.0.0；负责人：项目维护者。关联 `attendance_ui.py`、`attendance/ui_kiosk.py`、`attendance/ui_main.py`、`attendance/ui_login.py`。无网络路由或数据库迁移。Gherkin 场景由 §7 对应的 pytest 用例验证，不引入额外框架。验收命令见 §8。

## 1. 术语

| 术语 | 英文名 | 类型 | 定义 | 代码映射 | 数据库映射 | 示例 |
|---|---|---|---|---|---|---|
| 员工签到窗口 | CheckInWindow | Qt 主窗口 | 唯一常驻窗口，持有签到组件 | `attendance.ui_kiosk.CheckInWindow` | 无新增 | 启动看到「实时签到」 |
| 管理后台 | MainWindow | Qt 主窗口 | 验证通过后新建的独立窗口 | `attendance.ui_main.MainWindow` | 沿用现有表 | 默认打开「人员管理」 |
| 管理员登录 | LoginDialog | Qt 对话框 | 输入现有管理员凭据 | `attendance.ui_login.LoginDialog` | `admins` | 按取消退回签到 |

## 2. 验收场景

```gherkin
Feature: 员工签到与管理后台分流
  Scenario: 员工启动应用（TC-ENTRY-001）
    Given 应用配置和数据库初始化成功
    When 执行 attendance_ui.main
    Then 首屏仅显示实时签到，且未打开摄像头、未开始识别、未显示管理员登录
  Scenario: 管理入口拒绝未通过认证的请求（PT-ENTRY-101）
    Given 员工停留在签到窗口
    When 点击设置并取消、关闭、按 Esc 或提交错误凭据
    Then 不创建管理后台且签到窗口仍可用
  Scenario: 管理后返回员工签到（PT-ENTRY-102）
    Given 管理员通过账号密码进入管理后台
    When 点击退出管理或关闭后台
    Then 返回同一个签到窗口，再次进入须重新认证
  Scenario: 不争用摄像头（TC-ENTRY-002）
    Given 签到窗口已打开摄像头
    When 打开设置或关闭签到窗口
    Then 先释放摄像头；暂不能释放时维持原窗口并显示现有提示
```

## 3. 本地接口

- `attendance_ui.main() -> int`：配置、数据库、默认管理员初始化完成后展示 `CheckInWindow()`，退出事件循环后调用 `close_db()`；数据库初始化成功之后均用 `finally` 关闭，包括默认管理员初始化失败。
- `CheckInWindow.__init__(self) -> None`：创建一个现有 `CheckInTab`，右上角放 `⚙` 按钮（可访问名称及提示为「管理员设置」）；标题为「实时签到」，复用现有主题和状态栏。签到窗口启动尺寸不超过启动屏幕的可用工作区，并为系统窗口边框留空间；内容放不下时可滚动到相机操作和签到提示，设置齿轮仍在顶部。
- `MainWindow.__init__(self, admin: Admin, checkin_tab: CheckInTab, parent: Optional[QtWidgets.QWidget] = None) -> None`：不创建或嵌入签到组件，只借用它读写进程级活体设置；可独立构造用于测试。`parent=None` 表示无 Qt 父窗口；应用传入签到窗口并用独立窗口、窗口模态方式展示。
- `LoginDialog(parent)` 使用现有 `AdminService.authenticate(username, password)`；标题改为「管理员登录」，增加「取消」。无 HTTP API 或数据序列化。

## 4. 数据模型与校验

| 字段 | 类型 | 默认 / 必填 | 校验与作用域 |
|---|---|---|---|
| `CheckInWindow.checkin_tab` | `CheckInTab` | 构造时创建 | 同一进程窗口实例始终复用 |
| `CheckInWindow.settings_button` | `QPushButton` | 构造时创建 | 点击进入 §5 |
| `CheckInWindow._admin_window` | `Optional[MainWindow]` | `None` | 仅认证后赋值，后台销毁后清空 |
| `LoginDialog.admin` | `Optional[Admin]` | `None` | 认证成功后赋值；拒绝时不用于创建后台 |
| `MainWindow.checkin_tab` | `CheckInTab` | 必填，无默认 | 借用签到组件，不改变 Qt 归属 |

输入账号去首尾空白，密码按原值传递，空账号或密码沿用 `AUTH_FAILED`。不增加字段、枚举、文件存储或数据库校验。

## 5. 状态与规则

| 当前 | 操作 | 下一状态及副作用 |
|---|---|---|
| 实时签到 | 点击齿轮 | 若需要先调用 `checkin_tab._close_camera()`；返回 `False` 时原地停留，不弹登录；释放后显示模态登录 |
| 登录 | 错误凭据 | 留在登录，不创建后台 |
| 登录 | 取消、Esc、关闭 | 回到实时签到，不退出进程，不自动重新打开摄像头 |
| 登录 | `Accepted` 且 `admin` 非空 | 新建管理后台，按 02 人员管理、03 打卡记录、04 管理员管理、05 班次管理顺序，选中 02；后台打开期间签到窗口不可操作 |
| 登录 | `Accepted` 但 `admin` 为空 | 拒绝进入后台，回到实时签到 |
| 管理后台 | 「退出管理」（按钮、菜单、Ctrl+Q）或窗口关闭 | 销毁后台；返回原签到窗口，不关闭数据库、不退出应用；下次点击齿轮创建全新登录对话框 |
| 实时签到 | 关闭窗口 | `checkin_tab._close_camera()` 返回 `False` 则拒绝关闭，否则正常结束 |

`CheckInWindow._open_admin(self) -> None` 处理齿轮点击：存在后台时直接返回；已有摄像头、识别或彩光租借时先走现有关闭逻辑。登录处理结束后清空密码并延迟删除对话框。使用 `WA_DeleteOnClose` 销毁后台，`CheckInWindow._clear_admin_window(self) -> None` 连接 `destroyed` 并清空引用。`CheckInWindow.closeEvent(self, event: QtGui.QCloseEvent) -> None` 在后台存在时拒绝关闭签到窗口，其余情况委托原相机清理和 Qt 默认关闭。

管理后台复用原有管理页、账户菜单和试运行设置；每次构造从签到组件回填三眨眼开关、彩光开关、彩光比例（回填比例时阻断信号）。设置本身按原规则在本次应用运行期间有效，退出管理不重置；程序重启恢复原默认值。签到保持原「打开相机 → 开始识别 → 确认签到/签退」，不更改签到组件及人员、班次、定位、活体规则。

### Properties

| ID | 来源 | 可判定性质 | 输入集合 | 测试 |
|---|---|---|---|---|
| P-ENTRY-01 | §2 拒绝场景、§5 登录 | 对所有未通过认证的结果，管理窗口构造次数为 0 | 取消、Esc、关闭、空凭据、错误凭据、无管理员的 Accepted | PT-ENTRY-101 |
| P-ENTRY-02 | §2 返回场景、§5 后台 | 对所有正常退出后台方式，原签到窗口仍在且下次打开先重新认证 | 退出按钮、菜单、窗口关闭 | PT-ENTRY-102 |

## 6. 错误处理

| 错误码 | HTTP | 条件 | 日志及 UI |
|---|---|---|---|
| `AUTH_FAILED` | 不适用 | 空凭据或凭据错误 | 复用已有登录失败警告，不记录明文密码 |
| 无新增 | 不适用 | 彩光仍持有摄像头 | 复用签到状态栏提示，保持窗口 |
| 无新增 | 不适用 | 配置或数据库启动失败 | 沿用启动失败弹窗及 stderr |

## 7. 验证矩阵

| 来源 | ID | 类型 | 用例与自动化 |
|---|---|---|---|
| §2 启动 | REQ-ENTRY-01 | 入口集成 | TC-ENTRY-001，`tests/test_checkin_entry.py` |
| §2 相机 | REQ-ENTRY-02 | Qt 生命周期 | TC-ENTRY-002，`tests/test_checkin_entry.py` |
| §3 窗口尺寸 | REQ-ENTRY-05 | Qt 布局 | TC-ENTRY-003，模拟小屏工作区并检查按钮及提示可达 |
| P-ENTRY-01 | REQ-ENTRY-03 | 参数化 Qt | PT-ENTRY-101，`tests/test_checkin_entry.py` |
| P-ENTRY-02 | REQ-ENTRY-04 | 参数化 Qt | PT-ENTRY-102，`tests/test_checkin_entry.py` |

## 8. 非功能与验收门禁

运行 `python -m pytest --noconftest -q tests/test_checkin_entry.py`（`QT_QPA_PLATFORM=offscreen`）；0 次真实数据库、摄像头访问，断言启动不认证、只有一个员工签到组件、后台无签到组件。需 MySQL 的现有套件只使用 `ATTENDANCE_TEST_CONFIG` 指定的隔离测试库；禁止使用生产配置。

## 9. 假设、约束与变更日志

沿用本地 PyQt5、MySQL、既有管理员账号和密码校验；例如已有管理员在新登录框仍使用原密码。此为桌面应用操作入口隔离，不是操作系统权限隔离。不新增依赖；不触碰本地考勤数据、模板、权重与旧版识别入口。变更日志以 Git 历史为准。
