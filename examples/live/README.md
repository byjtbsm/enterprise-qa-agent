# 真实模型记录

本交付制作环境没有可用模型凭据，未提供伪造的真实模型结果。

执行 `python scripts/evaluate.py --mode live` 或手动运行 GitHub 的 Live model acceptance 后，将生成独立时间目录，并创建 LATEST.md 指向最新报告。每次失败也保留，不覆盖旧记录。

每个时间目录包含 11 场景的实际结果（遇模型故障时未执行场景明确标注）、原文快照、哈希、检查汇总与 REPORT.md。自动通过后仍须人工核验并填写个人记录。
