# SOUL 初始化 LLM 化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `soul init` 在固定方法论边界内，通过 LLM 初始化 `SOUL.md` 与 `SOUL_PROFILE.md`，并在非法输出时稳定回退。

**Architecture:** 程序继续固定生成桥接层、锚点层、方法论层和用户层文件；初始化阶段新增一条 `init_inference -> init_adjudicator -> bootstrap` 链路，LLM 只提交结构化候选，程序负责裁决后落盘。`SOUL_PROFILE` 的生成与周复盘迭代逻辑另行整理到 `codex/` 文档。

**Tech Stack:** Python 3.11+、pytest、asyncio、当前 nanobot provider 接口、Markdown + fenced JSON 状态文件。

---

## 文件结构

### 新增

- `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\soul\init_inference.py`
  - 初始化 LLM 提示词、协议解析、候选对象
- `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\soul\init_adjudicator.py`
  - 初始化候选裁决与默认回退
- `E:\zfengl-ai-project\nanobot-wenyuan\tests\soul\test_init_inference.py`
- `E:\zfengl-ai-project\nanobot-wenyuan\tests\soul\test_init_adjudicator.py`
- `E:\zfengl-ai-project\nanobot-wenyuan\codex\SOUL_PROFILE生成与迭代逻辑说明.md`

### 修改

- `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\soul\bootstrap.py`
  - 接入初始化候选覆盖写入
- `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\cli\commands.py`
  - `soul init` 接线 LLM 初始化链路
- `E:\zfengl-ai-project\nanobot-wenyuan\tests\cli\test_commands.py`
  - 新增成功候选与非法回退测试

---

### Task 1: 初始化协议与裁决层

**Files:**
- Create: `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\soul\init_inference.py`
- Create: `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\soul\init_adjudicator.py`
- Test: `E:\zfengl-ai-project\nanobot-wenyuan\tests\soul\test_init_inference.py`
- Test: `E:\zfengl-ai-project\nanobot-wenyuan\tests\soul\test_init_adjudicator.py`

- [ ] 写失败测试
- [ ] 运行确认失败
- [ ] 实现最小协议与裁决
- [ ] 运行测试确认通过

### Task 2: soul init 接入 LLM 初始化链路

**Files:**
- Modify: `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\soul\bootstrap.py`
- Modify: `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\cli\commands.py`
- Modify: `E:\zfengl-ai-project\nanobot-wenyuan\tests\cli\test_commands.py`

- [ ] 为 `soul init` 写失败测试
- [ ] 运行确认失败
- [ ] 接入候选生成、裁决和回退
- [ ] 运行 CLI 测试确认通过

### Task 3: 文档补齐与回归

**Files:**
- Create: `E:\zfengl-ai-project\nanobot-wenyuan\codex\SOUL_PROFILE生成与迭代逻辑说明.md`

- [ ] 写文档
- [ ] 运行相关回归测试
- [ ] 检查 git diff 范围

---

## 自审

- 已覆盖：初始化候选协议、程序裁决、CLI 接线、回退、SOUL_PROFILE 说明文档
- 未扩展：日常演化、周复盘/月校准逻辑本身
- 约束保持：方法论由程序固定，LLM 只提供候选，程序最终落盘
