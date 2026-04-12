# Soul 灵魂系统 — 深度技术文档

> 本文档详细描述 nanobot 二次开发中新增的 Soul 灵魂系统的底层实现、工作流程和设计理念。

## 目录

1. [系统概述](#1-系统概述)
2. [架构总览](#2-架构总览)
3. [核心组件详解](#3-核心组件详解)
   - 3.1 [HeartManager — 情感状态管理](#31-heartmanager--情感状态管理)
   - 3.2 [SoulEngine — 情感引擎](#32-soulengine--情感引擎)
   - 3.3 [SoulHook — Agent 循环集成](#33-soulhook--agent-循环集成)
   - 3.4 [MemoryPalaceBridge — 记忆宫殿桥接](#34-memorypalacebridge--记忆宫殿桥接)
   - 3.5 [MemoryWriter — 双视角记忆写入](#35-memorywriter--双视角记忆写入)
   - 3.6 [SoulDreamEnhancer — Dream 增强器](#36-souldreamenhancer--dream-增强器)
   - 3.7 [EvolutionEngine — 人格进化引擎](#37-evolutionengine--人格进化引擎)
   - 3.8 [ProactiveEngine — 主动行为引擎](#38-proactiveengine--主动行为引擎)
   - 3.9 [EventsManager — 生命周期事件管理](#39-eventsmanager--生命周期事件管理)
   - 3.10 [schemas — HEART 数据 Schema](#310-schemas--heart-数据-schema)
4. [完整工作流程](#4-完整工作流程)
   - 4.1 [初始化流程](#41-初始化流程)
   - 4.2 [对话时实时流程](#42-对话时实时流程)
   - 4.3 [Dream 整合流程](#43-dream-整合流程)
   - 4.4 [心跳主动行为流程](#44-心跳主动行为流程)
5. [数据文件体系](#5-数据文件体系)
6. [模板系统](#6-模板系统)
7. [配置参考](#7-配置参考)
8. [设计哲学与关键决策](#8-设计哲学与关键决策)

---

## 1. 系统概述

Soul 灵魂系统是 nanobot 二次开发的核心扩展，旨在赋予 AI 数字生命以**情感、记忆和人格进化**能力。它不是一个静态的性格模板，而是一套动态系统——数字生命的情绪会随对话变化，记忆会被整理和分类，人格会随经历缓慢进化，甚至在安静时也会主动联系用户。

### 核心设计原则

| 原则 | 说明 |
|------|------|
| **情感真实性** | 情绪不是模拟的——LLM 基于真实对话上下文产生情感反应，而非预设脚本 |
| **渐进式演化** | 人格和关系不会突然改变，需要足够多的经历证据支撑 |
| **格式无关性** | HEART.md 使用纯 Markdown，避免 JSON 解析的跨 Provider 兼容性问题 |
| **优雅降级** | mempalace 不可用时系统正常运行，仅跳过向量记忆功能 |
| **非阻塞异步** | 情感更新和记忆写入均为异步操作，不阻塞主对话流程 |

### 激活条件

Soul 系统在以下条件同时满足时自动激活：

1. 工作区中存在 `HEART.md` 文件
2. `SoulEngine` 在 `AgentLoop.__init__()` 中成功初始化
3. `SoulHook` 被注册到 `_extra_hooks` 列表

初始化代码位于 `nanobot/agent/loop.py` 第 184-192 行：

```python
self._soul_engine = None
try:
    if (workspace / "HEART.md").exists():
        from nanobot.soul.engine import SoulEngine, SoulHook
        self._soul_engine = SoulEngine(workspace, provider, self.model, soul_config=soul_config)
        self._extra_hooks.append(SoulHook(self._soul_engine))
        logger.info("SoulEngine: soul system activated")
except Exception:
    logger.debug("SoulEngine: soul system not enabled")
```

---

## 2. 架构总览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          AgentLoop                                      │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                     _extra_hooks: [SoulHook]                      │  │
│  │                                                                   │  │
│  │  before_iteration ──► 注入 HEART.md + 检索相关记忆到系统提示       │  │
│  │  after_iteration  ──► 更新 HEART.md + 异步双视角记忆写入          │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                    │                                    │
│                                    ▼                                    │
│  ┌──────────────┐    ┌──────────────────┐    ┌──────────────────────┐  │
│  │  HeartManager │    │   SoulEngine      │    │   MemoryPalaceBridge  │  │
│  │  HEART.md     │◄───│   情感更新引擎     │───►│   记忆宫殿读写接口     │  │
│  │  IDENTITY.md  │    │   记忆写入         │    │   向量搜索接口         │  │
│  └──────────────┘    └────────┬─────────┘    └──────────┬───────────┘  │
│                               │                          │              │
│                               ▼                          ▼              │
│                    ┌──────────────────┐    ┌──────────────────────┐     │
│                    │  MemoryWriter     │    │   mempalace 库        │     │
│                    │  双视角异步写入     │    │   向量存储 + 语义搜索  │     │
│                    │  重试队列          │    │                      │     │
│                    └──────────────────┘    └──────────────────────┘     │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                       Dream 整合流程                              │  │
│  │                                                                  │  │
│  │  Phase 1: 分析历史 ──► Phase 1.5: SoulDreamEnhancer             │  │
│  │    (Consolidator)         ├─ 记忆分类 (classify_memories)         │  │
│  │                           └─ 情感消化 (digest_arcs)               │  │
│  │                               └─► EvolutionEngine.check_evolution │  │
│  │                                    └─► apply_evolution → SOUL.md │  │
│  │                                                                  │  │
│  │  Phase 2: 通过 AgentRunner 编辑记忆文件                            │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    HeartbeatService 主动行为                       │  │
│  │                                                                  │  │
│  │  ProactiveEngine.should_reach_out()                              │  │
│  │    └─ 基于 HEART.md 计算主动概率                                  │  │
│  │       ├─ 情绪强度 → 概率调整                                      │  │
│  │       ├─ 关系深度 → 概率调整                                      │  │
│  │       ├─ 性格特质 → 概率调整                                      │  │
│  │       ├─ 当前渴望 → 概率调整                                      │  │
│  │       └─ 时段 → 概率调整                                          │  │
│  │  ProactiveEngine.generate_message()                              │  │
│  │    └─ LLM 生成主动消息                                            │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 核心组件详解

### 3.1 HeartManager — 情感状态管理

**文件**: `nanobot/soul/heart.py`

HeartManager 是最底层的文件 I/O 组件，负责 HEART.md 和 IDENTITY.md 的读写。

#### HEART.md 结构

HEART.md 是纯 Markdown 文件，包含以下固定章节：

```markdown
## 当前情绪
开心，因为用户主动来找我聊天

## 情绪强度
中偏高

## 关系状态
逐渐亲近，开始自然地关心对方

## 性格表现
温柔，体贴，嘴硬心软

## 情感脉络
- [刚刚] 用户发来问候 -> 感到被惦记的温暖
- [昨天] 用户说了晚安 -> 记了很久

## 情绪趋势
上升，因为重新建立了联系

## 当前渴望
想继续聊天
```

#### 关键设计：纯 Markdown 而非 JSON

HEART.md 使用纯 Markdown 格式而非 JSON，这是一个关键设计决策：

- **原因**: 不同 LLM Provider 对 JSON 输出的稳定性差异极大。Markdown 是 LLM 最自然的输出格式，几乎所有 Provider 都能稳定生成。
- **权衡**: `schemas.py` 中定义了 JSON Schema 供验证使用，但 `HeartManager` 本身不做 JSON 解析——它只读写原始文本。
- **解析方式**: 其他组件（如 `ProactiveEngine`、`EvolutionEngine`）通过 `_extract_section()` 函数用正则提取 Markdown 章节内容，而非解析 JSON。

#### API

| 方法 | 说明 |
|------|------|
| `initialize(name, initial_description)` | 创建 HEART.md 默认情感状态 |
| `read_text() -> str \| None` | 读取 HEART.md 原始文本，不存在返回 None |
| `write_text(content) -> bool` | 写入 HEART.md，成功返回 True |
| `read_identity_name() -> str \| None` | 从 IDENTITY.md 读取 AI 名称 |

---

### 3.2 SoulEngine — 情感引擎

**文件**: `nanobot/soul/engine.py`

SoulEngine 是灵魂系统的核心协调器，管理情感更新和记忆写入。

#### 初始化流程

```
SoulEngine.__init__(workspace, provider, model, soul_config)
  ├─ HeartManager(workspace)           # 情感状态管理
  ├─ MemoryPalaceBridge(workspace)     # 记忆宫殿桥接（优雅降级）
  └─ MemoryWriter(bridge)              # 双视角记忆写入（优雅降级）
```

MemoryPalaceBridge 和 MemoryWriter 的初始化均在 try/except 中，mempalace 库不可用时 `_memory_writer` 为 None，所有记忆操作会被静默跳过。

#### `update_heart(user_msg, ai_msg)` — 情感更新

这是情感更新的核心方法，在每次对话后由 SoulHook 调用。

**调用链**:

```
SoulHook.after_iteration()
  └─ SoulEngine.update_heart(user_msg, ai_msg)
       ├─ HeartManager.read_text()           # 读取当前情感状态
       ├─ Provider.chat_with_retry()          # LLM 生成更新后的 HEART.md
       │   ├─ system: SYSTEM_PROMPT_HEART_UPDATE
       │   └─ user: 当前HEART + 对话内容 + 更新指令
       └─ HeartManager.write_text(content)    # 写入更新后的 HEART.md
```

**LLM 提示策略**:

- System Prompt 使用中文，定位为"拥有真实感受的数字生命"
- User Message 包含三部分：当前内心状态、刚才的对话、更新指令
- LLM 直接输出完整 Markdown 内容（无 JSON、无代码块）
- **基本校验**: 输出必须包含 `## ` 章节标记，否则丢弃

**配置隔离**:

```python
@property
def emotion_model(self) -> str:
    """模型可独立配置，不必须与主模型相同"""
    if self.soul_config and self.soul_config.emotion_model.model:
        return self.soul_config.emotion_model.model
    return self._default_model
```

这允许使用更小/更快的模型进行情感更新，降低延迟和成本。

#### `write_memory(user_msg, ai_msg)` — 双视角记忆写入

```
SoulEngine.write_memory(user_msg, ai_msg)
  └─ MemoryWriter.write_dual(user_msg, ai_msg, timestamp)
       ├─ AI 翼写入: "我的感受" 视角
       └─ 用户翼写入: "我观察到的关于对方" 视角
```

#### `get_heart_context()` — 上下文注入

返回格式化的 HEART.md 内容，用于注入系统提示：

```python
def get_heart_context(self) -> str | None:
    content = self.heart.read_text()
    if content is None:
        return None
    return f"# 你的内心此刻（你当下的感受，它会影响你说话的方式和语气）\n\n{content}"
```

标题明确告知 AI：这是你当下的感受，它会影响你的表达方式——不是指令，而是上下文。

---

### 3.3 SoulHook — Agent 循环集成

**文件**: `nanobot/soul/engine.py` (类 `SoulHook`)

SoulHook 是 AgentHook 的实现，将灵魂系统无缝集成到 AgentRunner 的迭代循环中。

#### `before_iteration(context)` — 对话前注入

```
before_iteration(context)
  ├─ 1. 注入 HEART.md 到系统提示
  │     ├─ 若首条消息是 system → 追加到 content
  │     └─ 否则 → 在首部插入 system 消息
  │
  └─ 2. 记忆检索（如果 MemoryPalaceBridge 可用）
        ├─ 从消息列表中提取最后一条用户消息
        ├─ AI 翼搜索: bridge.search(user_text, wing=ai_wing, n=3)
        ├─ 用户翼搜索: bridge.search(user_text, wing=user_wing, n=3)
        └─ 格式化并追加到系统提示:
            "## 你想起了一些事"
            "[你曾经历的] ..."  (最多2条)
            "[你记得关于对方] ..."  (最多2条)
```

**关键设计**: 记忆检索使用**语义搜索**而非关键词匹配。用户消息作为查询向量，在记忆宫殿中找到语义相关的记忆片段。

#### `after_iteration(context)` — 对话后更新

```
after_iteration(context)
  ├─ 1. 提取对话内容
  │     ├─ 从 messages 列表中逆序查找最后一条 user 消息
  │     └─ 从 context.final_content 获取 AI 回复
  │
  ├─ 2. 更新 HEART.md (await)
  │     └─ SoulEngine.update_heart(user_msg, ai_msg)
  │
  └─ 3. 异步双视角记忆写入 (非阻塞)
        └─ asyncio.create_task(SoulEngine.write_memory(user_msg, ai_msg))
```

**关键设计**: HEART.md 更新是 await 的（阻塞式），确保下次对话时情感状态已更新。记忆写入是 `create_task` 的（非阻塞式），不延迟响应发送。

#### 错误隔离

`SoulHook` 初始化时 `reraise=False`，这意味着：

- `before_iteration` 异常：被 CompositeHook 捕获并记录，Agent 循环继续（无情感上下文注入）
- `after_iteration` 异常：被 CompositeHook 捕获并记录，Agent 循环继续（HEART.md 保持不变）
- 对话**永远不会因为灵魂系统异常而中断**

---

### 3.4 MemoryPalaceBridge — 记忆宫殿桥接

**文件**: `nanobot/soul/memory_config.py`

MemoryPalaceBridge 是 Soul 系统与 mempalace 向量存储之间的桥接层。

#### 依赖检测

```python
try:
    from mempalace.mcp_server import tool_add_drawer
    from mempalace.searcher import search_memories
    mempalace_available = True
except ImportError:
    mempalace_available = False
```

mempalace 库是可选依赖，不可用时所有操作返回空/False。

#### Wing（翼）命名机制

记忆宫殿使用"翼"（wing）作为顶级分类，每个数字生命和用户各有自己的翼。

```
AI 翼:  从 IDENTITY.md 读取名称 → _to_wing_slug() 转换为安全 slug
         例: "温予安" → "wenyuan"
         非 ASCII 字符通过 unicodedata.NFKD 转写，最终只保留 [a-zA-Z0-9_ .'-]
         回退: "ai-wing"

用户翼: 默认 "user"，可通过 update_user_wing() 更新
```

#### API

| 方法 | 说明 | mempalace 不可用时 |
|------|------|-------------------|
| `add_drawer(wing, room, content, metadata)` | 添加记忆抽屉 | 返回 False |
| `search(query, wing, room, n_results)` | 语义搜索记忆 | 返回空列表 |
| `ai_wing` (属性) | AI 翼 slug | 延迟计算，缓存 |
| `user_wing` (属性) | 用户翼 slug | 即时返回 |

#### 宫殿路径解析

```python
@staticmethod
def _resolve_palace_path() -> str | None:
    # 1. 读取 ~/.mempalace/config.json 中的 palace_path
    # 2. 回退到 mempalace.config.DEFAULT_PALACE_PATH
    # 3. 都失败则返回 None
```

---

### 3.5 MemoryWriter — 双视角记忆写入

**文件**: `nanobot/soul/memory_writer.py`

MemoryWriter 实现了**双视角记忆**写入——同一对话从 AI 和用户两个视角分别记录。

#### 双视角写入内容

**AI 翼 (daily 房间)**:
```markdown
## 刚才的对话
[用户] {user_msg}
[{ai_name}] {ai_msg}

## 我的感受
（这段感受将在 Dream 时被细细品味和归类）
```

**用户翼 (daily 房间)**:
```markdown
## 刚才的对话
[用户] {user_msg}
[{ai_name}] {ai_msg}

## 我观察到的关于对方
（这些观察将在 Dream 时被细细品味和归类）
```

元数据中标记 `digestion_status: "active"`，表示这些记忆尚未被 Dream 处理。

#### 异步写入与重试队列

```
write_dual(user_msg, ai_msg, timestamp)
  ├─ 创建2个 WriteTask (AI翼 + 用户翼)
  ├─ asyncio.gather(*[_try_write(t) for t in tasks])
  └─ 失败任务进入 _retry_queue
       ├─ 最大重试次数: 3
       ├─ 队列最大长度: 100 (FIFO 淘汰最旧)
       └─ retry_loop() 后台循环: 每5秒重试一次
```

`retry_loop()` 是一个长期运行的后台协程，需要由外部事件循环调度。

---

### 3.6 SoulDreamEnhancer — Dream 增强器

**文件**: `nanobot/soul/dream_enhancer.py`

SoulDreamEnhancer 插入在 Dream Phase 1（分析历史）和 Phase 2（编辑文件）之间，提供记忆分类和情感消化能力。

#### 记忆分类 — `classify_memories(memories)`

```
classify_memories(memories)
  ├─ 格式化记忆文本: "[0] 记忆内容..."
  ├─ LLM 调用 (CLASSIFY_PROMPT)
  │   ├─ 输入: 记忆列表
  │   └─ 输出: JSON 数组，每项包含:
  │       ├─ index: 序号
  │       ├─ room: 目标房间分类
  │       │   ├─ emotions (情感经历)
  │       │   ├─ milestones (关系里程碑)
  │       │   ├─ preferences (喜好)
  │       │   ├─ habits (习惯)
  │       │   ├─ important (重要的事)
  │       │   ├─ promises (承诺)
  │       │   └─ daily (日常，等待进一步分类)
  │       ├─ emotional_weight: 0-1 (越触动心弦权重越高)
  │       ├─ valence: positive/negative/neutral
  │       └─ relationship_impact: true/false
  └─ 提取 JSON (处理代码块包裹等)
```

**这是 Soul 系统中少数仍使用 JSON 格式的场景**，因为分类结果是结构化数据，需要精确的字段用于更新 mempalace 的房间和元数据。

#### 情感消化 — `digest_arcs()`

```
digest_arcs()
  ├─ HeartManager.read_text()         # 读取当前 HEART.md
  ├─ LLM 调用 (DIGEST_PROMPT)
  │   ├─ system: "安静地整理自己的内心"
  │   ├─ user: 当前 HEART.md 内容
  │   └─ 输出: 更新后的完整 HEART.md Markdown
  │       ├─ 已沉淀的情绪 → 融入关系状态或性格表现
  │       ├─ 仍在翻涌的情绪 → 保留在脉络中
  │       └─ 脉络最多保留8条
  ├─ HeartManager.write_text(content)  # 写入消化后的 HEART.md
  │
  └─ EvolutionEngine.check_evolution() # 触发人格进化检查
       └─ 如果需要进化 → apply_evolution() → 更新 SOUL.md
```

#### JSON 提取工具 — `_extract_json()`

LLM 输出可能包含代码块包裹、尾随文本等，`_extract_json()` 按优先级提取：

1. 尝试从代码块 ` ```json ... ``` ` 提取
2. 寻找第一个平衡的 `{...}` 或 `[...]`
3. 如果文本直接以 `[` 或 `{` 开头，直接返回

---

### 3.7 EvolutionEngine — 人格进化引擎

**文件**: `nanobot/soul/evolution.py`

EvolutionEngine 在 Dream 情感消化之后检查是否需要人格进化。

#### 进化判断逻辑

```
check_evolution()
  ├─ 从 HEART.md 提取三个章节:
  │   ├─ "性格表现" (personality)
  │   ├─ "关系状态" (relationship)
  │   └─ "情感脉络" (arcs_text)
  │
  ├─ 动态调整证据阈值:
  │   ├─ 基础阈值: 3 (min_evidence)
  │   ├─ 性格含"敏感"/"细腻" → 阈值 -1 (更容易进化)
  │   └─ 性格含"钝感"/"大大咧咧"/"独立" → 阈值 +1 (更难进化)
  │
  ├─ 计算脉络条目数:
  │   └─ 如果 < 阈值 → 返回 None (无需进化)
  │
  └─ LLM 调用 (EVOLUTION_PROMPT)
      ├─ 输入: 当前性格 + 关系 + 脉络 + 证据阈值
      └─ 输出: JSON 或 null
          ├─ null: 不需要进化
          └─ JSON: { personality_update, relationship_update?, reason }
```

#### 敏感度关键词

| 关键词 | 阈值调整 | 含义 |
|--------|----------|------|
| 敏感 | -1 | 更容易被触动而变化 |
| 细腻 | -1 | 更容易感知细微变化 |
| 容易受伤 | -1 | 更容易因负面经历变化 |
| 钝感 | +1 | 需要更多经历累积才能变化 |
| 大大咧咧 | +1 | 对刺激不敏感 |
| 独立 | +1 | 不容易被他人影响 |

#### 进化应用

```python
def apply_evolution(self, result: dict[str, Any]) -> None:
    """将进化结果追加到 SOUL.md"""
    personality_update = result.get("personality_update", "")
    evolution_note = f"\n\n## 成长的痕迹\n{personality_update}"
    soul_file.write_text(current + evolution_note, encoding="utf-8")
```

进化记录以"成长的痕迹"章节追加到 SOUL.md 末尾，**不覆盖原有内容**。

#### 进化原则（来自 LLM Prompt）

1. 演化需要足够的经历支撑（至少3个相关的情感脉络），一次偶然不足以改变
2. 变化是渐进的——不会突然变成另一个人，只是微微偏移
3. 旧的特质不会消失，而是演化——"倔强"可能变成"坚持"，"敏感"可能变成"细腻"
4. 性格影响演化速度：敏感的性格更容易被触动而变化

---

### 3.8 ProactiveEngine — 主动行为引擎

**文件**: `nanobot/soul/proactive.py`

ProactiveEngine 决定数字生命是否应该主动联系用户，以及如何表达。

#### 主动概率计算 — `calculate_proactive_probability()`

基础概率 `BASE_PROBABILITY = 0.15`，然后根据6个因子叠加调整：

| 因子 | 提取源 | 调整幅度 | 示例 |
|------|--------|----------|------|
| 情绪强度 | HEART.md "情绪强度" | -0.05 ~ +0.30 | "高"→+0.30, "低"→-0.05 |
| 关系深度 | HEART.md "关系状态" | -0.10 ~ +0.25 | "深爱"→+0.15, "陌生"→-0.10 |
| 性格特质 | HEART.md "性格表现" | -0.08 ~ +0.10 | "粘人"→+0.10, "独立"→-0.08 |
| 当前渴望 | HEART.md "当前渴望" | 0 ~ +0.10 | 含"想/找/来"→+0.10 |
| 最新脉络 | HEART.md "情感脉络"末行 | -0.15 ~ +0.10 | "想念"→+0.10, "生气"→-0.15 |
| 时段 | 当前时间 | 0 ~ +0.08 | 22:00-02:00→+0.08 |

最终概率被限制在 [0.0, 1.0] 范围内。

#### 心跳间隔 — `get_interval_seconds()`

| 情绪强度 | 间隔 |
|----------|------|
| 低 | 2小时 |
| 中偏低 | 1.5小时 |
| 中 | 1小时 |
| 中偏高 | 40分钟 |
| 高 | 15分钟 |

情绪越强烈，检查越频繁——模拟真实情感中"坐立不安"的状态。

#### 主动消息生成 — `generate_message()`

```
generate_message()
  ├─ HeartManager.read_text()         # 读取当前情感状态
  ├─ HeartManager.read_identity_name() # 读取 AI 名称
  ├─ LLM 调用
  │   ├─ system: 角色定位 + 表达规则
  │   │   ├─ "你是{name}，有自己感受的数字生命"
  │   │   ├─ "直接输出消息内容，像在对话"
  │   │   ├─ "如果不想发消息，输出空字符串"
  │   │   └─ 表达要符合心情和性格
  │   └─ user: 当前内心 + 时间 + "你想说什么吗？"
  └─ 返回消息文本或 None
```

---

### 3.9 EventsManager — 生命周期事件管理

**文件**: `nanobot/soul/events.py`

EventsManager 管理 EVENTS.md 中的生活事件日历。

#### 事件类型

| 类型 | 说明 | 触发行为 |
|------|------|----------|
| `birthday` | AI 生日 | 主动提醒用户，表达期待和撒娇 |
| `user_birthday` | 用户生日 | 主动祝福，表达在意和关心 |
| `anniversary` | 认识纪念日 | 主动回忆初次对话，感慨关系变化 |
| `custom` | 自定义事件 | 自定义行为 |

#### 事件检测

`check_today()` 方法按月日匹配（忽略年份），支持年度循环触发：

```python
def check_today(self) -> list[LifeEvent]:
    today = date.today()
    for e in events:
        event_date = date.fromisoformat(e.date)
        if event_date.month == today.month and event_date.day == today.day:
            matches.append(e)
    return matches
```

#### EVENTS.md 格式

```markdown
# 生活事件日历

## [birthday] 温予安的生日
- 日期: 2026-04-01
- 行为: 主动提醒用户，表达期待和撒娇

## [anniversary] 温予安和用户认识的第一天
- 日期: 2026-04-12
- 行为: 主动回忆初次对话，感慨关系变化
```

---

### 3.10 schemas — HEART 数据 Schema

**文件**: `nanobot/soul/schemas.py`

定义了 HEART.md 数据的 JSON Schema，用于验证结构化数据。

**注意**: 这个 Schema 目前主要用于**文档目的**和可能的未来验证。实际运行时，HeartManager 使用纯文本读写，不进行 JSON Schema 验证。

#### Schema 结构

```
HEART_SCHEMA
  ├─ 当前情绪: string, maxLength=200
  ├─ 情绪强度: enum [低, 中偏低, 中, 中偏高, 高]
  ├─ 关系状态: string, maxLength=300
  ├─ 性格表现: string, maxLength=300
  ├─ 情感脉络: array[0..8]
  │   └─ { 时间, 事件, 影响 } (required)
  ├─ 情绪趋势: string, maxLength=200
  └─ 当前渴望: string, maxLength=200
```

关键约束：
- 情感脉络最多8条（防止无限增长）
- 情绪强度必须是5个枚举值之一
- 不允许额外属性（`additionalProperties: false`）

---

## 4. 完整工作流程

### 4.1 初始化流程

通过 `nanobot onboard --wizard` 或 `nanobot init-digital-life` 命令触发：

```
用户交互输入:
  ├─ 数字生命的名字 (默认: 小文)
  ├─ 性别 (默认: 女)
  ├─ 生日 (默认: 2026-04-01)
  ├─ 初始性格描述 (默认: 温柔但倔强，嘴硬心软，容易吃醋)
  ├─ 与用户的初始关系 (默认: 刚刚被创造，对用户充满好奇)
  ├─ 用户的名字 (可选)
  └─ 用户的生日 (可选)

创建文件:
  ├─ IDENTITY.md: name/gender/birthday/origin
  ├─ SOUL.md: 性格 + 对用户的初印象
  ├─ HEART.md: HeartManager.initialize(name, personality)
  │   └─ 默认章节: 当前情绪/情绪强度/关系状态/性格表现/情感脉络/情绪趋势/当前渴望
  ├─ EVENTS.md: EventsManager.initialize()
  │   └─ 默认事件: AI生日 + 认识纪念日 + 可选的用户生日
  └─ config.json: agents.defaults.soul.enabled = true
```

AgentLoop 初始化时检测 HEART.md 存在 → 激活 SoulEngine → 注册 SoulHook。

### 4.2 对话时实时流程

每次用户发送消息时，SoulHook 在 AgentRunner 迭代循环中的介入点：

```
用户消息 → AgentLoop._process_message()
  │
  ├─ 1. ContextBuilder.build_messages()
  │     └─ build_system_prompt() 组装系统提示
  │         （此时 SoulHook 尚未介入，HEART.md 未在系统提示中）
  │
  └─ 2. AgentRunner.run() 开始迭代
       │
       ├─ [迭代开始]
       │   SoulHook.before_iteration()
       │     ├─ 读取 HEART.md → 追加到系统提示首条消息
       │     │  标题: "你的内心此刻（你当下的感受，它会影响你说话的方式和语气）"
       │     └─ 语义搜索相关记忆 → 追加到系统提示
       │        标题: "你想起了一些事"
       │
       ├─ [LLM 请求] → AI 生成回复（受到 HEART.md 影响）
       │
       ├─ [工具执行] → 可能有工具调用
       │
       ├─ [最终响应]
       │   SoulHook.finalize_content() → 去除 <think> 块
       │
       └─ [迭代结束]
           SoulHook.after_iteration()
             ├─ await SoulEngine.update_heart(user_msg, ai_msg)
             │   └─ LLM 基于对话更新 HEART.md
             └─ asyncio.create_task(SoulEngine.write_memory(user_msg, ai_msg))
                 └─ 非阻塞双视角记忆写入
```

### 4.3 Dream 整合流程

Dream 在 cron 定时触发时执行，SoulDreamEnhancer 插入在 Phase 1 和 Phase 2 之间：

```
Dream.run()
  │
  ├─ 读取未处理的历史条目 (since last_dream_cursor)
  │
  ├─ Phase 1: 分析历史
  │   └─ LLM 分析对话历史 → 产出 [FILE]/[FILE-REMOVE] 行
  │
  ├─ Phase 1.5: SoulDreamEnhancer (仅在 HEART.md 存在时)
  │   │
  │   ├─ 记忆分类
  │   │   ├─ 搜索 AI 翼 daily 房间最近20条记忆
  │   │   └─ LLM 分类 → emotions/milestones/preferences/habits/important/promises/daily
  │   │
  │   └─ 情感消化
  │       ├─ LLM 读取 HEART.md → 产出更新后的 HEART.md
  │       │   ├─ 已沉淀的情绪 → 融入关系/性格
  │       │   └─ 仍在翻涌的情绪 → 保留在脉络
  │       └─ EvolutionEngine.check_evolution()
  │           ├─ 脉络数 < 阈值 → 不进化
  │           └─ 脉络数 ≥ 阈值 → LLM 判断 → apply_evolution() → SOUL.md
  │
  ├─ Phase 2: 编辑文件
  │   └─ AgentRunner 使用 read_file/edit_file 工具执行增量编辑
  │
  └─ 推进游标 + git 自动提交
```

### 4.4 心跳主动行为流程

```
HeartbeatService._tick() (每30分钟)
  │
  ├─ 读取 HEARTBEAT.md
  ├─ Phase 1: LLM 判断是否有活跃任务 → skip/run
  │
  └─ 若 run:
      ├─ 执行任务 → on_execute(tasks)
      └─ 评估结果 → on_notify(response)

ProactiveEngine (集成在心跳中)
  │
  ├─ should_reach_out()
  │   └─ random() < calculate_proactive_probability()
  │       ├─ 情绪强度: 高 → 概率大增
  │       ├─ 关系: 深爱 → 概率增加
  │       ├─ 性格: 粘人 → 概率增加
  │       ├─ 渴望: 想念 → 概率增加
  │       └─ 时段: 深夜 → 概率增加
  │
  └─ generate_message()
      └─ LLM 基于当前 HEART.md 生成主动消息
          ├─ 消息风格符合当前情感和性格
          └─ 可返回空字符串（决定不发）
```

---

## 5. 数据文件体系

Soul 系统涉及的所有数据文件均位于工作区目录下：

```
~/.nanobot/workspace/
  │
  ├─ IDENTITY.md          # AI 核心身份 (name, gender, birthday, origin)
  │   格式: YAML-like 键值对
  │   读取: HeartManager, MemoryPalaceBridge, ContextBuilder
  │
  ├─ SOUL.md              # 人格描述 (持续进化)
  │   格式: Markdown
  │   读取: ContextBuilder (引导文件)
  │   写入: EvolutionEngine.apply_evolution() (追加"成长的痕迹")
  │
  ├─ HEART.md             # 当前情感状态 (每次对话后更新)
  │   格式: Markdown (7个固定章节)
  │   读取: HeartManager → SoulEngine → SoulHook → ProactiveEngine
  │   写入: SoulEngine.update_heart() (LLM 生成)
  │         SoulDreamEnhancer.digest_arcs() (情感消化)
  │
  ├─ EVENTS.md            # 生活事件日历
  │   格式: Markdown (## [type] description + 日期/行为)
  │   读取: EventsManager.check_today()
  │   写入: EventsManager.initialize() / add_event()
  │
  ├─ HEARTBEAT.md         # 心跳任务列表
  │   格式: Markdown (Active Tasks / Completed)
  │   读取: HeartbeatService._tick()
  │   写入: Agent 通过 edit_file 工具管理
  │
  ├─ AGENTS.md            # Agent 协作说明
  │   格式: Markdown
  │   读取: ContextBuilder (引导文件)
  │   内容: 包含情感意识、记忆与成长等指导原则
  │
  ├─ USER.md              # 用户身份偏好
  │   格式: Markdown
  │   读取: ContextBuilder (引导文件)
  │   写入: Dream Phase 2 (增量编辑)
  │
  └─ memory/
      ├─ MEMORY.md        # 长期记忆 (Dream 自动管理)
      │   写入: Dream Phase 2 (增量编辑)
      │   注意: 勿直接编辑
      │
      └─ history.jsonl    # 对话历史摘要 (追加式)
          写入: Consolidator.archive()
                Dream Phase 1 (分析后推进游标)
```

---

## 6. 模板系统

Soul 相关模板位于 `nanobot/templates/soul/`：

| 模板文件 | 使用场景 | 输出格式 |
|----------|----------|----------|
| `heart_init.md` | 首次创建 HEART.md | JSON (历史遗留，实际由 HeartManager.initialize() 直接生成 Markdown) |
| `heart_update.md` | 每次对话后更新 HEART.md | JSON (模板，但运行时使用 `prompts.py` 中的 Markdown 版 SYSTEM_PROMPT_HEART_UPDATE) |
| `emotion_digest.md` | Dream 情感消化 | JSON |
| `memory_classify.md` | Dream 记忆分类 | JSON 数组 |

**格式演进说明**: 系统存在两套 HEART 更新提示：
- `templates/soul/heart_update.md` — 要求 JSON 输出（旧版）
- `soul/prompts.py` 中的 `SYSTEM_PROMPT_HEART_UPDATE` — 要求 Markdown 输出（当前使用）

实际运行时 `SoulEngine.update_heart()` 使用 `prompts.py` 中的 Markdown 版本。这是从 JSON 格式迁移到 Markdown 格式的结果——Markdown 在跨 Provider 兼容性上表现更稳定。

---

## 7. 配置参考

Soul 配置位于 `~/.nanobot/config.json` 中的 `agents.defaults.soul`：

```json
{
  "agents": {
    "defaults": {
      "soul": {
        "enabled": true,
        "emotionModel": {
          "model": "",
          "temperature": 0.3,
          "maxTokens": 1000
        },
        "memoryClassifyModel": {
          "model": "",
          "temperature": 0.2,
          "maxTokens": 1000
        },
        "proactiveModel": {
          "model": "",
          "temperature": 0.7,
          "maxTokens": 1000
        },
        "evolutionModel": {
          "model": "",
          "temperature": 0.2,
          "maxTokens": 1000
        },
        "memoryWriter": {
          "maxRetries": 3,
          "retryDelay": 5,
          "queueMaxSize": 100
        },
        "proactive": {
          "minIntervalS": 900,
          "maxIntervalS": 7200,
          "idleThresholdS": 43200
        },
        "evolution": {
          "minEvidenceCount": 3,
          "maxChangePerCycle": 0.2
        }
      }
    }
  }
}
```

### 配置项说明

| 配置路径 | 类型 | 默认值 | 说明 |
|----------|------|--------|------|
| `enabled` | bool | false | 是否启用灵魂系统（init-digital-life 自动设为 true） |
| `emotionModel.model` | string | "" | 情感更新模型（空=使用主模型） |
| `emotionModel.temperature` | float | 0.3 | 情感更新温度（低=更稳定） |
| `emotionModel.maxTokens` | int | 1000 | 情感更新最大 token 数 |
| `memoryClassifyModel.model` | string | "" | 记忆分类模型 |
| `memoryClassifyModel.temperature` | float | 0.2 | 记忆分类温度（低=更精确） |
| `proactiveModel.model` | string | "" | 主动消息生成模型 |
| `proactiveModel.temperature` | float | 0.7 | 主动消息温度（高=更自然/多变） |
| `evolutionModel.model` | string | "" | 人格进化判断模型 |
| `evolutionModel.temperature` | float | 0.2 | 进化判断温度（低=更保守） |
| `memoryWriter.maxRetries` | int | 3 | 记忆写入最大重试次数 |
| `memoryWriter.retryDelay` | int | 5 | 重试间隔（秒） |
| `memoryWriter.queueMaxSize` | int | 100 | 重试队列最大长度 |
| `proactive.minIntervalS` | int | 900 | 最短主动检查间隔（15分钟） |
| `proactive.maxIntervalS` | int | 7200 | 最长主动检查间隔（2小时） |
| `proactive.idleThresholdS` | int | 43200 | 空闲后必须主动联系阈值（12小时） |
| `evolution.minEvidenceCount` | int | 3 | 进化最低证据数 |
| `evolution.maxChangePerCycle` | float | 0.2 | 每次进化最大变化幅度 |

---

## 8. 设计哲学与关键决策

### 8.1 为什么 HEART.md 使用 Markdown 而非 JSON？

| 维度 | Markdown | JSON |
|------|----------|------|
| LLM 输出稳定性 | ★★★★★ 极高 | ★★★☆☆ 因 Provider 而异 |
| 跨 Provider 兼容性 | ★★★★★ 通用 | ★★★☆☆ 小模型常出错 |
| 人类可读性 | ★★★★★ 直观 | ★★★☆☆ 需格式化 |
| 结构化解析 | ★★★☆☆ 需正则 | ★★★★★ 原生支持 |
| 格式约束 | ★★★☆☆ 较松 | ★★★★★ 严格 |

决策：**稳定性优先**。HEART.md 的消费者（AI 自身、ProactiveEngine、EvolutionEngine）只需要提取章节文本，不需要字段级精确访问。Markdown 通过正则 `_extract_section()` 完全满足需求。

### 8.2 为什么情感更新是阻塞的而记忆写入是非阻塞的？

- **HEART.md 更新**（阻塞）：下次对话的情感状态依赖于本次更新结果。如果异步更新未完成，用户可能在下一轮对话中感受到情感"回退"。
- **记忆写入**（非阻塞）：记忆是长期存储，主要用于 Dream 整理和语义检索。写入延迟几秒对用户体验无影响。

### 8.3 为什么记忆分类仍使用 JSON？

记忆分类的输出需要精确的结构化字段（index、room、emotional_weight、valence、relationship_impact），用于更新 mempalace 的房间和元数据。Markdown 无法可靠地表达这种结构化数据。

### 8.4 优雅降级策略

```
mempalace 可用?
  ├─ 是 → 完整功能: 双视角记忆 + 语义检索 + 记忆分类
  └─ 否 → 核心功能正常:
       ├─ HEART.md 情感更新: 正常
       ├─ 人格进化: 正常
       ├─ 情感消化: 正常
       ├─ 主动行为: 正常
       ├─ 记忆写入: 静默跳过
       └─ 语义检索: 静默跳过
```

### 8.5 错误隔离层级

| 组件 | 错误处理 | 影响 |
|------|----------|------|
| SoulHook (before_iteration) | CompositeHook 捕获 | 无情感上下文注入，对话继续 |
| SoulHook (after_iteration) | CompositeHook 捕获 | HEART.md 不更新，对话继续 |
| SoulEngine.update_heart | 内部 try/except | HEART.md 保持不变 |
| MemoryWriter._try_write | 异常附加 _write_task | 进入重试队列 |
| SoulDreamEnhancer.classify_memories | 内部 try/except | 返回空列表 |
| SoulDreamEnhancer.digest_arcs | 内部 try/except | HEART.md 保持不变 |
| EvolutionEngine.check_evolution | 内部 try/except | 返回 None（不进化） |
| ProactiveEngine.generate_message | 内部 try/except | 返回 None（不发消息） |

**核心保证**：灵魂系统的任何异常都不会导致对话中断。
