# SOUL_PROFILE 生成与迭代逻辑说明

> 日期：2026-04-15
> 范围：当前 `nanobot-wenyuan` 仓库内 `SOUL_PROFILE.md` 的生成、读取、迭代与治理逻辑

## 1. 文件定位

`SOUL_PROFILE.md` 是 SOUL 模块的**结构化慢变量状态层**。

它不是自然表达层，也不是情绪热状态层，而是程序需要稳定读取、校验、裁决的结构化状态文件。

当前承担三类信息：

1. `personality`
   - 荣格八维强度值
2. `relationship`
   - 关系阶段与关系维度
3. `companionship`
   - 陪伴能力维度

## 2. 文件格式

当前文件路径：

- `workspace/SOUL_PROFILE.md`

当前内容格式：

```md
```json
{
  "personality": {...},
  "relationship": {...},
  "companionship": {...}
}
```
```

也就是说，它是 Markdown 包裹的 JSON 状态文件。

## 3. 当前读写入口

核心管理器：

- `nanobot/soul/profile.py`

主要方法：

### 3.1 `read()`

职责：

- 读取 `SOUL_PROFILE.md`
- 去掉 fenced code block
- 解析 JSON
- 文件不存在或内容为空时回退到 `build_default_profile()`

说明：

- 当前对“JSON 损坏”没有单独恢复逻辑，非法 JSON 会抛异常

### 3.2 `write(profile)`

职责：

- 把结构化 dict 转成格式化 JSON
- 用 fenced block 包装
- 整文件覆盖写回

说明：

- 当前不是局部 patch，而是整文件写入

### 3.3 `update_relationship(stage, dimension_deltas)`

职责：

- 读取当前 profile
- 只更新 `relationship` 子结构
- 对维度增量做加减与 `0.0 - 1.0` clamp
- 最终重新整文件写回

说明：

- 当前只支持关系层更新
- 不负责更新 `personality`
- 不负责更新 `companionship`

## 4. 初始化生成逻辑

### 4.1 旧逻辑

旧版 `soul init` 中：

- 程序直接生成默认 `SOUL_PROFILE.md`
- LLM 最多只参与初始八维评估
- 最终整份文件仍由程序组装

### 4.2 当前逻辑

当前 `soul init` 已升级为：

- 程序先固定生成：
  - `AGENTS.md`
  - `IDENTITY.md`
  - `CORE_ANCHOR.md`
  - `SOUL_METHOD.md`
  - `USER.md`
  - `EVENTS.md`
- 初始化阶段调用 LLM
- LLM 输出：
  - `SOUL.md` 候选
  - `SOUL_PROFILE.md` 候选
- 程序通过 `init_adjudicator` 裁决
- 合法后再正式写入 `SOUL_PROFILE.md`
- 非法则回退默认 profile

### 4.3 初始化阶段谁负责什么

#### LLM 负责

- 根据用户初始化输入
- 根据 `CORE_ANCHOR.md`
- 根据 `SOUL_METHOD.md`
- 生成 `SOUL_PROFILE` 候选结构

#### 程序负责

- 定义默认结构
- 检查字段完整性
- 检查数值范围
- 检查初始化阶段关系边界
- 决定是否回退

## 5. 初始化裁决规则

当前初始化裁决至少包括：

### 5.1 personality

- 必须包含 8 个荣格八维字段
- 每个值必须在 `0.0 - 1.0`

### 5.2 relationship

- 必须包含：
  - `stage`
  - `trust`
  - `intimacy`
  - `attachment`
  - `security`
  - `boundary`
  - `affection`
- 初始化阶段 `stage` 只允许为 `熟悉`
- 所有数值必须在 `0.0 - 1.0`
- `boundary` 不允许初始化过低

### 5.3 companionship

- 必须包含：
  - `empathy_fit`
  - `memory_fit`
  - `naturalness`
  - `initiative_quality`
  - `scene_awareness`
  - `boundary_expression`
- 所有数值必须在 `0.0 - 1.0`
- `boundary_expression` 不允许初始化过低

### 5.4 非法回退

出现以下情况时，程序回退到默认 `SOUL_PROFILE`：

- 候选为空
- JSON 解析失败
- 字段缺失
- 数值越界
- 初始化阶段关系越界

## 6. 运行时读取逻辑

### 6.1 system prompt 注入

当前在：

- `nanobot/soul/engine.py`

`get_profile_context()` 会从 `SOUL_PROFILE.md` 读取摘要并注入 system prompt。

当前注入的是压缩摘要，不是全文 JSON。

现阶段注入内容主要包括：

- 当前关系阶段
- `trust / intimacy / attachment / affection`
- `empathy_fit`

说明：

- `security`
- `boundary`
- 其他 companionship 维度
- 全量 personality 八维

这些内容目前没有完整进入日常对话上下文。

## 7. 周期迭代逻辑

当前真正会改写 `SOUL_PROFILE.md` 的主流程是：

- `weekly_review`

对应模块：

- `nanobot/soul/review.py`

流程：

1. 读取当前 `SOUL_PROFILE.md`
2. 读取 `HEART.md`
3. 读取近期主动陪伴日志
4. LLM 生成关系变化候选
5. 程序用 `SoulAdjudicator` 审核关系阶段迁移是否合法
6. 合法时调用 `update_relationship()`
7. 重新写回 `SOUL_PROFILE.md`

### 当前能迭代的部分

- `relationship.stage`
- `relationship` 下各维度增量

### 当前还不能直接迭代的部分

- `personality`
- `companionship`

这些内容目前没有进入统一的慢变量更新器。

## 8. 当前生成与迭代的真实边界

可以理解成：

- **初始化生成**
  - 现在是 “LLM 候选 + 程序裁决”
- **关系迭代**
  - 现在是 “周复盘 LLM 候选 + 程序裁决 + 程序写入”
- **人格迭代**
  - 当前主要仍在 `SOUL.md / evolution.py` 侧，不是 `SOUL_PROFILE.md` 主导
- **陪伴能力迭代**
  - 当前已建模，但还没有完整周期写回闭环

## 9. 当前不足

当前 `SOUL_PROFILE.md` 还有几个明显不足：

1. 损坏 JSON 时缺少恢复逻辑
2. 日常上下文里只注入了摘要，不是完整结构
3. `personality` 与 `companionship` 的迭代闭环还不完整
4. 初始化裁决是首轮版本，后续还可以细化

## 10. 本节结论

当前 `SOUL_PROFILE.md` 已经具备：

- 结构化初始化
- 初始化裁决
- 关系层周期迭代
- 程序稳定读写

但它还没有成为“完整统一慢变量主状态机”。

现阶段它更准确的定位是：

- **结构化慢变量主存储层**
- **关系层已闭环**
- **人格层和陪伴能力层仍在逐步并轨中**
