# Digital Life - 项目进度

> 最后更新：2026-04-12

## 项目状态：Phase 5 已完成，进入实际测试阶段

---

## 当前阶段：实际测试

开发阶段全部完成（129 个单元测试通过），pip 已安装 wenyuan-mempalace 版本的 nanobot-ai。

### 测试步骤
1. `nanobot init-digital-life` — 交互式创建数字生命（IDENTITY.md / SOUL.md / HEART.md / EVENTS.md）
2. `nanobot agent -w <workspace>` — 对话测试（情感感知 + 记忆写入/检索）
3. `nanobot gateway -w <workspace>` — 完整功能测试（主动行为 + Dream 消化 + 生活事件）

### 验证清单
- [ ] 情感感知：聊天后 HEART.md 是否更新（纯 Markdown 格式）
- [ ] 记忆写入：mempalace 中是否有双视角记忆
- [ ] 记忆检索：再次提及相关话题，AI 是否引用之前对话
- [ ] 主动行为：Gateway 模式下是否主动发消息
- [ ] Dream 消化：Dream 周期后 HEART.md 脉络是否被消化
- [ ] 性格演化：长期交互后 SOUL.md 是否有"成长的痕迹"记录
- [ ] 生活事件：生日/纪念日是否触发

---

## 已完成

### 1. 需求讨论
- [x] 确定单用户模式
- [x] 确定通过 nanobot 已有聊天渠道交互
- [x] 确定身份固定、性格可演化
- [x] 确定情感模型：结构化状态文档 + 情感脉络 + Dream 消化
- [x] 确定有主动行为，由情绪和关系驱动
- [x] 确定代码在 nanobot 内扩展，模块化低侵入
- [x] 确定 Hook 驱动架构（方案一）
- [x] 确定记忆每轮全量写入，分类交给 Dream
- [x] 确定记忆是双视角（AI 经历 + 用户观察）
- [x] 确定记忆包含原始对话 + 视角解读
- [x] 确定情感状态需要因果锚点（情感脉络）
- [x] 确定身份与关系分离
- [x] 确定关系演变受性格影响（敏感性格更快变化）
- [x] ~~确定 HEART.md 格式通过 JSON Schema 强制约束~~ → **已变更为纯 Markdown + 基本校验**
- [x] 确定 Wing 命名动态化（AI 取自 name 经 slug 转写，用户默认 "user"）
- [x] 确定模型可独立配置（四个任务各自的模型/温度/参数）
- [x] 确定记忆写入失败走 fallback 重试队列（3次后丢弃）
- [x] 确定生日/纪念日等通过 CronService 定时触发
- [x] 确定主动行为由六维因素综合驱动
- [x] 确定 embedding 先用 mempalace 默认，后续再优化

### 2. 设计方案
- [x] 完整设计文档：`docs/superpowers/digital-life-design.md`
- [x] 9 个模块设计（IDENTITY/HEART/引擎/记忆/主动/事件/Dream/演化/配置）
- [x] 设计变更记录（初版 vs 实际实现差异）

### 3. 实施计划
- [x] 计划总览：`docs/superpowers/plans/README.md`
- [x] Phase 1 - 数据层 + 核心引擎：`docs/superpowers/plans/phase1-data-engine.md`
- [x] Phase 2 - 记忆系统：`docs/superpowers/plans/phase2-memory.md`
- [x] Phase 3 - 主动行为 + 生活事件：`docs/superpowers/plans/phase3-proactive.md`
- [x] Phase 4 - Dream 增强 + 记忆分类：`docs/superpowers/plans/phase4-dream.md`
- [x] Phase 5 - 演化 + 模型配置：`docs/superpowers/plans/phase5-evolution.md`

### 4. 技术文档
- [x] Soul 系统深度文档：`docs/SOUL_SYSTEM.md`

---

## 待执行

### Phase 1: 数据层 + 核心引擎 ✅ 已完成
- [x] Task 1: schemas.py — HEART.md JSON Schema + 校验（运行时不验证，仅作文档用途）
- [x] Task 2: heart.py — HEART.md 纯 Markdown 读写（非 JSON 互转）
- [x] Task 3: prompts.py — 提示词模板（含 SYSTEM_PROMPT_HEART_UPDATE Markdown 版）
- [x] Task 4: engine.py — SoulEngine + SoulHook
- [x] Task 5: 注册 SoulHook 到 AgentLoop
- [x] Task 6: 集成测试
- **里程碑：数字生命可以在对话中感知和表达情感**

### Phase 2: 记忆系统 ✅ 已完成
- [x] Task 1: memory_config.py — mempalace 连接层（wing slug 转写 + 优雅降级）
- [x] Task 2: memory_writer.py — 异步双视角写入 + fallback 队列
- [x] Task 3: 记忆写入集成到 SoulHook
- [x] Task 4: 记忆检索注入到 before_iteration（语义搜索，所有用户消息触发）
- **里程碑：每轮对话自动写入双视角记忆**

### Phase 3: 主动行为 + 生活事件 ✅ 已完成
- [x] Task 1: events.py — 生活事件管理（EVENTS.md Markdown 格式）
- [x] Task 2: proactive.py — 主动行为决策引擎（6因子概率计算 + _extract_section 解析）
- [x] Task 3: 集成到 HeartbeatService + CronService
- **里程碑：数字生命会主动找你、记得生日**

### Phase 4: Dream 增强 + 记忆分类 ✅ 已完成
- [x] Task 1: dream_enhancer.py — 记忆分类（JSON 输出）+ 情感消化（Markdown 输出）
- [x] Task 2: 集成到 Dream 流程（Phase 1.5）
- **里程碑：情感脉络被消化、记忆被分类**

### Phase 5: 演化 + 模型配置 ✅ 已完成
- [x] Task 1: schema.py — 完整 SoulConfig 模型配置
- [x] Task 2: evolution.py — 性格与关系演化引擎（动态阈值 + "成长的痕迹"追加）
- [x] Task 3: 演化集成到 Dream + 模型配置使用
- [x] Task 4: `nanobot init-digital-life` 命令
- **里程碑：长期交互塑造性格，模型可配置**

---

## 设计变更汇总

| 变更项 | 初版设计 | 实际实现 | 变更原因 |
|--------|----------|----------|----------|
| HEART.md 格式 | JSON + Schema 验证 | 纯 Markdown + 基本校验 | 跨 Provider 兼容性 |
| Wing 命名 | 中文原名 | ASCII slug 转写 | mempalace 名称限制 |
| 事件格式 | YAML | Markdown | 与 Agent 工具兼容 |
| CLI 命令 | `nanobot soul init` | `nanobot init-digital-life` | 更直观 |
| 情感消化输出 | JSON | 完整 HEART.md Markdown | 格式统一 |
| 演化记录标题 | "演化记录" | "成长的痕迹" | 叙事风格 |
| 记忆写入解读 | LLM 实时解读 | 占位描述（Dream 时解读） | 降低成本 |

---

## 已知限制

| 限制 | 影响 | 后续计划 |
|------|------|---------|
| mempalace 使用默认 embedding（all-MiniLM-L6-v2） | 中文语义搜索效果待优化 | 后续改造 mempalace 的 embedding 层，支持外部配置 |
| schemas.py 中 JSON Schema 运行时不验证 | HEART.md 格式校验较松 | 可选：在 digest_arcs 等场景增加结构化校验 |

---

## 文件索引

```
docs/
├── SOUL_SYSTEM.md                              Soul 系统深度技术文档
└── superpowers/
    ├── digital-life-design.md                  设计方案（已更新至实际实现）
    ├── PROGRESS.md                             本文件 - 项目进度
    └── plans/
        ├── README.md                           计划总览
        ├── phase1-data-engine.md               Phase 1 实施计划
        ├── phase2-memory.md                    Phase 2 实施计划
        ├── phase3-proactive.md                 Phase 3 实施计划
        ├── phase4-dream.md                     Phase 4 实施计划
        └── phase5-evolution.md                 Phase 5 实施计划
```
