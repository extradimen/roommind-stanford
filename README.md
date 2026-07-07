# RoomMind Stanford

基于 upstream RoomMind 的 **Stanford Generative Agents（小镇）架构对齐版**。

Server 核心已按论文逻辑优化（Seed Memory → Plan → Perceive → Retrieve → React → Act → Reflection），并补齐完整前端、管理后台与运维脚本，可与其它 RoomMind 实例 **并行部署**（端口独立）。

## 与原版 roommind 的差异（Server）

| 模块 | 优化点 |
|------|--------|
| **Seed Memory** | 会话启动时为每个 NPC 写入 turn_id=0 的身份/职责/私密认知种子观察 |
| **Plan** | 基于种子记忆生成更完整的初始计划（2–3 句策略） |
| **Retrieve** | recency/importance/relevance 三路 min-max 归一化后加权 |
| **Perceive** | 谈判关键词 importance；观察文案 POV 更中性 |
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
