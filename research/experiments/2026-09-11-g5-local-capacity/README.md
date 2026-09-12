# G5 本地完整请求容量夹具

仅合成工程验收，不是线上资格批次、真实模型先导或行为优势证据。

- 四组各 40 个事件、12 次显式重开，观察窗口为最新 2 条完整观察（JSON 字符上限 2048）。
- 完整注入请求/回执各限 100,000 canonical JSON UTF-8 字节；不是 token 配额或推荐配置。
- 模型、治理、反思、层级增量计划、向量和标注均为脚本返回，无真实外部调用。
- `synthetic-world.sqlite` 保留源数据库；`A/B/C/D-source.json` 是完整内部源快照；
  对应 `*-profile.json` 保留阶段 IO 与逐事件审计体积；`summary.json` 绑定摘要。
- 所有数据均保留；生成脚本拒绝已有输出目录，重跑必须使用新路径。

生成入口：`PYTHONPATH=server:server/tests .venv312/bin/python server/tests/test_g5_capacity.py --output-dir NEW_DIRECTORY`

四组最大请求均为 9,524 字节。A/B/C/D 源 JSON 分别为
357,514 / 4,157,231 / 437,190 / 4,236,907 字节。
B/D 完整认知状态随审计累积，不能据此宣称长期存储已解决，后续增量存储必须保持原文
和可恢复历史，不得回写这些记录。文件包含合成角色私有状态和内部审计，仍按内部资料处理。

summary SHA-256（协议 canonical JSON 内容摘要）:
`1070c3b3b4252e4be1aa1bb111ee8b900186eef4c2d0e2cf1b4d0314ece38213`
