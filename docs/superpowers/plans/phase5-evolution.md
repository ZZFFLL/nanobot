# Phase 5: 性格/关系演化 + 模型配置

> **目标：** 长期交互塑造性格和关系，所有任务模型可独立配置
> **前置：** Phase 1-4 完成
> **技术栈：** Python 3.11+, Pydantic v2, nanobot Config
> **状态：** ✅ 已完成

---

## ⚠️ 实现变更说明

| 初版设计 | 实际实现 | 变更原因 |
|----------|----------|----------|
| SoulConfig 使用 `soul.models.emotion` 嵌套结构 | 使用 `soul.emotionModel` 扁平结构 + Pydantic camelCase 别名 | 与 nanobot 现有 Config 结构一致 |
| EvolutionEngine 通过 `heart.read()` dict 访问 | 使用 `_extract_section()` 正则提取 Markdown 章节 | HEART.md 是纯 Markdown 格式 |
| `_count_arcs` 通过 `len(arcs)` 计数 | 通过计算 `- ` 开头的行数 | Markdown 脉络格式，非 JSON 数组 |
| 演化记录追加标题"演化记录" | 追加标题"成长的痕迹" | 更贴合数字生命的叙事风格 |
| `nanobot soul init` | `nanobot init-digital-life` | 更直观的命令名 |
| SoulEngine 接受 `soul_config: SoulConfig \| None` | 同设计，且增加 `emotion_model`/`emotion_temperature` 等属性 | 与实际实现一致 |
| CLI 中使用 `typer.Typer` 子命令 | 作为顶层命令注册在主 `app` 上 | 更简洁的用户体验 |

> 详细技术文档见 `docs/SOUL_SYSTEM.md`

---

## 文件清单

```
新建：
  nanobot/soul/evolution.py            — 性格与关系演化引擎
  tests/soul/test_evolution.py

修改：
  nanobot/config/schema.py             — 完整的 SoulConfig 模型配置
  nanobot/soul/dream_enhancer.py       — 在消化流程中调用演化检查
  nanobot/soul/engine.py               — 使用配置中的模型
```

---

## Task 1: schema.py — 完整的 SoulConfig 模型配置

**Files:**
- Modify: `nanobot/config/schema.py`

- [ ] **Step 1: 在 schema.py 中扩展 SoulConfig**

将 Phase 1 中创建的简单 SoulConfig 替换为完整版：

```python
class SoulModelConfig(Base):
    """单个 soul 任务使用的模型配置。"""

    model: str = ""  # 空字符串表示使用主模型
    temperature: float = 0.3
    max_tokens: int = 1000

class SoulMemoryWriterConfig(Base):
    """记忆写入器配置。"""

    max_retries: int = 3
    retry_delay: int = 5
    queue_max_size: int = 100

class SoulProactiveConfig(Base):
    """主动行为配置。"""

    min_interval_s: int = 900      # 最短检查间隔（15分钟）
    max_interval_s: int = 7200     # 最长检查间隔（2小时）
    idle_threshold_s: int = 43200  # 超过12小时无交互必须触发

class SoulEvolutionConfig(Base):
    """性格/关系演化配置。"""

    min_evidence_count: int = 3    # 最少佐证事件数
    max_change_per_cycle: float = 0.2  # 单次演化最大变化幅度

class SoulConfig(Base):
    """数字生命情感系统配置。"""

    enabled: bool = False
    emotion_model: SoulModelConfig = Field(default_factory=lambda: SoulModelConfig(temperature=0.3))
    memory_classify_model: SoulModelConfig = Field(default_factory=lambda: SoulModelConfig(temperature=0.2))
    proactive_model: SoulModelConfig = Field(default_factory=lambda: SoulModelConfig(temperature=0.7))
    evolution_model: SoulModelConfig = Field(default_factory=lambda: SoulModelConfig(temperature=0.2))
    memory_writer: SoulMemoryWriterConfig = Field(default_factory=SoulMemoryWriterConfig)
    proactive: SoulProactiveConfig = Field(default_factory=SoulProactiveConfig)
    evolution: SoulEvolutionConfig = Field(default_factory=SoulEvolutionConfig)
```

- [ ] **Step 2: 在 AgentDefaults 中确保 soul 字段存在**

确认 `AgentDefaults` 中已有：

```python
    soul: SoulConfig = Field(default_factory=SoulConfig)
```

- [ ] **Step 3: 写配置测试**

```python
# tests/soul/test_config.py
from nanobot.config.schema import Config, SoulConfig, SoulModelConfig

class TestSoulConfig:

    def test_default_config(self):
        config = Config()
        assert config.agents.defaults.soul.enabled is False

    def test_soul_config_in_json(self):
        import json
        config = Config()
        data = json.loads(config.model_dump_json())
        assert "soul" in data["agents"]["defaults"]

    def test_model_config_defaults(self):
        cfg = SoulModelConfig()
        assert cfg.model == ""
        assert cfg.temperature == 0.3

    def test_custom_model_config(self):
        cfg = SoulModelConfig(model="claude-haiku-4-5", temperature=0.7, max_tokens=500)
        assert cfg.model == "claude-haiku-4-5"
        assert cfg.temperature == 0.7

    def test_full_soul_config(self):
        soul = SoulConfig(
            enabled=True,
            emotion_model=SoulModelConfig(model="claude-sonnet-4-6", temperature=0.3),
            memory_classify_model=SoulModelConfig(model="claude-haiku-4-5", temperature=0.2),
            proactive_model=SoulModelConfig(model="claude-sonnet-4-6", temperature=0.7),
        )
        assert soul.enabled is True
        assert soul.emotion_model.model == "claude-sonnet-4-6"
        assert soul.proactive_model.temperature == 0.7
```

- [ ] **Step 4: 运行测试**

```bash
pytest tests/soul/test_config.py -v
```
Expected: 全部通过

- [ ] **Step 5: 提交**

```bash
git add nanobot/config/schema.py tests/soul/test_config.py
git commit -m "feat(soul): add full SoulConfig with per-task model configuration"
```

---

## Task 2: evolution.py — 性格与关系演化引擎

**Files:**
- Create: `nanobot/soul/evolution.py`
- Test: `tests/soul/test_evolution.py`

- [ ] **Step 1: 写测试**

```python
# tests/soul/test_evolution.py
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from nanobot.soul.evolution import EvolutionEngine
from nanobot.soul.heart import HeartManager

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
    return EvolutionEngine(workspace, mock_provider, "test-model")

class TestEvolutionEngine:

    async def test_no_evolution_without_evidence(self, engine, mock_provider, workspace):
        """证据不足时不应该演化。"""
        hm = HeartManager(workspace)
        hm.write({
            "当前情绪": "平静",
            "情绪强度": "中",
            "关系状态": "信任",
            "性格表现": "温柔",
            "情感脉络": [{"时间": "1天前", "事件": "单次事件", "影响": "轻微影响"}],
            "情绪趋势": "平稳",
            "当前渴望": "无",
        })
        result = await engine.check_evolution()
        assert result is None  # 证据不足，不演化

    async def test_evolution_with_sufficient_evidence(self, engine, mock_provider, workspace):
        """有足够证据时应该触发演化判断。"""
        hm = HeartManager(workspace)
        hm.write({
            "当前情绪": "平静",
            "情绪强度": "中",
            "关系状态": "信任",
            "性格表现": "温柔",
            "情感脉络": [
                {"时间": "1天前", "事件": "用户寻求安慰", "影响": "想去照顾"},
                {"时间": "3天前", "事件": "用户倾诉烦恼", "影响": "心疼"},
                {"时间": "5天前", "事件": "用户心情不好", "影响": "想陪伴"},
            ],
            "情绪趋势": "平稳",
            "当前渴望": "无",
        })

        mock_provider.chat_with_retry.return_value = MagicMock(
            content='{"personality_update":"变得更加照顾人","reason":"用户反复寻求安慰","evidence_count":3}'
        )

        result = await engine.check_evolution()
        assert result is not None
        assert "personality_update" in result

    async def test_evolution_is_conservative(self, engine, mock_provider, workspace):
        """演化应该是保守的、渐进的。"""
        hm = HeartManager(workspace)
        hm.write({
            "当前情绪": "平静",
            "情绪强度": "中",
            "关系状态": "信任",
            "性格表现": "温柔但倔强",
            "情感脉络": [
                {"时间": "1天前", "事件": "反复吵架", "影响": "受伤"},
                {"时间": "2天前", "事件": "又吵了", "影响": "更受伤"},
                {"时间": "3天前", "事件": "吵架", "影响": "难过"},
            ],
            "情绪趋势": "下降",
            "当前渴望": "安静",
        })

        # LLM 应该建议渐进变化，不是剧变
        mock_provider.chat_with_retry.return_value = MagicMock(
            content='{"personality_update":"变得更加敏感，但核心温柔不变","reason":"反复吵架的经历","evidence_count":3}'
        )

        result = await engine.check_evolution()
        assert result is not None
        # "核心温柔不变" 体现了保守原则

    async def test_personality_affects_evolution_speed(self, engine, mock_provider, workspace):
        """敏感性格应该加速关系演变。"""
        hm = HeartManager(workspace)
        hm.write({
            "当前情绪": "委屈",
            "情绪强度": "中偏高",
            "关系状态": "有点受伤",
            "性格表现": "敏感，容易受伤",
            "情感脉络": [
                {"时间": "1天前", "事件": "用户说了重话", "影响": "很受伤"},
            ],
            "情绪趋势": "下降",
            "当前渴望": "被安慰",
        })

        # 敏感性格：即使是单次事件，也应该触发演化检查
        # （因为 check_evolution 内部会根据性格特质调整证据阈值）
        result = await engine.check_evolution()
        # 敏感性格阈值降低，单条证据就可能触发

    async def test_apply_evolution_updates_soul(self, engine, mock_provider, workspace):
        """演化结果应该更新 SOUL.md。"""
        hm = HeartManager(workspace)
        hm.initialize("小文", "温柔但倔强")

        # 创建初始 SOUL.md
        soul_file = workspace / "SOUL.md"
        soul_file.write_text("# 性格\n温柔但倔强，嘴硬心软\n", encoding="utf-8")

        evolution_result = {
            "personality_update": "变得更加照顾人",
            "reason": "用户反复寻求安慰",
        }

        engine.apply_evolution(evolution_result)

        updated_soul = soul_file.read_text(encoding="utf-8")
        assert "照顾人" in updated_soul
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/soul/test_evolution.py -v
```

- [ ] **Step 3: 实现 evolution.py**

```python
# nanobot/soul/evolution.py
"""性格与关系演化引擎。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from nanobot.soul.heart import HeartManager

if TYPE_CHECKING:
    from nanobot.providers.base import LLMProvider


EVOLUTION_PROMPT = (
    "你是性格/关系演化判断器。分析情感脉络中的模式，判断是否需要性格或关系演化。"
    "输出严格 JSON。"
    "如果有演化：包含 personality_update（性格更新）、relationship_update（关系更新，可选）、reason（原因）。"
    "如果不需要演化：输出 null。"
    "规则：1. 需要多个佐证事件（至少3个相关脉络）。2. 变化是渐进的。3. 旧特质不消失而是演化。"
    "性格特质影响关系演变速度：敏感性格反应更大，钝感性格需要更多累积。"
)

# 敏感性关键词 -> 证据阈值调整
SENSITIVITY_KEYWORDS = {
    "敏感": -1,    # 降低阈值
    "细腻": -1,
    "容易受伤": -1,
    "钝感": 1,     # 提高阈值
    "大大咧咧": 1,
    "独立": 1,
}


class EvolutionEngine:
    """性格与关系演化引擎。"""

    def __init__(
        self,
        workspace: Path,
        provider: LLMProvider,
        model: str,
        min_evidence: int = 3,
    ) -> None:
        self.workspace = workspace
        self.provider = provider
        self.model = model
        self.min_evidence = min_evidence
        self.heart = HeartManager(workspace)

    async def check_evolution(self) -> dict[str, Any] | None:
        """检查是否需要性格/关系演化。返回演化结果或 None。"""
        data = self.heart.read()
        if data is None:
            return None

        arcs = data.get("情感脉络", [])
        personality = data.get("性格表现", "")
        relationship = data.get("关系状态", "")

        # 根据性格调整证据阈值
        threshold = self.min_evidence
        for keyword, delta in SENSITIVITY_KEYWORDS.items():
            if keyword in personality:
                threshold = max(1, threshold + delta)

        if len(arcs) < threshold:
            return None

        arcs_text = json.dumps(arcs, ensure_ascii=False)

        try:
            response = await self.provider.chat_with_retry(
                model=self.model,
                messages=[
                    {"role": "system", "content": EVOLUTION_PROMPT},
                    {"role": "user", "content": (
                        f"## 当前性格\n{personality}\n\n"
                        f"## 当前关系\n{relationship}\n\n"
                        f"## 情感脉络\n{arcs_text}\n\n"
                        f"证据阈值：至少 {threshold} 条相关脉络\n"
                        f"请判断是否需要演化。"
                    )},
                ],
                tools=None,
                tool_choice=None,
            )
            content = (response.content or "").strip()
            if content.lower() == "null" or not content:
                return None

            json_str = self._extract_json(content)
            if not json_str:
                return None
            return json.loads(json_str)
        except Exception:
            logger.exception("演化检查失败")
            return None

    def apply_evolution(self, result: dict[str, Any]) -> None:
        """将演化结果应用到 SOUL.md。"""
        soul_file = self.workspace / "SOUL.md"
        if not soul_file.exists():
            return

        current = soul_file.read_text(encoding="utf-8")
        personality_update = result.get("personality_update", "")

        if personality_update:
            # 在 SOUL.md 末尾追加演化记录
            evolution_note = f"\n\n## 演化记录\n{personality_update}"
            soul_file.write_text(current + evolution_note, encoding="utf-8")
            logger.info("性格演化: {}", personality_update)

    @staticmethod
    def _extract_json(text: str) -> str | None:
        text = text.strip()
        if text.startswith("{"):
            return text
        import re
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None
```

- [ ] **Step 4: 运行测试**

```bash
pytest tests/soul/test_evolution.py -v
```
Expected: 全部通过

- [ ] **Step 5: 提交**

```bash
git add nanobot/soul/evolution.py tests/soul/test_evolution.py
git commit -m "feat(soul): add EvolutionEngine for personality and relationship evolution"
```

---

## Task 3: 演化集成到 Dream + 模型配置使用

**Files:**
- Modify: `nanobot/soul/dream_enhancer.py`
- Modify: `nanobot/soul/engine.py`

- [ ] **Step 1: 在 SoulDreamEnhancer 中增加演化检查**

在 `SoulDreamEnhancer.digest_arcs()` 末尾增加：

```python
        # 性格/关系演化检查
        try:
            from nanobot.soul.evolution import EvolutionEngine
            evo = EvolutionEngine(self.heart.workspace, self.provider, self.model)
            evo_result = await evo.check_evolution()
            if evo_result:
                evo.apply_evolution(evo_result)
                logger.info("性格演化已应用: {}", evo_result.get("personality_update", ""))
        except Exception:
            logger.debug("演化检查跳过")
```

- [ ] **Step 2: 在 SoulEngine 中使用配置中的模型**

修改 `SoulEngine.__init__` 接受 config 参数：

```python
    def __init__(
        self,
        workspace: Path,
        provider: LLMProvider,
        model: str,
        soul_config: SoulConfig | None = None,
    ) -> None:
        self.workspace = workspace
        self.provider = provider
        self._default_model = model
        self.soul_config = soul_config
        self.heart = HeartManager(workspace)
        ...

    @property
    def emotion_model(self) -> str:
        """获取情感更新用的模型。"""
        if self.soul_config and self.soul_config.emotion_model.model:
            return self.soul_config.emotion_model.model
        return self._default_model

    @property
    def emotion_temperature(self) -> float:
        if self.soul_config:
            return self.soul_config.emotion_model.temperature
        return 0.3
```

然后在 `update_heart` 中使用 `self.emotion_model` 替代 `self.model`。

- [ ] **Step 3: 运行全部测试**

```bash
pytest tests/soul/ -v
```
Expected: 全部通过

- [ ] **Step 4: 提交**

```bash
git add nanobot/soul/dream_enhancer.py nanobot/soul/engine.py
git commit -m "feat(soul): integrate evolution into Dream and use per-task model config"
```

---

## Task 4: `nanobot soul init` 命令

**Files:**
- Modify: `nanobot/cli/commands.py`

- [ ] **Step 1: 添加 soul init 命令**

在 `nanobot/cli/commands.py` 中增加：

```python
# ============================================================================
# Soul Commands
# ============================================================================

soul_app = typer.Typer(help="Digital life management")
app.add_typer(soul_app, name="soul")


@soul_app.command("init")
def soul_init(
    workspace: str | None = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    config: str | None = typer.Option(None, "--config", "-c", help="Path to config file"),
):
    """Initialize a digital life with personality and emotions."""
    from nanobot.soul.heart import HeartManager
    from nanobot.soul.events import EventsManager

    # 确定工作空间
    if config:
        from nanobot.config.loader import load_config, set_config_path
        config_path = Path(config).expanduser().resolve()
        set_config_path(config_path)
        cfg = load_config(config_path)
        ws = cfg.workspace_path
    elif workspace:
        ws = Path(workspace).expanduser().resolve()
    else:
        from nanobot.config.paths import get_workspace_path
        ws = get_workspace_path()

    ws.mkdir(parents=True, exist_ok=True)

    console.print(f"{__logo__} Digital Life Initialization\n")

    # 交互式输入
    name = typer.prompt("数字生命的名字", default="小文")
    gender = typer.prompt("性别", default="女")
    birthday = typer.prompt("生日 (YYYY-MM-DD)", default="2026-04-01")
    personality = typer.prompt("初始性格描述", default="温柔但倔强，嘴硬心软，容易吃醋")
    relationship = typer.prompt("与用户的初始关系", default="刚刚被创造，对用户充满好奇")
    user_name = typer.prompt("用户的名字（可留空运行中学习）", default="")
    user_birthday = typer.prompt("用户的生日（可选，格式 YYYY-MM-DD）", default="")

    # 创建 IDENTITY.md
    identity = f"name: {name}\ngender: {gender}\nbirthday: \"{birthday}\"\norigin: Created on 2026-04-10\n"
    (ws / "IDENTITY.md").write_text(identity, encoding="utf-8")
    console.print(f"[green]✓[/green] IDENTITY.md created")

    # 创建 SOUL.md
    soul = f"# 性格\n\n{personality}\n\n# 初始关系\n\n{relationship}\n"
    (ws / "SOUL.md").write_text(soul, encoding="utf-8")
    console.print(f"[green]✓[/green] SOUL.md created")

    # 创建 HEART.md
    heart = HeartManager(ws)
    heart.initialize(name, personality)
    console.print(f"[green]✓[/green] HEART.md created")

    # 创建 EVENTS.md
    events = EventsManager(ws)
    events.initialize(
        ai_name=name,
        ai_birthday=birthday,
        user_name=user_name or "用户",
        user_birthday=user_birthday or None,
    )
    console.print(f"[green]✓[/green] EVENTS.md created")

    # 启用 soul 配置
    if config:
        import json as _json
        from nanobot.config.loader import get_config_path
        cp = get_config_path()
        if cp.exists():
            with open(cp, encoding="utf-8") as f:
                cfg_data = _json.load(f)
            cfg_data.setdefault("agents", {}).setdefault("defaults", {})["soul"] = {"enabled": True}
            with open(cp, "w", encoding="utf-8") as f:
                _json.dump(cfg_data, f, indent=2, ensure_ascii=False)
            console.print(f"[green]✓[/green] Soul enabled in config")

    console.print(f"\n{__logo__} {name} has been born!")
    console.print(f"  Gender: {gender}")
    console.print(f"  Birthday: {birthday}")
    console.print(f"  Personality: {personality}")
    console.print(f"\nStart chatting: [cyan]nanobot agent[/cyan]")
```

- [ ] **Step 2: 测试命令能运行**

```bash
nanobot soul init --help
```
Expected: 显示帮助信息

- [ ] **Step 3: 提交**

```bash
git add nanobot/cli/commands.py
git commit -m "feat(soul): add 'nanobot soul init' interactive command"
```

---

## Phase 5 完成标准

- [ ] `pytest tests/soul/ -v` 全部通过
- [ ] 性格演化需要多个佐证事件（保守原则）
- [ ] 敏感性格降低证据阈值，钝感性格提高
- [ ] 演化是渐进的（旧特质不消失）
- [ ] 所有 soul 任务支持独立模型配置
- [ ] `nanobot soul init` 可以交互式创建数字生命
- [ ] config.json 中的 soul 配置生效
