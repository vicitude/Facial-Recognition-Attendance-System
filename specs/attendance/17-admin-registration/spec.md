# SPEC-014：凭管理员设置码注册

## 0. 元数据
已批准，v1.0.0，项目维护者负责。覆盖 `attendance/{models,db,services,ui_admin_setup,ui_login,ui_kiosk,ui_admins}.py`。无网络接口，新增表由 `init_db` 的安全建表路径创建。Gherkin 行为由 §7 的 pytest 直接验证；相关变更须通过 §8。

## 1. 术语
| 术语 | 英文名 | 类型 | 定义 | 代码映射 | 数据库映射 | 示例 |
|---|---|---|---|---|---|---|
| 设置码 | AdminRegistrationCode | 单行配置 | 持有效值可注册完整权限管理员 | `AdminRegistrationCode` | `admin_registration_codes` | 初始码仅交付使用 |

## 2. 验收
```gherkin
功能: 凭码注册与轮换
  场景: 空库或已有管理员
    假设 用户打开凭码注册表单
    当 输入有效码及未占用的账号和有效密码
    那么 创建完整权限账号并回登录页，不创建会话
  场景: 管理员轮换
    当 当前管理员用自己的密码复核后提交合法新码
    那么 旧码失效、已有账号不变、只有新码可继续注册
  场景: 失败
    当 码错误或已轮换，或用户名已占用
    那么 不创建账号且不改写现有账号
```

## 3. 本地接口
- `AdminService.register_with_code(code: str, username: str, password: str) -> Admin` 替换无凭证 `create_first`；返回创建账号，不认证。
- `AdminService.change_registration_code(admin_id: int, password: str, new_code: str) -> None`：数据库读取该 ID，须为现存完整权限管理员且密码正确。
- `AdminService._registration_code_hash(code: str, salt: bytes) -> str` 和 `_registration_code_values(code: str) -> dict`：后者用 `os.urandom(16)`，计算前者并返回 `salt` 与 `code_hash`。`init_db` 建表后仅缺少 id=1 时尝试插入初始行；并发的重复主键仅在确认该行存在时忽略，不更新旧值。
- `RegistrationDialog(parent=None)` 保留原设置表单的用户名、密码、确认密码，新增 `code_edit`，提交 `register_with_code`；`saved_username` 初始 `None`，成功后记录。`ChangeRegistrationCodeDialog(admin_id: int, parent=None)` 使用 `password_edit`、`code_edit`、`confirmation_edit`、`save_button`、`cancel_button` 和 `error_label`；服务确认后 accept 并由后台状态栏显示「设置码已更换」。

## 4. 字段与校验
| 字段 | 类型 | 必填、默认与校验 |
|---|---|---|
| `id` | IntegerField 主键 | 必填；单行，固定 1 |
| `salt` | CharField(32) | 必填，无默认，16 字节随机盐的十六进制 |
| `code_hash` | CharField(64) | 必填，无默认，PBKDF2-HMAC-SHA256，600000 轮，UTF-8 输入，32 字节输出十六进制 |
| `code` / `code_edit` | str | 1–128 字符，非全空白，精确匹配、不裁剪；初始 `123456` |
| `new_code` / `code_edit` | str | 12–128 字符，非全空白、不裁剪，不能为当前码，确认值必须相同 |
| `username` / `username_edit` | str | 去两端空白后 1–50 字符；唯一 |
| `password` / `password_edit` | str | 注册 12–128 字符而且非全空白，确认值匹配；轮换时复核原密码，不改变现有密码规则 |
| `is_super` | bool | 两种创建路径均为 True，沿用后台新增的现有权限及自删、末位保护 |

## 5. 状态与规则
- 空库点齿轮打开「凭设置码注册」；取消回签到。已有账号先显示登录；`LoginDialog.register_button` 触发 `RegisterRequested = 2`，转入注册。取消或成功都回登录；成功预填用户名但不填密码；只有 `Accepted` 且有已认证 admin 才创建后台。登录单独实例默认隐藏注册链接，签到齿轮显式显示。启动仍不创建账号。
- 注册与轮换都在同数据库连接 `atomic()` 中使用 `SELECT ... FOR UPDATE` 锁住 id=1；注册在锁内按 `hmac.compare_digest` 验证并调用现有 `AdminService.create`；轮换也在锁内重新读取操作者并恒时比较密码散列，生成新盐和散列后更新。并发按获得锁顺序生效。缺行时失败而非回退初始码。后台「新增」不接触设置码。
- 设置码、密码和确认字段掩码显示，关闭对话框清空；错误只显示固定文案。轮换不影响既有账号。员工不接触账号或设置码。

### Properties
| 性质 | 回链 | 可判定性质 | 场景变量 | 自动化 |
|---|---|---|---|---|
| P-CODE-01 | §2/§5 注册 | 对任意已有管理员状态，错误码无写入；正确码创建完整权限账号 | 空库、已有账号、错误码 | PT-CODE-101 |
| P-CODE-02 | §2/§5 轮换 | 无正确管理员密码时不改码；有效轮换之后旧码无写入，新码可注册，旧账号可登录 | 密码错误/正确、重启 | PT-CODE-102 |
| P-CODE-03 | §5 窗口 | 注册成功或取消均不建立后台会话 | 打开注册、填写、取消、返回登录 | PT-SETUP-102 |

## 6. 错误处理
`AuthFailed`：码不正确或管理员身份未通过。`UsernameExists`：用户名已占用。`InternalError`：输入不满足契约、重复使用当前码、DB 异常或配置缺失。UI 各分支使用固定中文内联提示，不把异常内容或凭据写入日志。注册复用现有新增日志。

## 7. 验证矩阵
| 来源 | 需求 | 测试 | 自动化 |
|---|---|---|---|
| P-CODE-01 | REQ-CODE-01 | PT-CODE-101 | pytest |
| P-CODE-02 | REQ-CODE-02 | PT-CODE-102 | pytest |
| P-CODE-03 | REQ-CODE-03 | PT-SETUP-102 | pytest |

## 8. 非功能与门禁
0 条新增日志记录设置码。配置轮换使用 1 行事务锁。使用 `python -B -m pytest --noconftest -q tests/test_checkin_entry.py` 跑 Qt 模拟 UI；在 `ATTENDANCE_TEST_CONFIG` 指向隔离库时执行 `python -B -m pytest -q tests/test_first_admin.py tests/test_ui_login.py tests/test_ui_admins.py`。

## 9. 约束
Windows PyQt5、本地 MySQL（InnoDB）。使用标准库，无新依赖。初始设置码是公开且易猜的交付值，负责人必须在交接前轮换。共享码持有者可以创建拥有所有权限的账号；没有远程 API，不承诺抗本机源码或数据库写权限绕过。保留已有管理员和密码，不删除、重建现有表。修改历史由 Git 记录。
