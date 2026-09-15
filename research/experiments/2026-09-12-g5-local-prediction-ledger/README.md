# G5 固定预测适配器与持久化日志合成工件

`panel.json` 保存完整预测日志、固定模型规格、原始请求/合成回执、源绑定标注归档和
案例校准报告。4源/4案例，4个脚本预测clear对4个脚本一致clear参考。真实模型调用0，
不是真实误报率、模型有效性或资格通过证据。

内容摘要（去掉自身sha256后的canonical JSON）：
`e255fe3d95319e59ae75c98ea456dc70873a7e0f8b39ab31640bd366eea59789`。

新 `model_spec` 预测计划绑定模型/提供方/端点声明、提示摘要及可用的transport规格。
模型只接收dimension/rubric/context/turns；不包含case ID、参考标签、其他标注或裁决。
请求摘要、模型回执绑定、finish_reason、严格JSON和分类输出逐项校验。补充原始回执
留存，不将提供商声明当数字签名或真实调用的身份认证。

PredictionArchive单独SQLite日志先存started，再在事务外推理，最后事务保存finished；
桥接只把已完成回执纳入尝试，pending_indeterminate单列为未确定，不伪造技术失败。
技术失败可追加带前置摘要的重试；已完成含abstain不再调用、不覆盖。

定向验收包括坏回执/重复JSON键拒绝、固定规格漂移前无调用、超时重试、弃权终态、
中断保留pending、事务内真实进程退出回滚及完成后确认丢失恢复。显式恢复须由调用方
确认旧工作进程停止；没有worker租约，不可多worker并用或自动猜测旧请求未执行。
远端可能已执行但未保存回执，重推理可重复，不能保证exactly-once推理。

`prediction_archive.verify_export`重放整个日志，再由case桥接验原始输入/输出和分母。
旧无model_spec补充记录路径保持原语义，不追溯认证旧工件；所有G1–G4.16和之前G5
工件不修改。本工件不宣称24例/全六维规模性能验收，规模与完整发布审查仍待完成。
