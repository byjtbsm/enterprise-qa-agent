# 第三题：企业知识问答 Agent

帮助员工查询企业制度，以当前读取的原文为依据回答；资料冲突时说明差异并追问，资料不足时返回缺口。

**交付状态：代码、离线测试、离线案例已完成；真实模型验收与 GitHub 推送尚未完成。** 当前没有模型凭据，因此仓库中的 `examples/mock/` 全部由确定性 Mock 实际运行生成，不能作为真实模型 ReAct 效果证据。本项目未宣称已满足真实模型验收要求。

## 评审入口

1. 需求和成功标准：[docs/01-requirements.md](docs/01-requirements.md)
2. 动态决策与工程取舍：[docs/02-solution.md](docs/02-solution.md)
3. 测试结果与验收映射：[docs/03-evaluation.md](docs/03-evaluation.md)
4. AI 使用和贡献边界：[docs/04-ai-usage.md](docs/04-ai-usage.md)
5. 复盘：[docs/05-retrospective.md](docs/05-retrospective.md)
6. 实际案例与 Trace：[examples/mock/summary.json](examples/mock/summary.json)
7. 自动测试结果：[examples/test-results.txt](examples/test-results.txt)

## 环境与安装

Python 3.10+，仅使用标准库；本次验证环境为 Python 3.12.14。无 Agent 框架，无运行或测试第三方依赖。以下命令在仓库根目录执行。

无需安装即可运行：

```bash
python scripts/run.py --mode mock --question "报销期限是多少？" --data data/normal.json
python -m unittest discover -s tests -v
python scripts/evaluate.py --mode mock
```

可选安装：`python -m pip install -e .`，随后可使用 `enterprise-qa` 命令。构建安装会需要 setuptools；离线环境优先使用上面的免安装入口。

## 真实模型运行

使用支持 Chat Completions 与 JSON object 输出的模型接口。`.env.example` 是配置说明，程序不会自动加载 `.env`。不要把密钥写入代码或运行记录。

Linux/macOS Bash：

```bash
read -rs -p "Model API key: " MODEL_API_KEY
export MODEL_API_KEY
export MODEL_BASE_URL="https://api.openai.com/v1"
export MODEL_NAME="你的可用模型名称"
python scripts/run.py --mode live --question "报销期限是多少？" --output examples/live/manual-conflict.json
python scripts/evaluate.py --mode live
```

Windows PowerShell：

```powershell
$secureKey = Read-Host "Model API key" -AsSecureString
$env:MODEL_API_KEY = [System.Net.NetworkCredential]::new("", $secureKey).Password
$env:MODEL_BASE_URL = "https://api.openai.com/v1"
$env:MODEL_NAME = "你的可用模型名称"
python scripts/run.py --mode live --question "报销期限是多少？" --output examples/live/manual-conflict.json
python scripts/evaluate.py --mode live
```

`MODEL_BASE_URL` 包含 `/v1` 或供应商要求的等效 API 前缀，程序追加 `/chat/completions`。超时默认每次 30 秒，可用 `MODEL_TIMEOUT` 修改；最多 10 个决策步骤（可调 1–50）。live 是 CLI 默认模式，配置缺失明确报错，绝不自动转为 Mock。

部分模型不支持该 JSON 模式，需在真实运行前确认；协议测试通过不等于供应商兼容性已验证。

## 其他可复制案例

```bash
# 两份制度冲突：读取 D01、D02 后请求确认，不按更新日期擅自选制度
python scripts/run.py --mode mock --question "报销期限是多少？"

# 改写问题：首次无命中，补充标准业务词后检索
python scripts/run.py --mode mock --question "垫付之后最迟何时能报账？" --data data/normal.json

# 上下文追问：历史用于理解问题，当前事实必须重新读取
python scripts/run.py --mode mock --question "期限是多久？" --history data/history.json --data data/normal.json

# 读取连续失败：应退出 1，输出 tool_error
python scripts/run.py --mode mock --question "报销期限是多少？" --data data/normal.json --fail-read 2

# 达上限：应退出 1，输出 incomplete
python scripts/run.py --mode mock --question "报销期限是多少？" --max-steps 1
```

退出码：0 = 已回答或已如实说明缺口/请求确认；1 = 工具失败、模型失败或达到上限；2 = 参数/环境配置错误。退出码 0 不代表有确定答案，须同时查看 `status`。

## 输出与 Trace

输出 JSON 包含 `mode`、`model`、问题和历史、任务状态、答案、引用文档 ID 与原文、资料缺口、步骤数和工具次数。每步记录动作、参数、公开的简短依据及观察结果，下一条动作即后续动作。不要求或保存模型内部思维过程。小型合成资料直接记录完整工具结果，便于核查。

状态：`answered`、`needs_clarification`、`insufficient_evidence`、`tool_error`、`model_error`、`incomplete`。

## 目录

```text
src/enterprise_qa/   Agent、模型接入、检索与读取工具、CLI
scripts/            免安装入口、案例评估脚本
tests/              自动测试与本地 HTTP 协议测试
examples/           实际输入输出、Trace、测试结果
data/              带 ID、版本、适用范围的合成制度与对话历史
docs/              五份要求文档和提交说明
```

## 提交前仍须完成

接入真实模型，运行 `python scripts/evaluate.py --mode live`，人工核验至少两种依据工具结果调整动作的实际路径，并复核所有验收场景。评估脚本自动统计状态匹配率，**不能替代答案语义与冲突处理的人工核验**。

将代码推送到自己可提交的 GitHub 仓库后，提交题号 3、真实 GitHub URL 和 `git rev-parse HEAD` 的输出。当前不编造远程仓库 URL。具体命令见 [docs/06-submission.md](docs/06-submission.md)。
