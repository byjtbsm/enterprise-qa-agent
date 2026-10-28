# 提前澄清问题修复记录

用户机器上的真实正常用例返回 needs_clarification，工具次数为 0，说明接口已经可用但模型没有查询原文。这是失败案例，不是正常验收通过。用户报告摘要见 [reported-early-clarification.json](../examples/reported-early-clarification.json)。

修复了提示的过度澄清倾向，并增加运行时约束：结束前至少观察一次工具结果；检索有候选时回答或追问前先读取原文；确定回答不能遗漏最近检索的未读候选。约束失败被反馈给模型，具体查询、读取和结论仍由模型选择，不预设 30 天答案。

新增 6 项回归测试，总计 40 项通过；11 组离线场景通过。此数字是补丁开发环境结果，外部模型的修复效果需要重新运行验证。用户机器此前的网络问题通过切换到独立安装的 Python、重建 .venv 并更新 API 密钥后已进入正常模型响应阶段。

应用补丁后执行 `python scripts/test.py`、`python scripts/evaluate.py --mode mock` 和 `python scripts/evaluate.py --mode live`，Windows 上应使用项目的 `.venv\Scripts\python.exe`，避免调用 Inkscape 自带的解释器。记录实际测试、真实输出和个人投入，不能只根据补丁开发环境的测试宣称真实模型已通过。

若仍提前追问，应保留完整失败 Trace 并继续修改，不能改写日志或强制填入预设答案。
