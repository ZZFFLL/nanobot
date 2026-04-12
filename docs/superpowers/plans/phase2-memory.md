# Phase 2: 记忆系统（mempalace 集成）

> **目标：** 每轮对话自动写入双视角记忆，数字生命拥有长期记忆能力
> **前置：** Phase 1 完成（SoulEngine + SoulHook 已运行）
> **技术栈：** Python 3.11+, mempalace (ChromaDB + 知识图谱), asyncio
> **状态：** ✅ 已完成

---

## ⚠️ 实现变更说明

| 初版设计 | 实际实现 | 变更原因 |
|----------|----------|----------|
| AI wing 直接使用 IDENTITY.md 的 name（如"小文"） | AI wing 经 `_to_wing_slug()` 转写为 ASCII slug（如"wenyuan"） | mempalace sanitize_name 限制为 `[a-zA-Z0-9_ .'-]` |
| 用户 wing 默认"用户" | 用户 wing 默认 "user" | 同上，避免中文字符 |
| 记忆内容标题"原始对话" | 标题"刚才的对话" | 更自然的表述 |
| LLM 实时解读"我的感受"/"关于用户" | 使用占位描述"（这段感受将在 Dream 时被细细品味和归类）" | 降低写入时 LLM 调用成本 |
| bridge.add_drawer 调用 `_add_drawer()` | 调用 `tool_add_drawer()`（mempalace.mcp_server） | 使用 mempalace 实际导出的接口 |
| bridge.search 调用 `_search_memories()` | 调用 `search_memories()`（mempalace.searcher） | 使用 mempalace 实际导出的接口 |
| 记忆检索由关键词/情感触发 | 所有用户消息（长度 > 3 字符）触发语义检索 | 语义搜索已处理相关性，无需额外触发条件 |
| 记忆检索注入标题"相关记忆" | 标题"你想起了一些事"，标记"[你曾经历的]"/"[你记得关于对方]" | 更自然的上下文注入 |

> 详细技术文档见 `docs/SOUL_SYSTEM.md`

---

## 文件清单

```
新建：
  nanobot/soul/memory_writer.py       — 异步双视角记忆写入 + fallback 队列
  nanobot/soul/memory_config.py       — mempalace 连接配置
  tests/soul/test_memory_writer.py
  tests/soul/test_memory_config.py

修改：
  nanobot/soul/engine.py              — after_iteration 中增加记忆写入调用
  nanobot/config/schema.py            — 增加 memory_writer 配置段
```

---

## Task 1: memory_config.py — mempalace 连接层

**Files:**
- Create: `nanobot/soul/memory_config.py`
- Test: `tests/soul/test_memory_config.py`

- [ ] **Step 1: 写测试**

```python
# tests/soul/test_memory_config.py
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from nanobot.soul.memory_config import MemoryPalaceBridge

@pytest.fixture
def mock_mempalace():
    with patch("nanobot.soul.memory_config.mempalace_available", True):
        with patch("nanobot.soul.memory_config.Searcher") as mock_searcher:
            with patch("nanobot.soul.memory_config.KnowledgeGraph") as mock_kg:
                yield mock_searcher, mock_kg

class TestMemoryPalaceBridge:

    def test_init_creates_bridge(self, mock_mempalace, tmp_path):
        bridge = MemoryPalaceBridge(palace_path=str(tmp_path / "palace"))
        assert bridge is not None

    def test_ai_wing_name_from_identity(self, tmp_path):
        workspace = tmp_path
        (workspace / "IDENTITY.md").write_text("name: 小文\ngender: 女\n", encoding="utf-8")
        bridge = MemoryPalaceBridge(palace_path=str(tmp_path / "palace"), workspace=workspace)
        assert bridge.ai_wing == "小文"

    def test_user_wing_default(self, tmp_path):
        bridge = MemoryPalaceBridge(palace_path=str(tmp_path / "palace"), workspace=tmp_path)
        assert bridge.user_wing == "用户"

    def test_update_user_wing_name(self, tmp_path):
        bridge = MemoryPalaceBridge(palace_path=str(tmp_path / "palace"), workspace=tmp_path)
        bridge.update_user_wing("小明")
        assert bridge.user_wing == "小明"

    async def test_add_drawer_success(self, mock_mempalace, tmp_path):
        mock_searcher_cls, _ = mock_mempalace
        bridge = MemoryPalaceBridge(palace_path=str(tmp_path / "palace"), workspace=tmp_path)
        result = await bridge.add_drawer(
            wing="小文", room="daily",
            content="测试内容",
            metadata={"timestamp": "2026-04-10"}
        )
        assert result is True
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/soul/test_memory_config.py -v
```

- [ ] **Step 3: 实现 memory_config.py**

```python
# nanobot/soul/memory_config.py
"""mempalace 连接桥接层，提供统一的记忆读写接口。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from loguru import logger

# 检测 mempalace 是否可用
try:
    from mempalace.searcher import add_drawer as _add_drawer
    from mempalace.searcher import search_memories as _search_memories
    from mempalace.knowledge_graph import KnowledgeGraph
    from mempalace.config import MempalaceConfig
    mempalace_available = True
except ImportError:
    mempalace_available = False


class MemoryPalaceBridge:
    """连接 mempalace 的桥接层。"""

    DEFAULT_USER_WING = "用户"

    def __init__(
        self,
        palace_path: str | None = None,
        workspace: Path | None = None,
        user_wing: str | None = None,
    ) -> None:
        self.palace_path = palace_path
        self.workspace = workspace
        self._user_wing = user_wing or self.DEFAULT_USER_WING
        self._ai_wing: str | None = None

    @property
    def ai_wing(self) -> str:
        if self._ai_wing is None:
            self._ai_wing = self._read_identity_name() or "数字生命"
        return self._ai_wing

    @property
    def user_wing(self) -> str:
        return self._user_wing

    def update_user_wing(self, name: str) -> None:
        """更新用户的 wing 名称。"""
        if name and name != self._user_wing:
            old = self._user_wing
            self._user_wing = name
            logger.info("用户 wing 名称更新: {} -> {}", old, name)

    def _read_identity_name(self) -> str | None:
        if not self.workspace:
            return None
        identity_file = self.workspace / "IDENTITY.md"
        if not identity_file.exists():
            return None
        text = identity_file.read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if line.lower().startswith("name:"):
                return line.split(":", 1)[1].strip()
        return None

    async def add_drawer(
        self,
        wing: str,
        room: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """添加一条记忆到 mempalace。"""
        if not mempalace_available:
            logger.debug("mempalace 不可用，跳过记忆写入")
            return False
        try:
            _add_drawer(
                content=content,
                wing=wing,
                room=room,
                metadata=metadata or {},
                palace_path=self.palace_path,
            )
            return True
        except Exception:
            logger.exception("mempalace add_drawer 失败: wing={}, room={}", wing, room)
            return False

    async def search(
        self,
        query: str,
        wing: str | None = None,
        room: str | None = None,
        n_results: int = 5,
    ) -> list[dict[str, Any]]:
        """语义搜索记忆。"""
        if not mempalace_available:
            return []
        try:
            return _search_memories(
                query=query,
                wing=wing,
                room=room,
                n_results=n_results,
                palace_path=self.palace_path,
            )
        except Exception:
            logger.exception("mempalace search 失败")
            return []
```

- [ ] **Step 4: 运行测试**

```bash
pytest tests/soul/test_memory_config.py -v
```
Expected: 全部通过

- [ ] **Step 5: 提交**

```bash
git add nanobot/soul/memory_config.py tests/soul/test_memory_config.py
git commit -m "feat(soul): add MemoryPalaceBridge for mempalace integration"
```

---

## Task 2: memory_writer.py — 异步双视角写入 + Fallback 队列

**Files:**
- Create: `nanobot/soul/memory_writer.py`
- Test: `tests/soul/test_memory_writer.py`

- [ ] **Step 1: 写测试**

```python
# tests/soul/test_memory_writer.py
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from nanobot.soul.memory_writer import MemoryWriter, WriteTask

@pytest.fixture
def mock_bridge():
    bridge = MagicMock()
    bridge.ai_wing = "小文"
    bridge.user_wing = "用户"
    bridge.add_drawer = AsyncMock(return_value=True)
    return bridge

@pytest.fixture
def writer(mock_bridge):
    return MemoryWriter(mock_bridge)

class TestMemoryWriter:

    async def test_write_dual_creates_two_drawers(self, writer, mock_bridge):
        await writer.write_dual("你好", "你好呀~", "2026-04-10T12:00:00")
        assert mock_bridge.add_drawer.call_count == 2

    async def test_ai_perspective_uses_ai_wing(self, writer, mock_bridge):
        await writer.write_dual("你好", "你好呀~", "2026-04-10T12:00:00")
        first_call = mock_bridge.add_drawer.call_args_list[0]
        assert first_call.kwargs.get("wing") == "小文" or first_call[1].get("wing") == "小文"

    async def test_user_perspective_uses_user_wing(self, writer, mock_bridge):
        await writer.write_dual("你好", "你好呀~", "2026-04-10T12:00:00")
        second_call = mock_bridge.add_drawer.call_args_list[1]
        assert second_call.kwargs.get("wing") == "用户" or second_call[1].get("wing") == "用户"

    async def test_content_includes_raw_dialog(self, writer, mock_bridge):
        await writer.write_dual("我今天很开心", "真好呀！", "2026-04-10T12:00:00")
        first_content = mock_bridge.add_drawer.call_args_list[0]
        # content 参数中应该包含原始对话
        content = first_content.kwargs.get("content", "") or first_content[1].get("content", "")
        assert "我今天很开心" in content

    async def test_failure_enters_retry_queue(self, writer, mock_bridge):
        mock_bridge.add_drawer = AsyncMock(side_effect=Exception("写入失败"))
        await writer.write_dual("你好", "你好", "2026-04-10")
        # 应该有任务进入重试队列
        assert len(writer._retry_queue) > 0

    async def test_retry_max_then_discard(self, writer, mock_bridge):
        mock_bridge.add_drawer = AsyncMock(side_effect=Exception("持续失败"))
        task = WriteTask(
            wing="小文", room="daily",
            content="测试", metadata={},
            retries=3,  # 已经重试3次了
        )
        await writer._enqueue_retry(task)
        # 超过最大重试次数，不应该加入队列
        assert len(writer._retry_queue) == 0

    async def test_queue_max_size_drops_oldest(self, writer, mock_bridge):
        mock_bridge.add_drawer = AsyncMock(side_effect=Exception("失败"))
        # 填满队列
        for i in range(105):
            task = WriteTask(wing="小文", room="daily", content=f"内容{i}", metadata={}, retries=0)
            writer._retry_queue.append(task)
        writer.QUEUE_MAX_SIZE = 100
        await writer._enqueue_retry(WriteTask(wing="小文", room="daily", content="新的", metadata={}, retries=0))
        assert len(writer._retry_queue) <= 100
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/soul/test_memory_writer.py -v
```

- [ ] **Step 3: 实现 memory_writer.py**

```python
# nanobot/soul/memory_writer.py
"""异步双视角记忆写入器，含 fallback 重试队列。"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from loguru import logger

from nanobot.soul.memory_config import MemoryPalaceBridge


@dataclass
class WriteTask:
    """待写入（或待重试）的记忆任务。"""
    wing: str
    room: str
    content: str
    metadata: dict[str, Any]
    retries: int = 0


class MemoryWriter:
    """异步双视角记忆写入器。"""

    MAX_RETRIES: int = 3
    RETRY_DELAY: int = 5
    QUEUE_MAX_SIZE: int = 100

    def __init__(self, bridge: MemoryPalaceBridge) -> None:
        self.bridge = bridge
        self._retry_queue: list[WriteTask] = []

    async def write_dual(self, user_msg: str, ai_msg: str, timestamp: str) -> None:
        """非阻塞写入双视角记忆。失败进入重试队列。"""
        raw_dialog = f"[用户] {user_msg}\n[{self.bridge.ai_wing}] {ai_msg}"

        tasks = [
            WriteTask(
                wing=self.bridge.ai_wing,
                room="daily",
                content=(
                    f"## 原始对话\n{raw_dialog}\n\n"
                    f"## 我的感受\n"
                    f"（待 Dream 分类和解读）"
                ),
                metadata={"timestamp": timestamp, "digestion_status": "active"},
            ),
            WriteTask(
                wing=self.bridge.user_wing,
                room="daily",
                content=(
                    f"## 原始对话\n{raw_dialog}\n\n"
                    f"## 关于用户\n"
                    f"（待 Dream 分类和解读）"
                ),
                metadata={"timestamp": timestamp, "digestion_status": "active"},
            ),
        ]

        results = await asyncio.gather(
            *[self._try_write(t) for t in tasks],
            return_exceptions=True,
        )

        for result in results:
            if isinstance(result, Exception):
                task = getattr(result, "task", None)
                if task:
                    await self._enqueue_retry(task)

    async def _try_write(self, task: WriteTask) -> None:
        """单次写入，失败抛异常。"""
        try:
            success = await self.bridge.add_drawer(
                wing=task.wing,
                room=task.room,
                content=task.content,
                metadata=task.metadata,
            )
            if not success:
                raise RuntimeError(f"add_drawer 返回 False: wing={task.wing}")
        except Exception as e:
            e.task = task  # type: ignore
            raise

    async def _enqueue_retry(self, task: WriteTask) -> None:
        """失败的写入进入重试队列。"""
        task.retries += 1
        if task.retries > self.MAX_RETRIES:
            logger.error("记忆写入最终失败，静默丢弃: wing={}, retries={}", task.wing, task.retries)
            return
        if len(self._retry_queue) >= self.QUEUE_MAX_SIZE:
            self._retry_queue.pop(0)
            logger.warning("记忆重试队列已满，丢弃最旧条目")
        self._retry_queue.append(task)

    async def retry_loop(self) -> None:
        """后台持续运行，处理重试队列。"""
        while True:
            if self._retry_queue:
                task = self._retry_queue.pop(0)
                try:
                    await self._try_write(task)
                    logger.info("记忆重试写入成功: wing={}", task.wing)
                except Exception:
                    await self._enqueue_retry(task)
            await asyncio.sleep(self.RETRY_DELAY)
```

- [ ] **Step 4: 运行测试**

```bash
pytest tests/soul/test_memory_writer.py -v
```
Expected: 全部通过

- [ ] **Step 5: 提交**

```bash
git add nanobot/soul/memory_writer.py tests/soul/test_memory_writer.py
git commit -m "feat(soul): add async dual-perspective memory writer with fallback queue"
```

---

## Task 3: 记忆写入集成到 SoulHook

**Files:**
- Modify: `nanobot/soul/engine.py`

- [ ] **Step 1: 修改 SoulEngine 增加 MemoryWriter**

在 `SoulEngine.__init__` 中增加：

```python
        self._memory_writer: MemoryWriter | None = None
        try:
            from nanobot.soul.memory_config import MemoryPalaceBridge
            from nanobot.soul.memory_writer import MemoryWriter
            bridge = MemoryPalaceBridge(workspace=workspace)
            self._memory_writer = MemoryWriter(bridge)
        except Exception:
            logger.debug("SoulEngine: 记忆系统未初始化")
```

在 `SoulEngine` 中增加方法：

```python
    async def write_memory(self, user_msg: str, ai_msg: str) -> None:
        """异步写入双视角记忆。"""
        if not self._memory_writer:
            return
        timestamp = datetime.now().isoformat()
        await self._memory_writer.write_dual(user_msg, ai_msg, timestamp)
```

在 `SoulHook.after_iteration` 末尾增加记忆写入：

```python
        # 异步写入记忆（不阻塞）
        if self.engine._memory_writer:
            asyncio.create_task(
                self.engine.write_memory(user_msg, ai_msg)
            )
```

需要在 engine.py 顶部增加 `import asyncio` 和 `from datetime import datetime`。

- [ ] **Step 2: 运行全部 soul 测试**

```bash
pytest tests/soul/ -v
```
Expected: 全部通过

- [ ] **Step 3: 提交**

```bash
git add nanobot/soul/engine.py
git commit -m "feat(soul): integrate MemoryWriter into SoulHook after_iteration"
```

---

## Task 4: 记忆检索注入到 before_iteration

**Files:**
- Modify: `nanobot/soul/engine.py`

- [ ] **Step 1: 在 SoulHook.before_iteration 中增加记忆检索**

```python
    async def before_iteration(self, context: AgentHookContext) -> None:
        """对话前：注入情感上下文 + 相关记忆。"""
        heart_ctx = self.engine.get_heart_context()
        if not heart_ctx or not context.messages:
            return

        # 注入 HEART.md
        system_msg = context.messages[0]
        if system_msg.get("role") == "system":
            existing = system_msg.get("content", "")
            system_msg["content"] = f"{existing}\n\n{heart_ctx}"

        # 记忆检索（如果 bridge 可用）
        if self.engine._memory_writer:
            user_text = ""
            for msg in reversed(context.messages):
                if msg.get("role") == "user":
                    content = msg.get("content", "")
                    user_text = content if isinstance(content, str) else ""
                    break

            if user_text and len(user_text) > 3:
                bridge = self.engine._memory_writer.bridge
                ai_results = await bridge.search(user_text, wing=bridge.ai_wing, n_results=3)
                user_results = await bridge.search(user_text, wing=bridge.user_wing, n_results=3)

                if ai_results or user_results:
                    memory_parts = ["## 相关记忆"]
                    for r in ai_results[:2]:
                        snippet = r.get("text", "")[:200]
                        memory_parts.append(f"[我的记忆] {snippet}")
                    for r in user_results[:2]:
                        snippet = r.get("text", "")[:200]
                        memory_parts.append(f"[关于用户] {snippet}")
                    memory_text = "\n".join(memory_parts)

                    system_msg = context.messages[0]
                    system_msg["content"] = system_msg.get("content", "") + "\n\n" + memory_text
```

- [ ] **Step 2: 运行全部测试**

```bash
pytest tests/soul/ -v
```
Expected: 全部通过

- [ ] **Step 3: 提交**

```bash
git add nanobot/soul/engine.py
git commit -m "feat(soul): add memory retrieval to before_iteration context injection"
```

---

## Phase 2 完成标准

- [ ] `pytest tests/soul/ -v` 全部通过
- [ ] 每轮对话自动写入两条记忆（AI 视角 + 用户视角）
- [ ] 记忆内容包含原始对话 + 视角描述
- [ ] 写入失败进入重试队列，最多 3 次后静默丢弃
- [ ] 对话前自动检索相关记忆注入上下文
- [ ] mempalace 不可用时不影响正常对话
