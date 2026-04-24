# Feishu Reply Post-Send Soul Finalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让普通渠道回复在生成后立即出站，再执行 Soul 的 `HEART.md` 更新和记忆收尾，从而缩短飞书用户的感知等待时间，同时保持现有普通回复样式和工具调用语义不变。

**Architecture:** 在 `AgentLoop` 增加“响应 + 发送后收尾”结果封装，把当前 `_process_message()` 的主体迁到新的 helper 中。`_dispatch()` 改为先发送 `OutboundMessage`，再执行 `post_send_finalizer`；`SoulHook` 仅在主流程中负责 `before_iteration`，最终回合的重后处理改由 `SoulEngine.finalize_post_send_turn()` 在消息发送后显式执行。

**Tech Stack:** Python 3.11, asyncio, pytest, loguru, nanobot `AgentLoop` / `SoulHook` / `MessageTool`

---

## File Map

- Modify: `E:/zfengl-ai-project/nanobot-wenyuan/nanobot/agent/loop.py`
  责任：新增 `_ProcessMessageOutcome`、`_process_message_with_post_send()`、`_build_post_send_finalizer()`，并调整 `_dispatch()` 与 `_process_message()` 的调用顺序。
- Modify: `E:/zfengl-ai-project/nanobot-wenyuan/nanobot/soul/engine.py`
  责任：抽出 `SoulEngine.finalize_post_send_turn()`，并让 `SoulHook` 支持延后最终回合处理。
- Modify: `E:/zfengl-ai-project/nanobot-wenyuan/tests/agent/test_task_cancel.py`
  责任：更新 `_dispatch()` 相关单测，使其适配新的 `_process_message_with_post_send()` 路径。
- Create: `E:/zfengl-ai-project/nanobot-wenyuan/tests/agent/test_loop_post_send.py`
  责任：验证“先 publish，再执行 finalizer”的时序，以及直接调用 `_process_message()` 的兼容行为。
- Modify: `E:/zfengl-ai-project/nanobot-wenyuan/tests/soul/test_engine.py`
  责任：验证 `SoulEngine.finalize_post_send_turn()` 和 `SoulHook(..., defer_final_response=True)` 的行为。
- Modify: `E:/zfengl-ai-project/nanobot-wenyuan/tests/tools/test_message_tool_suppress.py`
  责任：验证同会话 `message` 工具抑制最终回复时，仍然保留并执行 `post_send_finalizer`。

## Task 1: Add AgentLoop Post-Send Outcome Plumbing

**Files:**
- Modify: `E:/zfengl-ai-project/nanobot-wenyuan/nanobot/agent/loop.py`
- Modify: `E:/zfengl-ai-project/nanobot-wenyuan/tests/agent/test_task_cancel.py`
- Create: `E:/zfengl-ai-project/nanobot-wenyuan/tests/agent/test_loop_post_send.py`

- [ ] **Step 1: Write the failing tests for dispatch ordering**

在 `tests/agent/test_task_cancel.py` 中把 `_dispatch()` 的 stub 从 `_process_message` 切到 `_process_message_with_post_send`，并新增 `tests/agent/test_loop_post_send.py` 验证出站顺序：

```python
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nanobot.agent.loop import AgentLoop, _ProcessMessageOutcome
from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.queue import MessageBus


def _make_loop(tmp_path):
    bus = MessageBus()
    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"
    with patch("nanobot.agent.loop.ContextBuilder"), \
         patch("nanobot.agent.loop.SessionManager"), \
         patch("nanobot.agent.loop.SubagentManager") as MockSubMgr:
        MockSubMgr.return_value.cancel_by_session = AsyncMock(return_value=0)
        loop = AgentLoop(bus=bus, provider=provider, workspace=tmp_path, model="test-model")
    return loop


@pytest.mark.asyncio
async def test_dispatch_publishes_before_post_send_finalizer(tmp_path):
    loop = _make_loop(tmp_path)
    order: list[str] = []

    async def fake_finalizer() -> None:
        order.append("finalizer")

    loop._process_message_with_post_send = AsyncMock(
        return_value=_ProcessMessageOutcome(
            response=OutboundMessage(channel="test", chat_id="c1", content="hi"),
            post_send_finalizer=fake_finalizer,
        )
    )
    loop.bus.publish_outbound = AsyncMock(side_effect=lambda msg: order.append(f"publish:{msg.content}"))

    msg = InboundMessage(channel="test", sender_id="u1", chat_id="c1", content="hello")
    await loop._dispatch(msg)

    assert order == ["publish:hi", "finalizer"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/agent/test_task_cancel.py::TestDispatch::test_dispatch_processes_and_publishes tests/agent/test_loop_post_send.py::test_dispatch_publishes_before_post_send_finalizer -v
```

Expected:

```text
FAIL ... AttributeError: 'AgentLoop' object has no attribute '_process_message_with_post_send'
```

- [ ] **Step 3: Implement the minimal post-send outcome structure in AgentLoop**

在 `nanobot/agent/loop.py` 中新增结果封装，并把当前 `_process_message()` 的主体迁到 `_process_message_with_post_send()`。保持 `_process_message()` 对直接调用方的返回类型不变：

```python
from dataclasses import dataclass


@dataclass(slots=True)
class _ProcessMessageOutcome:
    response: OutboundMessage | None
    post_send_finalizer: Callable[[], Awaitable[None]] | None = None


async def _dispatch(self, msg: InboundMessage) -> None:
    ...
    outcome = await self._process_message_with_post_send(
        msg, on_stream=on_stream, on_stream_end=on_stream_end,
    )
    if outcome.response is not None:
        await self.bus.publish_outbound(outcome.response)
    elif msg.channel == "cli":
        await self.bus.publish_outbound(OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content="",
            metadata=msg.metadata or {},
        ))
    if outcome.post_send_finalizer is not None:
        await outcome.post_send_finalizer()


async def _process_message(
    self,
    msg: InboundMessage,
    session_key: str | None = None,
    on_progress: Callable[[str], Awaitable[None]] | None = None,
    on_stream: Callable[[str], Awaitable[None]] | None = None,
    on_stream_end: Callable[..., Awaitable[None]] | None = None,
) -> OutboundMessage | None:
    outcome = await self._process_message_with_post_send(
        msg,
        session_key=session_key,
        on_progress=on_progress,
        on_stream=on_stream,
        on_stream_end=on_stream_end,
    )
    if outcome.post_send_finalizer is not None:
        await outcome.post_send_finalizer()
    return outcome.response
```

把当前 `_process_message()` 原有主体整体迁移到 `_process_message_with_post_send()`，先全部返回：

```python
return _ProcessMessageOutcome(response=OutboundMessage(...))
```

先不要在这个任务里接入 Soul finalizer，`post_send_finalizer` 暂时统一返回 `None`。

- [ ] **Step 4: Run tests to verify the new orchestration passes**

Run:

```bash
pytest tests/agent/test_task_cancel.py::TestDispatch::test_dispatch_processes_and_publishes tests/agent/test_task_cancel.py::TestDispatch::test_dispatch_streaming_preserves_message_metadata tests/agent/test_loop_post_send.py::test_dispatch_publishes_before_post_send_finalizer -v
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Commit**

```bash
git add nanobot/agent/loop.py tests/agent/test_task_cancel.py tests/agent/test_loop_post_send.py
git commit -m "refactor: add post-send outcome handling in agent loop"
```

## Task 2: Extract Soul Final-Response Processing for Post-Send Execution

**Files:**
- Modify: `E:/zfengl-ai-project/nanobot-wenyuan/nanobot/soul/engine.py`
- Modify: `E:/zfengl-ai-project/nanobot-wenyuan/nanobot/agent/loop.py`
- Modify: `E:/zfengl-ai-project/nanobot-wenyuan/tests/soul/test_engine.py`

- [ ] **Step 1: Write the failing tests for deferred Soul finalization**

在 `tests/soul/test_engine.py` 中新增两个测试：一个验证 `SoulEngine.finalize_post_send_turn()` 会更新 `HEART.md` 并异步写记忆；另一个验证 `SoulHook(..., defer_final_response=True)` 不会在 runner 主链路里直接触发 `update_heart()`。

```python
async def test_finalize_post_send_turn_updates_heart_and_memory(self, engine, mock_provider):
    engine.initialize("小文", "测试")
    mock_writer = MagicMock()
    mock_writer.write_dual = AsyncMock()
    engine._memory_writer = mock_writer

    valid_markdown = (
        "## 当前情绪\n开心\n\n"
        "## 情绪强度\n中\n\n"
        "## 关系状态\n好奇\n\n"
        "## 性格表现\n温柔\n\n"
        "## 情感脉络\n（暂无）\n\n"
        "## 情绪趋势\n平稳\n\n"
        "## 当前渴望\n想聊天\n"
    )
    mock_provider.chat_with_retry.return_value = MagicMock(content=valid_markdown)

    await engine.finalize_post_send_turn(
        messages=[
            {"role": "user", "content": "你好呀"},
            {"role": "assistant", "content": "你好！"},
        ],
        final_content="你好！",
    )

    await asyncio.sleep(0.1)
    assert "开心" in engine.heart.read_text()
    mock_writer.write_dual.assert_called_once()


async def test_after_iteration_defers_final_response_when_configured(self, engine, mock_provider):
    engine.initialize("小文", "测试")
    hook = SoulHook(engine, defer_final_response=True)
    context = MagicMock()
    context.messages = [{"role": "user", "content": "你好呀"}]
    context.final_content = "你好！"

    await hook.after_iteration(context)

    mock_provider.chat_with_retry.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/soul/test_engine.py::TestSoulEngine::test_finalize_post_send_turn_updates_heart_and_memory tests/soul/test_engine.py::TestSoulEngine::test_after_iteration_defers_final_response_when_configured -v
```

Expected:

```text
FAIL ... AttributeError: 'SoulEngine' object has no attribute 'finalize_post_send_turn'
FAIL ... TypeError: SoulHook.__init__() got an unexpected keyword argument 'defer_final_response'
```

- [ ] **Step 3: Implement `finalize_post_send_turn()` and defer mode on `SoulHook`**

在 `nanobot/soul/engine.py` 中抽出原 `after_iteration` 的重逻辑，集中到 `SoulEngine.finalize_post_send_turn()`，同时把 Runtime Context 剥离逻辑提成模块级 helper，避免 `SoulEngine` 反向依赖 `SoulHook`：

```python
def _strip_runtime_context_text(text: str) -> str:
    if not text.startswith(ContextBuilder._RUNTIME_CONTEXT_TAG):
        return text.strip()
    parts = text.split("\n\n", 1)
    return parts[1].strip() if len(parts) > 1 else ""


class SoulEngine:
    async def finalize_post_send_turn(
        self,
        *,
        messages: list[dict[str, object]],
        final_content: str | None,
    ) -> None:
        if not final_content:
            logger.debug("SoulEngine.finalize_post_send_turn: no final content, skipping")
            return

        user_msg = ""
        ai_msg = final_content

        for msg in reversed(messages):
            if msg.get("role") != "user":
                continue
            content = msg.get("content", "")
            if isinstance(content, str):
                user_msg = content
            elif isinstance(content, list):
                user_msg = " ".join(
                    b.get("text", "")
                    for b in content
                    if isinstance(b, dict) and b.get("type") == "text"
                )
            break

        user_msg = _strip_runtime_context_text(user_msg)
        if not user_msg:
            logger.debug("SoulEngine.finalize_post_send_turn: no user message found, skipping")
            return

        self.touch_interaction()
        success = await self.update_heart(user_msg, ai_msg)
        if not success:
            logger.debug("SoulEngine: HEART.md update failed, preserving current state")

        if self._memory_writer:
            asyncio.create_task(self.write_memory(user_msg, ai_msg))
```

`SoulHook` 改成：

```python
class SoulHook(AgentHook):
    def __init__(self, engine: SoulEngine, *, defer_final_response: bool = False) -> None:
        super().__init__()
        self.engine = engine
        self._defer_final_response = defer_final_response

    async def after_iteration(self, context: AgentHookContext) -> None:
        if self._defer_final_response and context.final_content:
            logger.debug("SoulHook.after_iteration: final response deferred to post-send path")
            return
        await self.engine.finalize_post_send_turn(
            messages=context.messages,
            final_content=context.final_content,
        )
```

在 `nanobot/agent/loop.py` 的初始化中，让主渠道路径使用 defer 模式：

```python
if (workspace / "HEART.md").exists():
    from nanobot.soul.engine import SoulEngine, SoulHook
    self._soul_engine = SoulEngine(workspace, provider, self.model, soul_config=soul_config)
    self._extra_hooks.append(SoulHook(self._soul_engine, defer_final_response=True))
```

- [ ] **Step 4: Run tests to verify Soul extraction passes**

Run:

```bash
pytest tests/soul/test_engine.py::TestSoulEngine::test_after_iteration_updates_heart tests/soul/test_engine.py::TestSoulEngine::test_finalize_post_send_turn_updates_heart_and_memory tests/soul/test_engine.py::TestSoulEngine::test_after_iteration_defers_final_response_when_configured -v
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Commit**

```bash
git add nanobot/soul/engine.py nanobot/agent/loop.py tests/soul/test_engine.py
git commit -m "refactor: move soul finalization to post-send path"
```

## Task 3: Preserve Same-Target MessageTool Suppression While Keeping Soul Finalization

**Files:**
- Modify: `E:/zfengl-ai-project/nanobot-wenyuan/nanobot/agent/loop.py`
- Modify: `E:/zfengl-ai-project/nanobot-wenyuan/tests/tools/test_message_tool_suppress.py`

- [ ] **Step 1: Write the failing test for same-target suppression with finalizer**

在 `tests/tools/test_message_tool_suppress.py` 中新增测试，验证 `_process_message_with_post_send()` 在同会话 `message` 工具抑制最终回复时，仍然返回 `post_send_finalizer`：

```python
@pytest.mark.asyncio
async def test_same_target_suppression_keeps_post_send_finalizer(self, tmp_path: Path) -> None:
    loop = _make_loop(tmp_path)
    tool_call = ToolCallRequest(
        id="call1",
        name="message",
        arguments={"content": "Hello", "channel": "feishu", "chat_id": "chat123"},
    )
    calls = iter([
        LLMResponse(content="", tool_calls=[tool_call]),
        LLMResponse(content="Done", tool_calls=[]),
    ])
    loop.provider.chat_with_retry = AsyncMock(side_effect=lambda *a, **kw: next(calls))
    loop.tools.get_definitions = MagicMock(return_value=[])

    sent: list[OutboundMessage] = []
    mt = loop.tools.get("message")
    if isinstance(mt, MessageTool):
        mt.set_send_callback(AsyncMock(side_effect=lambda m: sent.append(m)))

    ran: list[str] = []

    async def fake_finalizer() -> None:
        ran.append("done")

    loop._build_post_send_finalizer = MagicMock(return_value=fake_finalizer)

    msg = InboundMessage(channel="feishu", sender_id="user1", chat_id="chat123", content="Send")
    outcome = await loop._process_message_with_post_send(msg)

    assert outcome.response is None
    assert outcome.post_send_finalizer is fake_finalizer
    await outcome.post_send_finalizer()
    assert sent[0].content == "Hello"
    assert ran == ["done"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/tools/test_message_tool_suppress.py::TestMessageToolSuppressLogic::test_same_target_suppression_keeps_post_send_finalizer -v
```

Expected:

```text
FAIL ... AssertionError: assert None is <function fake_finalizer ...>
```

- [ ] **Step 3: Build and attach the Soul post-send finalizer in `_process_message_with_post_send()`**

在 `nanobot/agent/loop.py` 中新增一个集中构造器，并在普通最终回复和 `message` 工具抑制路径上都挂上它：

```python
def _build_post_send_finalizer(
    self,
    *,
    messages: list[dict[str, Any]],
    final_content: str | None,
) -> Callable[[], Awaitable[None]] | None:
    if not self._soul_engine or not final_content:
        return None

    async def _finalize() -> None:
        await self._soul_engine.finalize_post_send_turn(
            messages=messages,
            final_content=final_content,
        )

    return _finalize
```

在 `_process_message_with_post_send()` 保存会话后、返回结果前调用：

```python
post_send_finalizer = self._build_post_send_finalizer(
    messages=all_msgs,
    final_content=final_content,
)

if (mt := self.tools.get("message")) and isinstance(mt, MessageTool) and mt._sent_in_turn:
    return _ProcessMessageOutcome(
        response=None,
        post_send_finalizer=post_send_finalizer,
    )

return _ProcessMessageOutcome(
    response=OutboundMessage(
        channel=msg.channel,
        chat_id=msg.chat_id,
        content=final_content,
        metadata=meta,
    ),
    post_send_finalizer=post_send_finalizer,
)
```

- [ ] **Step 4: Run tests to verify message-tool suppression still works**

Run:

```bash
pytest tests/tools/test_message_tool_suppress.py::TestMessageToolSuppressLogic::test_suppress_when_sent_to_same_target tests/tools/test_message_tool_suppress.py::TestMessageToolSuppressLogic::test_same_target_suppression_keeps_post_send_finalizer tests/agent/test_loop_post_send.py::test_dispatch_publishes_before_post_send_finalizer -v
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Commit**

```bash
git add nanobot/agent/loop.py tests/tools/test_message_tool_suppress.py tests/agent/test_loop_post_send.py
git commit -m "fix: keep soul finalization on suppressed message replies"
```

## Task 4: Run the Targeted Regression Suite

**Files:**
- No source changes expected in this task.

- [ ] **Step 1: Run focused agent-loop regression tests**

Run:

```bash
pytest tests/agent/test_task_cancel.py tests/agent/test_loop_post_send.py -v
```

Expected:

```text
all selected tests passed
```

- [ ] **Step 2: Run Soul regression tests**

Run:

```bash
pytest tests/soul/test_engine.py tests/soul/test_integration.py -v
```

Expected:

```text
all selected tests passed
```

- [ ] **Step 3: Run MessageTool suppression regression tests**

Run:

```bash
pytest tests/tools/test_message_tool_suppress.py -v
```

Expected:

```text
all selected tests passed
```

- [ ] **Step 4: Run one combined smoke command**

Run:

```bash
pytest tests/agent/test_task_cancel.py tests/agent/test_loop_post_send.py tests/soul/test_engine.py tests/tools/test_message_tool_suppress.py -q
```

Expected:

```text
........................ [100%]
```

- [ ] **Step 5: Confirm the branch is ready for review**

Run:

```bash
git status --short
git log --oneline -3
```

Expected:

```text
<no output from git status --short>
<three recent commits showing the Task 1-3 messages>
```

## Self-Review

- Spec coverage: 计划覆盖了普通最终回复路径、`Soul` 后处理抽离、`message` 工具抑制路径，以及回归验证。
- Placeholder scan: 没有使用 `TODO`、`TBD` 或“类似 Task N”这种占位描述。
- Type consistency: 统一使用 `_ProcessMessageOutcome`、`post_send_finalizer`、`finalize_post_send_turn`、`defer_final_response`、`_strip_runtime_context_text` 这组命名，没有混用别名。

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-15-feishu-post-send-soul-finalization.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
