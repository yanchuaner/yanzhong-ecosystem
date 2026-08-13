# 燕中生态扩展规范

本文规定模块、适配器、能力、工作流和插件的边界、清单、权限与生命周期。当前 Preview 只允许内置实现、构建期注册和管理员白名单配置；本文不表示外部插件执行已经开放。

## 术语

| 概念 | 含义 | 是否可独立分发 |
| --- | --- | --- |
| 模块 | 拥有一组领域职责、数据和公共端口的代码边界 | 通常否 |
| 端口 | 领域或应用层声明的稳定接口 | 否 |
| 适配器 | 把外部平台、协议、供应商或存储映射到端口 | 可以 |
| 能力 | 可被授权和调用的原子操作，如聊天、检索、TTS | 可以由模块或适配器提供 |
| 工作流 | 按版本化定义组合能力和状态转换 | 可以，默认只含声明式定义 |
| 工作流块 | 具有明确输入输出、副作用和失败语义的步骤 | 可以 |
| 插件 | 由核心仓库之外发布、通过宿主 API 扩展能力的分发物 | 是，按不可信代码处理 |

“可插拔”表示实现可以在契约不变时替换，不表示运行时可以下载并执行任意代码。没有稳定端口、清单、权限和兼容测试的扩展不是插件系统。

## 扩展点

| 扩展点 | 所有者 | 输入输出 | 不得拥有 |
| --- | --- | --- | --- |
| 接入适配器 | AI 使用层或客户端 | 平台事件与统一消息/发送结果 | 角色提示、账本、供应商路由 |
| 身份消费者 | 各下游服务 | OIDC 声明与签名身份事件 | 主站用户表、密码登录 |
| 能力适配器 | AI 使用层 | 能力请求与标准结果 | 网关余额、全局 Secret |
| 工作流块 | AI 使用层 | 已声明 schema 与事件 | 未声明网络、文件或数据访问 |
| 供应商适配器 | API 网关 | 标准模型请求、事件、用量与错误 | 主体授权、余额写入 |
| 存储适配器 | 数据所有模块 | Repository 操作与迁移 | 跨服务数据库访问 |
| 观测导出器 | 平台运维 | 脱敏事件、指标与 span | 阻塞业务、读取正文或凭据 |
| CLI 工具 | YCZX Code | ToolCall 与 ToolResult | 绕过 Policy、直接渲染终端 |

新增扩展点前必须确认至少存在第二个真实实现、测试替身或明确替换需求。仅为“以后可能需要”创建的空注册表、空插件目录或通用基类不进入正式主线。

## 依赖方向

```text
host application
      |
      v
public extension contract
      ^
      |
adapter / built-in extension / isolated plugin
```

- 宿主只通过公开契约调用扩展，不导入扩展私有模块。
- 扩展只使用宿主提供的能力句柄，不读取宿主数据库、进程环境或全局注册表。
- 领域对象不包含 Next.js、Gin、GORM、LiteLLM、供应商 SDK 或平台事件类型。
- 跨仓扩展依赖版本化 schema，不通过复制 TypeScript、Go 或 Python 内部类型保持一致。

## 扩展清单

每个可独立注册的适配器、工作流或插件使用机器可读清单。最低字段：

```json
{
  "schema_version": "1.0",
  "id": "builtin.workflow.group-chat",
  "version": "1.0.0",
  "kind": "workflow",
  "api_version": "yanchuaner.extension/v1",
  "entrypoint": "builtin:group-chat",
  "provides": ["workflow.group-chat"],
  "requires": {
    "capabilities": ["text.chat.general"],
    "scopes": ["conversation.read", "conversation.write"]
  },
  "permissions": {
    "data": ["conversation:current", "persona:selected"],
    "network": { "mode": "none", "hosts": [] },
    "secrets": []
  },
  "resources": {
    "timeout_ms": 120000,
    "memory_mb": 128,
    "max_concurrency": 4
  },
  "license": "AGPL-3.0-only",
  "source": "https://github.com/yanchuaner/ai_yanchuaner"
}
```

`id` 一经公开不复用；`version` 表示分发物版本，`api_version` 表示宿主协议版本。清单校验失败、字段未知、权限无法识别、来源不可访问或许可证不允许时拒绝注册。

规范 schema 位于 `schemas/extension-manifest.v1.schema.json`。

## 权限模型

扩展默认无权限。宿主按安装、启用和单次调用三个阶段取交集：

```text
manifest requested permissions
  intersect administrator policy
  intersect current subject scopes
  intersect workflow grant
  = invocation capability handles
```

### 数据权限

数据访问以资源句柄表达，例如当前会话、已选角色、指定知识库，不提供数据库连接或任意 owner ID 查询。读、写、删除和导出分别授权。扩展不能通过一个对象句柄遍历到未声明的用户数据。

### 网络权限

默认 `none`。需要网络时声明 HTTPS 主机白名单、端口、重定向策略、DNS 解析策略和数据类别。宿主阻断回环、内网、云元数据、非预期重定向和 DNS 重绑定。统一 AI 能力通过网关句柄调用，不给插件供应商 Key。

### Secret 权限

清单只声明逻辑 Secret 名称和用途。宿主返回受限调用句柄或在隔离进程注入单用途短期凭据，不返回全局环境变量。Secret 不进入错误、事件、缓存或插件持久化。

### 副作用权限

文件写入、外部发送、内容发布、费用调用、状态变更和删除均为副作用。清单声明风险等级、幂等键、确认方式、补偿与审计事件。声明 `none` 的扩展发生副作用时立即隔离。

## 工作流

工作流是声明式编排，不是任意脚本。发布的工作流至少记录：

- `workflow_id`、版本、状态和 owner；
- 入口、输出与状态 schema；
- 允许的块 ID 和版本范围；
- 每个分支的超时、取消、重试与合并规则；
- 所需 scope、能力、费用来源和最大调用次数；
- 部分失败、降级、补偿和最终状态；
- 数据保留、观测字段和删除影响。

工作流版本发布后不可原地改变语义。运行中的会话保存采用的版本；新版本先并行注册，迁移会话需显式方案。删除旧版本前统计消费者和活动运行实例。

有副作用的块必须声明幂等策略。付费块只调用统一 API 网关，并把每个网关 `request_id` 关联到工作流 trace。工作流不得直接写额度或根据本地 token 估算结算。

## 插件执行

外部插件开放前必须满足：

1. 分发物有可验证来源、完整许可证、内容摘要和签名。
2. 宿主 API 版本化，插件不导入内部包。
3. 插件在独立进程、容器或其他受控沙箱中运行，不与业务服务同进程加载任意 npm/Python 包。
4. 文件、网络、Secret、模型和数据通过 capability handle 授予。
5. CPU、内存、并发、输出、磁盘、网络、超时和重试有硬限制。
6. 插件退出、崩溃、超限或观测失败不会破坏核心聊天、身份或账本。
7. 管理员可以禁用、隔离、回滚和卸载，紧急禁用不依赖插件自身响应。

Preview 期允许的扩展形式：核心仓内置模块、受评审的构建期适配器、静态工作流清单和管理员配置的供应商渠道。公网插件市场、用户上传代码和任意远程 MCP 服务保持关闭。

## 生命周期

```text
discovered -> validated -> registered -> disabled
                                      -> enabled -> draining -> disabled
                                      -> quarantined
disabled -> upgraded / uninstalled
```

- `discovered` 不执行入口代码。
- `validated` 完成 schema、签名、许可证、依赖和权限检查。
- `registered` 只写注册表，默认 `disabled`。
- `enabled` 需要管理员策略；高风险权限还需环境级批准。
- `draining` 拒绝新调用并等待有界时间内的现有调用结束。
- `quarantined` 由安全、崩溃、越权或完整性事件触发，撤销句柄并保留脱敏证据。
- `uninstalled` 清理分发物和临时状态；用户数据按明确迁移或删除策略处理，不由插件自行决定。

升级先并行安装新版本，运行合同与迁移检查，再切换新调用。失败时回到旧版本；不可逆数据迁移必须单独备份和审批。

## 错误与隔离

扩展错误映射为稳定类别：`extension_invalid`、`extension_disabled`、`permission_denied`、`resource_exhausted`、`timeout`、`dependency_unavailable`、`extension_failed`。原始堆栈只进入受限诊断，不直接返回用户。

- 超时触发取消；扩展忽略取消时强制终止隔离运行单元。
- 自动重试仅适用于声明为安全或有幂等键的调用。
- 连续失败触发断路和告警，不无限重启。
- Event Sink 故障不阻塞主链，但本地缓冲有硬上限。
- 工作流块失败按已发布策略终止、降级或补偿，不能由 UI 猜测结果。

## 兼容与弃用

- 宿主 API 使用主版本；破坏性变化发布新主版本并允许并行运行。
- 清单和 schema 可新增可选字段；删除、改名、收紧权限语义或改变默认副作用需要新主版本。
- 能力 ID 稳定，供应商模型和渠道映射不属于扩展兼容面。
- 弃用至少给出替代项、受影响消费者、观测方式、截止版本、数据迁移和回滚。
- 安全漏洞可立即禁用，但后续仍记录原因、影响、替代与恢复条件。

## 准入门禁

扩展进入 Preview 前必须通过：

- manifest 与所有引用 schema 校验；
- 宿主 API、输入输出、错误、取消和版本合同测试；
- 未授权数据、路径逃逸、SSRF、Secret 泄漏和权限提升测试；
- 超时、崩溃、超限、依赖故障和观测背压测试；
- 安装、升级、降级、禁用、卸载和数据迁移演练；
- 来源、许可证、NOTICE、品牌和源码入口检查；
- 确定的 owner、维护期、安全响应人和紧急禁用方式。

没有维护者、无法禁用、无法判断费用或无法隔离数据的扩展不得进入正式注册表。
