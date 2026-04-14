# SOUL 模块深度研究

> 研究时间：2026-04-13
> 研究方法：阅读 `nanobot/soul/`、相关接线代码、`tests/soul/`，并执行定向测试验证。

## 1. 研究结论摘要

当前 `SOUL` 模块已经不是纯设计稿，而是一套真实接入 `nanobot` 主运行时的增强层，核心能力已经落地到：

- 对话前情感上下文注入
- 对话后 `HEART.md` 更新
- 双视角记忆写入
- Dream 阶段的情感消化与记忆分类尝试
- Gateway 下的主动行为与事件触发
- `soul init` 初始化工作区文件

但它同时也保留了明显的“演进中痕迹”：

- 部分配置定义存在，但没有真正被消费
- 部分模板文件仍是旧协议，代码已改走新协议
- `tests/soul/` 中有一部分仍绑定旧接口
- Dream 与记忆重试存在接线不完整点

一句话判断：

**SOUL 模块已经进入“真实可运行，但实现与设计、实现与测试并未完全收敛”的阶段。**

## 2. 模块边界与职责

`nanobot/soul/` 当前可以分成 6 个层次：

### 2.1 状态文件层

- `heart.py`
  - `HEART.md` 读写
- `events.py`
  - `EVENTS.md` 读写

这一层只负责文件状态，不做复杂编排。

### 2.2 对话时运行层

- `engine.py`
  - `SoulEngine`
  - `SoulHook`

这一层直接挂在 `AgentLoop` 的 hook 生命周期上，是 SOUL 最关键的运行入口。

### 2.3 记忆桥接层

- `memory_config.py`
  - mempalace 桥接
- `memory_writer.py`
  - 双视角异步写入

这一层负责和外部记忆宫殿系统沟通，不直接参与 prompt 设计。

### 2.4 周期性演化层

- `dream_enhancer.py`
  - Dream 中的分类与情感消化
- `evolution.py`
  - 性格/关系演化

这一层不在每轮消息上运行，而是挂在慢速整理阶段。

### 2.5 主动行为层

- `proactive.py`
  - 主动联系判断与消息生成

这一层只在 gateway + heartbeat 场景下有意义。

### 2.6 独立配置层

- `soul_config.py`
  - `~/.nanobot/soul.json` 读取与保存

这是 SOUL 当前最特殊的一层，因为它和主 `config.json` 并存。

## 3. SOUL 的真实入口

### 3.1 激活入口：`AgentLoop.__init__`

SOUL 当前不是显式总开关驱动，而是：

1. `AgentLoop` 初始化时检查工作区是否存在 `HEART.md`
2. 若存在，则实例化 `SoulEngine`
3. 再把 `SoulHook` 注册到 `_extra_hooks`

因此它的真实激活条件是：

- `HEART.md` 存在

而不是：

- `config.agents.defaults.soul.enabled == true`

### 3.2 初始化入口：`nanobot soul init`

CLI 当前真实存在的初始化命令是：

```bash
nanobot soul init
```

它会创建或初始化：

- `IDENTITY.md`
- `SOUL.md`
- `HEART.md`
- `EVENTS.md`

并尝试：

- 用 `EvolutionEngine.assess_initial_profile()` 评估初始认知功能图谱
- 追加到 `SOUL.md`
- 写入 `config.json` 的 `agents.defaults.soul.enabled = true`

但这里要注意：

- “写 enabled=true” 已经不是运行时真实激活条件
- 真正决定后续是否加载 SOUL 的还是 `HEART.md`

## 4. 对话生命周期中的 SOUL

### 4.1 `before_iteration`

`SoulHook.before_iteration()` 会做两件事：

1. 注入 `HEART.md`
2. 如 mempalace 可用，则做双翼记忆检索并拼到 system prompt

其流程可以概括为：

```text
读取 HEART.md
  -> 追加到 system message
  -> 提取最后一条 user message
  -> 去掉 Runtime Context 元信息
  -> 对 ai_wing / user_wing 各做一次语义搜索
  -> 基于当前 session 文本去重
  -> 将少量检索结果注入 system prompt
```

这一阶段体现了 SOUL 的设计重点：

- `HEART.md` 不是配置，而是“当下内心状态”
- 记忆检索不是直接替代历史，而是作为额外情境提示

### 4.2 `after_iteration`

`SoulHook.after_iteration()` 会做三件事：

1. 从消息列表中回溯最后一条用户消息
2. 调用 `SoulEngine.update_heart()` 更新 `HEART.md`
3. 若记忆系统启用，则异步提交 `write_memory()`

这里有几个实现细节值得记住：

- 用户消息会先剥离 Runtime Context 再参与情感分析
- 多模态用户消息只会提取文本块
- 记忆写入是 `asyncio.create_task()` 异步提交，不阻塞主回复

## 5. `HEART.md` 在当前实现里的地位

### 5.1 它是 SOUL 的主状态文件

当前实现中，`HEART.md` 同时承担：

- SOUL 激活锚点
- 对话风格即时上下文
- 主动行为判断输入
- Dream 情感消化输入
- 演化判断输入

这意味着 `HEART.md` 是整个 SOUL 的“热状态中心”。

### 5.2 当前格式已经稳定为 Markdown

代码侧已经非常明确地选择了：

- 纯 Markdown
- 不做运行时 JSON 解析
- 仅做基础章节结构校验

`heart.py` 和 `engine.py` 的实现都与这个方向一致。

### 5.3 `schemas.py` 仍存在，但地位已经下降

`nanobot/soul/schemas.py` 仍然定义了 JSON Schema，并带有 `validate_heart()`。

但从实际接线看：

- `update_heart()` 不使用它
- `HeartManager` 不使用它
- `DreamEnhancer.digest_arcs()` 也不使用它

所以它现在更接近：

- 旧设计遗留
- 文档/参考用途

而不是当前主路径依赖。

## 6. 记忆系统的真实状态

### 6.1 写入路径

`SoulEngine.write_memory()` -> `MemoryWriter.write_dual()` -> `MemoryPalaceBridge.add_drawer()`

双写内容分别为：

- AI 翼：`## 刚才的对话` + `## 我的感受`
- 用户翼：`## 刚才的对话` + `## 我观察到的关于对方`

当前实现特点：

- 不做 LLM 实时解读
- 只写“待 Dream 整理”的占位式内容
- 默认都写入 `daily` room

### 6.2 wing 命名的真实行为

`memory_config._to_wing_slug()` 的实现与注释存在落差。

代码注释写的是：

- 尝试把中文名转成接近拼音的 slug

但真实实现只是：

- `unicodedata.normalize("NFKD", name)`
- 再 `encode('ascii', 'ignore')`

所以对中文名的实际效果通常是：

- ASCII 全丢失
- 最终回退到 `"ai-wing"`

`tests/soul/test_memory_config.py` 也明确验证了这一点。

这意味着当前实现并没有真正做到中文名到拼音 slug 的稳定转写。

### 6.3 重试机制的现状

`MemoryWriter` 内部有：

- `_retry_queue`
- `_enqueue_retry()`
- `retry_loop()`

但我在当前仓库里没有检索到 `retry_loop()` 的启动入口。

这意味着现状更可能是：

- 写入失败可以入队
- 但后台消费循环没有被真正启动

换句话说，**“设计上有重试”不等于“运行中重试循环已接线”**。

## 7. Dream 中的 SOUL 接线

### 7.1 接线位置

SOUL 没有替换原 Dream，而是插在 `Dream.run()` 的中间：

1. 先做 Dream Phase 1 分析
2. 再进入 `SoulDreamEnhancer`
3. 最后再做 Dream Phase 2 文件编辑

### 7.2 当前增强内容

`SoulDreamEnhancer` 主要做两件事：

- `classify_memories()`
  - 仍然使用 JSON 输出
- `digest_arcs()`
  - 直接输出更新后的完整 `HEART.md`

### 7.3 一个已确认的接线问题

`digest_arcs()` 的返回值签名是：

- `bool`

但 `agent/memory.py` 中调用它后，后续代码却按“字典返回值”来使用：

```python
digest_result = await enhancer.digest_arcs()
if digest_result:
    logger.info(
        "SoulDreamEnhancer: digested {} arcs",
        len(digest_result.get("digested_indices", [])),
    )
```

这里的实际结果会是：

- `digest_result == True` 时进入分支
- 然后访问 `True.get(...)`
- 抛异常
- 被 `except` 吃掉
- 最终日志表现成 “emotion digestion skipped”

也就是说：

**当前情感消化逻辑即使成功更新了 `HEART.md`，在 Dream 调用端也会因为返回值协议不一致而被异常吞掉。**

这是目前 SOUL 模块里最明确的已接线 bug 之一。

## 8. 主动行为的真实状态

### 8.1 当前已经从“概率模型”转为“门控 + LLM 判定”

`proactive.py` 顶部注释已经表明当前方案是：

1. 硬约束门控
2. LLM 精判并顺带生成消息

也就是现在的核心接口是：

- `check_gate()`
- `decide_and_generate()`
- `get_interval_seconds()`

而不是旧的概率式接口。

### 8.2 当前主动行为只在 gateway 路径下真正接入

`cli/commands.py` 会在 `gateway` 启动时：

- 创建 `ProactiveEngine`
- 创建 `EventsManager`
- monkeypatch `heartbeat._tick`

增强后的 `_soul_aware_tick()` 大致流程：

1. 根据当前情绪强度调整 heartbeat 间隔
2. 检查今日事件
3. 调用 `decide_and_generate()`
4. 若决定主动联系，则发消息并补写 HEART/记忆
5. 否则回退普通 heartbeat

这说明主动行为不是 AgentLoop 内建行为，而是：

- Gateway 模式下对 HeartbeatService 的增强

### 8.3 主动行为配置存在双轨

当前主动行为使用的不是 `config.schema.SoulConfig.proactive_model`，而是：

- `~/.nanobot/soul.json`

更具体地：

- 硬约束来自 `SoulJsonConfig.proactive`
- LLM 参数来自 `SoulJsonConfig.proactive_llm`

### 8.4 代码注释与实现也有漂移

`proactive.py` 内部注释写的是：

- “Hard constraints are loaded from workspace/soul.json”

但 `soul_config.py` 实际明确写的是：

- `~/.nanobot/soul.json`

所以这里连模块内部文档都已经落后于实现。

## 9. 演化系统的真实状态

### 9.1 当前演化逻辑已经升级成“认知功能图谱模型”

`evolution.py` 当前不是简单改一段人格描述，而是：

- 使用 8 个认知功能强度值
- 计算 dominant / auxiliary / tertiary / inferior / shadow
- 对不同角色施加不同演化上限
- 再做 bonded traits 联动变化

这说明演化系统已经从“自然语言人格漂移”进入了“结构化人格动力学”阶段。

### 9.2 演化的真实返回协议

`check_evolution()` 当前要求 LLM 返回：

- `evolved_function`
- `direction`
- `reason`
- `manifestation`

然后代码会计算：

- `changes`
- `profile`

再交给 `apply_evolution()`

也就是说，当前协议是：

- LLM 决定“哪一维变化”
- 代码决定“怎么变、变多少”

### 9.3 `apply_evolution()` 的输入要求已经变了

`apply_evolution()` 当前依赖：

- `changes`
- `profile`

如果没有这两个字段，它会直接返回，不修改 `SOUL.md`。

这和旧测试里只传：

- `personality_update`
- `reason`

的做法已经不兼容。

## 10. 配置消费矩阵

下面是我按“定义了什么 / 现在是否真的被消费”整理的矩阵。

### 10.1 主 `config.json` 下的 `SoulConfig`

#### 已确认被消费

- `emotion_model.model`
- `emotion_model.temperature`
- `emotion_model.max_tokens`

消费位置：

- `SoulEngine.update_heart()`

#### 定义了，但当前仓库里未找到明确消费点

- `memory_classify_model`
- `proactive_model`
- `evolution_model`
- `memory_writer.max_retries`
- `memory_writer.retry_delay`
- `memory_writer.queue_max_size`
- `proactive.*`
- `evolution.*`
- `enabled`

这说明一个重要现状：

**`config.schema.SoulConfig` 的定义显著超前于当前接线程度。**

### 10.2 独立的 `~/.nanobot/soul.json`

这里反而是真正被主动行为消费的配置：

- `proactive.*`
- `proactive_llm.*`

并且实际消费点明确存在于：

- `ProactiveEngine`
- `gateway` 路径中的 SOUL 增强 heartbeat

## 11. 模板与 prompt 资源的现状

### 11.1 当前主路径使用的是 `prompts.py` 常量

例如：

- `SYSTEM_PROMPT_HEART_UPDATE`

是直接在代码里内嵌字符串常量。

### 11.2 `templates/soul/` 中仍有旧 JSON 协议模板

我确认到：

- `templates/soul/heart_update.md`
- `templates/soul/heart_init.md`

仍然要求输出严格 JSON。

而当前代码真实主路径已经改成：

- 输出完整 Markdown

### 11.3 `prompts.py` 中的模板路径常量目前没有实际消费

`prompts.py` 定义了：

- `HEART_UPDATE_TEMPLATE`
- `HEART_INIT_TEMPLATE`

但当前仓库里没有看到这些常量被真正使用。

所以这一块的真实状态是：

- 模板文件保留
- 常量保留
- 但主实现已经绕过模板，直接使用内嵌 prompt

## 12. 测试覆盖与当前测试状态

### 12.1 测试文件分布

`tests/soul/` 当前包含：

- `test_config.py`
- `test_dream_enhancer.py`
- `test_engine.py`
- `test_events.py`
- `test_evolution.py`
- `test_heart.py`
- `test_integration.py`
- `test_memory_config.py`
- `test_memory_writer.py`
- `test_proactive.py`
- `test_schemas.py`

### 12.2 第一次运行测试的环境现象

直接运行：

```bash
pytest tests/soul -q
```

结果不是先暴露仓库内部问题，而是先暴露环境问题：

- 当前 Python 环境优先导入了另一个外部安装的 `nanobot`
- 导致模块路径指向了别的仓库

这说明该仓库当前测试对环境隔离有依赖，不能无脑直接跑。

### 12.3 修正 `PYTHONPATH` 后的真实状态

执行：

```bash
$env:PYTHONPATH='E:\zfengl-ai-project\nanobot-wenyuan'; pytest tests/soul -q
```

结果：

- 测试在 collection 阶段被 `test_proactive.py` 阻断
- 阻断原因是它尝试导入当前实现里已经不存在的：
  - `INTENSITY_BOOST`
  - `INTENSITY_INTERVAL`

### 12.4 排除 `test_proactive.py` 后的结果

执行：

```bash
$env:PYTHONPATH='E:\zfengl-ai-project\nanobot-wenyuan'; pytest tests/soul/test_config.py tests/soul/test_dream_enhancer.py tests/soul/test_engine.py tests/soul/test_events.py tests/soul/test_evolution.py tests/soul/test_heart.py tests/soul/test_integration.py tests/soul/test_memory_config.py tests/soul/test_memory_writer.py tests/soul/test_schemas.py -q
```

结果：

- `121 passed`
- `3 failed`

失败全部集中在：

- `tests/soul/test_evolution.py`

### 12.5 失败本质

#### `test_proactive.py`

这份测试仍基于旧接口假设：

- 旧常量：`INTENSITY_BOOST` / `INTENSITY_INTERVAL`
- 旧方法：`calculate_proactive_probability()`

而当前 `ProactiveEngine` 已经迁移到：

- `check_gate()`
- `decide_and_generate()`
- `get_interval_seconds()`

所以这是**测试协议明显落后于实现**。

#### `test_evolution.py`

这份测试中有部分案例仍使用旧结果结构，例如：

- `personality_update`
- `reason`

但当前 `EvolutionEngine` 期望的是：

- `evolved_function`
- `direction`
- `manifestation`
- 并由代码生成 `changes` / `profile`

因此失败不是因为演化系统完全不可用，而是：

- 测试断言还绑定旧协议
- 代码已经切到新认知功能模型

## 13. 已确认的实现风险与漂移点

### 13.1 Dream 调用 `digest_arcs()` 的返回值协议错误

这是当前最明确的接线问题。

### 13.2 `MemoryWriter.retry_loop()` 看起来没有启动入口

重试设计存在，但后台消费者未见接线证据。

### 13.3 `SoulConfig` 大量字段未消费

定义与实现之间有明显差距。

### 13.4 `SoulConfig.enabled` 不是实际激活开关

真实激活还是靠 `HEART.md` 是否存在。

### 13.5 `templates/soul/` 与当前 prompt 协议不一致

模板保留 JSON，主实现走 Markdown。

### 13.6 `schemas.py` 仍依赖 `jsonschema`

但 `pyproject.toml` 中没有声明 `jsonschema` 依赖。

这意味着：

- 当前环境恰好安装了它，测试可通过
- 但从项目声明依赖来看，这个模块的依赖关系并不完整

### 13.7 主动行为与演化路径都存在“新实现 / 旧测试”并存现象

这说明模块已经经历了结构升级，但测试与文档没有同步收口。

## 14. 我对 SOUL 模块成熟度的判断

### 14.1 已经比较稳的部分

- `HEART.md` 的 Markdown 化
- `SoulHook` 对话前后接线
- `HeartManager`
- `EventsManager`
- `MemoryWriter` 的基础双写行为
- 基础集成流程

### 14.2 正在演进中的部分

- `ProactiveEngine`
- `EvolutionEngine`
- `DreamEnhancer`
- 配置体系收敛

### 14.3 还需要收口的部分

- 测试协议更新
- Dream 接线 bug 修正
- 重试循环启动
- 配置消费统一
- 旧模板/旧 schema 的定位清理

## 15. 后续继续研究的建议顺序

如果后续还要继续往下深挖，我建议分 3 条线继续：

1. `ProactiveEngine` 重构史与当前行为边界
2. `EvolutionEngine` 的认知功能模型是否真正闭环
3. `SoulConfig` / `soul.json` / 模板体系的收敛方案

## 16. 最终判断

`SOUL` 模块当前最真实的形态不是“一个单独的新框架”，而是：

**在 nanobot 主运行时上，通过 Hook、Dream、Heartbeat、CLI 初始化四条通道逐步拼接起来的数字生命增强层。**

它已经具备完整的核心叙事链：

- 有当下情感
- 有对话后更新
- 有双视角记忆
- 有慢速消化
- 有主动联系
- 有人格演化方向

但它也还没有完全完成工程收口：

- 配置、模板、测试、返回值协议仍有几处未统一
- 这也是当前继续开发 SOUL 模块时最值得优先处理的区域
