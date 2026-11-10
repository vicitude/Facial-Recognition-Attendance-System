# 001 · 初始化 Agent 工作区（快速开始套餐）（2026-08-24）

- **状态**：活跃
- **关键词**：init, workspace, quickstart
- **相关模块**：通用

## 关联文档

- `AGENTS.md` §1（项目定位）、§2（当前入口）、§9（Agent 工具适配）
- `BACKLOG.md`（配套排期）
- `decisions/_INDEX.md`（本决策的索引行）

## 变化程度

- 新建：`AGENTS.md`、`decisions/_INDEX.md`、`decisions/001-v1-init-workspace.md`、`BACKLOG.md`
- 未生成：`.agents/` 个人层（单人模式不需要）、`tools/`（drift-check 未启用）

## 摘要

基于 `bootstrap-agent-workspace` Skill 在 `d:\yol\yolov8_facenet` 项目初始化 Agent 工作区。

**用户选择**：用户最初选择"完整工具链"，经提醒 `drift-check` 仅适合 Spec 驱动的大型协作项目后，主动降级为"快速开始"。最终落地的技术模块：

1. 核心工作区文档：生成 `AGENTS.md`（P0 唯一常驻事实源）、`decisions/` 决策目录与本首条决策。
2. 排期清单：复制 `BACKLOG.md` 模板并替换日期占位符。
3. 未启用：drift-check、Python workspace。

**协作模式**：单人（仓库非 git init 状态，无团队成员登记）。

**关于待开发的签到/签退人员管理系统**：尚处于需求采集阶段，详见 `BACKLOG.md` #001。完成需求对齐后将按"文档先行"流程先建 Spec 三件套，再写代码。
