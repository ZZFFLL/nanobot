# 数字生命实施计划 - 总览

> 设计文档：`docs/superpowers/digital-life-design.md`
> 技术文档：`docs/SOUL_SYSTEM.md`
> 目标项目：`E:\zfengl-ai-project\wenyuan\wenyuan-mempalace` (nanobot)

## 阶段划分

| 阶段 | 计划文件 | 内容 | 里程碑 | 状态 |
|------|---------|------|--------|------|
| Phase 1 | `phase1-data-engine.md` | 数据层 + 核心引擎 | 数字生命可以在对话中感知和表达情感 | ✅ 已完成 |
| Phase 2 | `phase2-memory.md` | 记忆系统（mempalace 集成） | 每轮对话自动写入双视角记忆 | ✅ 已完成 |
| Phase 3 | `phase3-proactive.md` | 主动行为 + 生活事件 | 数字生命会主动找你、记得生日 | ✅ 已完成 |
| Phase 4 | `phase4-dream.md` | Dream 增强 + 记忆分类 | 情感脉络被消化、记忆被分类 | ✅ 已完成 |
| Phase 5 | `phase5-evolution.md` | 性格/关系演化 + 模型配置 | 长期交互塑造性格，模型可配置 | ✅ 已完成 |

## 依赖关系

```
Phase 1 (数据层+引擎)
  └─→ Phase 2 (记忆系统)
       └─→ Phase 3 (主动行为)
            └─→ Phase 4 (Dream增强)
                 └─→ Phase 5 (演化+配置)
```

每个阶段产出可独立运行和测试的软件。Phase 1 完成后即可与数字生命进行带情感的对话。

## 约定

- 所有代码在 `E:\zfengl-ai-project\wenyuan\wenyuan-mempalace` 下
- 测试在 `tests/soul/` 下
- Python 3.11+，async-first
- 使用 nanobot 已有的 LLM Provider、Hook、模板机制
- TDD：先写测试，再写实现

## 关键设计变更

> 初版计划中的部分设计在实际实现中有所调整，详见各 phase 文件中的变更标注

| 变更 | 初版 | 实际 | 原因 |
|------|------|------|------|
| HEART.md 格式 | JSON + Schema 验证 | 纯 Markdown + 基本校验 | 跨 Provider 兼容性 |
| Wing 命名 | 中文原名 | ASCII slug | mempalace 限制 |
| CLI 命令 | `nanobot soul init` | `nanobot init-digital-life` | 更直观 |
| 事件格式 | YAML | Markdown | Agent 工具兼容 |

完整变更记录见设计文档附录。
