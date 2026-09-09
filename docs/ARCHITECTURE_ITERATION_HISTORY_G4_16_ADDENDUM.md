# Architecture iteration history addendum: G4.16

This additive record preserves the checksummed pre-G4.16 history file unchanged.

## 第53轮：G4.16共享模拟执行与可恢复证据治理候选

**目标：** 将“角色声称已经执行”替换为可验证的内部模拟动作，同时修复原批次恢复实际会创建
新会话重跑、评价无法区分真实回执与模型仿写文本、多受话人只识别单一对象等基础设施缺口。

**机制：** Baseline和RoomMind获得相同无外部副作用的内部世界、操作合同和公开回执；只有
RoomMind可在普通权限约束下把成功回执投影进类型化任务状态。服务端登记表与公开原文精确匹配
后才向六维评价提供回执侧栏。持久化响应队列维护有序受话所有权；批次恢复保留原会话并校验
已提交轮次。场景、角色、世界和调度规则逐项哈希，总哈希绑定研究清单。

**研究边界：** world-v1/v2继续保留，world-v3移除三个非实时场景中的空执行接口，只在事故
响应中启用动作。四个源场景均为反复使用的开发集，G4.16只能作为两次重复的筛选实验，不能
作为确认性证据。完整本地及在线门槛见`docs/EXPERIMENT_G4_16_LOCAL_PREQUALIFICATION.md`。
