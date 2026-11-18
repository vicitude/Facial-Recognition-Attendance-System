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
| [011-v1-anime-ui-phase-one.md](011-v1-anime-ui-phase-one.md) | v1 | anime-ui, theme, sidebar, checkin, offscreen | 活跃 | attendance/{ui_theme,ui_main,ui_checkin}.py + tests/test_anime_ui.py |
| [012-v1-ui-dialogs-dpi.md](012-v1-ui-dialogs-dpi.md) | v1 | login, dialog, theme, dpi, text-clipping | 活跃 | attendance/ui_*.py + attendance_ui.py |
| [013-v1-camera-preview-direction.md](013-v1-camera-preview-direction.md) | v1 | camera, preview, horizontal-flip | 活跃 | attendance/ui_checkin.py |
| [014-v1-management-pages-phase-two.md](014-v1-management-pages-phase-two.md) | v1 | management-pages, tables, filters, responsive-ui | 活跃 | attendance/{ui_employees,ui_records,ui_admins,ui_theme}.py |
| [015-v1-recognition-worker-phase-three.md](015-v1-recognition-worker-phase-three.md) | v1 | recognition-worker, qthread, frame-drop, camera-lifecycle | 活跃 | attendance/{recognition_worker,ui_checkin}.py + tests/test_anime_ui.py |
| [016-v1-research-s0-baseline.md](016-v1-research-s0-baseline.md) | v1 | research, s0, baseline, test-isolation, liveness | 活跃 | docs/research/S0-baseline.md + attendance/test_safety.py + tests/conftest.py |
| [017-v1-liveness-s1-research.md](017-v1-liveness-s1-research.md) | v1 | research, s1, liveness, minifasnet, offline-validation | ?? | attendance/liveness_research.py + liveness_research.py + docs/research/S1-liveness-result.md |
| [018-v1-m2-m3-encrypted-enrollment.md](018-v1-m2-m3-encrypted-enrollment.md) | v1 | m2, m3, enrollment, encrypted-template, dpapi, face-recognition | 进行中 | attendance/{ui_enrollment,ui_employees,ui_checkin,face_template_crypto,face_recognition_templates}.py |
| [019-v1-s1-active-liveness.md](019-v1-s1-active-liveness.md) | v1 | s1, active-liveness, challenge, anti-spoofing, research | 研究中 | attendance/active_liveness.py + tests/test_active_liveness.py |
| [020-v1-bugfix-enrollment-recognition-delete.md](020-v1-bugfix-enrollment-recognition-delete.md) | v1 | bugfix, enrollment, recognition, delete, encrypted-template | 已修复待现场验收 | attendance/{ui_enrollment,ui_checkin,ui_employees,services}.py |
| [021-v1-attendance-anomaly-rules.md](021-v1-attendance-anomaly-rules.md) | v1 | attendance, anomaly-rules, duplicate, late, early-leave, sequence | 实现中 | attendance/{attendance_rules,models,services,db,ui_records}.py |
| [022-v1-schedule-location-shipped.md](022-v1-schedule-location-shipped.md) | v1 | schedule-location, windows-location, async-checkin, geofence | 已闭环（实机验收待执行） | attendance/{location_validation,windows_location,location_worker,checkin_location,ui_checkin,ui_schedules}.py |
| [024-v1-unified-cuda-inference.md](024-v1-unified-cuda-inference.md) | v1 | cuda, inference-device, environment, fp32 | 自动化验证完成 | attendance/inference_device.py + facenet/facenet.py + attendance/liveness_research.py |
| [023-v1-liveness-checkin-trial.md](023-v1-liveness-checkin-trial.md) | v1 | liveness, blink, checkin, trial, employee-bound, camera-lifecycle | 试运行接入（现场验收待执行） | attendance/{liveness_backend,ui_liveness,ui_checkin,ui_main}.py |
| [025-v1-color-light-trial.md](025-v1-color-light-trial.md) | v1 | color-light, screen, liveness, trial | 开发中（现场验收待执行） | attendance/{color_light_controller,color_light_liveness,color_light_backend,ui_color_liveness,ui_checkin,ui_admins,ui_main}.py |
| [026-v1-color-light-ratio-diagnostics.md](026-v1-color-light-ratio-diagnostics.md) | v1 | color-light, ratio, diagnostics, green-light | 代码完成（现场验收待执行） | attendance/{ui_admins,ui_main,ui_checkin,ui_color_liveness}.py + tests/ |
| [027-v1-passive-liveness-checkin.md](027-v1-passive-liveness-checkin.md) | v1 | spec-011, passive-liveness, MiniFASNet, checkin | 隔离验证完成（现场验收待执行） | attendance/ui_checkin.py + tests/test_passive_checkin.py |
