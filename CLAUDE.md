# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

# nanobot-wenyuan 项目概览

> 基于 HKUDS/nanobot 的个人定制版本，集成 ReMe 向量记忆系统。

## 核心架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        AgentLoop (loop.py)                      │
│  主循环：消息分发 → 命令解析 → LLM调用 → 工具执行 → 响应生成       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ ContextBuilder│   │   AgentRunner │   │  Consolidator │
│  (context.py) │   │  (runner.py)  │   │  (memory.py)  │
│  上下文构建    │   │  LLM执行循环   │   │  记忆压缩      │
└───────────────┘   └───────────────┘   └───────────────┘
        │                   │                   │
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  MemoryStore  │   │  ToolRegistry │   │     Dream     │
│  (memory.py)  │   │ (registry.py) │   │  (memory.py)  │
│  文件存储层    │   │  工具注册中心   │   │  定时记忆提炼  │
└───────────────┘   └───────────────┘   └───────────────┘
        │                                       │
        ▼                                       ▼
┌───────────────┐                       ┌───────────────┐
│ ReMeAdapter   │                       │  ReMe向量库   │
│(reme_adapter) │◄──────────────────────│  语义记忆检索  │
└───────────────┘                       └───────────────┘
```

---

## 一、Agent 执行流程

### 1.1 主入口：AgentLoop (nanobot/agent/loop.py)

`AgentLoop` 是整个系统的核心，负责消息的生命周期管理。

```
消息流入流程：
InboundMessage → bus.consume_inbound() → _dispatch() → _process_message()
                                                    │
                                    ┌───────────────┼───────────────┐
                                    ▼               ▼               ▼
                               命令解析?      Token检查?       LLM调用
                               /new, /stop   consolidator    _run_agent_loop()
```

**关键方法：**

| 方法 | 职责 |
|------|------|
| `run()` | 主循环，持续消费 inbound 消息 |
| `_dispatch()` | 按会话串行执行，跨会话并发 |
| `_process_message()` | 单条消息处理：命令解析 → 上下文构建 → LLM 调用 |
| `_run_agent_loop()` | 执行工具循环直到 LLM 返回最终响应 |

### 1.2 LLM 执行循环：AgentRunner (nanobot/agent/runner.py)

`AgentRunner` 是与 LLM Provider 交互的核心执行器。

```python
# 执行循环伪代码
for iteration in range(max_iterations):
    response = await provider.chat_with_retry(messages, tools)

    if response.has_tool_calls:
        # 执行工具调用
        results = await _execute_tools(tool_calls)
        messages.append(tool_results)
        continue  # 继续循环

    # 无工具调用，返回最终响应
    return AgentRunResult(final_content=clean)
```

**关键特性：**

- **并发工具执行**: `concurrent_tools=True` 时，标记 `concurrency_safe` 的工具可并行执行
- **上下文截断**: `_snip_history()` 在 token 超限时自动截断历史
- **检查点恢复**: `checkpoint_callback` 支持中断后恢复

### 1.3 消息流转示例

```
用户: "帮我记住我的猫叫Luna"

1. AgentLoop._process_message()
   ├── 解析非命令，构建上下文
   │   └── ContextBuilder.build_messages()
   │       ├── _get_identity() → 系统身份
   │       ├── _load_bootstrap_files() → AGENTS.md, USER.md, SOUL.md
   │       └── build_system_prompt() → 完整 system prompt
   │
2. AgentRunner.run()
   ├── LLM 调用 → 决定调用 add_memory 工具
   ├── ToolRegistry.execute("add_memory", {"content": "用户有一只猫叫Luna"})
   │   └── AddMemoryTool.execute() → ReMe 存储记忆
   └── LLM 再次调用 → 生成响应 "好的，我记住了..."

3. _save_turn() → 保存到 Session 历史
4. 返回 OutboundMessage
```

---

## 二、Memory 管理系统

### 2.1 架构概览

nanobot 的记忆系统分为三层：

| 层级 | 组件 | 存储方式 | 用途 |
|------|------|----------|------|
| **Session** | SessionManager | JSONL 文件 | 当前会话历史 |
| **Working** | MemoryStore | 文件系统 | USER.md, SOUL.md, history.jsonl |
| **Long-term** | ReMeAdapter | 向量数据库 | 语义记忆检索 |

### 2.2 MemoryStore (nanobot/agent/memory.py)

纯文件 I/O 层，管理以下文件：

```
workspace/
├── USER.md          # 用户档案（偏好、习惯）
├── SOUL.md          # Bot 人格（行为、语气）
├── AGENTS.md        # 项目说明
└── memory/
    ├── MEMORY.md    # 长期记忆（已弃用，改用 ReMe）
    ├── history.jsonl # 压缩后的对话历史
    ├── .cursor      # history 游标
    └── .dream_cursor # Dream 处理进度
```

**关键方法：**

| 方法 | 说明 |
|------|------|
| `read_memory()` | 读取 MEMORY.md |
| `read_user()` | 读取 USER.md |
| `append_history(entry)` | 追加压缩后的历史记录 |
| `read_unprocessed_history(since_cursor)` | 读取未处理的 history |

### 2.3 Consolidator (nanobot/agent/memory.py)

轻量级 Token 触发的记忆压缩器。

```
触发时机：maybe_consolidate_by_tokens()

Token 检查流程：
1. estimate_session_prompt_tokens() → 估算当前 prompt 大小
2. 若超过 budget (context_window - max_tokens - buffer):
   ├── pick_consolidation_boundary() → 找到用户回合边界
   ├── archive_with_reme(messages) → 压缩并存储
   └── 更新 session.last_consolidated
```

**archive_with_reme() 流程：**

```python
async def archive_with_reme(messages):
    if reme_adapter:
        try:
            # 使用 ReMe 进行对话摘要
            await reme_adapter.summarize_conversation(messages, user_id=user_name)
            return True
        except:
            # 降级到传统 LLM 摘要
            return await archive(messages)
```

### 2.4 Dream (nanobot/agent/memory.py)

定时任务，处理 history.jsonl 并更新 USER.md / SOUL.md。

```
Dream 执行流程：

Phase 1: 分析
┌─────────────────────────────────────────┐
│ history.jsonl → LLM 分析 → 结构化输出   │
│ 输出格式：                               │
│ [USER] 用户偏好事实                      │
│ [SOUL] Bot 行为调整                      │
│ [SKIP] 无新信息                          │
│ 其他事实 → 存入 ReMe                     │
└─────────────────────────────────────────┘
                    │
                    ▼
Phase 2: 文件编辑
┌─────────────────────────────────────────┐
│ AgentRunner + read_file/edit_file 工具  │
│ → 增量编辑 USER.md / SOUL.md            │
│ → Git 自动提交                          │
└─────────────────────────────────────────┘
```

### 2.5 ReMeAdapter (nanobot/agent/reme_adapter.py)

ReMe 向量记忆系统的适配器，提供语义记忆检索。

**核心功能：**

| 方法 | 说明 |
|------|------|
| `start()` | 初始化 ReMe（加载配置、连接向量库） |
| `retrieve_memory(query)` | 语义检索记忆 |
| `add_memory(content)` | 添加记忆 |
| `summarize_conversation(messages)` | 对话摘要并存储 |
| `list_memories()` | 列出所有记忆 |

**断路器保护：**

```python
MAX_FAILURES = 3          # 失败3次后断开
RECOVERY_TIMEOUT = 60     # 60秒后尝试恢复
MIN_RETRIEVAL_INTERVAL = 5.0  # 最小检索间隔
MAX_RETRIEVALS_PER_MINUTE = 10  # 每分钟最大检索次数
```

---

## 三、上下文处理

### 3.1 ContextBuilder (nanobot/agent/context.py)

构建发送给 LLM 的完整上下文。

**System Prompt 组成：**

```
1. Identity (identity.md)
   ├── 运行时信息（系统、Python版本）
   ├── 工作空间路径
   └── 平台策略（安全限制）

2. Bootstrap Files
   ├── AGENTS.md (项目说明)
   ├── SOUL.md (Bot 人格)
   ├── USER.md (用户档案)
   └── TOOLS.md (工具说明)

3. Memory (已弃用，改用工具检索)
   └── _get_memory_content() 返回空字符串

4. Active Skills
   └── skills/ 目录下的技能模块

5. Skills Summary
   └── 可用技能列表
```

**build_messages() 流程：**

```python
def build_messages(history, current_message, ...):
    runtime_ctx = _build_runtime_context(channel, chat_id, timezone)
    user_content = _build_user_content(current_message, media)

    return [
        {"role": "system", "content": build_system_prompt()},
        *history,
        {"role": "user", "content": merged_runtime_and_user}
    ]
```

### 3.2 记忆工具化设计

**设计理念：** 长期记忆不再自动注入 prompt，而是通过工具让 LLM 自主决定何时检索。

```python
# nanobot/agent/tools/memory.py

retrieve_memory  # 语义检索记忆
add_memory       # 存储重要信息
list_memories    # 列出记忆
delete_memory    # 删除记忆
get_memory_status # 检查系统状态
```

**触发时机示例：**

```python
# AddMemoryTool 何时使用
- 用户说 "记住这个"
- 用户分享个人信息
- 重要决策达成

# RetrieveMemoryTool 何时使用
- 用户提到 "上次"、"之前"
- 需要用户偏好信息
- 查询历史对话内容
```

---

## 四、核心组件详解

### 4.1 ToolRegistry (nanobot/agent/tools/registry.py)

工具注册中心，管理所有可用工具。

```python
class ToolRegistry:
    def register(tool: Tool)      # 注册工具
    def get(name) -> Tool         # 获取工具
    def get_definitions() -> list # 获取 OpenAI 工具定义
    async def execute(name, params) -> Any  # 执行工具
```

**工具排序规则：**
1. 内置工具按名字排序
2. MCP 工具按名字排序并追加

### 4.2 SessionManager (nanobot/session/manager.py)

会话管理，存储对话历史。

```python
class Session:
    key: str              # channel:chat_id
    messages: list        # 对话历史
    last_consolidated: int # 已压缩的消息索引
    metadata: dict        # 元数据（包含检查点）

class SessionManager:
    def get_or_create(key) -> Session
    def save(session)     # 保存到 JSONL
    def invalidate(key)   # 清除缓存
```

### 4.3 LLMProvider (nanobot/providers/base.py)

LLM 提供者抽象接口。

```python
class LLMProvider(ABC):
    async def chat_with_retry(messages, tools, ...) -> LLMResponse
    async def chat_stream_with_retry(messages, on_content_delta, ...) -> LLMResponse

@dataclass
class LLMResponse:
    content: str
    tool_calls: list[ToolCallRequest]
    finish_reason: str
    usage: dict
    reasoning_content: str  # DeepSeek-R1 等推理内容
```

---

## 五、命令系统

### 5.1 内置命令 (nanobot/command/builtin.py)

| 命令 | 功能 |
|------|------|
| `/new` | 开始新会话，归档旧对话 |
| `/stop` | 停止当前任务 |
| `/status` | 显示会话状态 |
| `/dream` | 手动触发 Dream |
| `/dream-log` | 显示 Dream 日志 |
| `/dream-restore` | 恢复记忆状态 |
| `/memory` | ReMe 记忆管理 |
| `/help` | 显示帮助 |

### 5.2 /memory 命令详解

```bash
/memory status    # ReMe 健康状态
/memory list      # 列出记忆
/memory search <query>  # 语义搜索
/memory add <content>   # 添加记忆
/memory delete <id>     # 删除记忆
/memory clear     # 清空记忆
```

---

## 六、开发命令

```bash
# 安装
pip install -e .

# 运行
nanobot gateway

# 测试
pytest tests/

# 类型检查
mypy nanobot/

# 代码格式化
ruff format nanobot/
ruff check nanobot/
```

---

## 七、配置文件

### 7.1 主配置 (~/.nanobot/config.json)

```json
{
  "model": "gpt-4",
  "api_key": "...",
  "api_base": "...",
  "tools": {
    "exec": { "enabled": true },
    "web": { "enabled": true }
  }
}
```

### 7.2 ReMe 配置 (workspace/reme.yaml)

```yaml
embedding:
  model_name: "text-embedding-v4"
  api_key: "..."
  base_url: "..."
  dimensions: 1024

vector_store:
  backend: "chroma"
  collection_name: "nanobot_memory"

retrieve_top_k: 10
enable_time_filter: true
```

---

## 八、关键文件索引

| 文件 | 职责 |
|------|------|
| `nanobot/agent/loop.py` | Agent 主循环 |
| `nanobot/agent/runner.py` | LLM 执行器 |
| `nanobot/agent/context.py` | 上下文构建 |
| `nanobot/agent/memory.py` | MemoryStore, Consolidator, Dream |
| `nanobot/agent/reme_adapter.py` | ReMe 适配器 |
| `nanobot/agent/tools/registry.py` | 工具注册 |
| `nanobot/agent/tools/memory.py` | 记忆工具定义 |
| `nanobot/session/manager.py` | 会话管理 |
| `nanobot/command/builtin.py` | 内置命令 |
| `nanobot/providers/base.py` | LLM Provider 接口 |
| `nanobot/config/loader.py` | 配置加载 |

---

## 九、与原版 nanobot 的差异

| 特性 | 原版 | 本版本 |
|------|------|--------|
| 长期记忆 | 文件型 (MEMORY.md) | **ReMe 向量记忆** |
| 记忆检索 | 自动注入 prompt | **工具化检索** |
| 记忆写入 | Dream 编辑文件 | Dream + **ReMe 自动提炼** |
| 用户归因 | 无 | **基于 USER.md** |

详见 `docs/ReMe侵入报告_2026-04-09.md`。