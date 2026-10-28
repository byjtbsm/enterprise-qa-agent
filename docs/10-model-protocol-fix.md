# 模型响应协议兼容修复

用户真实运行在第 1 步正确 search 并获取 D01，随后第 2 步出现 model_invalid_response。原先错误处理同时吞掉 HTTP 外层 JSON、choices/message 结构、content 类型和动作 JSON 等差异，因此不能从旧日志断定是空内容或其他具体原因。摘要见 [reported-model-protocol-failure.json](../examples/reported-model-protocol-failure.json)。

修改包含：逐层解析并明确错误码；保留失败调用的 HTTP 状态、响应 ID、用量和结构诊断；仅剥离完整 JSON 代码围栏，不任意截取自然语言片段；不打印原始正文、密钥或模型内部思维。

依据 DeepSeek 官方文档，仅对 api.deepseek.com 的 deepseek-flash/deepseek-v4-pro 设置 thinking.type=disabled 和 max_tokens=4096，以使用本项目需要的 JSON 动作模式。其他供应商不发送这些专用字段。关闭 thinking 是协议适配选择，不是已经证明旧故障由 thinking 引起。

格式错误作为观察反馈模型，最多请求修复 2 次，所有尝试计入 max_steps；已成功的工具结果保留，不重复执行工具，不切换 Mock。预算耗尽或不可恢复错误明确未完成。格式恢复本身不能替代模型基于工具结果的 ReAct 决策。

新增 13 项协议测试，总计 53 项本地自动测试通过、11 组离线场景通过。本地 HTTP 伪服务验证了“检索成功→第 2 次响应为空→请求模型修复→读取→完成”的完整流程，不能代替真实模型重跑结果。

官方依据：

- https://api-docs.deepseek.com/guides/json_mode/
- https://api-docs.deepseek.com/guides/thinking_mode/

应用后先运行 scripts/test.py，再保存新的真实正常场景到与旧失败不同的输出文件；正常、冲突等场景稳定后执行完整 live 验收。原失败文件应保留，不应手改为成功。
