# RoomMind Stanford — 系统逻辑说明

> 基于 Stanford Generative Agents 论文对齐的 server 实现 + 完整前后端。

## 1. 架构概览

- **世界线（World Timeline）**：用户与 NPC 的所有公开事件（发言、观望、状态变化）写入共享 timeline
- **独立记忆流**：每个 NPC 有自己的 observation / reflection / plan / action 节点
- **编排器**：按 Agent 顺序串行执行 perceive → retrieve → react → act → reflect

## 2. 会话启动（首轮前）

```
ensure_seed_memories()   → turn_id=0 种子观察（身份、职责、倾向、私密认知、场景目标）
ensure_initial_plan()    → 基于种子生成 active plan 节点
```

前端会收到 WebSocket `processing.stage = seed_and_plan`。

## 3. 每轮用户输入

1. 用户消息写入 DB + timeline `user_speech`
2. 按 `_agent_order` 依次对每个 NPC 调用 `run_agent_tick()`
3. 每个 tick：感知新事件 → 检索 top-k 记忆 → decision LLM → execute_decision
4. 发言配额 `max_speakers_per_turn`（默认 2）
5. 若无人发言 → `plan_fallback_speak` 强制一人按计划开口
6. 重要性累积超阈值 → `maybe_reflect()` 写入 reflection

## 4. 为何一轮有多条「观察」

同一轮 Tn 内 Agent **按顺序**行动。后出场的 Agent 会看到更多 world 事件（用户发言 + 前人观望等），因此观察条数可能为 1、2、3… 这是预期行为。

## 5. 前端与后端分工

| UI 区域 | 数据 |
|---------|------|
| 会议对话 | 仅展示 `replies` / SessionMessage（真正开口的 NPC） |
| Agent 进度 | `last_agent_debug` + 当前轮记忆节点 |
| Seed 记忆 | turn_id=0，`meta.source=seed`，默认不在「本轮」列表中 |

## 6. 传输

- WebSocket 实时（推荐）或 REST 降级
- `turn_result` 在 DB commit 前推送；`committed` 后再拉 `/agent-memories`

## 7. 核心文件

| 路径 | 职责 |
|------|------|
| `server/app/orchestrator/generative.py` | 多 Agent 编排 |
| `server/app/agent/loop.py` | 单 Agent 循环 |
| `server/app/agent/reflect.py` | Seed / Plan / Reflection |
| `server/app/agent/memory_stream.py` | 检索打分 |
| `server/app/world/perception.py` | 感知与 importance |
| `server/app/agent/act.py` | 行动与 NPC 台词 |
