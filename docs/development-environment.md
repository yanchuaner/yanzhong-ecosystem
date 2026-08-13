# 燕中生态开发环境

本文定义多仓工作区的环境基线和依赖边界。各仓库的准确版本、启动命令和配置项以其锁文件、README 与部署文档为准。

## 环境分工

- 正式 Web、API、AI、小程序和 CLI 开发默认在 WSL/Linux 原生文件系统进行。
- Windows 可用于 Git/PR 入门、普通 Python 练习和 Markdown 等轻量任务；不要在 Windows 与 WSL 重复维护同一项目依赖。
- 生产服务器只运行已构建产物，不安装日常开发工具，不从工作树现场构建。
- 项目依赖留在项目目录或对应包管理器缓存，不使用全局 `pip` 或混用多个 Node 包管理器。

Windows 初学者环境与 YCZX Code Lab 学习流程见 `../yczx_code_lab/docs/setup/windows.md`。该教程是 Windows 入门的唯一维护位置。

## 仓库基线

| 仓库 | 运行时与包管理 | 最低检查 |
| --- | --- | --- |
| `yanzhong-ecosystem` | Python 3.12、venv、Make | `make check`；完整工作区使用 `make check-workspace` |
| `web_yanchuaner` | Node.js 22、npm、Prisma | `npm ci`，`npm run audit:docs`，按改动运行发布门禁 |
| `api_yanchuaner` | Go 1.25.1、Bun（前端） | `go build ./...`、相关 `go test`；前端使用锁定 Bun |
| `ai_yanchuaner` | Node.js 20+、pnpm 10.12.4 | `pnpm install --frozen-lockfile`、typecheck、test、build |
| `mp_yanchuaner` | Node.js 20、npm、微信开发者工具 | `npm ci`、typecheck、weapp build |
| `lab_yanchuaner` | Node.js 22、pnpm 10.20.0 | `pnpm install --frozen-lockfile`、`pnpm release:check` |
| `yczx_code` | Python 3.12、uv | `uv sync --dev`、lock、Ruff、pytest |
| `yczx_code_lab` | Python 3.12、uv | `uv sync`、Ruff 与教程声明的运行命令 |

版本表只提供进入仓库前的导航。项目声明变化时，同一改动必须更新本表；不得只凭本文升级运行时或锁文件。

## 工作区初始化

1. 将治理仓克隆到 WSL/Linux 原生路径，不放在 `/mnt/c` 或 `/mnt/d`。
2. 执行 `make setup` 建立治理仓本地 `.venv`；需要完整工作区时再执行 `make workspace-bootstrap`。
3. 使用 `make workspace-status` 查看七个项目的分支与改动，再进入目标仓查看详细差异。
4. 只进入当前任务涉及的仓库安装依赖。
5. 从示例配置创建本地、未跟踪的环境文件；任何真实 Secret 使用受控凭据来源。
6. 使用项目锁定命令安装，不把某仓 `node_modules`、`.venv` 或构建缓存复制给另一个仓。

根目录是治理 Git 仓库，七个项目目录由根 `.gitignore` 排除并保持独立历史。根 `git status` 不能代表项目状态，也不得用根目录命令批量清理或重置子仓库。

## 依赖安装

### Node.js

- `web_yanchuaner` 与 `mp_yanchuaner` 使用 npm，优先 `npm ci`。
- `ai_yanchuaner` 与 `lab_yanchuaner` 使用各自 `packageManager` 固定的 pnpm，优先通过 Corepack 启用对应版本。
- 不在同一仓库混用 npm、pnpm、Yarn 或 Bun；API 上游前端按其仓内 Bun 锁文件执行。
- 缺少 `node_modules` 时，类型或构建门禁应记录为未运行，不能把 `tsc: not found` 解释为源码失败。

### Python

- 治理仓使用 Python 3.12 和根 `.venv`，依赖由带哈希的 `requirements.txt` 固定；不安装到系统 Python。
- 两个 YCZX 仓库都使用 Python 3.12 和 uv 管理项目内 `.venv`。
- 依赖变更使用 `uv add`/`uv remove` 并同步锁文件；验证现有环境使用 `uv run --frozen` 或 `uv lock --check`。
- 不使用系统级 `pip install` 安装项目依赖，不提交 `.venv`、缓存或本地解释器配置。

### Go 与数据库

- API 使用 `go.mod` 声明的 Go 版本；不通过全局替换或未记录的 `replace` 绕过依赖。
- 数据库迁移只在明确的可销毁环境验证。不得让本地脚本、Compose 或测试指向主站生产 `prod.db` 或共享生产数据库。
- SQLite、PostgreSQL 和 MySQL 的兼容结论分别验收，不能用单一数据库通过代替全部支持范围。

## Secret 与本地数据

- `.env`、Cookie、API Key、OAuth Secret、供应商凭据、数据库、备份和用户文件不得提交。
- 小程序 `project.private.config.json` 属于开发者本地配置，不进入版本控制。
- 示例值必须明显无效；测试使用合成主体和可撤销测试凭据。
- 调试输出和截图发布前检查终端路径、请求头、成员信息和对话内容。

## 服务与端口

仅在真实集成需要时启动服务，并使用各仓部署文档声明的端口。发现端口占用时先识别已有进程，不结束不属于当前任务的服务。验证完成后停止本次启动的后台进程；生产与长期服务只由明确运维流程管理。

## 大型工具链

Docker Desktop、数据库服务器、完整 TeX 发行版、文档转换套件和其他大型工具不是全员前置条件。安装前先检查 WSL 与 Windows 已有能力，说明安装位置、磁盘占用、用途和轻量替代方案，再取得确认。

## 完成标准

- 实际命令使用仓库声明的运行时和包管理器；
- 安装只影响当前项目，没有全局环境污染；
- 锁文件与依赖清单一致，未意外重写其他仓库；
- 测试、类型、构建、数据库和外部上游的验收层级分别记录；
- 工作区没有本次产生的临时文件、日志、后台进程或真实凭据。
