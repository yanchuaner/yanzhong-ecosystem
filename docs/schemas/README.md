# 燕中生态 Schema

本目录是跨仓机器可读契约的 v1 基线，使用 JSON Schema Draft 2020-12。语义说明见上级 `contracts.md`，扩展、计费和观测规则分别见 `extensions.md`、`billing-and-ledger.md` 与 `observability.md`。

## 当前状态

| Schema | 所有者 | 状态 | 迁移说明 |
| --- | --- | --- | --- |
| [error-envelope.v1.schema.json](error-envelope.v1.schema.json) | 生态公共 | 目标基线 | 现有 API 错误尚未全部迁移 |
| [identity-event.v1.schema.json](identity-event.v1.schema.json) | `web_yanchuaner` | 语义已实现，schema 待接入 | 当前签名事件需增加提供方与消费者合同校验 |
| [capability.v1.schema.json](capability.v1.schema.json) | `api_yanchuaner` | 目标基线 | capability catalog 尚未发布 |
| [message-envelope.v1.schema.json](message-envelope.v1.schema.json) | `ai_yanchuaner` | 目标基线 | 现有 Web 消息需迁移，不能声明为当前内部格式 |
| [workflow-manifest.v1.schema.json](workflow-manifest.v1.schema.json) | `ai_yanchuaner` | 目标基线 | 版本化工作流运行时尚未实现 |
| [extension-manifest.v1.schema.json](extension-manifest.v1.schema.json) | 生态公共 | 治理基线 | 外部插件执行未开放 |
| [billing-event.v1.schema.json](billing-event.v1.schema.json) | `api_yanchuaner` | 目标基线 | 持久化 Request 状态机尚未完成 |
| [telemetry-event.v1.schema.json](telemetry-event.v1.schema.json) | 生态公共 | 目标基线 | 统一 trace 与事件导出尚未贯通 |
| [repository-registry.v1.schema.json](repository-registry.v1.schema.json) | 生态治理 | 已接入 | `repos.yaml` 由治理校验器强制校验 |

`common-defs.v1.schema.json` 只提供共享定义，不作为独立业务消息。

## 版本规则

- 文件名和 `$id` 固定主版本；v1 内新增可选字段需要同步更新 schema 与合同 fixture。
- 删除、改名、改变含义、收紧已有合法取值或改变默认权限时发布 v2。
- 业务事件允许未知可选字段，消费者忽略不认识的字段并按已知字段处理。
- 扩展清单属于安全输入，未知字段默认拒绝；扩展清单增加字段时先更新宿主，再发布使用该字段的分发物。
- Schema 只验证结构，不能替代身份签名、owner 授权、状态机、幂等、价格或业务不变量检查。

## 使用方式

提供方在写出响应或事件前用对应 schema 校验 fixture；消费者在 CI 中校验同一 fixture，并测试未知可选字段、缺失必填字段和不支持主版本。生产热路径是否逐条运行完整 JSON Schema 由服务性能与类型系统决定，但边界输入仍须执行等价校验。

引用使用相对文件名，便于单仓复制到生成工具；正式发布后 `$id` 对应的 `https://schemas.yanchuaner.cn/ecosystem/v1/` 地址应提供不可变内容。该域名尚未发布前，以本目录 Git 内容为真值。

从治理仓根目录准备依赖并校验：

```bash
make setup
.venv/bin/python docs/schemas/validate.py
```

治理仓依赖由带哈希的 `requirements.txt` 固定。脚本总是检查 JSON、`$id` 与本地 `$ref`；完整 Draft 2020-12 正例/负例验证需要 `jsonschema` 与 `referencing`，缺少它们时以退出码 2 明确报告，不静默跳过。`fixtures/invalid/` 中的文件必须持续被对应 schema 拒绝。

## 变更门禁

1. 更新语义文档和 ADR，列出提供方与消费者。
2. 修改 schema，并添加有效、无效和兼容 fixture；运行 `validate.py`。
3. 提供方先兼容新旧格式，消费者随后迁移。
4. 在隔离环境验证 HTTP、SSE、事件签名、重试和错误映射。
5. 通过观测确认旧版本无消费者后再删除兼容实现。

不得把供应商、New API、LiteLLM 或平台 SDK 的原始对象直接登记为燕中 Schema。
