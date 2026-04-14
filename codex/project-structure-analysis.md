# nanobot-wenyuan 项目结构认知分析

> 生成时间：2026-04-13
> 方法：以 `docs/` 为预读线索，以 `nanobot/`、`tests/`、`pyproject.toml` 的当前代码为准。

## 1. 先给结论

这个仓库本质上不是“独立于 nanobot 的新项目”，而是：

1. 以 `nanobot` 原有运行时为骨架。
2. 在 `nanobot/soul/` 中加入“数字生命 / Soul 灵魂系统”扩展。
3. 再通过 `cli`、`heartbeat`、`dream`、`memory` 等现有机制把 Soul 能力挂接进去。

所以理解这个项目时，最重要的认知不是“多了几个 Soul 文件”，而是：

- 主干仍然是 `MessageBus -> AgentLoop -> ContextBuilder -> AgentRunner -> ToolRegistry -> ChannelManager`
- Soul 是插在主干上的“条件激活增强层”
- `docs/superpowers/` 更像本次二开的设计与实施记录，不应直接当成最终事实来源

## 2. 仓库结构总览

### 2.1 顶层目录角色

- `nanobot/`
  - 主体源码，当前约 137 个文件，是项目的真实结构来源。
- `docs/`
  - 文档与设计资料。
  - 其中 `docs/*.md` 偏对外说明，`docs/superpowers/*` 偏这次二开的设计/计划/进度记录。
- `tests/`
  - 测试按模块分组，当前约 105 个文件，说明项目已经不是 demo 级别扩展。
- `bridge/`
  - 桥接相关资源，当前不属于本次结构认知的核心主线。
- `AGENTS.md`
  - 当前仓库内最完整的中文项目导读，和实际代码总体一致度较高。

### 2.2 `nanobot/` 内部主模块分层

- `agent/`
  - 运行时核心。消息处理、上下文构建、工具循环、记忆整合、子代理都在这里。
- `soul/`
  - 二次开发核心。情感、双视角记忆、主动行为、事件、Dream 增强、人格演化。
- `channels/`
  - 各聊天渠道实现与统一分发。
- `providers/`
  - LLM Provider 抽象层与注册表。
- `config/`
  - Pydantic 配置模型与配置加载。
- `bus/`
  - 收发消息总线。
- `session/`
  - 会话历史持久化。
- `cron/`
  - 定时任务系统。
- `heartbeat/`
  - 周期性“自唤醒”任务系统。
- `api/`
  - OpenAI 兼容 API 服务。
- `cli/`
  - `nanobot` 命令行入口。
- `templates/`
  - 系统提示、Dream、Soul 等模板。
- `skills/`
  - 内置技能定义。

## 3. 当前项目的真实主干

### 3.1 消息处理主链路

当前代码里的主链路是：

```text
Channel / CLI / API
  -> MessageBus(InboundMessage)
  -> AgentLoop.run() / process_direct()
  -> AgentLoop._dispatch()
  -> AgentLoop._process_message()
  -> ContextBuilder.build_messages()
  -> AgentRunner.run()
  -> ToolRegistry.execute()
  -> AgentLoop 保存会话/检查点/整合
  -> MessageBus(OutboundMessage)
  -> ChannelManager
  -> 具体渠道
```

这条主链路对应的关键文件：

- `nanobot/agent/loop.py`
- `nanobot/agent/context.py`
- `nanobot/agent/runner.py`
- `nanobot/agent/tools/registry.py`
- `nanobot/channels/manager.py`
- `nanobot/bus/events.py`
- `nanobot/bus/queue.py`

### 3.2 Agent 运行时的三个关键层

#### A. 上下文层

`nanobot/agent/context.py`

负责把这些内容拼成 system prompt：

- identity 模板
- 工作区引导文件：`AGENTS.md`、`SOUL.md`、`USER.md`、`TOOLS.md`
- 长期记忆 `memory/MEMORY.md`
- always 技能
- 技能摘要
- 最近未 Dream 处理的 `history.jsonl`

这个文件决定了“模型在每轮真正看到了什么”。

#### B. 循环层

`nanobot/agent/runner.py`

这是工具调用循环核心，职责包括：

- 请求模型
- 处理 tool calls
- 工具结果预算裁剪
- 微压缩旧工具结果
- 空响应恢复
- length 截断恢复
- checkpoint 发射

如果想理解项目的“Agent 能力边界”，这里比 README 更重要。

#### C. 会话与记忆层

`nanobot/session/manager.py` + `nanobot/agent/memory.py`

这里实际上分成三层：

- `Session`
  - 当前会话原始消息历史，保存在 `sessions/*.jsonl`
- `Consolidator`
  - 当上下文过长时，把旧消息总结进 `memory/history.jsonl`
- `Dream`
  - 周期性读取 `history.jsonl`，再回写 `SOUL.md` / `USER.md` / `memory/MEMORY.md`

也就是说，这个项目的“记忆”不是单文件，而是：

- 短期：`Session.messages`
- 中期：`memory/history.jsonl`
- 长期：`SOUL.md`、`USER.md`、`memory/MEMORY.md`

## 4. Soul 二次开发在主干上的挂载方式

### 4.1 激活方式

Soul 不是单独启动的子系统，而是在 `AgentLoop.__init__()` 中按条件挂载：

- 只要工作区存在 `HEART.md`
- 就初始化 `SoulEngine`
- 并把 `SoulHook` 加入 `_extra_hooks`

这意味着 Soul 当前是“文件存在即激活”的模式，而不是纯粹依赖配置开关。

### 4.2 Soul 在每轮对话中的插入点

#### 对话前

`SoulHook.before_iteration()`

会做两件事：

1. 把 `HEART.md` 注入 system prompt。
2. 如果 mempalace 可用，则从双翼记忆中检索相关记忆，再追加到 system prompt。

#### 对话后

`SoulHook.after_iteration()`

会做两件事：

1. 用 LLM 更新 `HEART.md`
2. 异步写入双视角记忆

所以 Soul 不是替代 AgentLoop，而是扩展 AgentLoop 的 hook 生命周期。

### 4.3 Soul 子模块职责

- `soul/heart.py`
  - `HEART.md` 文本读写，纯 Markdown，不做 JSON 解析。
- `soul/engine.py`
  - Soul 核心协调器，负责情感更新和记忆写入。
- `soul/memory_config.py`
  - mempalace 桥接层，负责 wing 命名与检索/写入接口。
- `soul/memory_writer.py`
  - 双视角记忆写入器。
- `soul/proactive.py`
  - 主动联系判断与消息生成。
- `soul/events.py`
  - `EVENTS.md` 生活事件管理。
- `soul/dream_enhancer.py`
  - 挂在 Dream 过程中的情感消化与记忆分类。
- `soul/evolution.py`
  - 性格/关系演化。
- `soul/soul_config.py`
  - 额外的 `~/.nanobot/soul.json` 配置读取。

## 5. 我对文档可信度的判断

### 5.1 相对可信，可作为结构导航

- `AGENTS.md`
  - 对整体架构、Soul 组件、运行流的描述与当前代码高度接近。
- `docs/SOUL_SYSTEM.md`
  - 适合作为 Soul 设计与实现导读，但细节仍需回到代码确认。
- `docs/CHANNEL_PLUGIN_GUIDE.md`
  - 与 `channels/base.py`、`channels/registry.py` 的实现基本一致。

### 5.2 可参考，但带有时间滞后

- `docs/MEMORY.md`
  - 核心思路和当前代码一致，但“planned to officially ship in v0.1.5”这类表述已经过时，因为当前 `pyproject.toml` 版本就是 `0.1.5`。
- `docs/PYTHON_SDK.md`
  - 概念和 `nanobot/nanobot.py` 基本一致，但同样带有旧版本阶段性描述。

### 5.3 更像“设计/实施过程记录”，不是最终事实

- `docs/superpowers/digital-life-design.md`
- `docs/superpowers/PROGRESS.md`
- `docs/superpowers/plans/*`

这些文档很有价值，但更适合回答：

- 这次二开原本想怎么做
- 设计经历过哪些变更
- 阶段计划怎么拆分

不适合直接回答：

- 当前命令到底是什么
- 当前配置到底从哪里生效
- 当前某个功能有没有真正接上线

## 6. 已确认的“文档 vs 代码”差异

### 6.1 CLI 命令名不一致

文档多处写的是：

```bash
nanobot init-digital-life
```

但当前代码里真实存在的是：

```bash
nanobot soul init
```

我在 `nanobot/cli/commands.py` 中确认到的命令入口只有 `@soul_app.command("init")`，没有 `init-digital-life` 顶层命令。

### 6.2 Soul 激活逻辑与文档中的“配置启用”不完全一致

当前代码里，Soul 是否激活的关键条件是 `HEART.md` 是否存在。

虽然 CLI 初始化时会往 `config.json` 写入：

```json
"soul": { "enabled": true }
```

但从当前代码检索结果看，没有发现这个 `enabled` 字段在 Soul 激活主路径中起决定作用。也就是说：

- 文档里写“配置启用”
- 代码里更像“文件存在即启用，配置只是附带写入”

### 6.3 Soul 配置目前是“双轨制”

文档多数描述把 Soul 配在主 `config.json` 下，但当前代码实际是两路配置并存：

- `config.schema.SoulConfig`
  - 通过 `agents.defaults.soul` 传入 `AgentLoop` / `SoulEngine`
- `soul/soul_config.py`
  - 再从 `~/.nanobot/soul.json` 读取主动行为相关配置

特别是 `ProactiveEngine` 这条链，实际会读取 `~/.nanobot/soul.json`，不是只依赖 `config.json`。

### 6.4 `docs/superpowers/` 内仍保留历史路径和历史说法

例如：

- `docs/superpowers/plans/README.md` 里仍指向另一个历史项目路径
- 多处写“已改为 `init-digital-life`”，但当前仓库代码没有落地这个命令

所以这部分文档应视为“实施记录”，不是部署手册。

## 7. 当前实现里的两个结构性注意点

这两点不是文档差异，而是我在读代码时看到的实现现状，后续继续开发时值得心里有数。

### 7.1 `MemoryWriter.retry_loop()` 目前没有看到启动入口

`nanobot/soul/memory_writer.py` 定义了失败重试循环，但当前代码检索中没有看到谁在启动它。

这意味着：

- “有重试设计”是成立的
- 但“后台重试循环已接线运行”这一点，当前代码里没有直接证据

### 7.2 Dream 与 Soul 增强已接入，但边界仍带实验性质

`Dream.run()` 已经会尝试：

- 分类 daily 记忆
- 消化 `HEART.md` 情感脉络
- 再进入 Phase 2 编辑长期文件

但这条链路整体仍明显带有“在现有 nanobot 上增量嫁接”的特征，不是从底层重写的新内核。

## 8. 推荐的源码阅读顺序

如果后续要继续在这个仓库里做开发，我建议按下面顺序读：

1. `AGENTS.md`
2. `codex/project-structure-analysis.md`
3. `nanobot/agent/loop.py`
4. `nanobot/agent/context.py`
5. `nanobot/agent/runner.py`
6. `nanobot/agent/memory.py`
7. `nanobot/cli/commands.py`
8. `nanobot/soul/engine.py`
9. `nanobot/soul/proactive.py`
10. `nanobot/soul/dream_enhancer.py`
11. `nanobot/config/schema.py`
12. `nanobot/providers/registry.py`
13. `nanobot/channels/base.py` + `nanobot/channels/manager.py`

这样读的原因是：

- 先建立运行时主干
- 再看 Soul 如何挂上去
- 最后再看外围扩展点（Provider、Channel、CLI）

## 9. 适合继续做的认知拆分

如果后续还要继续细化，我建议把结构认知再拆成三份专题文档：

1. `AgentLoop + AgentRunner` 运行时细读
2. `Soul` 子系统真实状态核查
3. `配置 / 渠道 / Provider / API` 接入层总览

当前这份文档适合作为第一层总览，不适合作为逐函数级实现说明。

## 10. 一句话认知模型

这个项目可以用一句话概括为：

**它仍然是一个以 nanobot 运行时为核心的轻量 Agent 框架，只是在 Hook、Memory、Dream、Heartbeat 这些既有骨架上，嫁接出了一套以 `HEART.md` 为入口的 Soul 数字生命系统。**
