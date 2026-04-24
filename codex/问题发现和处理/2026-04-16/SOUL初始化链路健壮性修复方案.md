# SOUL 初始化链路健壮性修复方案

## 1. 修复目标

围绕 `soul init`，本次修复目标不是单独修一条 `SOUL.md` 写入逻辑，而是一次性补齐初始化链路的 3 个核心缺口：

1. 去除 `--only SOUL.md --force` 对旧 `SOUL.md` seed 的反向依赖
2. 将 `SOUL.md` / `SOUL_PROFILE.md` 初始化改为真正的正向顺序：
   - 先结构化真源
   - 后自然语言投影
3. 扩展 `SOUL_GOVERNANCE.json` 的治理角色，使其成为初始化链路中的有效治理源，而不只是静态 stub

## 2. 修复原则

- 不改外部依赖
- 不扩边界到对话链路、Dream、Proactive
- 以最小必要改动重建初始化闭环
- 统一初始化链路与运行期演化链路的 `SOUL.md` 生成方式

## 3. 修复思路总览

### 3.1 真源重定义

初始化阶段应明确：

- `SOUL_PROFILE.md` 是结构化真源
- `SOUL.md` 是投影表达层

因此初始化结果不再接受：

- `SOUL.md` 与 `SOUL_PROFILE.md` 并列为同级真值

而应改为：

- `profile` 为真值
- `SOUL.md` 为投影结果

### 3.2 顺序重定义

不论是完整初始化还是局部初始化，都应统一走下面的顺序：

1. 准备 payload
2. 推理并裁决结构化 `profile`
3. 写入 `SOUL_PROFILE.md`
4. 使用 `project_soul_from_profile()` 生成并写入 `SOUL.md`
5. 写入 `HEART.md`
6. 记录 trace / audit

### 3.3 治理重定义

`SOUL_GOVERNANCE.json` 应逐步从“初始化门槛配置”升级为“初始化治理配置入口”。

现阶段不需要一次做成超大治理系统，但至少应承担：

- init 阶段允许的关系阶段集合
- 边界下限
- 是否允许仅重建 `SOUL.md`
- 是否必须依赖 `SOUL_PROFILE.md`

## 4. 三个问题的对应修复

### 问题 1：旧 `SOUL.md` 被复用为 seed

#### 修复策略

- 对涉及 `SOUL.md` 的局部初始化，不再从现有 `SOUL.md` 提取：
  - `性格`
  - `初始关系`

#### 推荐实现

- 在 `collect_payload_for_targets()` 调用链上增加 target-aware 行为
- 当目标包含 `SOUL.md` 时：
  - 不从旧 `SOUL.md` 读取人格与关系 seed
  - 若需要 seed，优先从 `SOUL_PROFILE.md` 推导，或要求显式输入

#### 修复结果

- `--only SOUL.md --force` 不再把旧版 `SOUL.md` 当作“初始化原料”

### 问题 2：同时初始化 `SOUL.md` 和 `SOUL_PROFILE.md` 仍然没有正向顺序

#### 修复策略

- 即使两个目标一起指定，也必须内部强制改成：
  - 先 `SOUL_PROFILE.md`
  - 后 `SOUL.md`

#### 推荐实现

- `infer_adjudicated_soul_init()` 仍然可以产出候选 `profile`
- 但最终 `SOUL.md` 不再采用候选 `soul_markdown` 直接落盘
- 统一改由 `project_soul_from_profile()` 生成

#### 修复结果

- 同时初始化不再是“并列直接写两个文件”
- 而是真正的“结构化真源先行”

### 问题 3：`SOUL_GOVERNANCE.json` 是静态 stub

#### 修复策略

- 不要求一次把治理系统做大
- 但应把它从“静态模板”升级成“初始化链路的显式规则载体”

#### 第一阶段建议扩展字段

建议在 `init` 下增加：

- `require_profile_projection_for_soul`: `true`
- `allow_soul_only_without_profile`: `false`
- `allow_existing_soul_seed_for_init`: `false`

#### 修复结果

- 初始化链路的关键行为不再散落在代码隐式约定里
- 而是被治理配置显式表达

## 5. 推荐方案

推荐采用 **联修方案**，一次修完整条初始化闭环：

### 方案 A：只修 seed 来源

优点：

- 改动小

缺点：

- 仍未解决正向顺序问题
- 也未解决治理配置空心化问题

结论：

- 不推荐

### 方案 B：修 seed + 强制 `SOUL.md` 走投影

优点：

- 能解决主要一致性问题

缺点：

- `SOUL_GOVERNANCE.json` 仍然只是弱治理

结论：

- 可接受，但不是最佳

### 方案 C：三问题联修

内容：

- 修 seed 来源
- 修初始化顺序
- 扩展治理配置作用域

优点：

- 能一次把初始化闭环补完整
- 与昨天整改目标最一致

缺点：

- 改动范围略大于单点修复

结论：

- 推荐方案

## 6. 修复后的目标行为

### 场景 1：完整初始化

执行 `soul init` 时：

1. 生成并裁决 `profile`
2. 写入 `SOUL_PROFILE.md`
3. 投影生成 `SOUL.md`
4. 写入 `HEART.md`

### 场景 2：`--only SOUL.md --force`

执行时：

- 若存在 `SOUL_PROFILE.md`
  - 直接从 `SOUL_PROFILE.md` 重投影 `SOUL.md`
- 若不存在 `SOUL_PROFILE.md`
  - 明确报错，不允许继续“伪重初始化”

### 场景 3：`--only SOUL.md --only SOUL_PROFILE.md --force`

执行时：

- 先裁决并写 `SOUL_PROFILE.md`
- 再基于它投影生成 `SOUL.md`

### 场景 4：治理覆盖

执行时：

- 初始化允许的关系阶段
- 边界最小值
- 是否允许单独重建 `SOUL.md`
- 是否允许复用旧 `SOUL.md` 作为 seed

都由 `SOUL_GOVERNANCE.json` 控制

## 7. 审计与日志调整

修复后 trace / audit 应明确区分：

- `candidate.soul_markdown`
  - LLM 原始候选
- `result.profile`
  - 裁决通过后的结构化真源
- `result.projected_soul_markdown`
  - 最终投影并写入磁盘的 `SOUL.md`

这样能避免以后再次出现：

- “日志显示初始化成功”
- “但不知道到底是哪一版 SOUL 被真正写入”

## 8. 风险与控制

### 风险 1：修复后初始化结果风格变化

原因：

- `SOUL.md` 将不再直接保留旧候选文风
- 而是服从 `SOUL_PROFILE.md` 投影结果

结论：

- 这是正确修复，不是副作用

### 风险 2：局部初始化会更严格

表现：

- 以前 `--only SOUL.md --force` 能跑
- 修复后可能直接报错

结论：

- 这是必要的边界收紧

### 风险 3：日志结构变化

表现：

- audit 格式会新增字段

结论：

- 可通过向后兼容字段方式解决

## 9. 方案结论

这次修复不应再被理解为：

- “修一下 SOUL.md 初始化”

而应明确成：

**“重建 `soul init` 的初始化闭环，使其回到方法论驱动的正向流程。”**

只有把：

- seed 来源
- 文件生成顺序
- 治理配置作用域

这三件事一起修掉，初始化链路才会真正健壮严谨。
