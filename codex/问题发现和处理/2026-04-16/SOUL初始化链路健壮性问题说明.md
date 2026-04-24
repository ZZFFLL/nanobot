# SOUL 初始化链路健壮性问题说明

## 1. 问题概述

围绕 `soul init` 初始化链路，当前已确认不是单点问题，而是至少存在 3 个彼此关联的结构性问题：

1. `--only SOUL.md --force` 会复用旧 `SOUL.md` 作为 seed，导致旧版非方法论文案被继续带入初始化输入。
2. 即使同时初始化 `SOUL.md` 和 `SOUL_PROFILE.md`，当前实现也没有走“先结构化、后投影”的正向完整流程，而是一次性并列生成并直接写入。
3. `SOUL_GOVERNANCE.json` 目前基本还是静态 stub，只对初始化阶段提供少量门槛治理，尚未成为完整的初始化/投影/演化治理源。

这 3 个问题指向同一个更高层结论：

**当前 `soul init` 初始化链路还没有形成“结构化真源 -> 投影表达层 -> 治理约束”的严格闭环，因此整体不够健壮，也不够方法论一致。**

## 2. 直接触发现象

### 现象 1：`SOUL.md` 看起来像没按新方法论初始化

执行：

```powershell
python -m nanobot.cli.commands soul init --config C:\Users\Administrator\.nanobot\config.json --only SOUL.md --force
```

终端输出显示：

- `Soul initialized via methodology-bound LLM candidate (attempt 1/3)`
- `overwritten: SOUL.md`

但磁盘上的 [SOUL.md](C:/Users/Administrator/.nanobot/workspace/SOUL.md) 内容仍然延续旧版、非 `SOUL_PROFILE.md` 一致投影风格。

### 现象 2：用户会自然认为 “同时初始化 `SOUL.md` + `SOUL_PROFILE.md` 应该按正向顺序完成”

从方法论和职责边界看，直觉上的正确流程应当是：

1. 先得到并裁决结构化 `SOUL_PROFILE.md`
2. 再由 `SOUL_PROFILE.md` 投影出自然语言 `SOUL.md`

但当前实现并不是这样。

### 现象 3：`SOUL_GOVERNANCE.json` 内容静态、治理覆盖面很窄

当前工作区中的 [SOUL_GOVERNANCE.json](C:/Users/Administrator/.nanobot/workspace/SOUL_GOVERNANCE.json) 与模板 [SOUL_GOVERNANCE.json](E:/zfengl-ai-project/nanobot-wenyuan/nanobot/templates/SOUL_GOVERNANCE.json) 完全一致，只有：

- `allowed_stages`
- `relationship_boundary_min`
- `boundary_expression_min`

这说明它目前还不是完整治理源，而更像初始化阶段的静态门槛配置。

## 3. 已核对证据

本次初始化日志位于：

- [初始化审计.json](C:/Users/Administrator/.nanobot/workspace/soul_logs/init/2026-04-16T09-29-20-初始化审计.json)
- [初始化追踪.jsonl](C:/Users/Administrator/.nanobot/workspace/soul_logs/init/2026-04-16T09-29-20-初始化追踪.jsonl)

核对结果：

1. 审计文件中的 `result.soul_markdown` 与当前磁盘上的 [SOUL.md](C:/Users/Administrator/.nanobot/workspace/SOUL.md) 内容一致。
2. 因此这不是“写入失败”或“写入后又被回滚”的问题。
3. 当前 `SOUL.md` 的确是本次初始化链路最终接受并落盘的内容。

## 4. 预期的正确初始化职责关系

当前系统已经引入：

- `SOUL_PROFILE.md`
- `SOUL_METHOD.md`
- `SOUL_GOVERNANCE.json`
- `project_soul_from_profile()`

从方法论一致性的角度，初始化后的职责关系应当是：

- `SOUL_PROFILE.md`：结构化慢状态真源
- `SOUL.md`：从 `SOUL_PROFILE.md` 投影出来的自然语言表达层
- `SOUL_GOVERNANCE.json`：初始化、投影、演化等链路共享的治理配置

也就是说，正确初始化应体现为：

1. 先在方法论与治理约束下得到结构化 `profile`
2. 再基于 `profile` 投影生成 `SOUL.md`
3. 整个过程持续受治理配置约束

## 5. 问题一：`--only SOUL.md --force` 会复用旧 `SOUL.md` 作为输入种子

### 5.1 根因

[init_files.py](E:/zfengl-ai-project/nanobot-wenyuan/nanobot/soul/init_files.py) 中：

- `collect_payload_for_targets()` 会优先读取现有工作区 seed
- `read_existing_seed()` 会直接从现有 `SOUL.md` 中提取：
  - `# 性格`
  - `# 初始关系`

因此在 `--only SOUL.md --force` 场景下：

- 旧版 `SOUL.md` 的人格/关系文案会重新进入 payload
- 新一轮初始化会在旧文案基础上继续生成

### 5.2 影响

- `force` 实际只表示“允许覆盖文件”
- 不表示“忽略旧 SOUL 种子重新初始化”
- 会让旧版非方法论文案持续污染新一轮初始化

## 6. 问题二：即使同时初始化 `SOUL.md` 与 `SOUL_PROFILE.md`，也没有走正向顺序

### 6.1 当前实现

即使用户同时指定：

```powershell
--only SOUL.md --only SOUL_PROFILE.md --force
```

当前链路也是：

1. 只跑一次 `infer_adjudicated_soul_init(...)`
2. LLM 一次性同时生成：
   - `soul_markdown`
   - `heart_markdown`
   - `profile`
3. `write_selected_files()` 再分别直接写：
   - `SOUL.md`
   - `SOUL_PROFILE.md`

而且当前局部写入顺序里，`SOUL.md` 还是先于 `SOUL_PROFILE.md` 被写入。

### 6.2 这为什么是问题

这意味着当前并不是：

`SOUL_PROFILE -> projection -> SOUL.md`

而是：

`LLM 一次性并列给出 soul_markdown + profile -> 直接分别写入`

因此：

- 即使“同时初始化”两个文件
- 也没有真正建立“结构化真源优先”的正向流程

## 7. 问题三：`SOUL_GOVERNANCE.json` 当前还是静态 stub

### 7.1 当前状态

[SOUL_GOVERNANCE.json](C:/Users/Administrator/.nanobot/workspace/SOUL_GOVERNANCE.json) 现在基本就是模板原样落地。

[methodology.py](E:/zfengl-ai-project/nanobot-wenyuan/nanobot/soul/methodology.py) 中读取它的主要入口是：

- `load_soul_governance()`
- `load_init_governance()`

但当前真正被消费的内容，主要只有初始化阶段的：

- `allowed_stages`
- `relationship_boundary_min`
- `boundary_expression_min`

### 7.2 这为什么是问题

这说明它目前更像：

- 初始化门槛配置

而不是：

- 初始化 / 投影 / 演化统一治理源

从方法论治理角度看，它的覆盖面还太窄，无法支撑完整闭环。

## 8. 为什么当前 `SOUL_PROFILE.md` 初始化比 `SOUL.md` 更可靠

### 8.1 `SOUL_PROFILE.md` 的方法论依据来源是存在的

初始化推理会把：

- 核心锚点
- SOUL 方法论
- 严格 JSON schema
- 阶段与边界治理要求

一起喂给模型。

### 8.2 `SOUL_PROFILE.md` 的程序侧裁决是强约束

[init_adjudicator.py](E:/zfengl-ai-project/nanobot-wenyuan/nanobot/soul/init_adjudicator.py) 会严格校验：

- 荣格八维是否齐全
- 数值范围是否合法
- `relationship.stage` 是否在允许集合中
- `boundary` / `boundary_expression` 是否满足治理阈值

### 8.3 `SOUL.md` 的程序侧裁决仍是弱约束

当前对 `SOUL.md` 只检查：

- 标题结构
- 空内容
- 越界词
- 是否混入方法论标题

不会检查：

- 是否与 `profile` 一致
- 是否由 `profile` 投影而来
- 是否延续旧版初始化风格

## 9. 统一根因

这 3 个问题可以统一归因到一件事：

**当前初始化链路把 `SOUL.md` 当成与 `SOUL_PROFILE.md` 并列的一等初始化产物，而不是把 `SOUL_PROFILE.md` 视为真源、把 `SOUL.md` 视为投影结果。**

由此带来了：

- 输入种子来源错误
- 文件生成顺序错误
- 治理配置使用过窄

## 10. 影响范围

当前问题会带来以下风险：

- 初始化后的 `SOUL.md` 与 `SOUL_PROFILE.md` 可能语义不一致
- 用户看到“按方法论初始化成功”，但外显人格文本仍可能延续旧版风格
- `--only SOUL.md --force` 的行为语义与用户直觉不一致
- 即使同时初始化 `SOUL.md` 与 `SOUL_PROFILE.md`，也不代表它们按正向顺序产生
- `SOUL_GOVERNANCE.json` 难以支撑更严格的初始化治理
- 初始化链路与演化/投影链路分叉，后续更难维护

## 11. 问题结论

当前 `soul init` 初始化链路存在 3 个已确认问题：

1. `--only SOUL.md --force` 错误复用旧 `SOUL.md` 作为输入种子
2. 同时初始化 `SOUL.md` 与 `SOUL_PROFILE.md` 也没有走“先 profile、后 projection”的正向流程
3. `SOUL_GOVERNANCE.json` 仍是静态 stub，治理覆盖面不足

因此可以明确判定：

**当前 `soul init` 初始化流程整体不够健壮，也不够严谨，尚未形成真正的“方法论驱动初始化闭环”。**
