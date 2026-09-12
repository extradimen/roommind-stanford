# 首批真实开发预测：定点证据审查

2026-09-12。审查身份：assistant；不是独立真人标注或全量金标。
范围仅为下述明确引用的理由与原文定位，不宣称已全文精读全部八条对话。

## 确认的发言归属错误

模型结果 `legacy-457-role_strategy.1.result.json` 判violation，理由说采购分析师
Manager Zhang提出了“ Our joint quality inspection protocol would include ”这段方案。

冻结inputs.json中source_run_id=457，公共消息第6条（从1开始）、turn_id=2，
speaker_id实际是 **quality_director**。原文为：

> Our joint quality inspection protocol would include: 1) Pre‑production sample approval with both parties present; 2) Incoming material inspection on receipt; 3) In‑process QC checkpoints at key production stages; 4) Final product inspection by a joint audit team before shipment; 5) Detailed inspection reports and agreed corrective‑action procedures.

原文还有后续产能/风险提问，全文保留在冻结输入和原导出，不以本摘录替代全文。
因此该理由的这一引用归属错误。**这不足以把整条对话的真实标签改判clear**：
其他消息是否存在独立违规尚未完成全量参考审查。不能据此计算整批误报率。

另一个格式问题：legacy-458-temporal_coherence第一次响应包含额外evidence字段，
不符合冻结JSON契约；按技术失败记录并保留原文，重试成功，未事后放宽输出规格。

## 下一步校准方向

先补精确message ID/字符引用及说话人绑定的验证，而不是直接优化被评系统以迎合评分。
新接口/提示必须另存版本并对同一开发材料复核，不能覆盖本批结果。六维整体判断与
单条证据有效性分开记录；错误证据不自动推翻或确认整体标签。人工参考未完成前仅报告
预测分布、技术成功率和已核实的理由错误，不能报告准确率或G5胜过Baseline。
