# G5 证据绑定开发复核 v2 结果

用户逐字授权将同8条内部公共对话再次发送给Ollama Cloud/gpt-oss:120b。
Mac单并发完成全部冻结任务；凭据仅从服务器根目录.env读入进程内存，未显示/落盘。
无推送、部署、重启、真人评审或正式研究。执行进程已退出，无后台任务。

- 48项均处理；90次请求；10项最终通过、38项最终技术失败。
- 通过项：7 violation、2 clear、1 abstain。这些不是参考标签或准确率。
- 所有失败均在2次上限后停止，未放宽协议或覆盖历史。
- 90次尝试：10 valid、37 incomplete_response、39 offset_quote_mismatch、
  2 speaker_mismatch、2 evidence_count。
- 25个失败尝试的消息ID/说话人/原文可在去掉模型偏移后唯一定位，涉及18个最终失败案例。
- 审计摘要：`3ced1eaeb2cf4251751384bc5917df9f3f9f6ebb896c2ea496c59f70c706948a`。

这证明v2严格门能阻止不可重放引用进入有效集，也证明让模型自行计算Unicode字符偏移
不是可靠接口。`incomplete_response`包含模型用尽4096输出token，不能当语义失败。
counterfactual唯一定位只作解析器诊断，不修改冻结v2结果。

本地后续v3改为模型选择message_id+精确唯一quote，由程序派生speaker/start/end；
同时把输出余量冻结为8192。它保留相同48案例和原消息，尚未获得外部执行授权。
即使v3格式成功，也仍需独立参考标注，不能直接报告误报/漏报或G5效果。
