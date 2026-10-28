# 实际执行报告

- 模式：`mock`；模型：`deterministic-offline-fixture-v1`
- 时间：2026-10-28T07:17:18.599545+00:00；运行前 HEAD：`aa9d5b695a7e7ac46c702c8d771044729d2a2061`
- 实际源码/资料 SHA-256：`badfb38f82a6784b7a55e0ebe5d726b0cde419e3a093dfc84bb3691420951998`（以此对应本次代码和资料）。
- 自动检查：11/11 场景通过。
- 两条不同工具观察路径：通过。
- 人工语义核验：尚未完成，自动通过不等于最终验收完成。

| 场景 | 预期 | 实际 | 自动检查 | Trace |
|---|---|---|---|---|
| 01_normal | answered | answered | 通过 | [查看](01_normal.json) |
| 02_conflict | needs_clarification | needs_clarification | 通过 | [查看](02_conflict.json) |
| 03_out_of_scope | insufficient_evidence | insufficient_evidence | 通过 | [查看](03_out_of_scope.json) |
| 04_paraphrase | answered | answered | 通过 | [查看](04_paraphrase.json) |
| 05_follow_up | answered | answered | 通过 | [查看](05_follow_up.json) |
| 06_search_recovery | answered | answered | 通过 | [查看](06_search_recovery.json) |
| 07_read_failure | tool_error | tool_error | 通过 | [查看](07_read_failure.json) |
| 08_step_limit | incomplete | incomplete | 通过 | [查看](08_step_limit.json) |
| 09_missing_context | needs_clarification | needs_clarification | 通过 | [查看](09_missing_context.json) |
| 10_document_changed | answered | answered | 通过 | [查看](10_document_changed.json) |
| 11_conflict_resolved | answered | answered | 通过 | [查看](11_conflict_resolved.json) |

## 失败检查


## 人工必须核验

- 答案是否被引用逐条支持，有没有添加原文没有的事实？
- 冲突是否说明差异并请求适用范围/优先级，是否擅自按日期选择？
- 下一步动作是否回应真实工具结果，失败后有没有假定成功？
- 替换资料后的回答与动作是否变化？
- 核查后填写 docs/08-personal-record.md，并记录真实个人投入。
