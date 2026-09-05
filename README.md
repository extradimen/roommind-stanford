# RoomMind Stanford

基于 upstream RoomMind 的 **Stanford Generative Agents（小镇）架构对齐版**，现已扩展为可配置的多角色互动任务模拟框架。

## Schema v2：任务语义属于场景

引擎不再内置“价格、交付、买方、成交”等谈判概念。每个场景必须通过 `schema_version: 2` 和 `task_config` 定义：

- 任务类型与术语；
- 状态变量及其类型；
- 阶段及阶段含义；
- 完成条件；
- 角色对每个状态字段的确认权限；
- 相关性信号和状态评估说明。

每轮对话后，状态评估模型只抽取带说话人证据的提议、争议与确认；确定性条件引擎负责最终完成判定。条件性报价、礼貌回应和单方表态不会被误判为任务完成。

内置示例覆盖三种不同任务：供应链合同会议、重大服务事故指挥、跨职能面试。

## 两种运行模式与导出

- 参与模式：真人作为玩家与多个 AI 角色互动。
- 测试模式：玩家也由 AI 驱动，完整会话为 AI-to-AI，可设置最大轮数与策略。
- 两种模式均可导出 JSON、CSV、JSONL；记录场景、会话、轮次、顺序、时间、说话人身份、团队、与玩家关系、互动角色和消息正文。

Server 核心已按论文逻辑优化（Seed Memory → Plan → Perceive → Retrieve → React → Act → Reflection），并补齐完整前端、管理后台与运维脚本，可与其它 RoomMind 实例 **并行部署**（端口独立）。

## 与原版 roommind 的差异（Server）

| 模块 | 优化点 |
|------|--------|
| **Seed Memory** | 会话启动时为每个 NPC 写入 turn_id=0 的身份/职责/私密认知种子观察 |
| **Plan** | 基于种子记忆生成更完整的初始计划（2–3 句策略） |
| **Retrieve** | recency/importance/relevance 三路 min-max 归一化后加权 |
| **Perceive** | 使用场景自定义 relevance signals 计算 importance；观察文案 POV 更中性 |
| **Reflect** | Q/A 格式，可一次产生多条 reflection 节点 |
| **Act** | NPC 台词注入 active plan；发言更短更计划驱动 |
| **Orchestrator** | 首轮 `seed_and_plan` 阶段；context 用 display_name |

补丁来源：`roommind-stanford-patch.zip`（7 个 server 文件）。

## 端口（独立，避免与 roommind 冲突）

| 服务 | 端口 |
|------|------|
| API | **8810** |
| 管理后台 | **5182** |
| 学员端 | **5183** |
| PostgreSQL | 5432（库名 `roommind_stanford`） |
| Redis | 6379（db **1**） |

## 快速开始（从零安装）

```bash
git clone https://github.com/extradimen/roommind-stanford.git
cd roommind-stanford
cp .env.example .env   # 可选：编辑 LLM Key；也可稍后在管理后台 /llm 填写

./start.sh   # 自动：apt 依赖 → PostgreSQL/Redis → Python venv → npm → 启动服务
./status.sh
```

`./start.sh` 会自动检测并安装缺失项（Ubuntu/Debian）：

| 类别 | 自动处理 |
|------|----------|
| 系统包 | python3、nodejs、npm、postgresql、redis-server、curl |
| 服务 | 启动 postgresql / redis-server（本机模式） |
| 数据库 | 创建用户 `roommind`、库 `roommind_stanford`（不存在时） |
| Python | 创建 `.venv`、pip install |
| 前端 | admin/client 的 `npm install` |
| Docker | 若已安装 docker，优先用 compose 起 PG/Redis |

访问：

- 学员端：http://\<公网IP\>:5183
- 管理后台：http://\<公网IP\>:5182
- API 健康检查：http://\<公网IP\>:8810/health

**注意：** 新会话才会写入 Seed Memory；旧库数据不会自动迁移种子节点，建议用新库或新 session。

## 项目结构

```
roommind-stanford/
├── server/          # FastAPI + Stanford 对齐 Agent 核心
├── client/          # 学员端（会议对话 + Agent 进度）
├── admin/           # 管理后台
├── config/          # platform.json
├── scripts/         # _lib.sh 环境/bootstrap 逻辑
├── start.sh         # 后台启动
├── stop.sh / status.sh
└── requirements.txt
```

## 架构文档

详见 [docs/STANFORD.md](docs/STANFORD.md)（系统逻辑总结，便于评审与二次开发）。
