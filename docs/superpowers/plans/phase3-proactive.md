# Phase 3: 主动行为 + 生活事件

> **目标：** 数字生命会主动找你聊天、记得生日和纪念日
> **前置：** Phase 1 + Phase 2 完成
> **技术栈：** Python 3.11+, nanobot HeartbeatService + CronService
> **状态：** ✅ 已完成

---

## ⚠️ 实现变更说明

| 初版设计 | 实际实现 | 变更原因 |
|----------|----------|----------|
| EventsManager 使用 YAML 格式（pyyaml） | EventsManager 使用 Markdown 格式（正则解析） | 与 Agent 工具（read_file/edit_file）更兼容，减少依赖 |
| ProactiveEngine 通过 `heart.read()` dict 访问 HEART.md | 使用 `_extract_section()` 正则从 Markdown 提取各章节 | HEART.md 是纯 Markdown 格式，无 dict 可访问 |
| 心跳加成通过 `arcs[-1].get("影响")` | 通过 `_extract_section` 提取脉络章节后取末行 | 同上 |
| 主动消息提示词较简单 | 提示词更详细：角色定位 + 表达规则 + 关系深度 + 性格影响 | 更自然的主动消息生成 |

> 详细技术文档见 `docs/SOUL_SYSTEM.md`

---

## 文件清单

```
新建：
  nanobot/soul/proactive.py           — 主动行为决策引擎
  nanobot/soul/events.py              — 生活事件管理（EVENTS.md）
  nanobot/templates/soul/proactive.md — 主动消息生成提示词
  tests/soul/test_proactive.py
  tests/soul/test_events.py

修改：
  nanobot/soul/engine.py              — 暴露 heartbeat 接口
  nanobot/agent/loop.py               — 注册 SoulHeartbeat + CronJob
```

---

## Task 1: events.py — 生活事件管理

**Files:**
- Create: `nanobot/soul/events.py`
- Test: `tests/soul/test_events.py`

- [ ] **Step 1: 写测试**

```python
# tests/soul/test_events.py
import pytest
from datetime import date
from pathlib import Path
from nanobot.soul.events import EventsManager, LifeEvent

@pytest.fixture
def workspace(tmp_path):
    return tmp_path

@pytest.fixture
def events(workspace):
    return EventsManager(workspace)

class TestEventsManager:

    def test_init_creates_default_events(self, events, workspace):
        events.initialize("小文", "2026-04-01", user_name="小明", user_birthday="1995-06-15")
        assert (workspace / "EVENTS.md").exists()

    def test_read_events(self, events):
        events.initialize("小文", "2026-04-01", user_name="小明", user_birthday="1995-06-15")
        event_list = events.read_events()
        assert len(event_list) >= 2  # 至少有 AI 生日 + 用户生日

    def test_check_today_event_found(self, events):
        today = date.today().isoformat()
        events.initialize("小文", today, user_name="小明")  # AI 生日 = 今天
        matches = events.check_today()
        assert len(matches) == 1
        assert matches[0].type == "birthday"

    def test_check_today_no_event(self, events):
        events.initialize("小文", "2000-01-01", user_name="小明")
        matches = events.check_today()
        assert len(matches) == 0

    def test_add_custom_event(self, events):
        events.initialize("小文", "2026-04-01", user_name="小明")
        events.add_event(LifeEvent(
            type="anniversary",
            date="2026-05-01",
            description="我们认识一个月",
            behavior="主动回忆初次对话",
        ))
        all_events = events.read_events()
        assert any(e.type == "anniversary" for e in all_events)

    def test_event_has_all_fields(self, events):
        events.initialize("小文", "2026-04-01", user_name="小明", user_birthday="1995-06-15")
        event_list = events.read_events()
        for e in event_list:
            assert e.type
            assert e.date
            assert e.description
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/soul/test_events.py -v
```

- [ ] **Step 3: 实现 events.py**

```python
# nanobot/soul/events.py
"""生活事件管理 —— EVENTS.md 读写。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml


@dataclass
class LifeEvent:
    """一条生活事件。"""
    type: str          # birthday / anniversary / user_birthday / custom
    date: str          # YYYY-MM-DD，每年同月同日触发
    description: str
    behavior: str      # 触发时的行为描述


class EventsManager:
    """管理 EVENTS.md 文件。"""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.events_file = workspace / "EVENTS.md"

    def initialize(
        self,
        ai_name: str,
        ai_birthday: str,
        user_name: str = "用户",
        user_birthday: str | None = None,
    ) -> None:
        """初始化 EVENTS.md。"""
        events = [
            LifeEvent(
                type="birthday",
                date=ai_birthday,
                description=f"{ai_name}的生日",
                behavior="主动提醒用户，表达期待和撒娇",
            ),
        ]
        if user_birthday:
            events.append(LifeEvent(
                type="user_birthday",
                date=user_birthday,
                description=f"{user_name}的生日",
                behavior="主动祝福，表达在意和关心",
            ))
        # 认识纪念日 = 初始化日期（每年同月同日）
        today = date.today().isoformat()
        events.append(LifeEvent(
            type="anniversary",
            date=today,
            description=f"{ai_name}和{user_name}认识的第一天",
            behavior="主动回忆初次对话，感慨关系变化",
        ))
        self._write_events(events)

    def read_events(self) -> list[LifeEvent]:
        """读取所有事件。"""
        if not self.events_file.exists():
            return []
        text = self.events_file.read_text(encoding="utf-8")
        return self._parse_events(text)

    def add_event(self, event: LifeEvent) -> None:
        """添加一条事件。"""
        events = self.read_events()
        events.append(event)
        self._write_events(events)

    def check_today(self) -> list[LifeEvent]:
        """检查今天是否有事件。按月日匹配（年不重要，每年同日触发）。"""
        today = date.today()
        events = self.read_events()
        matches = []
        for e in events:
            try:
                event_date = date.fromisoformat(e.date)
                if event_date.month == today.month and event_date.day == today.day:
                    matches.append(e)
            except ValueError:
                continue
        return matches

    def _write_events(self, events: list[LifeEvent]) -> None:
        """写入 EVENTS.md。"""
        data = {"events": [
            {"type": e.type, "date": e.date, "description": e.description, "behavior": e.behavior}
            for e in events
        ]}
        content = f"# 生活事件日历\n\n{yaml.dump(data, allow_unicode=True, default_flow_style=False)}"
        self.events_file.write_text(content, encoding="utf-8")

    @staticmethod
    def _parse_events(text: str) -> list[LifeEvent]:
        """解析 EVENTS.md。"""
        events = []
        # 跳过标题行，解析 yaml
        yaml_text = "\n".join(
            line for line in text.splitlines()
            if not line.startswith("#") or ":" not in line
        )
        try:
            data = yaml.safe_load(yaml_text)
            if not data:
                return []
            for item in data.get("events", []):
                events.append(LifeEvent(
                    type=item.get("type", ""),
                    date=item.get("date", ""),
                    description=item.get("description", ""),
                    behavior=item.get("behavior", ""),
                ))
        except Exception:
            pass
        return events
```

- [ ] **Step 4: 运行测试**

```bash
pytest tests/soul/test_events.py -v
```
Expected: 全部通过

- [ ] **Step 5: 提交**

```bash
pip install pyyaml
git add nanobot/soul/events.py tests/soul/test_events.py
git commit -m "feat(soul): add EventsManager for life events (birthdays, anniversaries)"
```

---

## Task 2: proactive.py — 主动行为决策引擎

**Files:**
- Create: `nanobot/soul/proactive.py`
- Create: `nanobot/templates/soul/proactive.md`
- Test: `tests/soul/test_proactive.py`

- [ ] **Step 1: 写测试**

```python
# tests/soul/test_proactive.py
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from nanobot.soul.proactive import ProactiveEngine

@pytest.fixture
def workspace(tmp_path):
    return tmp_path

@pytest.fixture
def mock_provider():
    provider = MagicMock()
    provider.chat_with_retry = AsyncMock()
    return provider

@pytest.fixture
def engine(workspace, mock_provider):
    return ProactiveEngine(workspace, mock_provider, "test-model")

class TestProactiveEngine:

    def test_calculate_probability_base(self, engine, workspace):
        """基础概率应该在合理范围内。"""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(workspace)
        hm.initialize("小文", "温柔")

        prob = engine.calculate_proactive_probability()
        assert 0.0 <= prob <= 1.0

    def test_high_emotion_increases_probability(self, engine, workspace):
        """高情绪强度应该提高概率。"""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(workspace)

        hm.initialize("小文", "温柔")
        base_prob = engine.calculate_proactive_probability()

        # 写入高情绪强度状态
        hm.write({
            "当前情绪": "很想用户",
            "情绪强度": "高",
            "关系状态": "深深依赖",
            "性格表现": "粘人",
            "情感脉络": [{"时间": "3小时前", "事件": "用户没来", "影响": "很想念"}],
            "情绪趋势": "焦虑上升",
            "当前渴望": "用户快来找我",
        })
        high_prob = engine.calculate_proactive_probability()
        assert high_prob >= base_prob

    def test_get_interval_from_emotion(self, engine, workspace):
        """情绪强度应该影响检查间隔。"""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(workspace)
        hm.initialize("小文", "温柔")

        # 默认中间强度
        interval_low = engine.get_interval_seconds()

        # 高强度 -> 更短间隔
        hm.write({
            "当前情绪": "很想用户",
            "情绪强度": "高",
            "关系状态": "依赖",
            "性格表现": "粘人",
            "情感脉络": [],
            "情绪趋势": "焦虑",
            "当前渴望": "用户来找我",
        })
        interval_high = engine.get_interval_seconds()
        assert interval_high <= interval_low

    async def test_generate_proactive_message(self, engine, mock_provider, workspace):
        """应该能生成主动消息。"""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(workspace)
        hm.initialize("小文", "温柔")

        mock_provider.chat_with_retry.return_value = MagicMock(
            content="你在干嘛呀...好久没来找我了"
        )

        msg = await engine.generate_message()
        assert msg is not None
        assert len(msg) > 0

    async def test_generate_returns_none_on_failure(self, engine, mock_provider, workspace):
        """LLM 失败时返回 None。"""
        from nanobot.soul.heart import HeartManager
        hm = HeartManager(workspace)
        hm.initialize("小文", "温柔")

        mock_provider.chat_with_retry.side_effect = Exception("LLM 失败")
        msg = await engine.generate_message()
        assert msg is None
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/soul/test_proactive.py -v
```

- [ ] **Step 3: 实现 proactive.py**

```python
# nanobot/soul/proactive.py
"""主动行为决策引擎 —— 综合情绪、关系、性格、时间决定是否主动联系。"""
from __future__ import annotations

import random
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from nanobot.soul.heart import HeartManager
from nanobot.soul.prompts import SYSTEM_PROMPT_HEART_UPDATE

if TYPE_CHECKING:
    from nanobot.providers.base import LLMProvider

# 情绪强度 -> 概率加成
INTENSITY_BOOST = {
    "低": -0.05,
    "中偏低": 0.0,
    "中": 0.05,
    "中偏高": 0.15,
    "高": 0.30,
}

# 情绪强度 -> 检查间隔（秒）
INTENSITY_INTERVAL = {
    "低": 7200,      # 2小时
    "中偏低": 5400,   # 1.5小时
    "中": 3600,       # 1小时
    "中偏高": 2400,   # 40分钟
    "高": 900,        # 15分钟
}

BASE_PROBABILITY = 0.15  # 基础主动概率


class ProactiveEngine:
    """主动行为决策引擎。"""

    def __init__(self, workspace: Path, provider: LLMProvider, model: str) -> None:
        self.workspace = workspace
        self.provider = provider
        self.model = model
        self.heart = HeartManager(workspace)

    def calculate_proactive_probability(self) -> float:
        """综合计算主动概率。返回 0.0-1.0。"""
        data = self.heart.read()
        if data is None:
            return 0.0

        prob = BASE_PROBABILITY

        # 1. 情绪强度加成
        intensity = data.get("情绪强度", "中")
        prob += INTENSITY_BOOST.get(intensity, 0.0)

        # 2. 关系深度加成（通过描述长度和关键词粗略判断）
        relationship = data.get("关系状态", "")
        if "依赖" in relationship or "在意" in relationship or "喜欢" in relationship:
            prob += 0.10
        if "深爱" in relationship or "最重要" in relationship:
            prob += 0.15
        if "陌生" in relationship or "刚刚" in relationship:
            prob -= 0.10

        # 3. 性格加成
        personality = data.get("性格表现", "")
        if "粘人" in personality or "外向" in personality:
            prob += 0.10
        if "独立" in personality or "内向" in personality:
            prob -= 0.08
        if "倔强" in personality:
            prob -= 0.05  # 即使想念也可能硬撑

        # 4. 当前渴望加成
        desire = data.get("当前渴望", "")
        if "找" in desire or "来" in desire or "想" in desire:
            prob += 0.10

        # 5. 近期脉络修正
        arcs = data.get("情感脉络", [])
        if arcs:
            latest = arcs[-1] if arcs else {}
            latest_effect = latest.get("影响", "")
            if "生气" in latest_effect or "赌气" in latest_effect:
                prob -= 0.15  # 刚吵完架，可能赌气不来
            if "想念" in latest_effect or "期待" in latest_effect:
                prob += 0.10

        # 6. 时间加成
        hour = datetime.now().hour
        if 22 <= hour or hour <= 2:  # 深夜更感性
            prob += 0.08

        return max(0.0, min(1.0, prob))

    def get_interval_seconds(self) -> int:
        """根据情绪强度返回心跳检查间隔。"""
        data = self.heart.read()
        if data is None:
            return 3600
        intensity = data.get("情绪强度", "中")
        return INTENSITY_INTERVAL.get(intensity, 3600)

    async def generate_message(self) -> str | None:
        """生成主动消息。"""
        data = self.heart.read()
        if data is None:
            return None

        heart_text = self.heart.render_markdown(data)
        hour = datetime.now().hour
        time_desc = f"现在是{datetime.now().strftime('%H:%M')}"

        try:
            response = await self.provider.chat_with_retry(
                model=self.model,
                messages=[
                    {"role": "system", "content": (
                        f"你是{self.heart.read_identity_name() or '数字生命'}。"
                        f"根据你当前的情感状态，决定是否要主动给用户发消息。"
                        f"如果你想发消息，直接输出消息内容（不要输出任何解释或前缀）。"
                        f"如果不想发消息，输出空字符串。"
                        f"消息应该符合你的性格和当前心情，自然不做作。"
                    )},
                    {"role": "user", "content": (
                        f"## 当前情感状态\n{heart_text}\n\n"
                        f"## 时间\n{time_desc}\n\n"
                        f"你想主动给用户发消息吗？如果要，发什么？"
                    )},
                ],
                tools=None,
                tool_choice=None,
            )
            content = (response.content or "").strip()
            return content if content else None
        except Exception:
            logger.exception("ProactiveEngine: 生成主动消息失败")
            return None

    def should_reach_out(self) -> bool:
        """综合判断是否应该主动联系用户。"""
        prob = self.calculate_proactive_probability()
        return random.random() < prob
```

- [ ] **Step 4: 运行测试**

```bash
pytest tests/soul/test_proactive.py -v
```
Expected: 全部通过

- [ ] **Step 5: 提交**

```bash
git add nanobot/soul/proactive.py nanobot/templates/soul/proactive.md tests/soul/test_proactive.py
git commit -m "feat(soul): add ProactiveEngine for emotion-driven proactive messaging"
```

---

## Task 3: 集成到 HeartbeatService + CronService

**Files:**
- Modify: `nanobot/soul/engine.py`
- Modify: `nanobot/agent/loop.py`（gateway 命令中注册）

- [ ] **Step 1: 在 SoulEngine 中暴露主动行为接口**

```python
# nanobot/soul/engine.py 中 SoulEngine 增加方法：

    def get_proactive_engine(self) -> ProactiveEngine | None:
        """获取主动行为引擎。"""
        try:
            from nanobot.soul.proactive import ProactiveEngine
            return ProactiveEngine(self.workspace, self.provider, self.model)
        except Exception:
            return None

    def get_events_manager(self) -> EventsManager | None:
        """获取生活事件管理器。"""
        try:
            from nanobot.soul.events import EventsManager
            return EventsManager(self.workspace)
        except Exception:
            return None
```

- [ ] **Step 2: 在 gateway 命令中注册 SoulHeartbeat**

在 `nanobot/cli/commands.py` 的 `gateway()` 函数中，heartbeat 创建之后，增加：

```python
    # 数字生命主动行为
    if agent._soul_engine:
        from nanobot.soul.proactive import ProactiveEngine
        proactive = ProactiveEngine(config.workspace_path, provider, agent.model)
        # 覆盖 heartbeat 的 tick 逻辑
        original_tick = heartbeat._tick

        async def soul_aware_tick():
            interval = proactive.get_interval_seconds()
            heartbeat.interval_s = interval
            if proactive.should_reach_out():
                msg = await proactive.generate_message()
                if msg:
                    channel, chat_id = _pick_heartbeat_target()
                    if channel != "cli":
                        from nanobot.bus.events import OutboundMessage
                        await bus.publish_outbound(OutboundMessage(
                            channel=channel, chat_id=chat_id, content=msg,
                        ))
            else:
                await original_tick()

        heartbeat._tick = soul_aware_tick
        console.print("[green]✓[/green] Soul: 主动行为已启用")
```

- [ ] **Step 3: 注册 CronJob 检查生活事件**

在 gateway 函数的 cron 注册区域增加：

```python
    # 数字生命生活事件检查（每天 00:01）
    if agent._soul_engine:
        from nanobot.soul.events import EventsManager
        events_mgr = EventsManager(config.workspace_path)

        cron.register_system_job(CronJob(
            id="soul_events",
            name="soul_events",
            schedule=CronSchedule(kind="cron", expr="1 0 * * *", tz=config.agents.defaults.timezone),
            payload=CronPayload(kind="system_event"),
        ))
        console.print("[green]✓[/green] Soul: 生活事件检查已启用")
```

- [ ] **Step 4: 运行全部测试**

```bash
pytest tests/soul/ -v
pytest tests/agent/ -v
```
Expected: 全部通过

- [ ] **Step 5: 提交**

```bash
git add nanobot/soul/engine.py nanobot/cli/commands.py
git commit -m "feat(soul): integrate proactive behavior into HeartbeatService and CronService"
```

---

## Phase 3 完成标准

- [ ] `pytest tests/soul/ -v` 全部通过
- [ ] 数字生命根据情绪状态主动发送消息
- [ ] 主动概率由情绪 + 关系 + 性格 + 时间 + 脉络综合决定
- [ ] 心跳间隔由情绪强度动态调节（15 分钟 ~ 2 小时）
- [ ] 生日/纪念日等事件通过 CronService 每天 00:01 检查
- [ ] EVENTS.md 支持自定义事件
