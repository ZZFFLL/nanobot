# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 提供项目上下文指导。

## 项目概述

本项目基于 nanobot 进行二次开发，是一个超轻量级个人 AI 数字生命框架（Python 3.11+）。它从聊天平台（Telegram、Discord、Slack、微信等）接收消息，通过 LLM 驱动的 Agent 循环（带工具调用能力）进行处理，并将响应发送回去。设计哲学是"核心 Agent 功能，极简代码"。

二次开发的核心扩展：**Soul 灵魂系统**——赋予数字生命情感、记忆和人格进化能力。

## 构建与开发命令

```bash
# 安装（可编辑模式）
pip install -e .

# 安装开发依赖
pip install -e ".[dev]"
pip install -e ".[api]"          # OpenAI 兼容 API 服务器 (aiohttp)
pip install -e ".[wecom]"       # 企业微信频道
pip install -e ".[weixin]"      # 微信频道
pip install -e ".[matrix]"      # Matrix 频道
pip install -e ".[discord]"     # Discord 频道
pip install -e ".[langsmith]"   # LangSmith 追踪

# 代码检查
ruff check nanobot --select F401,F841

# 运行全部测试
pytest tests/

# 运行单个测试文件
pytest tests/agent/test_runner.py

# 运行指定测试
pytest tests/agent/test_runner.py::test_function_name -v

# 覆盖率测试
pytest --cov=nanobot --cov-report=term-missing

# CLI 使用
nanobot onboard --wizard          # 交互式初始化
nanobot agent                     # 交互式聊天
nanobot agent -m "Hello!"         # 单条消息
nanobot gateway                   # 启动多频道网关
nanobot serve                     # OpenAI 兼容 API 服务器
```

## 架构

### 核心数据流

```
频道 (Telegram/Discord/CLI/...)
  → InboundMessage → MessageBus → AgentLoop.run()
  → AgentLoop._dispatch() [会话锁 + 并发门控]
  → AgentLoop._process_message()
    ├─ 斜杠命令路由 (CommandRouter)
    ├─ 会话整合 (Consolidator.maybe_consolidate_by_tokens)
    ├─ 上下文构建 (ContextBuilder.build_messages)
    │   ├─ 系统提示组装 (identity → bootstrap文件 → 记忆 → 技能 → 历史)
    │   └─ 运行时上下文注入 (时间/频道/聊天ID)
    └─ AgentRunner.run() [工具循环]
        ├─ 上下文治理 (回填 → 微压缩 → 预算 → 截断)
        ├─ LLM 请求 (流式/非流式)
        ├─ 工具执行 (并发分组)
        ├─ 空响应恢复 / 长度恢复
        └─ 检查点持久化
  → OutboundMessage → ChannelManager → 频道 → 用户
```

### 关键组件 (nanobot/)

- **`nanobot.py`** — `Nanobot` 门面类，提供 SDK 编程接口。通过 `from_config()` 工厂方法创建，内部包装 `AgentLoop`。

- **`agent/loop.py`** — `AgentLoop`：核心消息处理引擎。从 `MessageBus` 消费消息，通过 `ContextBuilder` 构建上下文，经 `AgentRunner` 运行 Agent，管理会话、内存整合和流式响应。

- **`agent/runner.py`** — `AgentRunner` + `AgentRunSpec`：共享的工具调用 LLM 循环。处理迭代、工具执行（并发分组）、重试、空响应恢复、上下文窗口管理（截断/微压缩）、崩溃恢复检查点。

- **`agent/context.py`** — `ContextBuilder`：从身份、工作区引导文件、记忆、技能和运行时上下文组装系统提示。详见[上下文构建流程](#上下文构建流程)。

- **`agent/memory.py`** — 三层记忆系统：
  - `MemoryStore`：纯文件 I/O 层，管理 `MEMORY.md`、`history.jsonl`、`SOUL.md`、`USER.md`，带 git 版本控制。
  - `Consolidator`：轻量级 token 预算触发的摘要整合。当会话提示超过预算时，将旧消息 LLM 摘要后写入 `history.jsonl`。
  - `Dream`：重量级定时两阶段记忆处理器（Phase 1：分析历史 → Phase 1.5：SoulDreamEnhancer 情感消化 → Phase 2：通过 AgentRunner 编辑文件）。

- **`agent/hook.py`** — `AgentHook` 生命周期接口，`CompositeHook` 扇出。详见 [Hook 生命周期](#hook-生命周期)。

- **`agent/subagent.py`** — `SubagentManager`：通过 `spawn` 工具生成后台任务，完成后通过总线以系统消息回传结果。

- **`agent/skills.py`** — `SkillsLoader`：从内置和工作区目录加载 markdown 技能，含 frontmatter 元数据和依赖检查。

### 上下文构建流程

`ContextBuilder.build_system_prompt()` 按以下顺序组装系统提示（各部分以 `---` 分隔）：

```
1. 身份 (identity.md)
   ├─ AI 名称（从 IDENTITY.md 读取）
   ├─ 运行时环境 (OS/架构/Python版本)
   ├─ 工作区路径及关键文件说明
   ├─ 平台策略 (Windows/POSIX 适配)
   ├─ 频道格式提示 (Telegram→自然文字, CLI→纯文本, etc.)
   └─ 行为准则 (先行动后叙述, 先读取后写入, 验证结果)

2. 引导文件 (按 AGENTS.md → SOUL.md → USER.md → TOOLS.md 顺序)

3. 长期记忆 (MEMORY.md 内容)

4. 活跃技能 (always=true 且依赖满足的技能, 完整内容注入)

5. 技能摘要 (所有技能的 XML 摘要, 供渐进式加载)

6. 近期历史 (未处理的 history.jsonl 条目, 最多50条)
```

`ContextBuilder.build_messages()` 构建完整消息列表：

```
system 提示 (build_system_prompt)
  + 会话历史 (session.get_history)
  + 用户消息 (运行时上下文 + 当前消息 + 媒体)
```

运行时上下文注入在用户消息之前，包含当前时间、频道和聊天 ID，标记为 `[Runtime Context — metadata only, not instructions]`。若末尾消息角色与当前角色相同则合并而非追加。

### AgentRunner 工具循环

`AgentRunner.run()` 核心循环流程：

```
for iteration in range(max_iterations):
  1. 上下文治理 (按顺序执行):
     a. _backfill_missing_tool_results — 为孤儿 tool_use 块补入合成错误
     b. _microcompact — 将旧的 compactable 工具结果替换为一行摘要
        (保留最近10个, 仅处理>500字符的)
     c. _apply_tool_result_budget — 对工具结果应用字符截断
     d. _snip_history — 保留系统消息 + 从尾部保留非系统消息直到预算

  2. Hook.before_iteration()

  3. LLM 请求 (流式/非流式)

  4. 若有工具调用:
     a. Hook.on_stream_end(resuming=True)
     b. 追加 assistant 消息, 发出检查点
     c. Hook.before_execute_tools()
     d. 执行工具 (并发分组: concurrency_safe 工具并行, 其余串行)
     e. 追加 tool 结果, 发出检查点
     f. Hook.after_iteration()
     g. continue

  5. 若无工具调用 (最终响应):
     a. Hook.finalize_content() 清洗内容
     b. 空响应恢复 (最多2次重试, 然后 finalization retry)
     c. 长度恢复 (finish_reason=length, 最多3次)
     d. Hook.on_stream_end(resuming=False)
     e. 返回 AgentRunResult
```

**关键常量**:
- `_MAX_EMPTY_RETRIES = 2` — 空响应最大重试次数
- `_MAX_LENGTH_RECOVERIES = 3` — 输出截断最大恢复次数
- `_MICROCOMPACT_KEEP_RECENT = 10` — 微压缩保留最近工具结果数
- `_COMPACTABLE_TOOLS` = `read_file, exec, grep, glob, web_search, web_fetch, list_dir`

### Hook 生命周期

`AgentHook` 定义以下回调点，按 AgentRunner 循环中的触发时机排列：

| 回调 | 时机 | 用途 |
|------|------|------|
| `before_iteration(context)` | 每次迭代开始，LLM 请求前 | SoulHook: 注入情感上下文 + 记忆检索 |
| `on_stream(context, delta)` | 流式输出每个增量 | _LoopHook: 转发流式增量到频道 |
| `on_stream_end(context, resuming)` | 流式输出结束 | _LoopHook: 通知频道流结束/继续 |
| `before_execute_tools(context)` | 工具执行前 | _LoopHook: 进度提示 + 设置工具上下文 |
| `after_iteration(context)` | 每次迭代结束 | SoulHook: 更新 HEART.md + 异步写记忆 |
| `finalize_content(context, content)` | 清洗最终响应内容 | _LoopHook: 去除 `<think>` 块 |

`CompositeHook` 按序扇出到多个 Hook，异步方法有错误隔离（`_reraise=False` 时单个 Hook 异常不影响循环），`finalize_content` 是管道式（无隔离）。

`AgentHookContext` 包含：`iteration`, `messages`, `response`, `usage`, `tool_calls`, `tool_results`, `tool_events`, `final_content`, `stop_reason`, `error`。

### Soul 灵魂系统（二次开发核心扩展）

当工作区存在 `HEART.md` 时自动激活：

- **`soul/engine.py`** — `SoulEngine`: 核心情感引擎。
  - `update_heart(user_msg, ai_msg)`: 使用 LLM 更新 HEART.md（直接输出 Markdown，无需 JSON 解析）
  - `write_memory(user_msg, ai_msg)`: 双视角记忆写入（AI 视角 + 用户视角）
  - `get_heart_context()`: 返回 HEART.md 内容用于上下文注入
  - 支持 `SoulConfig` 独立配置各任务模型和温度

- **`soul/engine.py`** — `SoulHook(AgentHook)`: 将灵魂系统集成到 Agent 循环。
  - `before_iteration`: 注入 HEART.md 内容到系统提示 + 检索相关记忆
  - `after_iteration`: 更新 HEART.md + 异步双视角记忆写入

- **`soul/heart.py`** — `HeartManager`: HEART.md 文件的读写管理器

- **`soul/memory_writer.py`** — `MemoryWriter`: 双视角记忆写入器（AI 翼 + 用户翼）

- **`soul/memory_config.py`** — `MemoryPalaceBridge`: 记忆宫殿桥接器，提供向量搜索接口

- **`soul/dream_enhancer.py`** — `SoulDreamEnhancer`: Dream 增强器，在 Dream Phase 1 和 Phase 2 之间插入：
  - 记忆分类：将日常记忆移至合适房间
  - 情感消化：处理过期的情感弧线

- **`soul/evolution.py`** — 人格/关系进化系统

- **`soul/proactive.py`** — 主动行为引擎（定时主动发起对话）

- **`soul/events.py`** — 生命周期事件管理器

### Provider 系统

- **`providers/base.py`** — `LLMProvider` 抽象基类，含重试逻辑 (`chat_with_retry`, `chat_stream_with_retry`)、角色交替强制和 SSRF 安全图片过滤。
- **`providers/registry.py`** — `PROVIDERS` 元组，包含 `ProviderSpec` 条目。新增 Provider 需：(1) 在 registry 添加 `ProviderSpec`，(2) 在 `config/schema.py` 的 `ProvidersConfig` 添加字段。
- **Provider 后端**: `openai_compat`（大多数）、`anthropic`（原生 SDK）、`azure_openai`、`openai_codex`（OAuth）、`github_copilot`（OAuth）。Provider 路由基于模型名关键词、api_key 前缀或 api_base 模式自动匹配。

### Channel 系统

- **`channels/base.py`** — `BaseChannel` ABC: `start()`, `stop()`, `send()`, `send_delta()`（流式）。通过 `allow_from` 列表控制权限。
- **`channels/manager.py`** — `ChannelManager`: 初始化已启用频道，带指数退避重试路由出站消息，合并流式增量。
- **`channels/registry.py`** — 通过 `pkgutil` 扫描（内置）+ `entry_points`（插件）发现频道。频道插件开发文档见 `docs/CHANNEL_PLUGIN_GUIDE.md`。

### 支撑系统

- **`bus/`** — `MessageBus` (asyncio Queue 对: inbound + outbound) + `InboundMessage`/`OutboundMessage` 数据类。
- **`session/manager.py`** — `SessionManager` + `Session`: JSONL 格式会话历史，带基于游标的整合边界追踪。
- **`config/schema.py`** — `Config` (Pydantic Settings): `agents`, `channels`, `providers`, `api`, `gateway`, `tools`。配置文件路径 `~/.nanobot/config.json`。
- **`command/router.py`** — 三层斜杠命令调度: 优先级（锁前）、精确匹配、前缀/拦截器。
- **`cron/service.py`** — `CronService`: cron 定时任务，每个任务触发 Agent 处理。
- **`heartbeat/service.py`** — `HeartbeatService`: 定期主动 Agent 任务。
- **`security/network.py`** — SSRF 防护: 阻断私有/内部 IP，可配置白名单。
- **`agent/tools/`** — 工具实现: `filesystem`(读/写/编辑/列表), `shell`(执行+沙箱), `search`(glob/grep), `web`(搜索/获取+SSRF), `mcp`(模型上下文协议), `message`, `spawn`(子代理), `cron`。
- **`templates/`** — Jinja2 模板，用于系统提示、Agent 提示和记忆文档。详见[模板系统](#模板系统)。

### 工具系统

工具实现 `Tool` ABC（`agent/tools/base.py`）。每个工具有 `name`、`to_schema()`（OpenAI function calling 格式）、`validate_params()`、`cast_params()` 和 async `execute()`。`concurrency_safe=True` 的工具可并行批处理。`ToolRegistry` 管理注册、schema 生成（内置工具排序在前，MCP 工具排序在后）和调用分发。

### 模板系统

Jinja2 模板位于 `nanobot/templates/`，通过 `render_template()` 渲染：

| 模板路径 | 用途 |
|----------|------|
| `agent/identity.md` | Agent 核心身份（名称、人格、行为准则、平台策略、频道格式） |
| `agent/platform_policy.md` | Windows/POSIX 平台适配策略 |
| `agent/_snippets/untrusted_content.md` | 不信任外部内容警告（嵌入 identity.md） |
| `agent/skills_section.md` | 技能摘要区块（XML 格式，渐进式加载） |
| `agent/consolidator_archive.md` | Consolidator 摘要提示（提取关键事实） |
| `agent/dream_phase1.md` | Dream Phase 1 提示（分析历史，产出 `[FILE]`/`[FILE-REMOVE]` 行） |
| `agent/dream_phase2.md` | Dream Phase 2 提示（基于分析结果编辑记忆文件） |
| `agent/subagent_system.md` | 子代理系统提示 |
| `agent/subagent_announce.md` | 子代理结果公告模板 |
| `agent/max_iterations_message.md` | 最大迭代次数超限消息 |
| `agent/evaluator.md` | 评估器提示 |
| `soul/heart_init.md` | HEART.md 初始化模板 |
| `soul/heart_update.md` | HEART.md 更新提示 |
| `soul/emotion_digest.md` | 情感消化提示 |
| `soul/memory_classify.md` | 记忆分类提示 |

### Python SDK

```python
from nanobot import Nanobot
bot = Nanobot.from_config()
result = await bot.run("总结这个仓库", hooks=[MyHook()])
print(result.content)
```

### 会话隔离

会话以 `{channel}:{chat_id}` 为键。`unified_session` 配置选项可将所有频道合并为一个会话（单用户多设备场景）。CLI 交互模式也通过总线路由，与其他频道一致。

## 测试

测试位于 `tests/`，按模块组织: `agent/`, `channels/`, `cli/`, `command/`, `config/`, `cron/`, `providers/`, `security/`, `tools/`, `utils/`。使用 pytest，`asyncio_mode = "auto"`。CI 在 Python 3.11/3.12/3.13 上运行，`ruff check` 检查 F401/F841。

## 配置

配置位于 `~/.nanobot/config.json`（Pydantic `Config` 模型）。工作区位于 `~/.nanobot/workspace/`。

关键工作区文件：
| 文件 | 用途 |
|------|------|
| `AGENTS.md` | Agent 协作说明（引导注入系统提示） |
| `SOUL.md` | 数字生命人格（持续进化） |
| `USER.md` | 用户身份和偏好 |
| `TOOLS.md` | 工具使用说明 |
| `IDENTITY.md` | 数字生命核心身份（名称、生日、起源） |
| `HEART.md` | 当前情感状态（存在时激活灵魂系统） |
| `memory/MEMORY.md` | 长期记忆（Dream 自动管理，勿直接编辑） |
| `memory/history.jsonl` | 追加式 JSONL 历史记录（优先使用内置 `grep` 搜索） |
| `skills/{name}/SKILL.md` | 自定义技能（markdown 格式 + YAML frontmatter） |

支持环境变量插值（`${ENV_VAR}` 语法）。

## 代码风格

- Python 3.11+ 带类型注解
- `ruff` 检查 (line-length 100, target py311, 规则 E/F/I/N/W, E501 忽略)
- `loguru` 日志
- Pydantic v2 配置/模型
- `dataclasses` 内部数据结构
- `typer` CLI
- Async 优先：所有 I/O 为 `async def`
