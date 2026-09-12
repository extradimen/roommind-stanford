# G5 程序定位证据开发复核 v3（仅本地冻结）

与v2完全相同的48案例和消息。模型只返回message_id、原文唯一quote和relevance；
本地程序从冻结消息派生speaker_id及Unicode start/end。未知消息、非精确/非唯一quote、
重复引用仍拒绝。输出上限由4096调到8192，以处理v2的37次长度耗尽；这属于新协议，
不是对v2结果补跑或覆盖。

本地输入摘要将在inputs.json中自证。当前 `external_execution_authorized=false`，真实调用0。
再次外发前须具体授权v3的48项请求。无独立参考标签，未来格式完成率不等于准确率。
