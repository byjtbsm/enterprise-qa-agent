# 03 效果验证

## 当前实测结论

Python 3.12.14 环境中，34 个 unittest 测试方法全部通过；独立场景评估 11/11 的可观察检查符合预期。**这些数字仅属于 Mock 流程、运行时约束和本地 HTTP 协议测试，不代表真实模型准确率。**

测试终端输出：[`../examples/test-results.txt`](../examples/test-results.txt)。
场景状态汇总：[`../examples/mock/summary.json`](../examples/mock/summary.json)。
模型未配置结果：[`../examples/live-unavailable.json`](../examples/live-unavailable.json)。本制作快照没有真实模型 Trace，没有真实模型 ReAct 达标结论。后续实际记录见 [真实运行目录说明](../examples/live/README.md)，执行后 LATEST.md 指向最新真实报告。

## 验收点与实际结果

下表链接均为脚本实际执行产生的 JSON，包含输入、历史、完整输出、动作参数、观察、简短操作依据及后续动作。每个文件中 mode=mock，模型名明确为 deterministic-offline-fixture-v1。

| 场景 | 预期与本次实际结果 | 运行记录 |
|---|---|---|
| 明确答案 | answered；D01 30 天，附原文 | [01_normal](../examples/mock/01_normal.json) |
| 文档冲突 | needs_clarification；引用 D01/D02，说明 30/15 天差异 | [02_conflict](../examples/mock/02_conflict.json) |
| 资料外问题 | insufficient_evidence；没有停车位分配依据 | [03_out_of_scope](../examples/mock/03_out_of_scope.json) |
| 改写相似问题 | 首次无命中，补查“报销”，answered | [04_paraphrase](../examples/mock/04_paraphrase.json) |
| 上下文追问 | 基于历史补查并重新读取 D01，answered | [05_follow_up](../examples/mock/05_follow_up.json) |
| 检索一次失败 | 观察失败后再尝试，answered | [06_search_recovery](../examples/mock/06_search_recovery.json) |
| 读取持续失败 | 两次读取失败，tool_error，未输出伪造引用 | [07_read_failure](../examples/mock/07_read_failure.json) |
| 上限 | max_steps=1，incomplete | [08_step_limit](../examples/mock/08_step_limit.json) |
| 背景缺失 | needs_clarification，请用户说明制度或事项 | [09_missing_context](../examples/mock/09_missing_context.json) |
| 原文替换 | D01 改为 45 天，answered，答案与引用同步改变 | [10_document_changed](../examples/mock/10_document_changed.json) |
| 冲突消除 | D02 与 D01 相同，读取双方后 answered | [11_conflict_resolved](../examples/mock/11_conflict_resolved.json) |

## 测试内容

除上表外，测试覆盖：修改 D01 后答案和 quote 改为 45 天；消除 D01/D02 差异后改变终止状态；不依据日期擅自选择制度；未知工具拒绝；非法动作有界退出；未读取/伪造引用拒绝；校验失败后可以修复；失败读取不能成为证据；证据不跨运行复用；历史不是原文证据；模型异常不暴露异常消息；配置缺失不自动切换 Mock。

HTTP 适配器测试使用本地伪服务核验请求路径、JSON 格式和响应解析。该测试不调用真实模型，不计入模型效果验证。

## 开发中发现的失败与修改

第一次测试中，“期限是多久？”在无历史时被宽泛检索匹配到报销，返回冲突而非明确追问事项。补充 Mock 的背景缺失夹具行为，并放宽“无原文时的澄清”引用要求：有答案必须引用，已读取证据后的冲突追问必须引用，无资料时询问问题背景可以没有引用。随后重新运行全量测试通过。

这只修复并验证离线夹具和运行时约定；不证明 live 模型一定能正确处理省略问题。真实模型需特别核验该用例。

## 真实模型待执行方案

1. 运行 configure.py 配置模型，或使用环境变量/GitHub Secret 与 Variables。
2. 执行 `python scripts/evaluate.py --mode live`，生成独立 `examples/live/<时间目录>/`；若状态不符，脚本退出 1，保留原始失败记录。
3. 人工核验每条引用是否支持答案、冲突是否完整呈现、是否有无依据推断、下一步是否回应了工具观察。
4. 特别检查至少两条不同实际路径：正常回答和冲突追问；同时检查改写检索及工具失败。
5. 用修改后的资料重新执行，保存到另一个输出目录，核验回答和动作变化。原始失败 Trace 应保留，以便在复盘中解释修改效果。

当前评估脚本检查状态、引用逐字存在、关键期限、冲突双方、故障观察、步骤上限及两条不同工具观察路径。不能以 `11/11` 替代引用语义质量、召回率、模型稳定性、成本或延迟评估。不能为了达标把 live 模型失误改写为预设日志。

## 已知限制

- 未调用真实模型，尚缺真实决策效果证据。
- 检索为字符匹配、最多返回 8 条；可能漏召回，无法保证全库无冲突。
- 引用逐字校验不等于答案蕴含校验。
- Mock 根据少量固定业务词和保守正文比较模拟动作，不具备真实语言理解能力。
- 无生产级鉴权、文档访问控制、长对话压缩和复杂故障恢复。系统提示包含不可信资料边界，但未证明能抵御所有提示注入。
- 故障注入为合成业务工具故障；真实模型接口仅完成本地协议测试。

## 新增工程验证

完整 HTTP 伪服务循环测试确认：后续请求携带前轮真实工具观察；响应元数据可以逐步保存。另测了 401 分类、工具抛异常后的明确停止、配置不执行命令、不泄露错误值、非法数据/历史形状，以及审计拒绝把 Mock 当 live。伪服务仍不是模型效果证据。

审计会比较当前代码/资料摘要与真实运行摘要；模型源码或制度改动后必须重跑。个人记录与文档改动不影响摘要。最终 submission.py 检查仓库无未提交改动且远程 main 与本地 HEAD 一致；实际 GitHub 推送尚需账户登录。
