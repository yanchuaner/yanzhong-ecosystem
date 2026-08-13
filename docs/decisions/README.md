# 生态决策记录

这里登记影响跨仓库架构、数据边界、许可或运营方式的决策。仓库内部的小决策不在此记录，写进对应 PR 即可。

## 记录规则

- 文件名：`NNNN-短横线标题.md`，`NNNN` 为递增序号。
- 每篇包含：背景、决策、理由、代价与回滚方式。
- 决策生效后，同步更新 `docs/燕中生态项目关系.txt` 或对应文档，避免状态真值滞后。
- 已有决策被推翻时，新开一篇记录，不直接改写历史决策。

## 已登记决策

- [0001：统一 AI API 网关与模块化平台边界](0001-unified-ai-gateway-and-modular-platform.md)
- [0002：自主内容统一采用 AGPL-3.0](0002-agpl-3-license-policy.md)
- [0003：燕中生态 IP、正式名称与技术命名分层](0003-ecosystem-naming.md)
- [0004：独立治理仓与多仓工作区布局](0004-governance-repository-and-workspace-layout.md)
