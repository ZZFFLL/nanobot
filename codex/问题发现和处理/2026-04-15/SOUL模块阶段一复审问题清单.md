# SOUL 模块阶段一复审问题清单

记录日期：2026-04-15

---

## 1. 说明

本文档用于记录在本日 SOUL 一阶段整改完成后，根据：

- 《单用户数字伴侣 SOUL 闭环正式方案》
- 《SOUL 状态架构整改方案》
- 《SOUL 状态架构整改实施计划》
- 当前仓库一阶段实际代码实现

进行 Code Review 后，当时新识别出的剩余问题，以及本轮整改完成后的处理结果。

本批次问题不再是早期那类“方向完全错误”的结构问题，而是：

- 生产调度没有真正走到治理闭环
- 慢状态真源与自然语言表达层在失败路径上仍可能断层
- 热状态运行期治理强度仍偏弱
- 月校准治理器尚未真正落地

这说明 SOUL 一阶段在复审当时已经完成了大部分架构收口，但尚未达到“可交付验收”的最终稳定状态。

---

## 2. 当前基线判断

截至本批次复审时，以下核心项已经完成：

- `SOUL_METHOD` 真源收口
- `SOUL_PROFILE -> SOUL` 改为 LLM 投影
- `soul init` 已支持 LLM 同时生成 `SOUL / HEART / SOUL_PROFILE`
- init 治理规则已外置到 `SOUL_GOVERNANCE.json`
- `init / projection` 已具备 trace + 审计快照
- 周复盘与演化链已具备代码层入口

本节仅记录复审当时识别出的关键缺口如下：

- 生产环境周复盘调度未走治理闭环
- 月校准仍为占位实现
- `SOUL_PROFILE` 与 `SOUL.md` 失败路径仍可能不一致
- 运行期 `HEART.md` 裁决仍过弱

---

## 3. 复审当时的问题清单（原始记录）

> 以下问题标题、描述、影响与建议处理保留复审当时的原始表述，用于留档，不代表当前状态；当前处理结果以第 4 节为准。

### 复审时问题 1：生产环境 `weekly_review` 仍绕过治理闭环

- 涉及文件：
  - `nanobot/cli/commands.py`
  - `nanobot/soul/review.py`
- 严重级别：P1
- 当时的问题描述：
  - 生产 cron 入口仍调用 `WeeklyReviewBuilder().build(...)`
  - 该路径只生成静态周报文本
  - 没有执行 `build_cycle()` 中的：
    - 关系候选推演
    - `SOUL_PROFILE` 更新
    - `SOUL` 重投影
- 本质问题：
  - 代码里虽然已经写出“周复盘治理闭环”，但生产调度实际上没有走进去
- 影响：
  - 周复盘日志会生成
  - 但不会真正驱动关系阶段迁移与表达层同步
  - 线上行为与整改方案不一致
- 建议处理：
  - 生产 cron 入口改为调用 `build_cycle()`
  - 必须注入运行时 provider / model
  - 若 provider 不可用，应显式留痕“治理未执行”，而不是静默退回静态周报

---

### 复审时问题 2：`monthly_calibration` 仍是占位报告，不是治理器

- 涉及文件：
  - `nanobot/soul/calibration.py`
  - `nanobot/cli/commands.py`
- 严重级别：P1
- 当时的问题描述：
  - 当前月校准仅输出固定摘要、锚点文件存在性和周报摘录
  - 没有：
    - 锚点一致性检查
    - 方法论边界检查
    - 偏移风险判断
    - 建议动作输出
- 本质问题：
  - 月校准在正式方案里应是“治理器”
  - 当前实现仍只是“日志模板”
- 影响：
  - 虽然每月会生成 Markdown 文件
  - 但文件不具备真实治理价值
  - 无法支撑最终验收标准里的“可控演化体系正常运行”
- 建议处理：
  - 将月校准升级为最小可用治理器
  - 输入至少包含：
    - `CORE_ANCHOR.md`
    - `SOUL_METHOD.md`
    - `SOUL_PROFILE.md`
    - `SOUL.md`
    - `HEART.md`
    - 近 4~5 份周复盘
    - 近期演化与投影审计日志
  - 输出至少包含：
    - 锚点一致性
    - 关系演化校验
    - 情绪与人格漂移风险
    - 建议动作

---

### 复审时问题 3：周复盘失败时，`SOUL_PROFILE` 与 `SOUL.md` 仍可能断层

- 涉及文件：
  - `nanobot/soul/review.py`
- 严重级别：P1
- 当时的问题描述：
  - 当前周复盘流程先写 `SOUL_PROFILE`
  - 后尝试投影 `SOUL.md`
  - 若投影失败，仅记录 warning，不回滚结构态
- 本质问题：
  - 结构化真源与自然语言承载层的更新不是原子性的
- 影响：
  - `SOUL_PROFILE` 已变
  - `SOUL.md` 未变
  - 后续运行时上下文会继续读取旧的 `SOUL.md`
  - 出现“真源与感知层不一致”的断层
- 建议处理：
  - 将周复盘改成两阶段提交：
    1. 先在内存中形成候选 profile
    2. 仅在投影成功后同时提交 `SOUL_PROFILE` 与 `SOUL`
  - 若短期不做两阶段提交，也至少要在投影失败时回滚旧 profile

---

### 复审时问题 4：人格演化失败时，`SOUL_PROFILE` 与 `SOUL.md` 仍可能断层

- 涉及文件：
  - `nanobot/soul/evolution.py`
- 严重级别：P1
- 当时的问题描述：
  - 当前人格演化流程先写 `SOUL_PROFILE.personality`
  - 后尝试投影 `SOUL.md`
  - 若投影失败，只记 warning，不恢复旧状态
- 本质问题：
  - 与周复盘相同，属于“先落结构、后落表达”的非原子更新
- 影响：
  - 人格结构态与 `SOUL.md` 的长期画像可能长期不一致
  - 容易造成对话表现与内部结构偏移
- 建议处理：
  - 与周复盘共用一套一致性提交机制
  - 不允许 review 和 evolution 各自实现不同的失败补救逻辑

---

### 复审时问题 5：运行期 `HEART.md` 裁决强度仍弱于 init 阶段

- 涉及文件：
  - `nanobot/soul/adjudicator.py`
  - `nanobot/soul/engine.py`
  - `nanobot/soul/heart.py`
- 严重级别：P2
- 当时的问题描述：
  - init 阶段已经要求 `HEART.md` 必须具备完整章节结构
  - 但运行期 `adjudicate_heart_update()` 仍只检查：
    - 非空
    - 包含 `## `
- 本质问题：
  - init 路径和运行期路径的治理强度不一致
  - 热状态文件运行一段时间后仍可能漂移出定义结构
- 影响：
  - `HEART.md` 可能逐步出现：
    - 缺章节
    - 结构漂移
    - 无关标题
    - 只保留局部片段
  - 会削弱热状态文件在长期运行中的稳定性
- 建议处理：
  - 运行期 `HEART` 裁决应复用 init 阶段的结构校验能力
  - 最低要求：
    - 必须包含完整章节
    - 不允许一级标题
    - 不允许明显越界结构

---

## 4. 当前处理状态（2026-04-15 更新）

- 已处理：
  - production `weekly_review` 已接入治理闭环，生产 cron 走 `build_cycle()`，不再回落静态周报
  - `monthly_calibration` 已升级为最小治理器，并锁定固定 5 个治理 section
  - review / evolution 已统一为候选态投影成功后再提交，收口 `SOUL_PROFILE -> SOUL` 断层
  - 运行期 `HEART.md` 裁决已复用 `validate_heart_markdown()`，与 init 路径同级
- 回归结果：
  - 执行命令：`python -m pytest tests/soul tests/cli/test_commands.py tests/agent/test_context_prompt_cache.py tests/agent/test_heartbeat_service.py -q`
  - 执行结果：`283 passed, 3 warnings`
- 当前判断：
  - 本批次 5 个复审问题均已完成整改闭环
  - 后续工作重点可转入飞书长期运行验证，以及后续记忆模块闭环

---

## 5. 本批次优先级建议（复审当时）

### 第一优先级

1. 问题 1：生产环境 `weekly_review` 仍绕过治理闭环
2. 问题 2：`monthly_calibration` 仍是占位报告
3. 问题 3 / 4：`SOUL_PROFILE` 与 `SOUL.md` 的失败路径断层

### 第二优先级

4. 问题 5：运行期 `HEART.md` 裁决强度不足

---

## 6. 结论

本批次复审最初的结论是：

- SOUL 一阶段的大方向已经正确
- 但“真正可运行的治理闭环”还差最后一层生产接线与失败路径一致性处理

截至 2026-04-15 本轮整改执行完成后，上述问题已经完成收口：

1. 生产调度已真正接入治理闭环
2. 月校准已从占位报告升级为最小治理器
3. `SOUL_PROFILE` 与 `SOUL.md` 更新已改为一致性提交
4. 运行期 `HEART` 裁决已提升到和 init 同级

因此，SOUL 一阶段当前已经进入“可继续进行飞书长期验收”的状态，后续重点转为长期运行观察与下一阶段能力闭环。
