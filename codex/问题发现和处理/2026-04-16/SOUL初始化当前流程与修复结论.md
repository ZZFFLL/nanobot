# SOUL 初始化当前流程与修复结论

## 1. 结论先说

截至当前分支 [HEAD](E:/zfengl-ai-project/nanobot-wenyuan) `16e469c`，这轮围绕 `soul init` 的**阻塞性问题已经收掉**。

可以明确认为已经解决的核心问题有：

1. `--only SOUL.md --force` 不再复用旧 `SOUL.md` 文本作为初始化 seed。
2. 初始化链路已经改成以 `SOUL_PROFILE.md` 为结构化真源，`SOUL.md` 走投影生成。
3. `SOUL_GOVERNANCE.json` 的 3 个新增 init 治理项已经接到初始化控制流，而不是静态摆设。
4. init 审计日志现在区分：
   - 候选 `SOUL.md`
   - 最终投影后的 `SOUL.md`
   - 最终 `profile`
   - `profile_source`
   - 生效治理参数
5. 同次命令里如果同时覆盖 `SOUL_GOVERNANCE.json`，后续 init 行为会使用这次命令**将要写入**的新治理，而不是旧治理。
6. 完整 `soul init` 路径里，非法 `profile.expression.*_seed` 不会再通过 adjudication 后写出坏 `SOUL_PROFILE.md`。
7. 对旧版“半完整但可归一化”的 `SOUL_PROFILE.md`，`SOUL.md` 重建路径现在可以兼容；但对于“字段存在但值类型/范围错误”的 profile，仍会明确失败。

## 2. 当前验证结果

本轮我重新跑了以下验证：

```powershell
python -m pytest tests/soul/test_init_files.py tests/soul/test_projection.py tests/soul/test_init_flow.py tests/soul/test_methodology.py tests/soul/test_logs.py tests/soul/test_init_adjudicator.py tests/cli/test_commands.py -q
```

结果：

- `125 passed`

另外还跑了：

```powershell
python -m pytest tests/soul -q
```

结果：

- `239 passed`

因此，至少就这轮改动覆盖到的 `soul init` 及相关 `soul` 测试面，当前状态是稳定的。

## 3. 这轮修复到底把 init 变成了什么样

### 3.1 以前的核心问题

旧链路里最致命的问题不是“某一个文件没写对”，而是职责边界混乱：

- `SOUL.md` 会被当成可直接写入的初始化真值
- `SOUL_PROFILE.md` 也是一份真值
- `SOUL_GOVERNANCE.json` 只是弱使用
- `--only` 路径和完整初始化路径行为不一致
- 审计日志和磁盘最终状态有时对不上

所以它看起来简单，但实际是不可靠的。

### 3.2 现在的核心原则

当前 init 链路已经明确成：

- `SOUL_PROFILE.md` = 结构化真源
- `SOUL.md` = 从结构化 profile 投影出来的表达层
- `SOUL_GOVERNANCE.json` = 控制 init 行为的治理输入
- 审计 = 以实际落盘后状态为准，而不是只记录推理中间结果

这意味着：

- init 比以前复杂
- 但职责和顺序更清楚
- 当前不是“有冲突”，而是“为了正确性显式化了原本隐式混乱的分支”

## 4. 当前完整 `soul init` 流程

### Step 1：解析工作区与配置

`soul init` 会先根据 `--config` / `--workspace` / 默认配置，确定：

- 工作区目录
- 配置文件路径
- 当前使用的 provider / model

### Step 2：计算 full-init 目标集

完整初始化内部固定使用一组完整目标文件，当前包含：

- `IDENTITY.md`
- `USER.md`
- `AGENTS.md`
- `CORE_ANCHOR.md`
- `SOUL_METHOD.md`
- `SOUL_GOVERNANCE.json`
- `SOUL_PROFILE.md`
- `SOUL.md`
- `HEART.md`
- `EVENTS.md`

### Step 3：解析本次运行的 effective governance

即使是完整初始化，也会先根据当前工作区和本次命令目标，解析本次真正应该生效的 init governance。

如果本次命令会写 `SOUL_GOVERNANCE.json`，那么后续流程不再吃旧治理，而是吃本次将要写入的治理。

### Step 4：采集用户输入

完整 init 会采集：

- 名字
- 性别
- 生日
- 初始性格描述
- 初始关系描述
- 用户名字
- 用户生日

### Step 5：如果 provider 可用，则跑 LLM 初始化推理

会调用：

- `infer_adjudicated_soul_init(...)`

注意这里现在已经修成：

- 推理阶段会吃到本次运行的 effective governance
- 不再只回读旧工作区治理

推理输出包括候选：

- `candidate.soul_markdown`
- `candidate.heart_markdown`
- `candidate.profile`

### Step 6：adjudication

候选会经过 `SoulInitAdjudicator` 裁决。

当前它会严格挡掉：

- `profile` 结构不合法
- 关系阶段不在允许范围
- 边界值不满足治理
- `expression.personality_seed` / `expression.relationship_seed` 类型非法

所以现在不会再出现：

- 候选先被接受
- 再在 projection 阶段因为坏 `expression` seed 爆炸
- 同时已经把坏 `SOUL_PROFILE.md` 写进工作区

### Step 7：bootstrap_workspace()

完整初始化最终走 `bootstrap_workspace()`。

当前顺序是：

1. 先在内存中构建：
   - `heart_markdown`
   - `profile`
   - `projected SOUL.md`
2. 只有这些都成立后，才开始实际写文件
3. 写入顺序里：
   - 先写 `SOUL_PROFILE.md`
   - 再写 `SOUL.md`

这一步把之前的“先写 profile，后面投影失败导致半初始化”的问题关掉了。

### Step 8：写 init trace / audit

如果本次走了 LLM 初始化，之后会写：

- `初始化追踪.jsonl`
- `初始化审计.json`

当前审计内容已经拆分为：

- `candidate.soul_markdown`
- `result.projected_soul_markdown`
- `result.profile`
- `result.profile_source`
- `governance`（包含 3 个新布尔项）

### Step 9：开启 soul 配置

如果有 config 文件，会把：

- `cfg.agents.defaults.soul.enabled = true`

写回配置。

## 5. 当前 `--only ...` 局部初始化流程

### 5.1 先 normalize 目标文件

`--only` 支持的文件会被标准化排序，顺序上当前是：

- `SOUL_PROFILE.md`
- `SOUL.md`
- `HEART.md`

等按固定顺序处理。

### 5.2 先解析 effective governance

和完整 init 一样，`--only` 分支也会先算本次命令真正生效的治理。

这意味着如果你同次命令中既改：

- `SOUL_GOVERNANCE.json`

又改：

- `SOUL.md`

那么 `SOUL.md` 的行为会按本次写入的新治理走。

### 5.3 决定是否需要 provider / LLM

当前局部初始化里，默认会把这些视为 LLM 相关目标：

- `SOUL_PROFILE.md`
- `HEART.md`

而不是把 `SOUL.md` 当作一等 LLM 直写目标。

### 5.4 收集 payload

`collect_payload_for_targets()` 会按目标和治理决定：

- 需要哪些字段
- 是否允许复用现有 `SOUL.md` 里的 seed

默认情况下：

- `allow_existing_soul_seed_for_init = false`

所以不会再读旧 `SOUL.md` 的“性格/初始关系”回来。

只有治理显式放开时才会允许。

### 5.5 `write_selected_files()` 的当前关键规则

这是目前局部初始化的核心：

#### 情况 A：写 `SOUL_PROFILE.md`

- 如果本次有 `profile_override`，写它
- 否则按 payload 构造 profile
- 但在真正写入前，会先检查 profile 是否可投影

#### 情况 B：写 `SOUL.md`

默认治理下：

- 必须依赖 `SOUL_PROFILE.md`
- 会从当前有效 profile 投影生成
- 不再允许直接把自由文本当最终 SOUL 写入

只有在治理明确允许时，才可以：

- 无 profile 直接写 `SOUL.md`

而且这已经是显式行为，不再是偶然绕过。

#### 情况 C：写 `HEART.md`

- 仍然可以按 payload 或 LLM 候选写入
- 但 audit 现在会反映这次写入后工作区里的真实状态

## 6. 现在还有没有“冲突”

当前我对这个问题的判断是：

- **没有逻辑冲突**
- **有工程复杂度**

复杂度来自这些现实需求同时成立：

- full init
- `--only` init
- 同次命令里改治理
- 兼容旧 profile 形态
- 保持严格的类型/范围校验
- 让 audit 和实际落盘结果一致

所以目前的 init 链路不是“互相打架”，而是“为了消掉旧的不一致，把控制流拆开了”。

## 7. 现在还剩什么没做

当前这轮我没有继续扩的点主要是：

### 非阻塞项 1：full-init audit 的 `targets` 元数据还可以更精确

虽然实际 payload 内容已经对得上，但顶层 `targets` 元数据还有继续精细化的空间。

### 非阻塞项 2：init 流程还可以进一步收敛复杂度

比如后续可以再做一轮纯重构，把：

- full init
- `--only` init
- audit 结果组装

统一成一套“初始化计划对象”，减少现在分散在多个函数里的判断。

但这已经属于“重构简化”，不是当前这轮阻塞性 bug 修复范围。

## 8. 你现在可以怎么理解它

如果用一句话总结当前版本：

**现在的 `soul init` 已经从“简单但容易错”变成了“复杂一点，但结构上更一致、行为上更可信”。**

再压缩一点就是：

- 以前：`SOUL.md` 和 `SOUL_PROFILE.md` 混着当真源
- 现在：`SOUL_PROFILE.md` 是真源，`SOUL.md` 是投影

## 9. 推荐你接下来怎么用

### 如果你要完整初始化

直接用：

```powershell
python -m nanobot.cli.commands soul init --config C:\Users\Administrator\.nanobot\config.json --force
```

### 如果你只想重建 `SOUL.md`

默认治理下要保证工作区里已经有：

- `SOUL_PROFILE.md`

然后执行：

```powershell
python -m nanobot.cli.commands soul init --config C:\Users\Administrator\.nanobot\config.json --only SOUL.md --force
```

这时它会按 profile 重投影，不会再复用旧 `SOUL.md` 文案。

### 如果你想同时改 profile 和 soul

可以显式指定：

```powershell
python -m nanobot.cli.commands soul init --config C:\Users\Administrator\.nanobot\config.json --only SOUL_PROFILE.md --only SOUL.md --force
```

它会走：

- 先 profile
- 后 soul

## 10. 最终结论

你的那句“我都被你搞懵了”是合理的，因为这轮不是修一个点，而是把 init 流程里长期混在一起的几件事拆开了。

但从当前代码和验证结果看，**最后阻塞性的 correctness 问题已经解决了**，当前 init 流程可以概括为：

1. 先确定本次命令真正生效的治理规则
2. 再决定是否走 LLM 初始化
3. 再以 `SOUL_PROFILE.md` 为真源
4. 最终由投影生成 `SOUL.md`
5. 审计按实际落盘结果记录

当前这套流程虽然比以前复杂，但已经比以前更严谨、更可追溯。
