# SOUL 初始化 LLM 化桥接方案

> 日期：2026-04-15
> 状态：待评审
> 范围：仅针对 `soul init` 初始化流程，不扩展到日常演化链路

## 1. 目标

把 `soul init` 从“静态模板初始化”升级为“方法论约束下的 LLM 候选初始化”。

升级后的目标：

1. `SOUL.md` 不再只有非常基础的一句性格描述，而是具备更完整的人格表达层。
2. `SOUL_PROFILE.md` 不再只靠默认值，而是由 LLM 基于方法论生成更合理的初始结构化画像。
3. 初始化阶段继续坚持既定边界：方法论由人定义，LLM 只在方法论内推演，程序负责裁决与落盘。

## 2. 范围边界

本次只改：

- `soul init`
- 初始化提示词与裁决逻辑
- 初始化落盘内容

本次不改：

- 日常对话中的 `SOUL` 演化逻辑
- 周复盘 / 月校准
- Dream / mempalace 流程
- 飞书渠道逻辑

## 3. 方案选择

采用方案：

- **方案 B：LLM 初始化 `SOUL.md + SOUL_PROFILE.md`，程序裁决后落盘**

不采用：

- 只让 LLM 丰富 `SOUL.md` 的简化方案
- 让 LLM 一次性接管 `USER.md / HEART.md / EVENTS.md` 的扩张方案

## 4. 职责边界

### 4.1 程序负责

程序固定生成并控制：

- `AGENTS.md`
- `IDENTITY.md`
- `CORE_ANCHOR.md`
- `SOUL_METHOD.md`
- `USER.md`
- `EVENTS.md`
- `soul_logs/*` 目录

程序还负责：

- 构造 LLM 初始化输入
- 解析 LLM 输出
- 对 `SOUL_PROFILE.md` 做结构和数值裁决
- 对 `SOUL.md` 做最小格式校验
- 失败回退到默认初始化

### 4.2 LLM 负责

LLM 只负责根据：

- 用户在 `soul init` 输入的初始信息
- `CORE_ANCHOR.md`
- `SOUL_METHOD.md`

生成两个候选：

1. `SOUL.md` 候选文本
2. `SOUL_PROFILE.md` 候选结构

LLM 不负责：

- 自创方法论
- 修改核心锚点
- 直接决定超范围关系阶段
- 绕过程序裁决直接落盘

## 5. 初始化数据流

```text
用户输入初始化表单
  -> 程序先生成 CORE_ANCHOR / SOUL_METHOD / USER / IDENTITY / EVENTS
  -> 调用初始化 LLM
  -> 输出候选: SOUL markdown + SOUL_PROFILE json
  -> 程序裁决
     -> 合法: 写入正式文件
     -> 非法/解析失败: 回退默认初始化
```

## 6. LLM 输出协议

初始化 LLM 输出严格 JSON，建议格式：

```json
{
  "soul_markdown": "# 性格\n\n...\n\n# 初始关系\n\n...",
  "profile": {
    "personality": {
      "Fi": 0.80,
      "Fe": 0.35,
      "Ti": 0.20,
      "Te": 0.05,
      "Si": 0.50,
      "Se": 0.10,
      "Ni": 0.05,
      "Ne": 0.65
    },
    "relationship": {
      "stage": "熟悉",
      "trust": 0.15,
      "intimacy": 0.05,
      "attachment": 0.00,
      "security": 0.10,
      "boundary": 0.90,
      "affection": 0.00
    },
    "companionship": {
      "empathy_fit": 0.20,
      "memory_fit": 0.00,
      "naturalness": 0.15,
      "initiative_quality": 0.00,
      "scene_awareness": 0.10,
      "boundary_expression": 0.85
    }
  }
}
```

## 7. 裁决规则

程序裁决至少包含：

### 7.1 `SOUL.md`

- 必须包含 `# 性格`
- 必须包含 `# 初始关系`
- 不允许出现与 `CORE_ANCHOR.md` 冲突的表述

### 7.2 `SOUL_PROFILE.md`

- 必须包含 `personality / relationship / companionship`
- 八维值必须在 `0.0 - 1.0`
- 关系维度必须在 `0.0 - 1.0`
- `boundary`、`boundary_expression` 默认偏高，不允许初始化成极低值
- `relationship.stage` 初始化只允许为 `熟悉`
- 陪伴能力各项允许低值起步，但不能缺字段

### 7.3 回退策略

任一情况触发回退：

- LLM 调用失败
- JSON 解析失败
- 字段缺失
- 数值越界
- 违反初始化边界

回退时：

- `SOUL.md` 使用程序默认版本
- `SOUL_PROFILE.md` 使用默认结构 + 默认或规则化八维

## 8. 文件职责调整

### 8.1 初始化后由程序固定写入

- `AGENTS.md`
- `IDENTITY.md`
- `CORE_ANCHOR.md`
- `SOUL_METHOD.md`
- `USER.md`
- `EVENTS.md`

### 8.2 初始化后由 LLM 候选 + 程序裁决写入

- `SOUL.md`
- `SOUL_PROFILE.md`

### 8.3 初始化后由程序派生写入

- `HEART.md`
  - 仍由程序创建
  - 初始关系文案可引用用户输入关系描述

## 9. 实现落点

建议修改：

- `nanobot/cli/commands.py`
  - `soul init` 接线
- `nanobot/soul/bootstrap.py`
  - 增加初始化 LLM 调用与回退逻辑
- `nanobot/soul/heart.py`
  - 继续保留程序生成 `HEART.md`

建议新增：

- `nanobot/soul/init_inference.py`
  - 初始化 LLM 提示词与解析协议
- `nanobot/soul/init_adjudicator.py`
  - 初始化裁决逻辑
- `tests/soul/test_init_inference.py`
- `tests/soul/test_init_adjudicator.py`

## 10. 测试要点

至少覆盖：

1. `soul init` 成功时生成完整文件
2. `SOUL.md` 来自 LLM 候选且满足格式约束
3. `SOUL_PROFILE.md` 来自 LLM 候选且被裁决
4. LLM 返回非法结构时能回退
5. 初始化阶段 `relationship.stage` 不会越界
6. `soul.enabled` 能正常写回配置

## 11. 风险与控制

主要风险：

- 初始化过度依赖 LLM，导致首轮人格漂移
- 初始化 JSON 不稳定，造成失败率高
- 初始化文本过长，污染 prompt

控制方式：

- 方法论与锚点先由程序固定写入
- 初始化只放开 `SOUL.md + SOUL_PROFILE.md`
- 强制裁决与默认回退
- 测试覆盖非法输出场景

## 12. 本节结论

`soul init` 应升级为“程序搭骨架、LLM 生成人格候选、程序裁决落盘”的初始化模式。这样既能提升初始化人格质量，又不破坏既定方法论边界和程序治理主权。
