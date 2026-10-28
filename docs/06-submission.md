# GitHub 提交操作

当前交付为本地项目包，含 Git 历史。没有远程 GitHub 仓库，也没有公开/私有仓库权限信息，因此没有自动推送。

先按 README 完成真实模型验证并补全个人贡献，然后在 GitHub 创建自己的空仓库。以下 `YOUR_ACCOUNT/YOUR_REPO` 为必须替换的占位符，不是已创建的仓库。

```bash
# 在项目根目录中执行；请先使用自己的 Git 提交身份
# git config user.name "你的名字"
# git config user.email "你的邮箱"
git add .
git commit -m "Verify live model traces and record personal contributions"
git remote add origin https://github.com/YOUR_ACCOUNT/YOUR_REPO.git
git push -u origin main
git rev-parse HEAD
```

如果已经添加 origin，用 `git remote set-url origin ...`。若把项目复制到自己的新仓库而没有保留 .git，先运行 `git init -b main`。

提交信息：

- 题号：3，企业知识问答 Agent。
- GitHub URL：填写自己实际推送成功的仓库地址。
- 最终 commit SHA：填写最后修改并推送后 `git rev-parse HEAD` 的完整输出。
- 私有仓库：按考核方提供的账号授予读取权限，不猜测评审账号。

请在最终提交对应的 commit 中保留所有文档、测试、输入输出和实际 Trace。不要把离线 Mock 标为真实模型，不要填入未经验证的个人贡献。真实密钥不要提交。
