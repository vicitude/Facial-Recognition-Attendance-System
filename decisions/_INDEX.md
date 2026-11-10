# 决策索引

> 唯一索引表。新增决策时在末尾追加一行；追溯决策先读本表按关键词定位，再读对应文件。
> 文件命名：`NNN-vN-keyword1-keyword2.md`，序号三位递增，关键词小写英文 kebab-case。

| 文件 | 版本 | 关键词 | 状态 | 相关模块 |
|---|---|---|---|---|
| [001-v1-init-workspace.md](001-v1-init-workspace.md) | v1 | init, workspace, quickstart | 活跃 | 通用 |
| [002-v1-foundation-shipped.md](002-v1-foundation-shipped.md) | v1 | foundation, peewee, pymysql, smoke-test | 活跃 | attendance/ 基础层 |
| [003-v1-service-shipped.md](003-v1-service-shipped.md) | v1 | service, business-logic, peewee, pytest, smoke-test | 活跃 | attendance/ 业务服务层 |
| [004-v1-ui-shipped.md](004-v1-ui-shipped.md) | v1 | ui, pyqt5, qt, smoke-test, pytest-qt, offscreen | 活跃 | attendance/ UI 层 |
| [005-v1-test-shipped.md](005-v1-test-shipped.md) | v1 | test, integration, e2e, pytest, pyqt5, offscreen | 活跃 | tests/ 测试层 |
| [006-v1-bugfix-checkin-warning-loop.md](006-v1-bugfix-checkin-warning-loop.md) | v1 | bugfix, ui-checkin, warning-loop, race-condition, p1-assertion | 活跃 | attendance/ui_checkin.py + tests/test_e2e.py |
| [007-v1-admin-features-shipped.md](007-v1-admin-features-shipped.md) | v1 | spec-002, admin, change-password, multi-admin, self-delete, last-admin, ui-tab, pytest, pyqt5 | 活跃 | attendance/{utils,services,ui_change_password,ui_admins,ui_main}.py + tests/{test_services,test_ui_change_password,test_ui_admins,test_e2e}.py |
| [008-v1-bugfix-employee-face-path.md](008-v1-bugfix-employee-face-path.md) | v1 | bugfix, ui-employees, face-image-path, absolute-vs-relative, qfiledialog, path-normalization | 已被 v2 补强 | attendance/ui_employees.py |
| [008-v2-bugfix-employee-face-path-defensive-save.md](008-v2-bugfix-employee-face-path-defensive-save.md) | v2 | bugfix, ui-employees, face-image-path, defensive-normalization, save-boundary, regression-test, p1-assertion | 活跃 | attendance/ui_employees.py + tests/test_ui_employees.py |
| [009-v1-bugfix-checkin-face-name-lookup.md](009-v1-bugfix-checkin-face-name-lookup.md) | v1 | bugfix, ui-checkin, face-name-lookup, employee-by-face-image, design-assumption, unit-test, e2e-mock | 活跃 | attendance/{services,ui_checkin}.py + tests/{test_services,test_e2e}.py |
| [010-v1-table-name-plural-rebuild.md](010-v1-table-name-plural-rebuild.md) | v1 | table-name, plural, legacy-table, drop-database, rebuild, peewee-meta | 活跃 | attendance/{models,db}.py + temp_rebuild_db.py |
