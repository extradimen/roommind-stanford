# RoomMind 重大架构迭代记录

本文是RoomMind架构演进的长期索引。每次发生会改变系统研究假设、运行方式、评价方式或多人仿真语义的重大调整，都应在此新增一轮；普通缺陷修复不单独编号，但应归入对应轮次的“问题与验证”。

## 记录规范

每轮必须记录：

1. 调整前的问题与证据；
2. 新增或改变的架构机制；
3. 保持不变的实验边界；
4. 验证方法与观察结果；
5. 新暴露的问题；
6. 对论文研究问题、指标或有效性威胁的影响；
7. 对应代码提交。

## 第1轮：结构化多Agent场景

**目标：** 从单一大模型角色提示词升级为可配置多人情境。

**主要机制：**

- 角色身份、职责、倾向和关系；
- 私有状态、隐藏议程、红线和权限；
- 多角色独立发言；
- dispatch rules；
- phases、state schema和completion conditions。

**核心认识：** 语言风格不是角色真实性。真实角色还需要利益、知识边界、责任和不可越权的行动范围。

## 第2轮：Participation/Test双模式与统一导出

**目标：** 同时支持真人参与训练与AI对AI自动测试。

**主要机制：**

- participation mode：真人玩家与AI角色互动；
- test mode：AI玩家自动推进；
- `speaker_source=human|ai`；
- session、turn、sequence、speaker和message统一导出；
- 后台单步/连续运行。

**主要问题：** AI玩家最初仍以`user`表示，容易与真人混淆；自动模式比参与模式产生更多模型调用和长上下文。

## 第3轮：长对话与LLM韧性

**触发证据：** `finish_reason=length`、空content、502、`ERR_EMPTY_RESPONSE`。

**主要机制：**

- 空内容和length finish识别；
- 紧凑提示与有限历史窗口；
- 重试和fallback；
- 后端异常保护；
- LLM调用、预览、错误和重试日志；
- resilience smoke tests。

**核心认识：** 自动多人会话的稳定性不能依赖一次模型调用成功；长对话必须有有界上下文和可诊断失败。

## 第4轮：受控Baseline与批量实验

**目标：** 不把RoomMind与一个被故意弱化的聊天机器人比较。

**主要机制：**

- 中央提示词式多角色Baseline；
- RoomMind与Baseline共享公共场景、参与者、任务说明、玩家策略和模型锁定；
- 场景×条件×重复次数批量运行；
- 后台并发、恢复、取消和统一导出；
- matched pair与固定随机种子。

**核心认识：** Baseline必须获得同等公共信息，只缺少待检验的独立记忆、调度、状态治理等机制。

## 第5轮：生成、AI评价、人工盲评解耦

**目标：** 外部评价失败不能污染已经成功生成的对话。

**主要机制：**

1. 生成并冻结对话；
2. 独立AI六维真实性评价；
3. 可选人工盲评；
4. 最终证据报告；
5. forensic debug bundle。

**六个维度：**

- Role & strategic fidelity；
- Information boundaries；
- Temporal coherence；
- Interaction structure；
- Multi-party dynamics；
- Procedural fidelity。

**主要问题与修复：** evaluator曾将规范响应内部`metrics`误当包装层，造成全部评价失败；随后修复解析并保存每个维度的原始响应、错误和证据。

## 第6轮：开放场景治理与收敛

**触发证据：** 多个角色分别合理发言，但会议整体重复承诺、无限等待或运行到50轮。

**主要机制：**

- domain-neutral event ledger；
- work items；
- artifact offered/submitted/reviewed；
- action committed/completed；
- blocker、handoff、schedule、decision和outcome；
- evidence-grounded状态变更；
- progress signature和stagnation window；
- completed、conditional、deferred、failed、stalled；
- Agent contribution gate；
- 开放场景治理数据导出。

**对应提交：** `94d61fc Improve open scenario simulation convergence`

**验证结果：** 最新四个RoomMind场景分别运行44、29、21、21轮。事件账本和多终局确实运行，但工作项碎片化、状态缺失和伪进展仍让停滞计数频繁归零。

## 第7轮：事件语义规范化与强制收敛

**触发证据：** 批次`c532e2e7-078e-446c-bbaf-3097e20aa384`的forensic debug bundle。

发现：

- 供应链会话44轮、28个事件、16个工作项，其中12个仍开放；
- 产品发布29轮、20个工作项，其中16个仍开放；
- `information_provided`和`outcome`工作项可能没有status；
- 同一事项因`draft/details/summary`等措辞形成多个工作项；
- `artifact_reviewed`可以在没有`artifact_submitted`的情况下发生；
- 承诺和提案被计入进展；
- 第21至29轮之间只有7个连续无事件回合，恰好绕过8轮停滞阈值；
- 面试中多个NPC同轮提问，AI玩家回答了较旧问题；
- 明确宣布会议结束后仍继续生成。

**本轮机制：**

- task state升级为schema v4；
- 只有confirmed/rejected变量和submitted/completed/blocked/rejected工作项计入持久进展；
- promise/proposal不再重置停滞计数；
- 工作项支持稳定`work_item_key`、别名和确定性近似归并；
- 补齐information/outcome等事件的工作项状态；
- 只有required且未解决的工作项进入`open_issues`；
- 工作项保存milestones和last event；
- `artifact_reviewed`强制依赖`artifact_submitted`，非法转换保留在日志但不改变状态；
- 明确的meeting/interview/session closure直接形成completed/conditional/deferred终局；
- AI玩家提取本轮NPC直接问题，并优先回答最新具体问题；
- 增加对应回归测试。

**保持不变：**

- 不加入谈判专用流程；
- 不让后验评价影响对话生成；
- Baseline与RoomMind继续使用同一公共AI玩家策略；
- 角色私有记忆不进入共享治理状态。

**待验证假设：**

- 供应链和产品发布对话轮数应明显下降；
- repeated promise不应重置stagnation；
- 产品发布应在首次明确闭会时终止；
- 面试玩家应优先回应本轮最后一个具体问题；
- invalid artifact review应出现在forensic日志，但不进入完成状态。

## 第8轮：传统独立智能体Baseline

**触发原因：** 第4轮集中式Baseline虽然能够输出多个角色，但所有NPC由
一次中央模型调用生成、共享同一上下文，也同时暴露于所有角色私有资料。
这种比较适合衡量完整系统与集中式聊天的差异，却不能严格回答：在角色已经
是独立传统智能体并具有普通对话记忆后，RoomMind结构化认知与治理是否仍有
贡献。

**本轮Baseline定义：**

- 每个NPC独立调用相同平台模型；
- 每个NPC只获得自己的角色提示、private state和authority资料；
- 每个NPC分别持久化最近N条公开对话，属于普通滚动聊天记忆；
- 所有NPC获得相同公开场景和公开参与者名录；
- 每个NPC独立决定`speak`或`wait`；
- 不使用observation节点、reflection、planning或语义记忆检索；
- 不执行dispatch rules、authority enforcement、task state、event ledger、
  work items、evidence gate、completion correction或stagnation governance；
- 仅保留最大轮数、输出长度、格式修复和API重试等基础运行安全措施。

**新的核心比较：**

- C：传统独立智能体＋按角色隔离的普通滚动对话记忆；
- D：完整RoomMind结构化认知与治理架构。

**方法学意义：** 两组都已经是独立多智能体，且私有资料都按角色隔离。
主要处理差异不再是“一个模型还是多个模型”，而是RoomMind新增的结构化
认知、调度、权限、状态、证据和收敛治理机制。

**有效性边界：** C与D仍可能具有不同的模型调用次数和自然终止长度。
六维真实性的主要盲评应使用相同固定窗口；自然终止结果另行报告完成、延期、
失败、停滞和收敛轮数。

## 第9轮：运行时韧性与恢复体验

**触发原因：** 生产与预发日志显示，真实性架构本身之外，陈旧数据库连接、
WebSocket掉线、浏览器缓存失效会话、LLM欠费/下架/空响应，以及批量任务状态
耦合会直接中断用户任务。这些故障会把基础设施不稳定误记为模拟质量问题。

**本轮通用改进：**

- PostgreSQL连接池启用`pool_pre_ping`与定期回收，避免复用已关闭连接；
- WebSocket不仅在首次失败时重试，已连接后的异常断开也指数退避重连；
- 浏览器发现缓存session返回404时自动创建新session；
- `finish_reason=length`连续出现时压缩历史输入并保留系统指令、输出契约和最近对话；
- 参与模式在主提供商欠费、模型下架、持续5xx、空响应或传输故障时，可切换到
  另一个已经配置密钥的提供商；受控`test/baseline`实验明确禁用该切换；
- 单个失败对话可与外部评价并行重跑，不再因为批次处于评价状态返回409；
- systemd拆分守护API、Admin与Client，任一进程退出后独立自动重启。

**方法学边界：** LLM提供商降级只属于参与模式的可用性策略。论文批量实验继续
固定提供商和模型，因此不会因为容灾切换产生处理条件污染。技术故障、降级次数和
模型标签仍应保存在日志中，与真实性评分分开报告。

## 论文使用建议

论文中应将这些轮次描述为“证据驱动的设计迭代”，而不是把每次修改都作为性能提升结果。每轮均应区分：

- 设计目标；
- 可观察失败；
- 架构机制；
- 验证数据；
- 新的有效性威胁。

最终系统评价必须使用第8轮之后重新生成的独立批次，不能把用于发现和修复问题的批次同时作为最终效果证据。第8轮之前标记为`baseline`的数据属于集中式Baseline，不得与第8轮后的传统独立智能体Baseline混合统计。
