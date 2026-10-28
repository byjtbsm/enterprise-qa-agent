# 从零运行、验证并提交 GitHub：Windows 操作教程

这道考核允许 CLI，并明确“不要求线上部署”。本项目采用 CLI；你需要把可运行代码、文档和实际证据提交到 GitHub，不用购买服务器，也不用配置 GitHub Pages。

请按主线 A 顺序操作。若本地网络无法调用模型，可改用后面的主线 B 在 GitHub 上运行真实验证。两条路线最终都要核验 Trace、补充个人记录、提交 URL 和最终 SHA。

## 1. 准备环境和项目

安装 Python 3.10 或以上版本及 Git for Windows：

- https://www.python.org/downloads/windows/
- https://git-scm.com/install/windows

安装 Python 时确保命令行能找到 Python；安装完成后重新打开 PowerShell，检查：

```powershell
python --version
git --version
```

如果电脑只有 `py` 能运行，可把教程中的 `python` 替换为 `py -3`。项目没有运行或测试第三方依赖，不需要先安装大型框架。

解压压缩包，建议路径为 `D:\Projects\enterprise-qa-agent`。这一层应直接看见 README.md、src、tests、scripts 等，不能只把 zip 文件上传到仓库。

打开 PowerShell：

```powershell
cd "D:\Projects\enterprise-qa-agent"
```

路径按你实际解压位置修改。后续命令均在这一层执行。

## 2. 先验证本地基础功能

```powershell
python scripts/test.py
python scripts/evaluate.py --mode mock
python scripts/audit.py
```

本交付版本预期：53 个测试通过、11 个离线场景通过，结构检查通过。结果保存在 examples/test-results.txt 和 examples/mock/REPORT.md。

实际体验两种行为：

```powershell
python scripts/run.py --mode mock --question "报销期限是多少？" --data data/normal.json
python scripts/run.py --mode mock --question "报销期限是多少？"
```

第一条应依据 D01 回答 30 天。第二条应引用 D01 与 D02 的差异，请求确认适用制度。这里明确为 Mock，只说明流程工作，不能替代真实模型决策验收。

## 3. 主线 A：配置并运行真实模型

准备你有权使用的模型 API 三项信息：

| 项目 | 含义 | 示例 |
|---|---|---|
| MODEL_BASE_URL | API 基础地址，包括平台要求的前缀 | https://api.deepseek.com 或 https://api.openai.com/v1 |
| MODEL_NAME | 账户实际可用且支持 Chat Completions JSON 模式的模型名 | 在你所用平台查看并填写，不照抄未知模型名 |
| MODEL_API_KEY | 对应 API 平台的密钥 | 只在自己电脑/自己的 GitHub Secret 中填写 |

本项目核对了 DeepSeek 官方 JSON 模式和 OpenAI Chat Completions 文档；具体账户模型权限和网络连通性仍由实际调用确认。不要把网页对话产品名称当作可用 API 配置。

执行：

```powershell
python scripts/configure.py
```

依次粘贴基础地址、模型名、密钥。密钥输入不会显示，这是正常情况。成功后产生本地 .env，程序会自动读取；该文件已经被 git 忽略。

如果需要修改配置，在自己电脑打开 `.env` 编辑。向导不会覆盖现有文件。已设置的系统环境变量会优先于 .env；如发现仍使用旧模型，检查相应环境变量。

然后执行真正的验收：

```powershell
python scripts/evaluate.py --mode live
```

本命令会实际调用模型，运行全部 11 场景，每个场景最多 10 步。执行需要时间并消耗对应 API 额度。每轮结束会显示 PASS/FAIL；模型请求失败后停止后续调用，其他未执行场景明确记为 not_executed。

成功时应显示 11/11 场景自动检查通过。打开 `examples/live/LATEST.md`，进入它链接的 REPORT.md 和各案例 JSON。

每次运行保存独立目录，旧失败不会覆盖。不要手改输出或 Trace 来让检查通过。如果失败，保留失败记录，查明原因、修改实现/配置后重新运行；若是实现问题，把报错和不含密钥的失败记录发给我可以继续修复。

## 4. 核验真实输出，并填写个人记录

重点查看 01_normal、02_conflict、03_out_of_scope、04_paraphrase、05_follow_up、06_search_recovery、07_read_failure、10_document_changed 和 11_conflict_resolved。

至少确认两条不同路径：

- 正常：模型根据检索结果读取 D01，根据原文回答 30 天。
- 冲突：模型读取 D01/D02，看到 30 天与 15 天后请求确认，没有擅自采用更新版本。

同时核验引用是否逐字存在、是否真的支持答案；工具失败后下一步是否调整；修改成 45 天时回答是否变化；消除冲突后是否可以回答。自动检查不等于这些语义判断已经完成。

创建个人记录：

```powershell
Copy-Item data/personal-record.example.json data/personal-record.json
notepad data/personal-record.json
```

把 null、空字符串和 false 改成你真实做过的事情；字段说明见 docs/08-personal-record.md。`reviewed_live_run` 填实际核验的目录，例如 `examples/live/20261028T080000000000Z`，必须替换为你自己生成的目录，不能照抄时间。

同时在 docs/04-ai-usage.md 的个人贡献表补充实际修改、执行和观察，并在 docs/05-retrospective.md 补充你的学习、失败和投入时间。可以如实写“主要代码由 AI 辅助生成，本人阅读、配置、验证并修改了……”。没做过的事情不要写成已完成。

然后执行：

```powershell
python scripts/audit.py --require-live --require-personal
```

检查通过后再进入提交步骤。如代码或合成制度改变，需重新运行真实验证；只填写个人记录或文档不会改变源码摘要。

## 5. 在 GitHub 建空仓库

登录 https://github.com ，打开 https://github.com/new 。

填写仓库名，例如 enterprise-qa-agent。公开或私有按考核要求选；私有仓库后续须让指定评审账号可读。创建空仓库时不要勾选新增 README、.gitignore 或 License，避免与已有历史冲突。

点击 Create repository，记住仓库地址，例如 `https://github.com/你的用户名/enterprise-qa-agent`。这里是占位形式，不是已经替你创建的仓库。

## 6. 把完整代码与证据推送到 GitHub

压缩包已带本地 Git 历史，通常不需要 git init。若解压工具没有保留 .git，先执行 `git init -b main`。

在项目目录设置你自己的提交身份。以下中文值必须替换：

```powershell
git config user.name "你的GitHub用户名"
git config user.email "你的GitHub邮箱或noreply邮箱"
git add .
git status
```

确认状态里包含源代码、docs、examples/live、tests 和 .github/workflows，但没有 .env。然后提交：

```powershell
git commit -m "Complete live verification and personal review"
git branch -M main
git remote add origin https://github.com/你的用户名/enterprise-qa-agent.git
git push -u origin main
```

若提示 origin 已存在，先查看 `git remote -v`；地址确需修改时使用：

```powershell
git remote set-url origin https://github.com/你的用户名/enterprise-qa-agent.git
```

Git for Windows 可能打开浏览器要求登录 GitHub，按提示登录并授权。不要把账号密码或 Token 写进仓库 URL。若出现 push rejected，先确认远程是不是空仓库，不要直接强制推送覆盖内容。

推送后刷新仓库网页，根目录应显示 README.md、src、tests、data、docs、examples、scripts，以及 .github 工作流，而不只是一个压缩包。

## 7. 查看 GitHub 自动测试

仓库网页点击 Actions → Offline CI，等待本次运行完成。它会分别在 Python 3.10 和 3.12 执行测试、离线场景和结构检查，保留实际结果供下载。

普通推送不调用付费模型，也不需要模型密钥。若首次需要启用 Actions，按页面提示启用。远程 CI 是否通过必须看你自己的运行结果，不能把本地通过等同于远程已通过。

## 8. 主线 B：可选，在 GitHub 上执行真实模型验证

如果已按主线 A 在本地生成并提交真实记录，可以跳过这一节。

先完成建仓库和首次推送。然后进入：

`Settings → Secrets and variables → Actions`

在 Secrets 标签页创建 Repository secret：

| 名称 | 值 |
|---|---|
| MODEL_API_KEY | 你的真实模型 API 密钥 |

在 Variables 标签页创建两个 Repository variables：

| 名称 | 值 |
|---|---|
| MODEL_BASE_URL | 平台 API 基础地址 |
| MODEL_NAME | 账户可用模型名 |

进入 `Actions → Live model acceptance → Run workflow`，选择 main 后触发。这个工作流只由你手动运行。默认分支中必须已经存在对应工作流，才会出现手动运行入口。

它会运行测试、实际调用模型、校验结果，上传运行证据，并把 examples/live 中的实际记录提交回你的仓库；失败记录也会保留。报告必须看到全部场景通过，并且你仍需按第 4 节人工核验。

如果保存证据时报写入权限不足，检查 Settings → Actions → General 中的工作流权限及 main 的保护规则。无法自动提交时，可从该次运行的 Artifacts 下载 live-evidence，按其中原有目录放回本地 examples/live，再手动提交。工作流失败不能解读为验收成功。

完成后在本地更新：

```powershell
git pull --ff-only
```

按第 4 节填写个人记录，再提交推送。GitHub Actions 通过 GITHUB_TOKEN 提交的证据不会再次触发普通 push 工作流；如需确认最终快照，可以手动运行 Offline CI。

## 9. 获取并提交最终信息

在所有代码、真实记录、个人记录都提交推送后：

```powershell
python scripts/submission.py
```

它会检查真实证据、个人记录、工作区是否有未提交修改，以及 GitHub 远程 main 是否与本地 HEAD 一致。通过后生成被 git 忽略的 submission.txt，包含题号、真实 GitHub URL 和最终 SHA。

也可以手动读取：

```powershell
git rev-parse HEAD
git ls-remote origin refs/heads/main
```

两个 SHA 应一致。最终向考核方提交：题号 3、你实际的仓库 URL、最终完整 commit SHA。后续再改代码/文档并推送，SHA 会变化，应重新生成提交信息。

私有仓库：在仓库 Settings → Collaborators 或对应访问管理中添加考核方指定的评审账号，并确认其已获得读取权限。不能猜测评审账号，也不能只说“已邀请”就认为已可读。

## 10. 可选图形化上传方式

不熟悉 git push 时可使用 GitHub Desktop：File → Add local repository，选择项目目录，再点击 Publish repository，确认仓库名和可见性。后续用 Commit 和 Push origin 提交改动。具体以 GitHub Desktop 当前界面为准。

不要把 API 密钥粘贴到提交说明、Issue、README 或代码中。GitHub Secret 只在你手动运行的真实验收工作流中使用。

## 常见问题

| 现象 | 含义与处理 |
|---|---|
| python 找不到 | 重开终端检查安装；也可尝试 py -3 |
| live requires MODEL_API_KEY and MODEL_NAME | 运行 configure.py，或检查环境变量是否为空 |
| invalid model endpoint | 基础地址为空、带了密钥/查询串或不是允许的 HTTP(S) 地址 |
| model_http_error_401/403 | 平台密钥或权限有问题；在平台核查，不要公开密钥 |
| model_http_error_404 | 检查 API 前缀和模型名；程序已追加 /chat/completions |
| model_http_error_400 | 检查模型是否支持 Chat Completions 和 JSON object 模式 |
| model_http_error_429 | 额度或限流问题，核查平台后重试 |
| model_connection_error | 网络/证书/超时问题；必要时改用 GitHub 手动验收 |
| model_invalid_response | 返回不是所需 JSON；检查模型模式和支持能力，保留失败记录 |
| audit 显示 source digest mismatch | 自上次 live 验证以来代码或资料改变了，重新运行 live |
| audit 找不到真实记录 | 只有 Mock 或 live 配置失败，不能直接提交达标声明 |
| Run workflow 不出现 | 检查工作流是否已推送至默认分支，Actions 是否启用 |
| submission 提示远程不一致 | 先拉取可能的工作流提交，再提交本地修改并推送 |

## 官方参考

- 建仓库：https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository
- 推送本地项目：https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github
- Actions Secret：https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets
- 手动运行：https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow
- DeepSeek JSON：https://api-docs.deepseek.com/guides/json_mode/
- OpenAI JSON：https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=chat
