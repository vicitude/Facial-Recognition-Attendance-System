# 009 · v1 · 任务 "实时签到识别不到员工" Bug 修复（2026-08-24）

- **状态**: 活跃
- **版本**: v1
- **关键词**: bugfix, ui-checkin, face-name-lookup, employee-by-face-image, design-assumption, unit-test, e2e-mock
- **相关模块**: `attendance/services.py` (L257-277 `get_by_face_image_name`) + `attendance/ui_checkin.py` (L277-289 `_do_recognition` 关联方式) + `tests/test_services.py` (B-19 新增) + `tests/test_e2e.py` (D-07 改造)

## 关联文档

- `AGENTS.md` §1, §5, §6 (**L-014/L-015 新增**), §10 变更日志
- `decisions/008-v2-bugfix-employee-face-path-defensive-save.md` (任务 8 修复, 路径归一化背景)
- `decisions/004-v1-ui-shipped.md` (C UI 层闭环, 涉及 ui_checkin._do_recognition 初版)
- `decisions/006-v1-bugfix-checkin-warning-loop.md` (任务 1, 同样在 ui_checkin.py 修 bug, 风格沿用)
- `attendance/services.py:257-277` (`EmployeeService.get_by_face_image_name` 新方法)
- `attendance/ui_checkin.py:277-289` (`_do_recognition` 改用新方法, 注释说明设计假设错误)
- `tests/test_services.py` B-19 (新增 P1 单元测试, 4 场景)
- `tests/test_e2e.py` D-07 (e2e 改造, mock `get_name.rec` + mock `get_by_face_image_name`)
- 闭环事实唯一来源：本文件

## 变化程度

- **修改 1 个文件**: `attendance/services.py`
  - L257-277: 新增 `EmployeeService.get_by_face_image_name(name: str) -> Employee` 静态方法 (+21 行, 含 11 行 docstring)
- **修改 1 个文件**: `attendance/ui_checkin.py`
  - L277-289: `_do_recognition` 改用 `get_by_face_image_name`, 注释说明原"约定为 employee_id"是设计假设错误 (+13 行注释)
- **修改 1 个文件**: `tests/test_e2e.py` (D-07 改造)
  - L169-186: docstring 更新 (4 mock → 5 mock + P1 修正说明)
  - L211-228: section 3 改 `get_name.rec` mock 返 `100001` (face_datasets/100001.jpg 的 basename) + 新增 section 3.5 mock `EmployeeService.get_by_face_image_name` (+19 行)
- **新增 1 个文件** (按 B 层 spec §7 编号):
  - `tests/test_services.py` L341-400: B-19 单元测试, 4 场景 (+60 行, 自建 `tmp_path/face_datasets/` 真目录真文件 + `monkeypatch.chdir`)
- **未触碰** (红线保护):
  - `recognition.py` / `get_name.py` / `ui.py` (A 层红线)
  - `tests/conftest.py` (D 层 G-06 红线)
  - `attendance/utils.py` (异常类不变, 复用现有 EmployeeNotFound)
  - `attendance/ui_checkin.py` 其他方法 (camera / timer / dialog 不变)

## 摘要

按用户拍板**方案 A**修复"加了员工但实时签到识别不到"的核心 Bug。根因是 `attendance/ui_checkin.py:282` 原代码用 `EmployeeService.get(name)` 假设 `name` (即 `get_name.rec` 返回值) = `employee_id`, 但 `get_name.rec` 实际返回 `face_datasets/xxx.{jpg,png}` 文件的 **basename (无扩展名)**, 与 employee_id (6 位数字) 是完全不同的标识体系。原代码注释"约定为 employee_id"是设计假设错误, 无任何代码层校验或文档化。

## 修复方案

### 1. B 层: 新增 `EmployeeService.get_by_face_image_name`

按人脸照片文件名 (basename, 无扩展名) 反查员工, 关联字段从 `employee_id` 改为 `face_image_path`:

```python
@staticmethod
def get_by_face_image_name(name: str) -> Employee:
    """按人脸照片文件名查找员工 (face_datasets/xxx.ext 的 basename, 无扩展名).

    用于签到流程: get_name.rec 返回 face_datasets/xxx.{jpg,png}
    的文件名 (无扩展名), 反查 DB 找对应员工 (face_image_path 字段).

    抛出: EmployeeNotFound
    """
    if not name:
        raise EmployeeNotFound("人脸照片文件名为空")
    try:
        return Employee.select().where(
            Employee.face_image_path.startswith(
                f"face_datasets/{name}."
            )
        ).get()
    except Employee.DoesNotExist:
        raise EmployeeNotFound(
            f"未找到人脸照片文件名为 {name!r} 的员工"
        )
```

**契约**: 输入 basename (无扩展名), 内部拼 `face_datasets/{name}.` 前缀, 用 peewee `startswith` 查询。找不到抛 `EmployeeNotFound` (与 `EmployeeService.get` 异常类型一致, 复用现有异常类)。

**为什么用 `startswith` 而不是 `=`**: 兼容 `face_datasets/HuangJiaWei.jpg` / `.png` / `.jpeg` 三种扩展名, 不需要三遍查询。

### 2. UI 层: 改用新方法

`attendance/ui_checkin.py:282`:

```python
# 改前
try:
    emp = EmployeeService.get(name)
except EmployeeNotFound:
    ...

# 改后
try:
    emp = EmployeeService.get_by_face_image_name(name)
except EmployeeNotFound:
    ...
```

注释说明原假设错误 (避免后续维护踩坑):

```python
# name 来自 get_name.rec 返回的 face_datasets/ 文件 basename (无扩展名),
# 用 face_image_path 字段反查 DB 找对应员工
# (原注释"约定为 employee_id"是设计假设错误: 实际 employee_id 是 6 位数字,
#  file basename 是拼音/中文, 二者不等; 修复后改用 face_image_path 关联)
```

### 3. 单元测试 B-19 (4 场景)

`tests/test_services.py:341-400` 新增 B-19, 验证 `get_by_face_image_name` 行为:

1. 正常匹配: `face_image_path = "face_datasets/HuangJiaWei.jpg"` → 查 `"HuangJiaWei"` → 找到 employee_id=200001
2. 多员工库中精确匹配: `face_image_path = "face_datasets/ZhangSan.png"` → 查 `"ZhangSan"` → 找到 employee_id=200002
3. 文件名不存在 → `EmployeeNotFound`
4. 空字符串 → `EmployeeNotFound`

**测试设计要点**:

- **不复用 conftest `face_image` fixture**: 该 fixture 返回绝对 tmp 路径 (如 `C:/Users/.../tmp/xxx/100001.jpg`), 不匹配生产路径格式 `face_datasets/xxx.{jpg,png}`, 强行使用会导致 `get_by_face_image_name` 必然查不到 (与 L-012 教训一致: 测试不能放宽 regex 跳过业务契约)
- **自建 `tmp_path/face_datasets/` 真目录真文件**: 匹配生产路径, 让 `_validate_face_image_path` 真实校验文件存在性
- **`monkeypatch.chdir(tmp_path)`**: 让 `face_datasets/xxx` 相对路径能解析到真文件 (因为 `_validate_face_image_path` 用 `os.path.isfile(v)` 验证文件存在, 而 `v` 是相对路径, 必须切到正确 CWD)

### 4. 集成测试 D-07 改造

`tests/test_e2e.py:164-289` D-07 改造, mock 入口调整:

**改前 (旧假设)**:
- `get_name.rec` mock 返 `"200007"` (假设 filename = employee_id)
- 不 mock `get_by_face_image_name` (此方法原不存在)

**改后 (新设计)**:
- `get_name.rec` mock 返 `"100001"` (face_datasets/100001.jpg 的 basename, 匹配生产实际)
- 新增 section 3.5 mock `EmployeeService.get_by_face_image_name` → 直接返测试员工, 绕开 conftest `face_image` fixture 的绝对 tmp 路径 (不匹配 `face_datasets/xxx.*` 前缀)

**为什么 mock `get_by_face_image_name` 而不是用真实查询**: e2e 测试关注"UI → Service → DB 端到端流程", 但 conftest `face_image` fixture 用绝对 tmp 路径 (与生产 face_datasets/ 前缀格式不一致), 真实查询必然失败。在 e2e 层 mock service 入口 (而非整个 service) 是合理简化, 前提是 service 本身有 B-19 单元测试覆盖 (L-014 教训)。

## 闭环验证

- **B 层 21/21 PASSED**: B-19 + 既有 18 个 B + E-09/E-10 (新增 1 个, 既有 20 个无回归)
- **D 层**: 受沙箱环境限制 (PowerShell profile 损坏 + torch DLL 加载失败), 无法在当前 session 跑 D-07 验证, 但代码静态分析 + D-09/D-10 已验证 (用 `get_name.rec` mock 返不同值走不同分支, 不依赖 `get_by_face_image_name` 真实查询, 不需要改造)。请用户在本地 Python 环境跑 `python -m pytest tests/test_e2e.py -v` 验证 D-07。
- **代码语法**: 3 个修改文件 (`services.py` / `ui_checkin.py` / `test_e2e.py`) + 1 个新增测试 (`test_services.py` B-19) Python 编译通过, 无语法错误。

## 不在本次范围内

- **`ui.py` 旧版能识别, `attendance_ui.py` 新版不能**: 旧版用 `get_name.rec` 返回值直接做 face 匹配, 走的是 `ui.py` 内置的 `name` 字段, 不查 DB; 新版要做"识别 → 反查员工 → 弹确认 → 打卡"的完整流程, 必然要走 DB 查询, 所以 `get_by_face_image_name` 是新流程的必要补全。
- **`recognition.py` / `get_name.py` 返回值契约**: 未文档化, 是 L-014 教训之一 ("隐式契约必须在 B 层用 unit test + spec 文档化, 不能默认'大家知道'")。下一轮建议补 spec 文档化。
- **`face_image_path` 字段命名规范**: 当前是 `face_datasets/{basename}.{ext}` 前缀匹配, 假设 face 库与员工一一对应 (一个员工一张图)。如果未来需要"一个员工多张图", 需重新设计查询方式, 本 v1 修复不考虑。

## 后续行动

1. 用户本地跑全套测试验证: `python -m pytest tests/ -v` (关注 D-07 是否通过, B-19 是否通过)
2. 重启 `attendance_ui.py` 加载 v1 修复 (按 §5 临时文件规范, 不需要 .pyc 清理, Python 自动重新编译)
3. 实测签到: 「人员管理 → 确认员工 face_image_path 格式正确 → 实时签到 → 摄像头识别 → 应弹确认 dialog 而非"未识别"」
4. 下一轮 backlog 排期: 补 `recognition.py` / `get_name.py` 返回值契约到 spec, 避免再次踩"隐式契约"坑
