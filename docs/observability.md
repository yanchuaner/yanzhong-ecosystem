# 燕中生态可观测性规范

本文定义身份、工作流、模型请求、计费和客户端操作如何关联。可观测性用于解释系统状态和费用，不以收集用户正文为代价。

## 标识层级

```text
client_request_id          one client intent and its retries
  `- trace_id              one cross-service operation
       |- workflow_run_id  one workflow execution
       |    `- step_id     one workflow step
       |- request_id       one paid gateway request
       |    `- attempt_id  one provider attempt
       `- event_id         one immutable domain/telemetry event

request_id -> ledger_entry_id / reconciliation_case_id
```

| 标识 | 创建者 | 稳定范围 | 用途 |
| --- | --- | --- | --- |
| `client_request_id` | 首个可信客户端/BFF | 同一用户意图的重试 | 幂等与重复提交 |
| `trace_id` | 生态入口 | 一次跨服务操作 | 分布式追踪 |
| `workflow_run_id` | AI 使用层 | 一次工作流运行 | 群聊、RAG、工具扇出 |
| `step_id` | 工作流运行时 | 一个步骤实例 | 顺序、重试和耗时 |
| `request_id` | API 网关 | 一次付费业务请求 | 策略、用量与账本 |
| `attempt_id` | API 路由层 | 一次供应商尝试 | 重试与故障切换 |
| `upstream_request_id` | 供应商 | 供应商范围 | 外部支持与对账 |
| `event_id` | 事件生产者 | 全局事件 | 幂等消费 |

标识使用随机、不含个人信息的值。邮箱、用户名、数据库自增 ID、模型提示或时间戳拼接值不能作为外部关联 ID。

## 传播

- HTTP 优先使用 W3C `traceparent`/`tracestate`；入口校验格式和长度，不盲目信任外部采样标志。
- `X-Yanchuaner-Client-Request-ID` 传播客户端幂等标识；服务端响应 `X-Request-ID` 和可公开的 trace ID。
- SSE 握手返回同一 trace/request，上游增量事件不生成新的业务 request ID。
- 队列、outbox 和 webhook 把 trace context 放入显式元数据，重试沿用原 event ID 并新增 delivery attempt。
- 日志、span、指标 exemplar、审计和账本使用相同 ID 名称，不创建 `reqId`、`requestId`、`rid` 等平行别名。
- 下游服务没有收到有效 trace 时生成新 trace，并记录 `trace.parent_missing`，不能拒绝正常业务。

浏览器只能提供 client request ID；主体、scope、账单 request ID 和可信 trace 属性由服务端生成。

## 结构化事件

最低公共字段：

```json
{
  "schema_version": "1.0",
  "event_id": "evt_01J...",
  "timestamp": "2026-08-13T12:00:00Z",
  "service": "ai-web",
  "component": "workflow.runtime",
  "environment": "preview",
  "version": "20260813-a1b2c3d",
  "event": "workflow.step.completed",
  "outcome": "success",
  "trace_id": "tr_01J...",
  "request_id": "req_01J...",
  "duration_ms": 842,
  "attributes": {}
}
```

规范 schema 位于 `schemas/telemetry-event.v1.schema.json`。事件名称使用稳定命名空间：

- `identity.*`：登录、回调、事件投递、撤销；
- `workflow.*`：运行、步骤、取消、降级；
- `capability.*`：发现、调用、拒绝、依赖失败；
- `gateway.*`：策略、路由、供应商尝试；
- `billing.*`：预留、结算、退款、待对账；
- `storage.*`：迁移、损坏、备份与恢复；
- `security.*`：越权、Secret、完整性和限流异常；
- `deployment.*`：发布、回滚和健康检查。

事件 schema 新增可选属性可兼容发布；改变字段语义或事件结果需要新 schema 版本。

## 日志、追踪、指标和审计

| 信号 | 回答的问题 | 数据特点 |
| --- | --- | --- |
| 日志 | 单个组件发生了什么 | 结构化、带上下文、有限保留 |
| Trace | 一次操作经过哪些服务和步骤 | 层级 span、耗时、错误和采样 |
| 指标 | 系统整体是否健康 | 聚合、低基数、适合告警 |
| 审计 | 谁在何时改变了安全或业务真值 | 不可变、权限受控、长期保留 |
| 账本 | 权益和费用如何变化 | 只追加、可重建、不得采样 |

日志不替代审计，Trace 不替代账本。管理员调额、策略修改、Key 撤销和插件启用即使正常成功也写审计；高频健康检查只进入指标与有限日志。

## Span 模型

一次 AI 群聊可产生：

```text
adapter.receive
  workflow.run
    scheduler.select
    context.assemble
      knowledge.retrieve
      memory.read
    capability.invoke (persona A)
      gateway.policy
      billing.reserve
      provider.attempt
      billing.settle
    capability.invoke (persona B)
    repository.commit
  adapter.send
```

span 名使用低基数操作名，角色 ID、模型别名、错误码等放属性；角色名、用户输入和完整 URL 不进入 span 名。付费请求 span 记录 `request_id`，供应商尝试记录 `attempt_id` 和允许公开的上游 ID。

## 指标

### 身份

- OIDC authorize/token/userinfo 成功率和延迟；
- 身份事件投递、重试、积压、最老事件年龄和撤销延迟；
- 非法回调、nonce/state/PKCE 拒绝和重复授权码。

### AI 使用层

- 工作流运行量、成功、失败、取消和降级；
- 每个稳定 workflow/block/capability ID 的 P50/P95 延迟；
- SSE 首段延迟、断流、取消和并发；
- RAG 命中、空结果、索引失败和上下文预算裁剪；
- Repository 错误、锁等待、schema 迁移和数据损坏。

### API 与账本

- 策略拒绝、额度不足、RPM/TPM/并发限制；
- 渠道健康、尝试次数、上游错误类别和故障切换；
- 预留、结算、退款、待对账、未终结预留年龄；
- 余额投影不一致、供应商用量缺失和价格版本缺失。

### 基础设施

- CPU、内存、磁盘、inode、连接池、队列、Redis、数据库和容器重启；
- 备份时长、大小、校验、离机复制和恢复演练结果；
- TLS 到期、镜像/版本漂移、健康检查和发布回滚。

指标标签只使用环境、服务、组件、稳定能力/工作流 ID、公开模型族、结果和错误类别等低基数字段。用户、request ID、会话 ID、原始 URL 和文件名不作指标标签。

## SLI 与告警

Preview 先定义 SLI，再按真实基线设定 SLO；没有观测数据时不编造百分比承诺。每个环境记录：

- 核心身份成功率与 P95 延迟；
- 首段输出和完整请求成功率；
- 付费请求终态完成率与最长未终结年龄；
- 身份撤销传播时长；
- 备份成功与最近一次恢复演练时间。

立即告警：账本无法预留、重复终态、负余额、Secret 泄漏迹象、身份事件长期积压、生产数据库不可用、磁盘即将写满、外部插件越权。

工作时段告警：P95 持续恶化、单渠道错误率上升、RAG 索引失败、备份失败、Open WebUI/LiteLLM 内部端口暴露检查失败。

信息事件：新部署、配置版本变化、扩展启停、计划内恢复演练。

## 脱敏与数据分类

禁止默认记录：

- Authorization、Cookie、grant、Key、Secret、私钥和完整请求头；
- 消息正文、系统提示、知识片段、记忆、上传内容和供应商完整错误体；
- 姓名、邮箱、手机号、学校账号、IP 全值和精确位置；
- 用户自配服务地址中可能包含的凭据与查询参数。

需要关联主体时使用服务内 ID 或定期轮换盐的不可逆 `subject_hash`，并限制跨环境关联。IP 仅在安全与限流确需时按受限保留期保存；普通产品分析使用截断或分桶。

内容级调试只允许隔离环境和合成数据。生产问题确需用户内容时，由用户主动提供最小片段，限定访问者、目的、保留期和删除时间。

## 采样与保留

- 安全审计、身份撤销、计费状态和账本事件不采样。
- Trace 可按环境和结果采样；错误、慢请求、待对账和恢复演练保留较高比例。
- 日志按服务与敏感等级设置保留期和访问权限，不无限保留。
- 指标保留聚合趋势，不通过高基数标签变相保存用户行为。
- 删除用户数据时，观测系统保留法律和安全所需的最小匿名事件，不保留可还原正文。

具体天数和存储位置属于部署配置，需在各环境运维文档登记并由数据治理评审。

## 导出失败

应用先写有界本地缓冲，再异步导出。导出器故障不应阻塞身份、聊天或账本主事务，但必须：

- 限制内存和磁盘缓冲；
- 超限时优先保留安全、计费和错误事件；
- 统计丢弃数量并告警；
- 使用退避和断路，不无限快速重试；
- 不把敏感事件降级写入不受控 stdout 或临时文件。

账本和业务审计先写权威数据库，再由 outbox 导出，不能依赖遥测接收成功作为业务提交条件。

## 发布验收

- 从入口到身份、工作流、网关、供应商和账本的 trace ID 一致。
- 群聊扇出中的每次付费调用有独立 request ID 和共同 workflow run ID。
- 客户端重试复用 client request ID，未产生重复账单。
- 错误信封、日志、span、审计和流水使用相同稳定错误码。
- 日志和导出样本通过 Secret、个人信息和正文扫描。
- 观测后端中断、缓慢和拒绝时主链保持边界内运行并产生告警。
- Dashboard 能从 request ID 定位策略、路由、尝试、用量和终态，不要求查询业务数据库原始表。
