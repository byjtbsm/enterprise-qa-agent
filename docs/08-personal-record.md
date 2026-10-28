# 个人验证与贡献记录

复制 `data/personal-record.example.json` 为 `data/personal-record.json` 后据实际情况填写。此文件不含密钥，应提交进仓库。

| 字段 | 填写要求 |
|---|---|
| actual_minutes | 你本人实际投入的分钟数，不能照抄 AI 制作用时 |
| personal_changes | 个人改动了什么；若没有改核心代码，可以如实写未改核心代码并说明所做工作 |
| personal_verification | 自己执行的命令、核查文件、观察到的结果与失败 |
| learning | 对动作循环、引用校验或失败处理的真实理解与收获 |
| reviewed_live_run | 实际人工核验的目录，相对项目根目录，例如 examples/live/你的真实运行目录 |
| semantic_review_completed | 只有完成逐条语义检查后才设为 true |

同时在 docs/04-ai-usage.md 和 docs/05-retrospective.md 记录候选人自己的贡献和复盘。自动审计检查填写状态，不能证明填写内容真实。

建议至少逐条检查：正常答案受原文支持；冲突引用完整且未擅自选答案；资料外问题未编造；改写检索有效；追问结合历史；失败后没有假定成功；资料替换后答案与动作变化。
