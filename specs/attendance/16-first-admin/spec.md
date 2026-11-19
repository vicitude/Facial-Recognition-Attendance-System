# SPEC-013：交付现场创建首个管理员

## 0. 元数据
已批准，v1.0.0，维护者负责。实现：`attendance_ui.py`、`attendance/{config,services,ui_kiosk,ui_admin_setup}.py`；无网络 API、无迁移。Gherkin 由 §7 的 pytest 实现驱动；合并门禁执行 §8 命令。

## 1. 术语
| 术语 | 英文名 | 类型 | 定义 | 代码映射 | 数据库映射 | 示例 |
|---|---|---|---|---|---|---|
| 首次设置 | FirstAdminDialog | 对话框 | 空管理员表时经齿轮创建首个账号 | `FirstAdminDialog` | `admins` | 设置完成后重新登录 |

## 2. 验收场景
```gherkin
功能: 当面设置首个管理员
  场景: 首次设置
    假设 admins 表为空
    当 打开签到窗口后点击齿轮并提交合法且一致的密码
    那么 仅创建一个管理员并显示登录页，未认证不得进入后台
  场景: 旧数据库
    假设 admins 表有账号
    当 点击齿轮
    那么 直接显示登录页，账号不改写
  场景: 放弃或失败
    假设 首次设置表单已打开
    当 取消或提交无效数据
    那么 不写入新账号，不进入后台
```

## 3. 本地接口
- `AdminService.has_admins() -> bool`：用 `Admin.select().exists()`；数据库异常转通用 `InternalError`，不当作空库。
- `AdminService.create_first(username: str, password: str) -> Optional[Admin]`：已有管理员返回 `None`，成功返回账号；只允许从设置流程调用，不返回登录会话。
- `FirstAdminDialog(parent: Optional[QtWidgets.QWidget] = None)`：使用现有主题，提供创建和取消按钮。`_create(self) -> None` 提交；`saved_username: Optional[str]` 初始化为 `None`，成功后记录并用于登录页回填账号。
- `ConfigService.load() -> dict` 不再读取或校验旧 `[admin]` 段，存在则忽略。`ensure_exists()` 生成的配置不含该段。启动只初始化数据库，不调用 `AdminService.ensure_default`（保留旧测试助手）。

## 4. 数据与校验
| 字段 | 类型 | 默认 | 校验与存储 |
|---|---|---|---|
| `username` / `username_edit` | str / QLineEdit | 空 | 去两端空白后 1–50 字符；服务及表单验证；写 `admins.username` |
| `password` / `password_edit` | str / QLineEdit | 空 | 12–128 字符，不去空白，非全空白；服务及表单验证；掩码输入，复用现有 `AdminService.create` 散列格式，不存明文 |
| `confirmation_edit` | QLineEdit | 空 | 掩码输入，必须和原密码完全相同，不存储 |
设置按钮 `create_button` / `cancel_button`；内联提示 `error_label`，初始为空。提交错误仅显示固定中文提示，不回显输入或数据库错误。成功与离开窗口均清空两次密码输入。

## 5. 状态与规则
- 既有相机释放规则不变。齿轮先判定 `has_admins()`：真走正常登录；假打开「设置首个管理员」。查询失败提示「无法读取管理员状态，请检查数据库连接后重试。」并返回签到。
- 创建前重新检查表是否为空。在生产 MySQL 连接中用 `GET_LOCK` 串行化首建，以 `attendance:first:` 加数据库名 SHA-256 前 40 位作为锁名，等待 5 秒；成功获取（返回 1）才检查及写入，`finally` 执行 `RELEASE_LOCK`。锁失败或 Peewee 异常报告通用 `InternalError`。不允许普通注册；兼容的旧助手不属于生产入口。
- `create_first` 返回 `None` 时提示已有账号，取消设置后重新点齿轮走登录；成功时接受对话框，显示现有登录并预填用户名，密码留空。取消/Esc/关闭不创建、不继续登录。后台仍仅由有效登录打开。

### Properties
| ID | 回链 | 可判定性质 | 测试 |
|---|---|---|---|
| P-SETUP-01 | §2 旧数据库、§5 | 任意已有账号状态，首建不写；并行首建最多一次写入 | PT-SETUP-101 |
| P-SETUP-02 | §2 首次设置、放弃 | 任意设置结果未获得登录成功时，后台构造次数为 0 | PT-SETUP-102 |

## 6. 错误处理
无 HTTP。输入不合规或密码不一致仅给内联提示；已有账号提示「管理员已设置，请取消后重新点击齿轮登录。」；服务失败显示「创建失败，请检查数据库连接后重试。」；不记录密码，成功使用现有账号创建日志。

## 7. 验证矩阵
| 来源 | 需求 | 用例 | 状态 |
|---|---|---|---|
| §3 不使用默认配置 | REQ-SETUP-01 | TC-SETUP-001、TC-ENTRY-001 | 已纳入本轮自动化 |
| P-SETUP-01 | REQ-SETUP-02 | PT-SETUP-101（隔离 MySQL） | 已纳入本轮自动化 |
| P-SETUP-02 | REQ-SETUP-03 | PT-SETUP-102（Qt） | 已纳入本轮自动化 |

## 8. 门禁
`py -3.12 -B -m pytest --noconftest -q tests/test_checkin_entry.py`；服务回归单独运行 `tests/test_first_admin.py`，只允许 `ATTENDANCE_TEST_CONFIG` 隔离的本机测试库。UI 自动化要求 0 次真实 DB 或相机连接。

## 9. 假设与约束
MySQL 为本项目数据库。没有激活码，负责人必须在设备交给员工前完成设置；这个模式不能区分谁先接触空库。不移除或重置旧账号，不拷贝开发数据库交付。变更日志由 Git 生成，本轮不擅自提交。
