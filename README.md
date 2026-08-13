# 燕中生态治理仓库

本仓库是燕中生态跨项目治理、架构、契约、决策与阶段状态的唯一写入源，也可作为七个独立代码仓库的本地工作区父目录。主站提供唯一身份与内容真值，燕中 API 提供统一 AI API 网关、策略和账本，燕中 AI 提供会话、角色、知识、记忆与工作流；小程序、Lab 和 YCZX 产品通过稳定契约接入，不复制身份、账本或供应商逻辑。

“燕中”与 `yanchuaner` 均为生态 IP 和核心关键词；生态正式名称只使用“燕中生态 / Yanzhong Ecosystem”。`yanchuaner` 继续用于域名、账号、仓库、包和技术命名空间，不被改写或扩展为另一套生态名称。

## 当前状态

- 主站、API 与自主 AI Web 已形成真实身份、模型调用和逐主体账本链路。
- 跨系统语义、扩展、安全、计费、观测和开源治理已有文档基线。
- 九份跨系统契约与一份仓库注册表已有版本化 JSON Schema。
- Schema 的运行时接入、提供方/消费者契约测试、持久化计费终态和 AI 使用层模块化尚未完成。
- `repos.yaml` 登记七个项目的职责、数据权威、依赖方向与校验入口；项目阶段仍只在状态真值维护。
- 独立校验与完整工作区校验已经分离，治理仓 CI 不依赖克隆全部项目。

完成度、验收层级和当前风险只以 [阶段状态真值](docs/燕中生态项目关系.txt) 为准。

## 仓库

机器可读清单见 [`repos.yaml`](repos.yaml)。下列目录在完整工作区中是独立 Git 仓库，受根 `.gitignore` 排除，不使用 submodule，也不进入本仓提交历史。

| 目录 | 职责 | 当前阶段 |
| --- | --- | --- |
| `web_yanchuaner` | 主站、唯一身份源、成员、内容、活动与后台 | 生产身份源 |
| `api_yanchuaner` | 统一 AI API 网关、策略、路由、Key、计费、流水和审计 | 生产链路加固 |
| `ai_yanchuaner` | 自主 AI 使用层、Web/BFF、领域数据与工作流 | Preview 运行与模块化 |
| `mp_yanchuaner` | 主站在微信环境中的客户端适配器 | 设备联合验收待完成 |
| `lab_yanchuaner` | 教程、学习路径、项目展示与公开贡献入口 | 可发布内容站 |
| `yczx_code` | 通过统一网关工作的 CLI Coding Agent | 初始工程骨架 |
| `yczx_code_lab` | 学习、练习与实验仓库 | 活跃学习仓库 |

Forum、Birthday 与 App 仍是规划对象，不属于已交付项目。

## 开始使用

只维护生态规范：

```bash
git clone https://github.com/yanchuaner/yanzhong-ecosystem.git
cd yanzhong-ecosystem
make check
```

建立完整工作区：

```bash
make workspace-bootstrap
make workspace-status
make check-workspace
```

`workspace-bootstrap` 只克隆缺失项目，不覆盖已有目录；每个子仓库仍独立建分支、提交和发起 PR。具体模式与发布边界见 [治理仓运行规范](docs/governance-repository.md)。

## 架构入口

1. [愿景](docs/vision.md)
2. [生态架构](docs/architecture.md)
3. [跨系统契约](docs/contracts.md)
4. [架构审查](docs/architecture-review.md)
5. [演进路线](docs/roadmap.md)
6. [文档索引](docs/README.md)

开发任何仓库前先读根 [AGENTS.md](AGENTS.md)，再读目标仓库的 `AGENTS.md`。跨仓变更按 `api -> ai -> web/客户端` 的依赖方向设计和验收。

## 许可与来源

燕中自主代码与原创文档统一采用 [GNU Affero General Public License v3.0](LICENSE)。第三方代码、依赖、图片、字体、模型和数据保持各自许可证与归属。

- `api_yanchuaner` 是 [QuantumNous/new-api](https://github.com/QuantumNous/new-api) 的修改分发，保留其 AGPL、NOTICE、附加条款和可见署名。
- [Kirara AI](https://github.com/lss233/kirara-ai) 只作为 AI 使用层架构参考；当前不因参考关系宣称复制或衍生其源码。
- [LiteLLM](https://github.com/BerriAI/litellm) 是可替换的内网设施依赖，不定义燕中业务契约。

详细边界见 [上游、许可证与 IP](docs/upstream-and-ip.md) 和各仓库来源清单。

## 参与与安全

- [贡献规则](CONTRIBUTING.md)
- [行为规范](CODE_OF_CONDUCT.md)
- [安全策略](SECURITY.md)
- [项目标识政策](TRADEMARKS.md)
- [开源治理](docs/open-source-governance.md)
- [开发环境](docs/development-environment.md)

不得在 Issue、PR、日志、截图或测试数据中提交真实密钥、Cookie、用户资料、对话、知识原文、数据库、上传文件或生产配置。安全问题按 [SECURITY.md](SECURITY.md) 私密报告。
