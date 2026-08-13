# 燕中生态跨系统契约

本文定义跨仓库稳定契约的最低要求。具体字段由各服务的 OpenAPI、JSON Schema 或类型包维护；本文件定义所有者、语义、版本和兼容规则。

首批机器可读基线位于 `schemas/`。Schema 状态和现有实现迁移规则见 `schemas/README.md`；Markdown 示例不能替代 schema 校验。

## 契约规则

- 对外 HTTP API 使用路径主版本，例如 `/api/ecosystem/v1/...`；已发布的 `/api/yancore/...` 和 `/v1/...` 在迁移期视为 v1。
- 事件使用 `type` 与 `schema_version` 独立版本。新增可选字段属于兼容变更；删除、改名、改变含义或收紧已有取值必须升主版本。
- 时间使用 UTC RFC 3339；金额不使用浮点数；额度使用整数最小单位并同时标注 `unit`。
- 主体使用主站不可变 `sub`；禁止以邮箱、用户名或本地数据库 ID 作为跨系统身份。
- 每次请求携带或生成 `client_request_id`、`request_id`、`trace_id`。这些标识不包含个人信息。
- 错误以稳定 `code` 判断，HTTP 状态表示类别，中文 `message` 只用于展示。
- 契约先于消费者合入；提供方维护 schema 与契约测试，消费者维护兼容测试。

## 通用信封

### 请求上下文

```json
{
  "schema_version": "1.0",
  "client_request_id": "01J...",
  "trace_id": "01J...",
  "application": "ai-web",
  "subject": "main-site-subject",
  "scopes": ["ai.chat"],
  "sent_at": "2026-08-13T12:00:00Z"
}
```

`subject` 只在可信服务端上下文中传播。浏览器不能通过自行填写该字段改变主体。

### 错误信封

```json
{
  "schema_version": "1.0",
  "error": {
    "code": "quota_exhausted",
    "message": "公益额度不足。",
    "retryable": false,
    "request_id": "req_...",
    "trace_id": "01J...",
    "details": {}
  }
}
```

稳定错误类别：

| 类别 | HTTP | 是否默认重试 |
| --- | ---: | --- |
| `invalid_request` | 400 | 否 |
| `unauthenticated` | 401 | 否 |
| `forbidden` | 403 | 否 |
| `not_found` | 404 | 否 |
| `conflict` | 409 | 否，先读取当前状态 |
| `rate_limited` | 429 | 按 `Retry-After` |
| `quota_exhausted` | 402 或兼容期 400 | 否 |
| `upstream_unavailable` | 502/503 | 仅幂等请求 |
| `timeout` | 504 | 仅幂等请求 |
| `internal_error` | 500 | 谨慎重试 |

现有接口尚未全部返回该信封。迁移期间消费者必须兼容旧格式，提供方不得把旧 `message` 文本当稳定代码。

## 身份契约

所有者：`web_yanchuaner`。

### OIDC 声明

| 声明 | 含义 |
| --- | --- |
| `sub` | 主站不可变主体 ID |
| `iss` | 主站签发方 |
| `aud` | 精确客户端 ID |
| `email_verified` | 邮箱验证状态 |
| `role` | `admin`、`alumni`、`student`、`teacher` |
| `session_version` | 可选，会话全局失效版本 |

客户端必须使用 Authorization Code + S256 PKCE、`state` 和 `nonce`。不同产品使用不同 client ID 与 Secret，不共享 Cookie。

### 身份事件

```json
{
  "schema_version": "1.0",
  "event_id": "evt_...",
  "type": "identity.account.disabled",
  "occurred_at": "2026-08-13T12:00:00Z",
  "subject": "main-site-subject",
  "data": { "session_version": 4 }
}
```

- 通过 HMAC 或后续非对称签名验证来源。
- 消费者按 `event_id` 幂等；乱序事件通过 `occurred_at` 和 `session_version` 判定。
- `account.disabled` 撤销所有 grant 与 Key；`sessions.revoked` 只撤销会话级凭据；`role.changed` 同步最小角色并撤销高权限会话。
- 投递采用 outbox 与重试；失败不能回滚主站已经完成的账号操作。

## YanCore 主体契约

所有者：`api_yanchuaner`。

YanCore 把主站主体转换为面向某个应用和受众的短期授权。核心语义：

```text
subject + application + audience + scopes + policy + expires_at
```

- grant 最长有效期由服务端上限约束；AI Web Preview 默认不超过 15 分钟。
- 会话应用 Key 只返回一次，服务端只保存哈希；Key 的权限不得超过 grant。
- grant 和 Key 的撤销必须可立即生效，不依赖浏览器 Cookie 自然过期。
- 消费者不得自行解析并信任未验证的 grant 字段。

现有端点与鉴权见 `api_yanchuaner/docs/yanchuaner/yancore-api.md`。

## 能力目录契约

所有者：`api_yanchuaner`；消费者：AI Web、YCZX Code、后续客户端。

目标目录项：

```json
{
  "id": "text.chat.general",
  "version": "1",
  "modalities": { "input": ["text"], "output": ["text"] },
  "streaming": true,
  "billing_unit": "token",
  "limits": { "max_input_bytes": 32768 },
  "availability": "preview"
}
```

- 稳定能力 ID 与供应商模型名分离。
- 过渡期允许公开模型别名，例如 `deepseek-v4-flash`；别名由网关解析，客户端不绑定渠道。
- 能力目录只暴露用户可理解的限制和状态，不暴露供应商密钥、内部渠道 ID、成本底价或管理员备注。

## 模型与能力调用契约

所有者：`api_yanchuaner`。

- 公网入口固定为 `https://api.yanchuaner.cn/v1` 及后续版本化燕中能力接口。
- 鉴权使用个人虚拟 Key 或受控应用会话 Key。
- 网关在进入供应商前完成主体、scope、能力、模型、预算、速率和并发检查。
- 流式响应必须保留标准完成/失败事件；取消、断连和上游完成分别记录。
- 响应返回 `request_id`，并在可用时返回标准化 usage；消费者不能以本地 token 估算替代最终账本。

## 计量与账本契约

所有者：`api_yanchuaner`。

请求状态机：

```text
accepted → reserved → dispatched → settled
                        ├────────→ refunded
                        └────────→ reconciliation_required
```

- `accepted` 后才可生成网关 `request_id`。
- `reserved` 是持久化预扣；没有预留不得向付费上游发请求。
- `settled` 记录标准化实际用量和差额；一次请求最多有一个最终状态。
- 上游明确未消费时进入 `refunded`；结果不确定时进入 `reconciliation_required`，不得静默当作成功或退款。
- 所有状态转换以 `request_id + operation` 幂等，并写只追加流水。
- `users.quota` 等余额列只作投影，可从流水核对，不作为审计真值。

资金来源至少区分：`public_benefit`、`campaign`、`legacy`、未来 `byok`。不同来源不得静默互相扣减。

完整状态、重试、流式、异步和对账规则见 `billing-and-ledger.md`。

## AI 消息信封

所有者：`ai_yanchuaner`；用于 AI 使用层内部和未来接入适配器。

```json
{
  "schema_version": "1.0",
  "message_id": "msg_...",
  "conversation_id": "conv_...",
  "sender": { "kind": "user", "id": "subject" },
  "parts": [
    { "type": "text", "text": "..." }
  ],
  "metadata": {
    "adapter": "web",
    "reply_to": null
  },
  "created_at": "2026-08-13T12:00:00Z"
}
```

首批 part 类型：`text`、`image_ref`、`audio_ref`、`tool_call`、`tool_result`、`error`。二进制内容使用受控引用，不直接嵌入跨服务事件。

## 工作流与能力块契约

所有者：`ai_yanchuaner`。

每个工作流必须记录 `workflow_id`、`version`、入口消息 schema、允许的块、默认超时和发布状态。每个块清单至少包含：

```json
{
  "id": "knowledge.retrieve",
  "version": "1.0.0",
  "input_schema": "schema://knowledge-query/v1",
  "output_schema": "schema://knowledge-hits/v1",
  "required_scopes": ["knowledge.read"],
  "side_effects": [],
  "billing": "none",
  "timeout_ms": 3000,
  "retry": "safe"
}
```

- 工作流版本发布后不可原地改变含义。
- 有副作用的块必须有幂等键和补偿说明。
- 付费块只能调用统一 API 网关并返回网关 `request_id`。
- 插件块不获得宿主全部环境变量，只获得声明并授权的能力句柄。

扩展清单、权限、隔离、生命周期和准入门禁见 `extensions.md`。

## 可观测性契约

所有服务输出结构化事件，最低公共字段如下：

| 字段 | 用途 |
| --- | --- |
| `timestamp` | UTC 事件时间 |
| `service`、`component` | 服务与模块 |
| `environment`、`version` | 环境与部署版本 |
| `trace_id`、`request_id` | 跨服务与模型调用关联 |
| `event`、`outcome` | 稳定事件名和结果 |
| `duration_ms` | 延迟 |
| `subject_hash` | 需要时使用不可逆主体标识 |
| `error_code` | 稳定错误码 |

禁止默认记录：Authorization、Cookie、grant、Key、供应商凭据、完整消息正文、上传原文、邮箱和手机号。

最低指标：请求量、成功率、P50/P95 延迟、SSE 中断、策略拒绝、预扣未终结数、退款数、对账积压、渠道健康、工作流块失败、身份事件积压。

标识层级、传播、采样、保留与告警规则见 `observability.md`。

## 契约变更流程

1. 在根 `docs/decisions/` 登记跨仓决策。
2. 修改本文件及提供方 schema/OpenAPI，列出消费者和兼容窗口。
3. 提供方先实现兼容读写和契约测试。
4. 按 `api → ai → web/客户端` 更新消费者。
5. 通过观测确认旧版本无调用后再移除。
6. 删除前保留回滚版本和数据迁移说明。
