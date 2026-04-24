# SOUL 初始化链路健壮性实施计划

> **目标:** 一次性修复 `soul init` 初始化链路中的 3 个问题：旧 `SOUL.md` seed 反向污染、`SOUL_PROFILE -> SOUL` 顺序缺失、`SOUL_GOVERNANCE.json` 治理覆盖不足。

## 1. 实施范围

本计划只覆盖初始化链路：

- 完整 `soul init`
- 局部 `soul init --only ...`
- 初始化 trace / audit
- 初始化治理配置读取
- 初始化相关测试

不覆盖：

- 对话轮次 Soul Hook
- Dream
- Evolution 运行时流程
- Proactive

## 2. 涉及文件

### 需要修改

- [nanobot/cli/commands.py](E:/zfengl-ai-project/nanobot-wenyuan/nanobot/cli/commands.py)
- [nanobot/soul/init_files.py](E:/zfengl-ai-project/nanobot-wenyuan/nanobot/soul/init_files.py)
- [nanobot/soul/bootstrap.py](E:/zfengl-ai-project/nanobot-wenyuan/nanobot/soul/bootstrap.py)
- [nanobot/soul/init_adjudicator.py](E:/zfengl-ai-project/nanobot-wenyuan/nanobot/soul/init_adjudicator.py)
- [nanobot/soul/methodology.py](E:/zfengl-ai-project/nanobot-wenyuan/nanobot/soul/methodology.py)
- [nanobot/soul/projection.py](E:/zfengl-ai-project/nanobot-wenyuan/nanobot/soul/projection.py)

### 需要新增或修改测试

- [tests/soul/test_init_files.py](E:/zfengl-ai-project/nanobot-wenyuan/tests/soul/test_init_files.py)
- [tests/soul/test_init_adjudicator.py](E:/zfengl-ai-project/nanobot-wenyuan/tests/soul/test_init_adjudicator.py)
- [tests/soul/test_init_inference.py](E:/zfengl-ai-project/nanobot-wenyuan/tests/soul/test_init_inference.py)
- [tests/soul/test_projection.py](E:/zfengl-ai-project/nanobot-wenyuan/tests/soul/test_projection.py)
- 建议新增：
  - `tests/soul/test_init_flow.py`

## 3. 任务拆分

### Task 1：禁止 `SOUL.md` 继续作为初始化 seed 真源

**目标**

- 去掉 `--only SOUL.md` 对旧 `SOUL.md` 的反向依赖

**动作**

- 修改 `read_existing_seed()` / `collect_payload_for_targets()` 的目标感知逻辑
- 当目标包含 `SOUL.md` 时：
  - 不再从旧 `SOUL.md` 回填 `personality` / `relationship`

**验收**

- 执行 `--only SOUL.md --force` 时，不再把旧版 `SOUL.md` 内容带回 payload

### Task 2：重构完整初始化顺序为 “profile -> projection -> soul”

**目标**

- 完整初始化不再把 `SOUL.md` 作为并列一等产物直接落盘

**动作**

- 保留 LLM 生成候选 `profile` / `heart`
- `SOUL.md` 的最终落盘改为：
  - 先写 `SOUL_PROFILE.md`
  - 再调用 `project_soul_from_profile(trigger=\"init\")`

**验收**

- 完整初始化后的 `SOUL.md` 必须来自投影链路

### Task 3：重构局部初始化顺序为 “先 profile，再 soul”

**目标**

- 即使同时初始化 `SOUL.md` + `SOUL_PROFILE.md`，也必须走正向顺序

**动作**

- 调整 `write_selected_files()` 或其调用层
- 对目标组合：
  - `SOUL_PROFILE.md`
  - `SOUL.md`

  统一改成内部强制顺序：
  1. 先处理 `SOUL_PROFILE.md`
  2. 再投影生成 `SOUL.md`

**验收**

- 同时初始化时，不再出现 `SOUL.md` 先写、`SOUL_PROFILE.md` 后写的错误顺序

### Task 4：定义 `--only SOUL.md --force` 的严格语义

**目标**

- 让局部重建 `SOUL.md` 行为可预测

**动作**

- 若存在 `SOUL_PROFILE.md`
  - 直接从现有 profile 投影重建 `SOUL.md`
- 若不存在 `SOUL_PROFILE.md`
  - 报错
  - 提示先初始化 `SOUL_PROFILE.md`，或同时指定两个目标

**验收**

- 不再允许无 profile 的 `SOUL.md` 伪方法论初始化

### Task 5：扩展 `SOUL_GOVERNANCE.json` 的初始化治理作用

**目标**

- 让治理配置不再只是静态 stub

**动作**

- 在 `init` 下新增并接入下列治理项：
  - `require_profile_projection_for_soul`
  - `allow_soul_only_without_profile`
  - `allow_existing_soul_seed_for_init`

- 在 `load_init_governance()` 中解析它们
- 在 `commands.py` / `init_files.py` 中消费它们

**验收**

- 初始化关键行为不再写死在代码里，而是由治理配置控制

### Task 6：升级 trace / audit 语义

**目标**

- 让初始化日志可区分候选与最终落盘内容

**动作**

- 审计中新增：
  - `candidate.soul_markdown`
  - `result.projected_soul_markdown`
  - `result.profile`
  - `result.profile_source`

**验收**

- 可以清楚回答“LLM 候选是什么、最终投影是什么、磁盘上写的是什么”

### Task 7：补齐自动化测试

**至少需要新增以下测试**

1. `--only SOUL.md --force` 不再从旧 `SOUL.md` 读取 seed
2. 完整初始化时 `SOUL.md` 由投影生成
3. 同时初始化 `SOUL.md` + `SOUL_PROFILE.md` 时内部顺序正确
4. 没有 `SOUL_PROFILE.md` 时，单独重建 `SOUL.md` 会报错
5. 初始化 audit 同时记录候选 `SOUL.md` 与投影 `SOUL.md`
6. 新治理字段会影响初始化行为

**验收**

- 新行为均有自动化覆盖

## 4. 推荐实施顺序

建议按以下顺序推进：

1. 先修 Task 1
   - 去掉旧 `SOUL.md` seed

2. 再修 Task 5
   - 把治理开关补出来

3. 再修 Task 2 + Task 3 + Task 4
   - 重建初始化正向顺序

4. 最后做 Task 6 + Task 7
   - 补日志与测试

这样可以避免一开始就把控制流和审计同时改乱。

## 5. 风险控制

### 风险 1：初始化结果风格变化明显

原因：

- `SOUL.md` 将从“候选直写”变成“投影写入”

处理：

- 接受为正确修复结果
- 在变更说明中明确告知

### 风险 2：CLI 行为更严格

原因：

- 某些以前能跑的命令将改为报错

处理：

- 输出清晰提示
- 提供正确使用方式

### 风险 3：日志格式变化影响排查习惯

原因：

- trace / audit 将新增字段

处理：

- 向后兼容现有字段
- 只新增，不删除核心字段

## 6. 交付验收清单

- [ ] `SOUL.md` 不再直接作为初始化真值
- [ ] `SOUL_PROFILE.md` 成为初始化真源
- [ ] `--only SOUL.md --force` 不再复用旧 `SOUL.md`
- [ ] 同时初始化 `SOUL.md` + `SOUL_PROFILE.md` 时顺序正确
- [ ] 无 `SOUL_PROFILE.md` 时只重建 `SOUL.md` 会报错
- [ ] `SOUL_GOVERNANCE.json` 新增治理项已生效
- [ ] trace / audit 可区分候选与最终投影
- [ ] 测试通过

## 7. 最终结论

本次不应被视为一个“小修复”，而应定义为：

**“SOUL 初始化链路健壮性修复”**

因为真正需要修的是整条初始化闭环：

- 输入来源
- 结构化真源
- 投影顺序
- 治理控制
- 审计可追踪性

只有 3 个问题联修，初始化流程才会真正变得健壮严谨。
