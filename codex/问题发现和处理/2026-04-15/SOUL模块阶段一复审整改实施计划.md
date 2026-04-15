# SOUL 模块阶段一复审整改实施计划

> 归档说明：本文档最初用于任务执行跟踪，当前已同步为实施留档；复选框用于保留执行痕迹，`git commit` 项单独视为可选收尾动作。

**Goal:** 收口 SOUL 一阶段复审新增问题，让周复盘生产闭环真正生效、月校准具备最小治理能力、`SOUL_PROFILE` 与 `SOUL.md` 更新具备一致性提交、运行期 `HEART.md` 裁决与 init 路径同级。

**Architecture:** 保持现有 SOUL 架构不变，只在 `nanobot/soul/*` 和少量 `nanobot/cli/commands.py` 内做最小闭环补强。周复盘和月校准继续复用现有 cron 注册点，重点补齐生产入口、失败回滚、一致性提交和运行期结构治理，不引入新的后台或数据库。

**Tech Stack:** Python 3.11+, Typer, Loguru, Pydantic/Dataclass, pytest

---

## 文件分工

- `nanobot/cli/commands.py`
  - 负责 cron 系统任务的生产接线
  - 本轮需要把 `weekly_review` 切到真正的治理闭环路径
  - 需要让 `monthly_calibration` 在生产入口上使用升级后的 builder
- `nanobot/soul/review.py`
  - 负责周复盘治理闭环
  - 本轮需要补齐“候选关系更新 -> 投影 -> 一致性提交”的原子化提交逻辑
- `nanobot/soul/calibration.py`
  - 负责月校准治理器
  - 本轮需要从占位报告升级为最小可用治理器
- `nanobot/soul/evolution.py`
  - 负责人格演化应用
  - 本轮需要复用和周复盘相同的一致性提交机制
- `nanobot/soul/profile.py`
  - 负责结构化慢状态读写
  - 本轮可能需要提供“候选更新但暂不提交”或“快照/回滚”支持
- `nanobot/soul/projection.py`
  - 负责 `SOUL_PROFILE -> SOUL` 投影
  - 本轮需要支持在一致性提交中以候选 profile 驱动投影，避免先写后投影
- `nanobot/soul/adjudicator.py`
  - 负责运行期 `HEART` 与关系阶段裁决
  - 本轮需要提升运行期 `HEART` 结构校验强度
- `nanobot/soul/heart.py`
  - 负责 `HEART.md` 结构定义与校验能力
  - 本轮需要复用现有 `validate_heart_markdown()` 到运行期路径
- `tests/soul/test_review.py`
  - 验证周复盘治理闭环与失败回滚
- `tests/soul/test_calibration.py`
  - 验证月校准治理器最小输出
- `tests/soul/test_evolution.py`
  - 验证人格演化失败时不会留下 `SOUL_PROFILE/SOUL` 断层
- `tests/soul/test_engine.py`
  - 验证运行期 `HEART` 裁决收紧后的行为
- `tests/cli/test_commands.py`
  - 验证 cron 生产入口接线改动

---

### Task 1: 修正 `weekly_review` 生产调度入口

**Files:**
- Modify: `E:/zfengl-ai-project/nanobot-wenyuan/nanobot/cli/commands.py`
- Modify: `E:/zfengl-ai-project/nanobot-wenyuan/nanobot/soul/review.py`
- Test: `E:/zfengl-ai-project/nanobot-wenyuan/tests/cli/test_commands.py`

- [x] **Step 1: 写失败测试，锁定生产 cron 会调用治理闭环而不是静态周报**

```python
@pytest.mark.asyncio
async def test_gateway_weekly_review_uses_build_cycle(monkeypatch, tmp_path: Path) -> None:
    config_file = _write_instance_config(tmp_path)
    config = Config()
    config.agents.defaults.workspace = str(tmp_path / "config-workspace")
    provider = object()
    seen: dict[str, object] = {}

    class _FakeCron:
        def __init__(self, _store_path: Path) -> None:
            self.on_job = None
            seen["cron"] = self

    class _FakeAgentLoop:
        def __init__(self, *args, **kwargs) -> None:
            self.provider = provider
            self.model = "test-model"

        async def close_mcp(self) -> None:
            return None

        async def run(self) -> None:
            return None

        def stop(self) -> None:
            return None

    class _StopAfterCronSetup:
        def __init__(self, *_args, **_kwargs) -> None:
            raise _StopGatewayError("stop")

    class _FakeWeeklyReviewBuilder:
        def __init__(self, provider=None, model=None, adjudicator=None) -> None:
            seen["provider"] = provider
            seen["model"] = model

        async def build_cycle(self, workspace: Path) -> str:
            seen["workspace"] = workspace
            seen["used_build_cycle"] = True
            return "# 周复盘\n\n## 本周摘要\n治理闭环已执行\n"

        def build(self, workspace: Path) -> str:
            raise AssertionError("static build() should not be used")

    monkeypatch.setattr("nanobot.cron.service.CronService", _FakeCron)
    monkeypatch.setattr("nanobot.agent.loop.AgentLoop", _FakeAgentLoop)
    monkeypatch.setattr("nanobot.channels.manager.ChannelManager", _StopAfterCronSetup)
    monkeypatch.setattr("nanobot.soul.review.WeeklyReviewBuilder", _FakeWeeklyReviewBuilder)
    _patch_cli_command_runtime(
        monkeypatch,
        config,
        message_bus=lambda: object(),
        session_manager=lambda _workspace: object(),
        make_provider=lambda _config: provider,
    )

    result = runner.invoke(app, ["gateway", "--config", str(config_file)])
    assert isinstance(result.exception, _StopGatewayError)

    cron = seen["cron"]
    job = CronJob(id="weekly_review", name="weekly_review", payload=CronPayload(kind="system_event"))
    response = asyncio.run(cron.on_job(job))

    assert response is None
    assert seen["used_build_cycle"] is True
    assert seen["provider"] is provider
    assert seen["model"] == "test-model"
```

- [x] **Step 2: 运行测试并确认失败**

Run: `python -m pytest tests/cli/test_commands.py::test_gateway_weekly_review_uses_build_cycle -q`
Expected: FAIL，当前实现仍调用 `build()` 或没有把 provider/model 传给 `WeeklyReviewBuilder`

- [x] **Step 3: 最小实现生产入口切换**

```python
if job.name == "weekly_review":
    try:
        from datetime import datetime as _dt
        from nanobot.soul.logs import SoulLogWriter
        from nanobot.soul.review import WeeklyReviewBuilder

        builder = WeeklyReviewBuilder(
            provider=provider,
            model=agent.model,
        )
        content = await builder.build_cycle(config.workspace_path)
        SoulLogWriter(config.workspace_path).write_weekly(
            _dt.now().strftime("%Y-%m-%d"),
            content,
        )
        logger.info("Soul weekly review completed")
    except Exception:
        logger.exception("Soul weekly review failed")
    return None
```

- [x] **Step 4: 运行测试并确认通过**

Run: `python -m pytest tests/cli/test_commands.py::test_gateway_weekly_review_uses_build_cycle -q`
Expected: PASS

- [ ] **Step 5: 可选收尾动作 - 提交**

```bash
git add nanobot/cli/commands.py tests/cli/test_commands.py
git commit -m "fix: route weekly review cron through governance cycle"
```

---

### Task 2: 为周复盘与演化补齐一致性提交

**Files:**
- Modify: `E:/zfengl-ai-project/nanobot-wenyuan/nanobot/soul/profile.py`
- Modify: `E:/zfengl-ai-project/nanobot-wenyuan/nanobot/soul/review.py`
- Modify: `E:/zfengl-ai-project/nanobot-wenyuan/nanobot/soul/evolution.py`
- Modify: `E:/zfengl-ai-project/nanobot-wenyuan/nanobot/soul/projection.py`
- Test: `E:/zfengl-ai-project/nanobot-wenyuan/tests/soul/test_review.py`
- Test: `E:/zfengl-ai-project/nanobot-wenyuan/tests/soul/test_evolution.py`

- [x] **Step 1: 写失败测试，锁定周复盘投影失败时不能留下断层**

```python
@pytest.mark.asyncio
async def test_weekly_review_cycle_rolls_back_profile_when_projection_fails(tmp_path):
    from nanobot.soul.heart import HeartManager

    HeartManager(tmp_path).initialize("小文", "温柔")
    SoulProfileManager(tmp_path).write({
        "personality": {"Fi": 0.8},
        "relationship": {
            "stage": "熟悉",
            "trust": 0.1,
            "intimacy": 0.0,
            "attachment": 0.0,
            "security": 0.1,
            "boundary": 0.9,
            "affection": 0.0,
        },
        "companionship": {"empathy_fit": 0.2},
    })
    (tmp_path / "SOUL.md").write_text(
        "# 性格\n\n稳定画像。\n\n# 初始关系\n\n仍在慢慢靠近。\n",
        encoding="utf-8",
    )
    provider = MagicMock()
    provider.chat_with_retry = AsyncMock(side_effect=[
        MagicMock(
            content='{"current_stage_assessment":"熟悉","proposed_stage":"亲近","direction":"up","evidence_summary":"证据充分","dimension_changes":{"trust":0.2},"personality_influence":"Fi高","risk_flags":[],"confidence":0.8}'
        ),
        MagicMock(
            content="# 性格\n\n{\"bad\": true}\n\n# 初始关系\n\nrelationship.stage=亲近"
        ),
    ])

    builder = WeeklyReviewBuilder(provider=provider, model="test-model")
    content = await builder.build_cycle(tmp_path)

    profile = SoulProfileManager(tmp_path).read()
    assert profile["relationship"]["stage"] == "熟悉"
    assert "证据充分" not in content
    assert "稳定画像" in (tmp_path / "SOUL.md").read_text(encoding="utf-8")
```

- [x] **Step 2: 写失败测试，锁定人格演化投影失败时不能留下断层**

```python
@pytest.mark.asyncio
async def test_apply_evolution_rolls_back_profile_when_projection_fails(engine, mock_provider, workspace):
    from nanobot.soul.profile import SoulProfileManager

    original = FunctionProfile().to_json()
    SoulProfileManager(workspace).write({
        "personality": original,
        "relationship": {
            "stage": "熟悉",
            "trust": 0.1,
            "intimacy": 0.0,
            "attachment": 0.0,
            "security": 0.1,
            "boundary": 0.9,
            "affection": 0.0,
        },
        "companionship": {
            "empathy_fit": 0.2,
            "memory_fit": 0.0,
            "naturalness": 0.2,
            "initiative_quality": 0.0,
            "scene_awareness": 0.1,
            "boundary_expression": 0.9,
        },
    })
    (workspace / "SOUL.md").write_text("# 性格\n\n原始画像。\n\n# 初始关系\n\n原始关系。\n", encoding="utf-8")
    mock_provider.chat_with_retry.return_value = MagicMock(
        content="# 性格\n\n{\"bad\": true}\n\n# 初始关系\n\nrelationship.stage=熟悉"
    )

    profile = FunctionProfile(dict(original))
    profile.apply_change("Fe", "up", "测试")
    await engine.apply_evolution({
        "reason": "测试",
        "changes": {"Fe": {"delta": 0.05, "reason": "测试"}},
        "profile": profile,
    })

    saved = SoulProfileManager(workspace).read()
    assert saved["personality"] == original
    assert "原始画像" in (workspace / "SOUL.md").read_text(encoding="utf-8")
```

- [x] **Step 3: 运行测试并确认失败**

Run: `python -m pytest tests/soul/test_review.py::test_weekly_review_cycle_rolls_back_profile_when_projection_fails tests/soul/test_evolution.py::test_apply_evolution_rolls_back_profile_when_projection_fails -q`
Expected: FAIL，当前实现会留下 `SOUL_PROFILE` 已更新但 `SOUL.md` 未更新的断层

- [x] **Step 4: 为 `SoulProfileManager` 增加快照/候选提交辅助接口**

```python
class SoulProfileManager:
    ...
    def snapshot(self) -> dict:
        return self.read()

    def replace(self, profile: dict) -> dict:
        self.write(profile)
        return profile

    def apply_relationship_candidate(
        self,
        *,
        current_profile: dict,
        stage: str,
        dimension_deltas: dict[str, float],
    ) -> dict:
        next_profile = build_default_profile()
        next_profile.update(current_profile)
        relationship = build_default_profile()["relationship"]
        relationship.update(current_profile.get("relationship", {}))
        relationship["stage"] = stage
        for name, delta in dimension_deltas.items():
            if name not in RELATIONSHIP_DIMENSIONS:
                continue
            current_value = float(relationship.get(name, 0.0))
            relationship[name] = max(0.0, min(1.0, current_value + float(delta)))
        next_profile["relationship"] = relationship
        return next_profile
```

- [x] **Step 5: 为 `project_soul_from_profile()` 增加候选 profile 输入**

```python
async def project_soul_from_profile(
    workspace: Path,
    *,
    provider,
    model: str,
    max_attempts: int = 2,
    trigger: str = "runtime",
    profile_override: dict | None = None,
) -> str:
    ...
    profile = profile_override if profile_override is not None else SoulProfileManager(workspace).read()
```

- [x] **Step 6: 用两阶段提交修正 `WeeklyReviewBuilder.build_cycle()`**

```python
current_profile = profile_mgr.snapshot()
candidate_profile = profile_mgr.apply_relationship_candidate(
    current_profile=current_profile,
    stage=candidate.proposed_stage,
    dimension_deltas=candidate.dimension_changes,
)
try:
    projected = await project_soul_from_profile(
        workspace,
        provider=self.provider,
        model=self.model,
        trigger="weekly_review",
        profile_override=candidate_profile,
    )
except SoulProjectionError as exc:
    logger.warning("WeeklyReviewBuilder: SOUL projection skipped: {}", exc)
else:
    profile_mgr.replace(candidate_profile)
    current_stage = candidate_profile.get("relationship", {}).get("stage", current_stage)
    summary = candidate.evidence_summary or summary
```

- [x] **Step 7: 用同一策略修正 `EvolutionEngine.apply_evolution()`**

```python
profile_mgr = SoulProfileManager(self.workspace)
current_profile = profile_mgr.snapshot()
candidate_profile = dict(current_profile)
candidate_profile["personality"] = profile.to_json()
try:
    await project_soul_from_profile(
        self.workspace,
        provider=self.provider,
        model=self.model,
        trigger="evolution",
        profile_override=candidate_profile,
    )
except SoulProjectionError as exc:
    logger.warning("EvolutionEngine: SOUL projection skipped: {}", exc)
    return
profile_mgr.replace(candidate_profile)
```

- [x] **Step 8: 运行测试并确认通过**

Run: `python -m pytest tests/soul/test_review.py tests/soul/test_evolution.py -q`
Expected: PASS

- [ ] **Step 9: 可选收尾动作 - 提交**

```bash
git add nanobot/soul/profile.py nanobot/soul/projection.py nanobot/soul/review.py nanobot/soul/evolution.py tests/soul/test_review.py tests/soul/test_evolution.py
git commit -m "fix: keep soul profile and projection in sync"
```

---

### Task 3: 将月校准升级为最小可用治理器

**Files:**
- Modify: `E:/zfengl-ai-project/nanobot-wenyuan/nanobot/soul/calibration.py`
- Modify: `E:/zfengl-ai-project/nanobot-wenyuan/tests/soul/test_calibration.py`
- Test: `E:/zfengl-ai-project/nanobot-wenyuan/tests/cli/test_commands.py`

- [x] **Step 1: 写失败测试，锁定月校准输出必须包含治理字段**

```python
def test_monthly_calibration_builder_outputs_governance_sections(tmp_path):
    (tmp_path / "CORE_ANCHOR.md").write_text("# 核心锚点\n\n- 不无底线顺从\n", encoding="utf-8")
    (tmp_path / "SOUL_METHOD.md").write_text("# SOUL 方法论\n\n- 荣格八维\n", encoding="utf-8")
    (tmp_path / "SOUL.md").write_text("# 性格\n\n稳定。\n\n# 初始关系\n\n克制。\n", encoding="utf-8")
    (tmp_path / "HEART.md").write_text(
        "## 当前情绪\n平静\n\n## 情绪强度\n低到中\n\n## 关系状态\n克制\n\n## 性格表现\n稳定\n\n## 情感脉络\n（暂无）\n\n## 情绪趋势\n尚在形成\n\n## 当前渴望\n观察\n",
        encoding="utf-8",
    )
    SoulProfileManager(tmp_path).write({
        "personality": {"Fi": 0.8},
        "relationship": {"stage": "熟悉", "trust": 0.2, "intimacy": 0.1, "attachment": 0.0, "security": 0.2, "boundary": 0.9, "affection": 0.0},
        "companionship": {"empathy_fit": 0.2},
    })
    builder = MonthlyCalibrationBuilder()

    content = builder.build(tmp_path)

    assert "## 锚点一致性" in content
    assert "## 关系演化校验" in content
    assert "## 风险与偏移点" in content
    assert "## 建议动作" in content
```

- [x] **Step 2: 运行测试并确认失败**

Run: `python -m pytest tests/soul/test_calibration.py::test_monthly_calibration_builder_outputs_governance_sections -q`
Expected: FAIL，当前输出仍只有占位段落

- [x] **Step 3: 写最小实现，不接入复杂 LLM，只做规则化治理摘要**

```python
def build(self, workspace: Path) -> str:
    anchor_text = AnchorManager(workspace).read_text()
    soul_text = _read_optional(workspace / "SOUL.md")
    heart_text = _read_optional(workspace / "HEART.md")
    profile = SoulProfileManager(workspace).read()
    stage = profile.get("relationship", {}).get("stage", "还不认识")
    weekly_excerpt = self._recent_weekly_excerpt(workspace)
    anchor_state = "已读取核心锚点" if anchor_text else "未发现核心锚点文件"
    relationship_check = f"当前关系阶段为 {stage}，需结合周复盘继续观察是否存在异常跳变。"
    risks = "暂未发现明显越界，但仍需关注 SOUL/PROFILE/HEART 是否长期一致。"
    actions = "- 保留：当前锚点与阶段状态\n- 观察：关系变化与热状态波动\n- 人工复核：若出现连续异常跳变"
    return (
        "# 月校准报告\n\n"
        f"## 本月总体结论\n本月已完成最小校准，后续可继续增强。\n\n"
        f"## 锚点一致性\n{anchor_state}\n\n"
        f"## 关系演化校验\n{relationship_check}\n\n"
        f"## 风险与偏移点\n{risks}\n\n"
        f"## 建议动作\n{actions}\n\n"
        f"## 近期周复盘摘要\n{weekly_excerpt or '（暂无）'}\n"
    )
```

- [x] **Step 4: 为 cron 路径补一条最小接线验证**

```python
def test_gateway_monthly_calibration_writes_governance_report(...):
    ...
    assert "## 建议动作" in written_content
```

- [x] **Step 5: 运行测试并确认通过**

Run: `python -m pytest tests/soul/test_calibration.py tests/cli/test_commands.py -q`
Expected: PASS

- [ ] **Step 6: 可选收尾动作 - 提交**

```bash
git add nanobot/soul/calibration.py tests/soul/test_calibration.py tests/cli/test_commands.py
git commit -m "feat: add minimal monthly calibration governance"
```

---

### Task 4: 提升运行期 `HEART.md` 裁决强度

**Files:**
- Modify: `E:/zfengl-ai-project/nanobot-wenyuan/nanobot/soul/adjudicator.py`
- Modify: `E:/zfengl-ai-project/nanobot-wenyuan/nanobot/soul/engine.py`
- Test: `E:/zfengl-ai-project/nanobot-wenyuan/tests/soul/test_engine.py`

- [x] **Step 1: 写失败测试，锁定运行期 HEART 缺章节时必须拒绝**

```python
@pytest.mark.asyncio
async def test_update_heart_rejects_incomplete_heart_markdown(engine, mock_provider, workspace):
    from nanobot.soul.heart import HeartManager

    HeartManager(workspace).initialize("小文", "温柔")
    mock_provider.chat_with_retry.return_value = MagicMock(
        content="## 当前情绪\n有点开心\n\n## 情绪强度\n中\n"
    )

    result = await engine.update_heart("你好", "我也在")

    assert result is False
    saved = (workspace / "HEART.md").read_text(encoding="utf-8")
    assert "当前渴望" in saved
```

- [x] **Step 2: 运行测试并确认失败**

Run: `python -m pytest tests/soul/test_engine.py::test_update_heart_rejects_incomplete_heart_markdown -q`
Expected: FAIL，当前运行期只检查有无 `## `

- [x] **Step 3: 复用 `validate_heart_markdown()` 提升裁决**

```python
from nanobot.soul.heart import validate_heart_markdown

def adjudicate_heart_update(
    self,
    current_heart: str,
    candidate_text: str,
) -> tuple[bool, str]:
    error = validate_heart_markdown(candidate_text)
    if error:
        return False, current_heart
    return True, candidate_text
```

- [x] **Step 4: 运行测试并确认通过**

Run: `python -m pytest tests/soul/test_engine.py -q`
Expected: PASS

- [ ] **Step 5: 可选收尾动作 - 提交**

```bash
git add nanobot/soul/adjudicator.py nanobot/soul/engine.py tests/soul/test_engine.py
git commit -m "fix: harden runtime heart adjudication"
```

---

### Task 5: 全量回归并同步文档状态

**Files:**
- Modify: `E:/zfengl-ai-project/nanobot-wenyuan/codex/问题发现和处理/2026-04-15/SOUL模块阶段一复审问题清单.md`
- Modify: `E:/zfengl-ai-project/nanobot-wenyuan/codex/问题发现和处理/2026-04-15/SOUL模块阶段一复审整改方案.md`
- Modify: `E:/zfengl-ai-project/nanobot-wenyuan/codex/问题发现和处理/2026-04-15/SOUL模块阶段一复审整改实施计划.md`

- [x] **Step 1: 运行 SOUL 相关全量回归**

Run: `python -m pytest tests/soul tests/cli/test_commands.py tests/agent/test_context_prompt_cache.py tests/agent/test_heartbeat_service.py -q`
Expected: `PASS`，总测试数上升，但全部通过

- [x] **Step 2: 更新问题清单状态**

```markdown
- 已处理：
  - production `weekly_review` 已接入治理闭环
  - `monthly_calibration` 已升级为最小治理器
  - review / evolution 已统一一致性提交
  - 运行期 `HEART` 裁决已提升到与 init 同级
```

- [x] **Step 3: 更新整改方案中的落地进展**

```markdown
- `weekly_review` 生产 cron 已接入 `build_cycle()`
- `monthly_calibration` 已具备最小治理输出
- `SOUL_PROFILE -> SOUL` 的失败路径断层已收口
- 运行期 `HEART` 裁决已复用结构校验
```

- [ ] **Step 4: 可选收尾动作 - 提交**

```bash
git add codex/问题发现和处理/2026-04-15/SOUL模块阶段一复审问题清单.md codex/问题发现和处理/2026-04-15/SOUL模块阶段一复审整改方案.md codex/问题发现和处理/2026-04-15/SOUL模块阶段一复审整改实施计划.md
git commit -m "docs: update soul phase1 review remediation status"
```

---

## 自检

### 覆盖检查

- 问题 1：已由 Task 1 覆盖
- 问题 2：已由 Task 3 覆盖
- 问题 3 / 4：已由 Task 2 覆盖
- 问题 5：已由 Task 4 覆盖

### 占位检查

- 计划中没有使用 `TBD / TODO / 后续补充`
- 每个任务均包含测试、实现、验证和提交步骤

### 类型与接口检查

- `WeeklyReviewBuilder.build_cycle()` 作为生产入口
- `project_soul_from_profile(..., profile_override=...)` 作为一致性提交基础接口
- `validate_heart_markdown()` 作为 init / runtime 共用结构校验

---

## 执行结果（2026-04-15 更新）

- 已完成：
  - Task 1：`weekly_review` 生产调度入口已切到治理闭环，并完成复审
  - Task 2：review / evolution 一致性提交已落地，并完成复审
  - Task 3：月校准最小治理器已落地，并完成复审
  - Task 4：运行期 `HEART.md` 裁决已提升到与 init 同级，并完成复审
  - Task 5：全量回归与文档状态同步已完成
- 全量回归：
  - 执行命令：`python -m pytest tests/soul tests/cli/test_commands.py tests/agent/test_context_prompt_cache.py tests/agent/test_heartbeat_service.py -q`
  - 执行结果：`283 passed, 3 warnings`
- 当前未执行项：
  - 各 Task 中的 `git commit` 步骤尚未执行，保留为待用户确认后的独立动作
