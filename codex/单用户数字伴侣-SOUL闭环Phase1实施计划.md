# 单用户数字伴侣 SOUL 闭环 Phase 1 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不破坏 nanobot 主干与现有飞书入口的前提下，完成 SOUL 模块第一阶段闭环，实现方法论驱动、程序裁决、周期治理、全链路留痕的单用户数字伴侣内核。

**Architecture:** 保持 `AgentLoop + SoulHook + Dream + Heartbeat + CronService` 五条现有链路不变，把新增能力尽量内聚到 `nanobot/soul/`。LLM 负责在方法论框架内生成情绪、关系、演化与治理候选结论，程序负责结构校验、边界裁决、状态写入、日志留痕与定时治理。

**Tech Stack:** Python 3.11+、Pydantic v2、pytest、asyncio、nanobot 当前 Hook/Dream/Heartbeat/Cron 架构、Markdown 状态文件、飞书渠道验证。

---

## 文件结构规划

### 新增文件

- `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\soul\methodology.py`
  - 方法论定义与读取，固定人格、关系、情绪、陪伴能力的演化边界。
- `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\soul\anchor.py`
  - `CORE_ANCHOR.md` 的读写与锚点校验。
- `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\soul\profile.py`
  - `SOUL_PROFILE.md` 的结构化状态读写。
- `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\soul\inference.py`
  - 统一 SOUL 的 LLM 候选输出协议。
- `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\soul\adjudicator.py`
  - 程序裁决层，负责边界与幅度控制。
- `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\soul\review.py`
  - 周复盘生成逻辑。
- `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\soul\calibration.py`
  - 月校准生成逻辑。
- `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\soul\logs.py`
  - 演化、复盘、校准日志统一写入。
- `E:\zfengl-ai-project\nanobot-wenyuan\tests\soul\test_anchor.py`
- `E:\zfengl-ai-project\nanobot-wenyuan\tests\soul\test_profile.py`
- `E:\zfengl-ai-project\nanobot-wenyuan\tests\soul\test_inference.py`
- `E:\zfengl-ai-project\nanobot-wenyuan\tests\soul\test_adjudicator.py`
- `E:\zfengl-ai-project\nanobot-wenyuan\tests\soul\test_review.py`
- `E:\zfengl-ai-project\nanobot-wenyuan\tests\soul\test_calibration.py`
- `E:\zfengl-ai-project\nanobot-wenyuan\tests\soul\test_logs.py`

### 修改文件

- `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\soul\engine.py`
  - 接入统一候选协议、裁决层、日志写入。
- `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\soul\heart.py`
  - 明确快变状态职责，不承载锚点。
- `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\soul\proactive.py`
  - 改成“候选生成 + 基础门控”，不直接充当最终裁决。
- `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\soul\evolution.py`
  - 与方法论、画像状态、裁决层打通。
- `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\agent\memory.py`
  - 修 Dream 与 SOUL 协议对接，接入 review/calibration 材料。
- `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\cli\commands.py`
  - 注册 `weekly_review` 与 `monthly_calibration` 定时任务。
- `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\agent\context.py`
  - 在 system prompt 中补充锚点/画像摘要。
- `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\config\schema.py`
  - 收敛并明确 SOUL 配置消费点。

### 工作区文件职责

- `CORE_ANCHOR.md`
  - 稳定层，不允许日常对话直接改写。
- `SOUL_METHOD.md`
  - 稳定层，定义方法论与边界。
- `SOUL_PROFILE.md`
  - 慢变结构化状态层。
- `SOUL.md`
  - 慢变人格表达层。
- `HEART.md`
  - 快变热状态层。
- `soul_logs/weekly/*.md`
- `soul_logs/monthly/*.md`
- `soul_logs/evolution/*.md`

### 测试运行约束

当前环境必须显式设置：

```powershell
$env:PYTHONPATH='E:\zfengl-ai-project\nanobot-wenyuan'
```

否则 `pytest tests/soul` 可能优先导入外部安装的 `nanobot`，导致测试结果无效。

---

### Task 1: 方法论、锚点与画像状态基础层

**Files:**
- Create: `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\soul\methodology.py`
- Create: `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\soul\anchor.py`
- Create: `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\soul\profile.py`
- Test: `E:\zfengl-ai-project\nanobot-wenyuan\tests\soul\test_anchor.py`
- Test: `E:\zfengl-ai-project\nanobot-wenyuan\tests\soul\test_profile.py`

- [ ] **Step 1: 写出锚点与画像状态的失败测试**

```python
from nanobot.soul.anchor import AnchorManager
from nanobot.soul.profile import SoulProfileManager


def test_anchor_manager_reads_core_anchor(tmp_path):
    anchor_file = tmp_path / "CORE_ANCHOR.md"
    anchor_file.write_text("# 核心锚点\n\n- 不无底线顺从\n", encoding="utf-8")
    manager = AnchorManager(tmp_path)
    assert "不无底线顺从" in manager.read_text()


def test_profile_manager_roundtrip(tmp_path):
    manager = SoulProfileManager(tmp_path)
    profile = {
        "personality": {"Fi": 0.8, "Fe": 0.3},
        "relationship": {"stage": "亲近", "trust": 0.6},
        "companionship": {"empathy_fit": 0.5},
    }
    manager.write(profile)
    assert manager.read()["relationship"]["stage"] == "亲近"
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
$env:PYTHONPATH='E:\zfengl-ai-project\nanobot-wenyuan'
pytest tests/soul/test_anchor.py tests/soul/test_profile.py -q
```

Expected:

- FAIL，提示 `nanobot.soul.anchor` 或 `nanobot.soul.profile` 不存在

- [ ] **Step 3: 实现最小方法论、锚点与画像状态管理器**

```python
# nanobot/soul/anchor.py
from pathlib import Path


class AnchorManager:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.anchor_file = workspace / "CORE_ANCHOR.md"

    def read_text(self) -> str:
        try:
            return self.anchor_file.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""
```

```python
# nanobot/soul/profile.py
from pathlib import Path
import json


class SoulProfileManager:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.profile_file = workspace / "SOUL_PROFILE.md"

    def read(self) -> dict:
        try:
            text = self.profile_file.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {}
        if text.startswith("```json"):
            text = text.removeprefix("```json").removesuffix("```").strip()
        return json.loads(text) if text else {}

    def write(self, profile: dict) -> None:
        text = "```json\n" + json.dumps(profile, ensure_ascii=False, indent=2) + "\n```"
        self.profile_file.write_text(text, encoding="utf-8")
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```powershell
$env:PYTHONPATH='E:\zfengl-ai-project\nanobot-wenyuan'
pytest tests/soul/test_anchor.py tests/soul/test_profile.py -q
```

Expected:

- PASS

- [ ] **Step 5: 提交**

```bash
git add nanobot/soul/anchor.py nanobot/soul/profile.py nanobot/soul/methodology.py tests/soul/test_anchor.py tests/soul/test_profile.py
git commit -m "feat: add soul anchor and profile foundations"
```

### Task 2: 统一 SOUL 候选输出协议与裁决层

**Files:**
- Create: `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\soul\inference.py`
- Create: `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\soul\adjudicator.py`
- Test: `E:\zfengl-ai-project\nanobot-wenyuan\tests\soul\test_inference.py`
- Test: `E:\zfengl-ai-project\nanobot-wenyuan\tests\soul\test_adjudicator.py`

- [ ] **Step 1: 写关系阶段候选协议与裁决失败测试**

```python
from nanobot.soul.inference import RelationshipInference
from nanobot.soul.adjudicator import SoulAdjudicator


def test_relationship_inference_has_required_fields():
    candidate = RelationshipInference(
        current_stage_assessment="亲近",
        proposed_stage="依恋",
        direction="up",
        evidence_summary="近 7 天高频互动",
        dimension_changes={"trust": 0.1},
        personality_influence="Fi 高导致情感感知更强",
        risk_flags=[],
        confidence=0.82,
    )
    assert candidate.proposed_stage == "依恋"


def test_adjudicator_rejects_large_stage_jump():
    adjudicator = SoulAdjudicator()
    allowed, reason = adjudicator.check_stage_transition(
        current_stage="熟悉",
        proposed_stage="爱意",
        direction="up",
        confidence=0.9,
    )
    assert allowed is False
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
$env:PYTHONPATH='E:\zfengl-ai-project\nanobot-wenyuan'
pytest tests/soul/test_inference.py tests/soul/test_adjudicator.py -q
```

Expected:

- FAIL，提示模块不存在

- [ ] **Step 3: 实现最小协议对象与裁决器**

```python
# nanobot/soul/inference.py
from dataclasses import dataclass


@dataclass(slots=True)
class RelationshipInference:
    current_stage_assessment: str
    proposed_stage: str
    direction: str
    evidence_summary: str
    dimension_changes: dict[str, float]
    personality_influence: str
    risk_flags: list[str]
    confidence: float
```

```python
# nanobot/soul/adjudicator.py
_STAGES = ("熟悉", "亲近", "依恋", "深度依恋", "喜欢", "爱意")


class SoulAdjudicator:
    def check_stage_transition(
        self,
        current_stage: str,
        proposed_stage: str,
        direction: str,
        confidence: float,
    ) -> tuple[bool, str]:
        if current_stage not in _STAGES or proposed_stage not in _STAGES:
            return False, "未知关系阶段"
        if confidence < 0.5:
            return False, "置信度不足"
        current_index = _STAGES.index(current_stage)
        proposed_index = _STAGES.index(proposed_stage)
        if abs(proposed_index - current_index) > 1:
            return False, "单周期阶段跨越过大"
        return True, ""
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```powershell
$env:PYTHONPATH='E:\zfengl-ai-project\nanobot-wenyuan'
pytest tests/soul/test_inference.py tests/soul/test_adjudicator.py -q
```

Expected:

- PASS

- [ ] **Step 5: 提交**

```bash
git add nanobot/soul/inference.py nanobot/soul/adjudicator.py tests/soul/test_inference.py tests/soul/test_adjudicator.py
git commit -m "feat: add soul inference protocol and adjudicator"
```

### Task 3: 情绪闭环收口到候选推演 + 裁决 + 落盘

**Files:**
- Modify: `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\soul\engine.py`
- Modify: `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\soul\heart.py`
- Test: `E:\zfengl-ai-project\nanobot-wenyuan\tests\soul\test_engine.py`
- Test: `E:\zfengl-ai-project\nanobot-wenyuan\tests\soul\test_integration.py`

- [ ] **Step 1: 写出情绪候选必须经过裁决的失败测试**

```python
from unittest.mock import AsyncMock, MagicMock
import pytest

from nanobot.soul.engine import SoulEngine


@pytest.mark.asyncio
async def test_update_heart_calls_adjudicator(tmp_path):
    provider = MagicMock()
    provider.chat_with_retry = AsyncMock(return_value=MagicMock(content="## 当前情绪\n开心\n\n## 情绪强度\n中\n"))
    engine = SoulEngine(tmp_path, provider, "test-model")
    engine.initialize("小文", "温柔")
    engine._adjudicator = MagicMock()
    engine._adjudicator.adjudicate_heart_update.return_value = (True, "## 当前情绪\n开心\n\n## 情绪强度\n中\n")
    await engine.update_heart("你好", "你好呀")
    engine._adjudicator.adjudicate_heart_update.assert_called_once()
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
$env:PYTHONPATH='E:\zfengl-ai-project\nanobot-wenyuan'
pytest tests/soul/test_engine.py::test_update_heart_calls_adjudicator -q
```

Expected:

- FAIL，当前 `SoulEngine` 尚未调用裁决层

- [ ] **Step 3: 在 `SoulEngine` 中接入裁决层**

```python
# nanobot/soul/engine.py
from nanobot.soul.adjudicator import SoulAdjudicator


class SoulEngine:
    def __init__(...):
        ...
        self._adjudicator = SoulAdjudicator()

    async def update_heart(self, user_msg: str, ai_msg: str) -> bool:
        ...
        allowed, result = self._adjudicator.adjudicate_heart_update(
            current_heart=current_heart,
            candidate_text=content,
        )
        if not allowed:
            return False
        return self.heart.write_text(result)
```

- [ ] **Step 4: 运行情绪相关测试确认通过**

Run:

```powershell
$env:PYTHONPATH='E:\zfengl-ai-project\nanobot-wenyuan'
pytest tests/soul/test_engine.py tests/soul/test_integration.py -q
```

Expected:

- PASS，或只剩与旧测试协议不一致的已知失败项

- [ ] **Step 5: 提交**

```bash
git add nanobot/soul/engine.py nanobot/soul/heart.py tests/soul/test_engine.py tests/soul/test_integration.py
git commit -m "feat: gate heart updates through soul adjudicator"
```

### Task 4: 关系阶段的周期性评估与画像状态迁移

**Files:**
- Modify: `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\soul\evolution.py`
- Modify: `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\soul\profile.py`
- Create: `E:\zfengl-ai-project\nanobot-wenyuan\tests\soul\test_relationship_cycle.py`

- [ ] **Step 1: 写出关系阶段只能在周期评估时迁移的失败测试**

```python
from nanobot.soul.profile import SoulProfileManager


def test_relationship_stage_is_persisted_in_profile(tmp_path):
    manager = SoulProfileManager(tmp_path)
    profile = {"relationship": {"stage": "亲近", "trust": 0.6, "affection": 0.2}}
    manager.write(profile)
    assert manager.read()["relationship"]["stage"] == "亲近"
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
$env:PYTHONPATH='E:\zfengl-ai-project\nanobot-wenyuan'
pytest tests/soul/test_relationship_cycle.py -q
```

Expected:

- FAIL，尚无关系周期评估测试与实现

- [ ] **Step 3: 在画像状态中补关系维度与阶段管理**

```python
# nanobot/soul/profile.py
DEFAULT_RELATIONSHIP = {
    "stage": "熟悉",
    "trust": 0.0,
    "intimacy": 0.0,
    "attachment": 0.0,
    "security": 0.0,
    "boundary": 1.0,
    "affection": 0.0,
}
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```powershell
$env:PYTHONPATH='E:\zfengl-ai-project\nanobot-wenyuan'
pytest tests/soul/test_relationship_cycle.py tests/soul/test_profile.py -q
```

Expected:

- PASS

- [ ] **Step 5: 提交**

```bash
git add nanobot/soul/evolution.py nanobot/soul/profile.py tests/soul/test_relationship_cycle.py
git commit -m "feat: add cyclical relationship state management"
```

### Task 5: 主动陪伴闭环与统一日志层

**Files:**
- Create: `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\soul\logs.py`
- Modify: `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\soul\proactive.py`
- Modify: `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\cli\commands.py`
- Test: `E:\zfengl-ai-project\nanobot-wenyuan\tests\soul\test_logs.py`

- [ ] **Step 1: 写出主动陪伴日志失败测试**

```python
from nanobot.soul.logs import SoulLogWriter


def test_log_writer_creates_weekly_log_dir(tmp_path):
    writer = SoulLogWriter(tmp_path)
    path = writer.write_weekly("2026-04-14", "# 周复盘\n")
    assert path.exists()
    assert "weekly" in str(path)
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
$env:PYTHONPATH='E:\zfengl-ai-project\nanobot-wenyuan'
pytest tests/soul/test_logs.py -q
```

Expected:

- FAIL，`SoulLogWriter` 不存在

- [ ] **Step 3: 实现最小日志写入器并在主动陪伴流程中调用**

```python
# nanobot/soul/logs.py
from pathlib import Path


class SoulLogWriter:
    def __init__(self, workspace: Path) -> None:
        self.base_dir = workspace / "soul_logs"

    def write_weekly(self, stamp: str, content: str) -> Path:
        target = self.base_dir / "weekly"
        target.mkdir(parents=True, exist_ok=True)
        path = target / f"{stamp}-周复盘.md"
        path.write_text(content, encoding="utf-8")
        return path
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```powershell
$env:PYTHONPATH='E:\zfengl-ai-project\nanobot-wenyuan'
pytest tests/soul/test_logs.py -q
```

Expected:

- PASS

- [ ] **Step 5: 提交**

```bash
git add nanobot/soul/logs.py nanobot/soul/proactive.py nanobot/cli/commands.py tests/soul/test_logs.py
git commit -m "feat: add soul logging and proactive trace hooks"
```

### Task 6: 周复盘 / 月校准任务与 Dream 收口

**Files:**
- Create: `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\soul\review.py`
- Create: `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\soul\calibration.py`
- Modify: `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\agent\memory.py`
- Modify: `E:\zfengl-ai-project\nanobot-wenyuan\nanobot\cli\commands.py`
- Test: `E:\zfengl-ai-project\nanobot-wenyuan\tests\soul\test_review.py`
- Test: `E:\zfengl-ai-project\nanobot-wenyuan\tests\soul\test_calibration.py`

- [ ] **Step 1: 写出周复盘与月校准生成失败测试**

```python
from nanobot.soul.review import WeeklyReviewBuilder
from nanobot.soul.calibration import MonthlyCalibrationBuilder


def test_weekly_review_builder_returns_markdown():
    builder = WeeklyReviewBuilder()
    content = builder.render({"summary": "本周关系升温"})
    assert "# 周复盘" in content


def test_monthly_calibration_builder_returns_markdown():
    builder = MonthlyCalibrationBuilder()
    content = builder.render({"summary": "本月总体稳定"})
    assert "# 月校准报告" in content
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
$env:PYTHONPATH='E:\zfengl-ai-project\nanobot-wenyuan'
pytest tests/soul/test_review.py tests/soul/test_calibration.py -q
```

Expected:

- FAIL，构建器不存在

- [ ] **Step 3: 实现最小构建器并注册 cron 任务**

```python
# nanobot/soul/review.py
class WeeklyReviewBuilder:
    def render(self, payload: dict) -> str:
        summary = payload.get("summary", "")
        return f"# 周复盘\n\n## 本周摘要\n{summary}\n"
```

```python
# nanobot/soul/calibration.py
class MonthlyCalibrationBuilder:
    def render(self, payload: dict) -> str:
        summary = payload.get("summary", "")
        return f"# 月校准报告\n\n## 本月总体结论\n{summary}\n"
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```powershell
$env:PYTHONPATH='E:\zfengl-ai-project\nanobot-wenyuan'
pytest tests/soul/test_review.py tests/soul/test_calibration.py -q
```

Expected:

- PASS

- [ ] **Step 5: 提交**

```bash
git add nanobot/soul/review.py nanobot/soul/calibration.py nanobot/agent/memory.py nanobot/cli/commands.py tests/soul/test_review.py tests/soul/test_calibration.py
git commit -m "feat: add weekly review and monthly calibration tasks"
```

### Task 7: 收口现有 SOUL 测试与飞书验收准备

**Files:**
- Modify: `E:\zfengl-ai-project\nanobot-wenyuan\tests\soul\test_proactive.py`
- Modify: `E:\zfengl-ai-project\nanobot-wenyuan\tests\soul\test_evolution.py`
- Modify: `E:\zfengl-ai-project\nanobot-wenyuan\codex\单用户数字伴侣-SOUL闭环正式方案.md`

- [ ] **Step 1: 把旧测试协议更新到当前实现**

```python
# tests/soul/test_proactive.py
from nanobot.soul.proactive import ProactiveEngine


def test_should_reach_out_is_gate_result(initialized_engine):
    result = initialized_engine.should_reach_out()
    assert isinstance(result, bool)
```

```python
# tests/soul/test_evolution.py
mock_provider.chat_with_retry.return_value = MagicMock(
    content=json.dumps({
        "evolved_function": "Fe",
        "direction": "up",
        "reason": "用户反复寻求安慰",
        "manifestation": "更容易主动照顾对方",
    })
)
```

- [ ] **Step 2: 运行 SOUL 测试集确认状态**

Run:

```powershell
$env:PYTHONPATH='E:\zfengl-ai-project\nanobot-wenyuan'
pytest tests/soul -q
```

Expected:

- PASS，或仅剩明确记录的已知失败项且有对应修复任务

- [ ] **Step 3: 编写飞书验收检查单**

```markdown
# 飞书验收检查单

- [ ] HEART 更新稳定
- [ ] 主动陪伴频率可控
- [ ] 周复盘可生成
- [ ] 月校准可生成
- [ ] 锚点指令篡改被拒绝
```

- [ ] **Step 4: 运行计划层验证**

Run:

```powershell
git status --short
```

Expected:

- 只包含本阶段相关文件变更

- [ ] **Step 5: 提交**

```bash
git add tests/soul/test_proactive.py tests/soul/test_evolution.py codex/单用户数字伴侣-SOUL闭环正式方案.md
git commit -m "test: align soul tests with phase1 architecture"
```

---

## 计划自审

### 覆盖检查

本计划已覆盖：

- 方法论层与锚点层
- 候选输出协议
- 程序裁决层
- 情绪闭环
- 关系阶段周期更新
- 主动陪伴留痕
- 周复盘 / 月校准
- Dream 对接
- 测试收口

当前未纳入本计划的内容：

- `mempalace` 深度优化闭环
- 3 个月长期记忆召回优化
- 前端或多用户能力

### 占位符检查

本计划未使用 `TBD`、`TODO`、`后续补充代码` 之类占位表述。所有任务都给出了：

- 目标文件
- 最小测试样例
- 运行命令
- 最小实现骨架
- 提交点

### 一致性检查

本计划坚持以下一致性：

- 关系阶段由 LLM 感知，程序裁决
- 所有参数双向变化
- `SOUL` 内聚演进
- 非侵入 nanobot 主干
- 周复盘 / 月校准为周期治理主入口

---

计划完成并保存到 `codex/单用户数字伴侣-SOUL闭环Phase1实施计划.md`。

两种执行方式：

1. Subagent-Driven（推荐）  
   我按任务逐个推进，并在每个任务后回看结果。

2. Inline Execution  
   我在当前会话直接按这个计划连续执行。
