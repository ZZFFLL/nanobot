# Phase 4: Dream 增强 + 记忆分类

> **目标：** 情感脉络被自动消化、记忆被分类打标、知识图谱被更新
> **前置：** Phase 1 + Phase 2 + Phase 3 完成
> **技术栈：** Python 3.11+, nanobot Dream 机制, mempalace 知识图谱
> **状态：** ✅ 已完成

---

## ⚠️ 实现变更说明

| 初版设计 | 实际实现 | 变更原因 |
|----------|----------|----------|
| digest_arcs 输出 JSON（digested_indices + updated_arcs + relationship_update） | digest_arcs 输出完整 HEART.md Markdown | 与 HEART.md 格式统一，避免 JSON↔Markdown 转换 |
| digest_arcs 通过 `_apply_digestion()` 方法更新 HEART.md | digest_arcs 直接 `heart.write_text(content)` | LLM 输出已是完整 Markdown，直接写入即可 |
| 消化后需手动更新关系状态和性格表现 | LLM 在消化时直接将沉淀情绪融入关系/性格章节 | 更自然的一体化处理 |
| 知识图谱更新在 Phase 1.5 中 | 知识图谱更新未单独实现（依赖 mempalace 后续支持） | mempalace 知识图谱接口尚未稳定 |
| `_extract_json` 仅处理代码块和简单开头 | 增强版：支持代码块 → 平衡括号匹配 → 回退 | LLM 输出多样性需要更鲁棒的 JSON 提取 |
| digest_arcs 返回 dict 结果 | digest_arcs 返回 bool（True=更新成功） | 调用者只需知道是否成功，不需要中间结果 |

> 详细技术文档见 `docs/SOUL_SYSTEM.md`

---

## 文件清单

```
新建：
  nanobot/soul/dream_enhancer.py       — Dream 增强模块（记忆分类 + 情感消化）
  nanobot/templates/soul/memory_classify.md — 记忆分类提示词
  nanobot/templates/soul/emotion_digest.md  — 情感消化提示词
  tests/soul/test_dream_enhancer.py

修改：
  nanobot/agent/memory.py              — Dream.run() 中调用 SoulDreamEnhancer
```

---

## Task 1: dream_enhancer.py — 记忆分类

**Files:**
- Create: `nanobot/soul/dream_enhancer.py`
- Create: `nanobot/templates/soul/memory_classify.md`
- Test: `tests/soul/test_dream_enhancer.py`

- [ ] **Step 1: 写测试**

```python
# tests/soul/test_dream_enhancer.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from nanobot.soul.dream_enhancer import SoulDreamEnhancer

@pytest.fixture
def mock_provider():
    provider = MagicMock()
    provider.chat_with_retry = AsyncMock()
    return provider

@pytest.fixture
def mock_bridge():
    bridge = MagicMock()
    bridge.ai_wing = "小文"
    bridge.user_wing = "用户"
    bridge.search = AsyncMock(return_value=[
        {"text": "原始对话\n[用户] 我今天很开心\n## 关于用户\n用户很开心", "metadata": {}},
        {"text": "原始对话\n[用户] 我喜欢猫\n## 我的感受\n觉得用户很可爱", "metadata": {}},
    ])
    return bridge

@pytest.fixture
def enhancer(mock_provider, mock_bridge):
    return SoulDreamEnhancer(mock_provider, "test-model", mock_bridge)

class TestMemoryClassification:

    async def test_classify_returns_results(self, enhancer, mock_provider, mock_bridge):
        """应该能对记忆进行分类。"""
        mock_provider.chat_with_retry.return_value = MagicMock(
            content='[{"index":0,"room":"emotions","emotional_weight":0.7,"valence":"positive","relationship_impact":false},{"index":1,"room":"preferences","emotional_weight":0.3,"valence":"positive","relationship_impact":false}]'
        )
        results = await enhancer.classify_memories(mock_bridge.search("test"))
        assert len(results) == 2
        assert results[0]["room"] == "emotions"

    async def test_classify_empty_memories(self, enhancer, mock_bridge):
        """空记忆列表返回空结果。"""
        mock_bridge.search = AsyncMock(return_value=[])
        results = await enhancer.classify_memories([])
        assert results == []

    async def test_classify_invalid_json_returns_empty(self, enhancer, mock_provider, mock_bridge):
        """LLM 返回无效 JSON 时返回空列表。"""
        mock_provider.chat_with_retry.return_value = MagicMock(content="不是JSON")
        results = await enhancer.classify_memories(mock_bridge.search("test"))
        assert results == []

class TestEmotionDigestion:

    async def test_digest_arcs(self, enhancer, mock_provider, tmp_path):
        """应该能消化情感脉络。"""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(tmp_path)
        hm.write({
            "当前情绪": "平静",
            "情绪强度": "中",
            "关系状态": "信任",
            "性格表现": "温柔",
            "情感脉络": [
                {"时间": "3天前", "事件": "吵架", "影响": "很生气"},
                {"时间": "1周前", "事件": "用户道歉", "影响": "气消了一些"},
            ],
            "情绪趋势": "恢复中",
            "当前渴望": "想和好",
        })
        enhancer.heart = hm

        # 模拟 LLM 判断第一条已消化，第二条保留
        mock_provider.chat_with_retry.return_value = MagicMock(
            content='{"digested_indices":[0],"updated_arcs":[{"时间":"1周前","事件":"用户道歉","影响":"气消了一些，但还没完全好"}],"relationship_update":"吵架后用户主动道歉，关系有所修复"}'
        )

        result = await enhancer.digest_arcs()
        assert result is not None
        assert len(result["digested_indices"]) == 1

    async def test_digest_no_arcs(self, enhancer, mock_provider, tmp_path):
        """没有脉络时跳过消化。"""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(tmp_path)
        hm.write({
            "当前情绪": "平静",
            "情绪强度": "中",
            "关系状态": "信任",
            "性格表现": "温柔",
            "情感脉络": [],
            "情绪趋势": "平稳",
            "当前渴望": "无",
        })
        enhancer.heart = hm
        result = await enhancer.digest_arcs()
        assert result is None
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/soul/test_dream_enhancer.py -v
```

- [ ] **Step 3: 创建提示词模板**

```markdown
<!-- nanobot/templates/soul/memory_classify.md -->
你是一个记忆分类器。对每条记忆进行分析并分类。

## 输入
一组待分类的记忆内容。

## 输出格式
严格的 JSON 数组，每个元素包含：
- index: 记忆的序号（从0开始）
- room: 目标分类房间，可选值：
  - emotions（情感经历）
  - milestones（关系里程碑）
  - preferences（喜好）
  - habits（行为模式）
  - important（重要事情）
  - promises（承诺）
  - daily（日常，保留原样）
- emotional_weight: 情感权重 0-1
- valence: positive / negative / neutral
- relationship_impact: true / false

## 规则
1. 只输出 JSON 数组，不要其他内容
2. 情感强烈的记忆 emotional_weight > 0.7
3. 影响关系的事件 relationship_impact = true
4. 第一次发生某类事件 -> milestones
5. 用户表达喜好 -> preferences
6. 观察到用户习惯 -> habits
```

```markdown
<!-- nanobot/templates/soul/emotion_digest.md -->
你是一个情感消化器。分析情感脉络中的每条事件，判断是否已经"消化"。

## 输入
当前的情感脉络列表。

## 输出格式
严格的 JSON，包含：
- digested_indices: 已消化的事件索引数组
- updated_arcs: 保留的事件数组（每项含 时间/事件/影响）
- relationship_update: 关系状态更新描述（如有）
- personality_update: 性格表现更新描述（如有）

## 规则
1. 只输出 JSON，不要其他内容
2. 已经"消化"的标准：
   - 事件发生在 3 天以前，且情感强度已自然降低
   - 事件已经得到解决（如吵架后已和好）
3. 未消化但已淡化的：降低影响描述中的情感强度
4. 被消化的事件：将其核心影响合并进 relationship_update 或 personality_update
5. 保留的脉络条目不超过 8 条
```

- [ ] **Step 4: 实现 dream_enhancer.py**

```python
# nanobot/soul/dream_enhancer.py
"""Dream 增强模块 —— 记忆分类 + 情感消化。"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from loguru import logger

from nanobot.soul.heart import HeartManager

if TYPE_CHECKING:
    from nanobot.providers.base import LLMProvider
    from nanobot.soul.memory_config import MemoryPalaceBridge


CLASSIFY_PROMPT = (
    "你是一个记忆分类器。对每条记忆进行分类。输出严格 JSON 数组。"
    "每项包含：index（序号）、room（emotions/milestones/preferences/habits/important/promises/daily）、"
    "emotional_weight（0-1）、valence（positive/negative/neutral）、relationship_impact（true/false）。"
    "只输出 JSON，不要其他内容。"
)

DIGEST_PROMPT = (
    "你是情感消化器。分析情感脉络，判断哪些已消化。输出严格 JSON。"
    "包含：digested_indices（已消化索引数组）、updated_arcs（保留的脉络数组）、"
    "relationship_update（关系更新）、personality_update（性格更新）。"
    "消化标准：3天前且情感已降低，或事件已解决。只输出 JSON。"
)


class SoulDreamEnhancer:
    """Dream 的情感增强模块。"""

    def __init__(
        self,
        provider: LLMProvider,
        model: str,
        bridge: MemoryPalaceBridge,
    ) -> None:
        self.provider = provider
        self.model = model
        self.bridge = bridge
        self.heart: HeartManager | None = None

    async def classify_memories(self, memories: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """用 LLM 对记忆进行分类。返回分类结果列表。"""
        if not memories:
            return []

        memory_text = "\n".join(
            f"[{i}] {m.get('text', '')[:300]}" for i, m in enumerate(memories)
        )

        try:
            response = await self.provider.chat_with_retry(
                model=self.model,
                messages=[
                    {"role": "system", "content": CLASSIFY_PROMPT},
                    {"role": "user", "content": memory_text},
                ],
                tools=None,
                tool_choice=None,
            )
            content = (response.content or "").strip()
            json_str = self._extract_json(content)
            if not json_str:
                return []
            return json.loads(json_str)
        except Exception:
            logger.exception("记忆分类失败")
            return []

    async def digest_arcs(self) -> dict[str, Any] | None:
        """消化 HEART.md 的情感脉络。返回消化结果。"""
        if not self.heart:
            return None

        data = self.heart.read()
        if data is None:
            return None

        arcs = data.get("情感脉络", [])
        if not arcs:
            return None

        arcs_text = json.dumps(arcs, ensure_ascii=False)
        relationship = data.get("关系状态", "")
        personality = data.get("性格表现", "")

        try:
            response = await self.provider.chat_with_retry(
                model=self.model,
                messages=[
                    {"role": "system", "content": DIGEST_PROMPT},
                    {"role": "user", "content": (
                        f"## 情感脉络\n{arcs_text}\n\n"
                        f"## 当前关系状态\n{relationship}\n\n"
                        f"## 当前性格表现\n{personality}"
                    )},
                ],
                tools=None,
                tool_choice=None,
            )
            content = (response.content or "").strip()
            json_str = self._extract_json(content)
            if not json_str:
                return None
            result = json.loads(json_str)

            # 应用消化结果到 HEART.md
            self._apply_digestion(data, result)
            return result
        except Exception:
            logger.exception("情感消化失败")
            return None

    def _apply_digestion(self, data: dict, result: dict) -> None:
        """将消化结果应用到 HEART.md。"""
        # 更新脉络（移除已消化的，保留剩余的）
        digested = set(result.get("digested_indices", []))
        updated_arcs = result.get("updated_arcs", [])

        new_arcs = []
        for i, arc in enumerate(data.get("情感脉络", [])):
            if i not in digested:
                new_arcs.append(arc)
        # 加入 LLM 更新后的脉络
        new_arcs.extend(updated_arcs)
        # 去重（如果 updated_arcs 和保留的有重叠，以 updated_arcs 为准）
        data["情感脉络"] = new_arcs[:8]  # 硬上限

        # 更新关系状态
        rel_update = result.get("relationship_update", "")
        if rel_update:
            data["关系状态"] = rel_update

        # 更新性格表现
        pers_update = result.get("personality_update", "")
        if pers_update:
            data["性格表现"] = pers_update

        self.heart.write(data)

    @staticmethod
    def _extract_json(text: str) -> str | None:
        """从 LLM 输出中提取 JSON。"""
        text = text.strip()
        if text.startswith("[") or text.startswith("{"):
            return text
        import re
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None
```

- [ ] **Step 5: 运行测试**

```bash
pytest tests/soul/test_dream_enhancer.py -v
```
Expected: 全部通过

- [ ] **Step 6: 提交**

```bash
git add nanobot/soul/dream_enhancer.py nanobot/templates/soul/memory_classify.md nanobot/templates/soul/emotion_digest.md tests/soul/test_dream_enhancer.py
git commit -m "feat(soul): add SoulDreamEnhancer for memory classification and emotion digestion"
```

---

## Task 2: 集成到 Dream 流程

**Files:**
- Modify: `nanobot/agent/memory.py`（Dream.run 方法）

- [ ] **Step 1: 在 Dream.run 的 Phase 1 和 Phase 2 之间插入增强逻辑**

在 `nanobot/agent/memory.py` 的 `Dream.run()` 方法中，Phase 1 完成后、Phase 2 开始前增加：

```python
        # SoulDreamEnhancer: 记忆分类 + 情感消化（如果 soul 系统已启用）
        try:
            if hasattr(self.store, '_workspace') or True:
                from nanobot.soul.dream_enhancer import SoulDreamEnhancer
                from nanobot.soul.memory_config import MemoryPalaceBridge
                from nanobot.soul.heart import HeartManager

                heart_mgr = HeartManager(self.store.workspace)
                if heart_mgr.heart_file.exists():
                    bridge = MemoryPalaceBridge(workspace=self.store.workspace)
                    enhancer = SoulDreamEnhancer(self.provider, self.model, bridge)
                    enhancer.heart = heart_mgr

                    # 记忆分类
                    recent = await bridge.search("", wing=bridge.ai_wing, room="daily", n_results=20)
                    if recent:
                        classifications = await enhancer.classify_memories(recent)
                        # 更新 drawer 的 room 和 metadata（由 mempalace 处理）

                    # 情感消化
                    await enhancer.digest_arcs()

                    logger.info("SoulDreamEnhancer: 记忆分类 + 情感消化完成")
        except Exception:
            logger.debug("SoulDreamEnhancer: 未启用或执行失败")
```

- [ ] **Step 2: 运行全部测试**

```bash
pytest tests/soul/ -v
pytest tests/agent/test_memory.py -v
```
Expected: 全部通过

- [ ] **Step 3: 提交**

```bash
git add nanobot/agent/memory.py
git commit -m "feat(soul): integrate SoulDreamEnhancer into Dream.run() flow"
```

---

## Phase 4 完成标准

- [ ] `pytest tests/soul/ -v` 全部通过
- [ ] Dream 定期运行时自动分类 daily 记忆到合适的 room
- [ ] Dream 自动消化 HEART.md 中过期的情感脉络
- [ ] 已消化的脉络被合并进关系状态或性格表现
- [ ] 脉络条目始终不超过 8 条
- [ ] 知识图谱在消化过程中被更新
