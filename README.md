# 第三题：企业知识问答 Agent

基于合成企业制度的可追溯问答项目。模型自主选择检索、读取原文、改写检索、追问或结束；工具观察逐轮反馈，运行时校验引用并限制执行步数。

**从运行到 GitHub 提交的详细中文教程：[docs/06-submission.md](docs/06-submission.md)。**

本交付版本已实现完整代码、模型配置入口、验收脚本、离线与真实模型两套 GitHub 工作流，以及提交前检查。当前制作环境没有模型凭据，已实测 **53 项自动测试通过、11/11 组离线场景通过**；未声称已经完成外部真实模型验证。接入你有权使用的模型后，脚本会实际生成真实 Trace，检查通过后再提交。

## 评审入口

| 材料 | 入口 |
|---|---|
| 用户、范围、成功标准 | [01-requirements](docs/01-requirements.md) |
| 动态决策、工具职责、技术取舍 | [02-solution](docs/02-solution.md) |
| 验收映射、结果与限制 | [03-evaluation](docs/03-evaluation.md) |
| AI 辅助与个人贡献边界 | [04-ai-usage](docs/04-ai-usage.md) |
| 失败、修改、学习和后续计划 | [05-retrospective](docs/05-retrospective.md) |
| Windows 与 GitHub 操作教程 | [06-submission](docs/06-submission.md) |
| 理解代码与答辩提示 | [07-walkthrough](docs/07-walkthrough.md) |
| 人工核验记录填写方式 | [08-personal-record](docs/08-personal-record.md) |
| 实测离线报告与 Trace | [examples/mock/REPORT.md](examples/mock/REPORT.md) |
| 实测自动测试输出 | [examples/test-results.txt](examples/test-results.txt) |
| 真实运行记录位置 | [examples/live/README.md](examples/live/README.md) |

## 快速运行

Python 3.10+，运行与测试均无第三方依赖。本次本地验证为 Python 3.12.14；GitHub 离线 CI 配置覆盖 3.10 和 3.12，须实际推送后才能确认远程结果。

在项目根目录执行：

```bash
python scripts/run.py --mode mock --question "报销期限是多少？"
python scripts/test.py
python scripts/evaluate.py --mode mock
```

默认资料包含 D01=30 天和 D02=15 天且没有优先级，应引用双方并请求确认。希望看正常回答：

```bash
python scripts/run.py --mode mock --question "报销期限是多少？" --data data/normal.json
```

可选安装 `python -m pip install -e .` 后使用 `enterprise-qa`；安装需要 setuptools，离线环境优先用免安装入口。

## 真实模型运行

先取得支持 Chat Completions 与 JSON object 输出的 API 地址、模型名和密钥，然后运行：

```bash
python scripts/configure.py
python scripts/evaluate.py --mode live
```

配置向导隐藏密钥输入并写入本地 `.env`；live 模式自动读取它，系统环境变量优先。`.env.example` 说明变量含义，Mock 不需要任何配置。API 地址必须包含供应商要求的 API 前缀，例如 `https://api.openai.com/v1` 或 `https://api.deepseek.com`；模型名以你自己的平台当前可用列表为准。程序追加 `/chat/completions`。

评估执行全部 11 个场景，包含两组资料变更测试。每次 live 运行保留到新的 `examples/live/<UTC时间>/`，包含实际输入、原文快照及哈希、模型响应 ID/用量（供应商返回时）、输出、Trace、检查结果和 REPORT.md。自动生成 `examples/live/LATEST.md` 指向最新报告；不会覆盖旧的失败结果。

单次模型请求默认超时 45 秒，每个场景最多 10 步；无凭据或接口失败不会悄悄切换为 Mock。真实调用会消耗你配置的 API 额度。

## 提交前检查

```bash
python scripts/audit.py
python scripts/audit.py --require-live
```

完成真实记录的人工语义核验后，按 [个人记录说明](docs/08-personal-record.md) 填写，再执行：

```bash
python scripts/audit.py --require-live --require-personal
```

自动检查覆盖格式、引用原文、关键事实、冲突双方、失败观察、步数、两条不同执行路径和资料变更。它不能证明所有答案语义正确，也不能替候选人证明个人贡献。

## CLI 参数与输出

`--mode live|mock`（默认 live）、`--question`、`--data`、`--history`、`--output`、`--max-steps`、`--fail-search`、`--fail-read`。

输出含：模式、模型名、问题与历史、状态、答案、引用 ID/原文、资料缺口、步骤、工具次数、模型调用元数据和 Trace。每步含动作、参数、公开的短操作依据和观察；下一步记录体现后续动作。不记录模型内部思维过程。

状态为 answered、needs_clarification、insufficient_evidence、tool_error、model_error、incomplete。

退出码：0=已回答或已明确追问/说明资料不足；1=模型/工具失败、上限未完成或验收不通过；2=配置/参数错误。退出码 0 不代表一定有答案，应看 status。

## 工程结构

```text
src/enterprise_qa/   原生 Agent 循环、模型接入、工具、配置和 CLI
scripts/            运行、配置、测试、评估、审计、生成提交信息
tests/             运行时与本地 HTTP 伪服务测试
data/              合成制度、变更制度、历史、个人记录样例
examples/          实际输出、工具观察、Trace、评估报告
docs/              要求文档与中文操作教程
.github/workflows/  离线 CI 与手动触发真实模型验收
```

## GitHub 交付

该题选择 CLI，无需额外服务器或 GitHub Pages。推送源代码和证据到 GitHub，确认评审可读后提交题号、URL 和最终 SHA。

普通推送触发 Offline CI，不使用密钥、不调用真实模型。手动触发 Live model acceptance 才使用你配置的 Secret 调用模型，并把实际结果提交回仓库；失败结果也保留。

本项目没有多 Agent、前端、生产鉴权或向量库；采用标准库和原生动作协议，便于在有限时间内实现与解释。
