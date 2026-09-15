# G5 报告契约v2：未决分母与分析元数据

本包只处理本地报告和显式新版本，不启动研究，不改写任何旧manifest/源/标签/预测。
`panel.json` 内容摘要：`9b6759579549acc521b86995c9dc1d09223da934985dae425adee81dbac653d4`。
真实模型调用0；全部判断/评分为合成工程证据，不认证真实误报率或研究优势。

## 旧工件兼容

读取已有24例校准panel及评分控制panel，逐项重算v1校准报告与v1分析计划，完全一致。
工件保留输入文件字节哈希及原始内容摘要。新v2轨迹为独立合成测试，没有把旧源修改
后冒充新计划证据；旧文件未覆盖。新校准报告保留legacy_report_sha256。

## 校准v2

新入口 `app.g5.calibration_bounds.report(annotation, results)`；原
`app.g5.calibration_bridge.report` 仍返回原v1语义。新入口先全量验证来源/参考/预测，
再给overall及family/dimension/category/reference_sources各层增加reference_strata。

每个参考clear/violation层保留总数N、明确预测、错误E、未决M及missing/technical_failure/
abstain拆分。可能补为二元判断的错误比例界为 `[E/N, (E+M)/N]`，不是置信区间。
N=0为null；N>0且全部未决为[0,1]。参考awaiting/disputed/uncertain/NA保留在全部分母，
不伪造为clear或violation。弃权的实际成本及未知参考真值不由此界推断。

| 原脚本参考层 | N | 明确预测 | 未决 | 条件错误率 | 可能二元错误比例界 |
|---|---:|---:|---|---:|---|
| clear | 10 | 7 | 技术失败3 | 0 | [0, .3] |
| violation | 9 | 3 | 缺失3、弃权3 | 0 | [0, 2/3] |

其余5例参考未决/不确定/NA，全部24例仍保留。各分层轴重叠，不能相加当独立样本。
全部失败尝试保留；重试链、完成/弃权不可覆盖仍由旧验证器校验。

## 分析元数据v2

显式 `freeze_analysis(config, version=2)`，由verify_analysis按schema重算。默认version=1
保持旧哈希。v2顶层interval与config的实际方法一致，报告schema也为v2并带interval_method。
bootstrap的resamples_role为used；Hoeffding为unused-retained-config-field，说明保留旧
config形状/验证要求不是实际执行了重采样。v1顶部历史bootstrap字符串不追溯改写，其实际
方法仍由config/interval_status解释。

新plan哈希不同，必须在生成前重新绑定新design的analysis/common-evaluator字段；旧
manifest不能临时换上v2。相同配置的新旧数值结果一致，重算哈希的错误方法字段仍被拒绝。
适配器、评分索引、独立SQLite评价归档/重连及release源校验均验证显式v2。

新合成四组全六维归档25条尝试：1技术失败+24完成，全部原始请求/响应和完整源保存。
家族数不够时区间仍不返回，metadata正确不等于资格通过。

## 验收与剩余门

集中回执：`docs/G5_LOCAL_ACCEPTANCE_20260912_REPORT_CONTRACTS.json`。
本包补齐两个报告工程门；真实校准集、家族框架、主要阈值/样本量和服务验收仍未完成。
研究决定登记仍是draft_not_executable，不沿用旧批次授权外发/部署/招募评审。
下一完整本地包：校准材料登记模板、家族派生/暴露记录和可审阅材料包，区分synthetic/
assistant/真实人类来源，确认家族不能因改ID被当作未见。

最终303项G5 + 9项契约 = **312项通过**，100.042秒，包含本机SQLite/PostgreSQL；
无错误/失败/跳过/预期失败，源码/测试前后稳定，编译/JSON/差异检查通过。
验收摘要 `ce28fccd624beb7de848c2bd6b2d252c8673fdf22739125ce0cbb0c51c7f8f06`。
本包完成，验证进程退出；不是实际研究通过或线上运行状态。
