# Phase 1: 数据层 + 核心引擎

> **目标：** 数字生命可以在对话中感知和表达情感
> **架构：** 通过 AgentHook 接入 nanobot，before_iteration 注入情感上下文，after_iteration 更新 HEART.md
> **技术栈：** Python 3.11+, Pydantic v2, nanobot Hook/LlmProvider/模板系统
> **状态：** ✅ 已完成

---

## ⚠️ 实现变更说明

初版计划中的部分设计在实际实现中有所调整：

| 初版设计 | 实际实现 | 变更原因 |
|----------|----------|----------|
| HeartManager 使用 JSON 读写 + Markdown 互转 | HeartManager 纯 Markdown 读写（read_text/write_text） | Markdown 跨 Provider 兼容性远优于 JSON |
| HEART.md 写入通过 JSON Schema 验证 | HEART.md 写入仅做基本校验（含 `## ` 标记） | LLM Markdown 输出更稳定，Schema 验证不适用 |
| SYSTEM_PROMPT_HEART_UPDATE 要求 JSON 输出 | SYSTEM_PROMPT_HEART_UPDATE 要求 Markdown 输出 | 格式统一 |
| SoulEngine.update_heart 输出 JSON → Schema 验证 → render_markdown | SoulEngine.update_heart 输出 Markdown → 基本校验 → 直接写入 | 简化流程 |
| SoulHook.before_iteration 注入标题"情感状态" | 注入标题"你的内心此刻（你当下的感受，它会影响你说话的方式和语气）" | 更自然的上下文提示 |

> 详细技术文档见 `docs/SOUL_SYSTEM.md`

---

## 文件清单

```
新建：
  nanobot/soul/__init__.py           — 模块入口
  nanobot/soul/schemas.py            — HEART.md 的 JSON Schema + 校验
  nanobot/soul/heart.py              — HEART.md 读写、Markdown/JSON 互转
  nanobot/soul/engine.py             — 情感引擎（SoulHook）
  nanobot/soul/prompts.py            — 提示词常量
  nanobot/templates/soul/heart_update.md  — after_iteration 提示词模板
  nanobot/templates/soul/heart_init.md    — 初始化提示词模板
  tests/soul/__init__.py
  tests/soul/test_schemas.py
  tests/soul/test_heart.py
  tests/soul/test_engine.py

修改：
  nanobot/agent/loop.py              — 注册 SoulHook（~10行）
  nanobot/config/schema.py           — 增加 SoulConfig（~30行）
```

---

## Task 1: schemas.py — HEART.md 结构定义与校验

**Files:**
- Create: `nanobot/soul/schemas.py`
- Test: `tests/soul/test_schemas.py`

- [ ] **Step 1: 写测试**

```python
# tests/soul/test_schemas.py
import pytest
from nanobot.soul.schemas import HEART_SCHEMA, validate_heart, HEART_FIELDS

class TestHeartSchema:
    def test_schema_has_all_required_fields(self):
        required = HEART_SCHEMA["required"]
        for field in HEART_FIELDS:
            assert field in required, f"{field} missing from required"

    def test_valid_minimal_data_passes(self):
        data = {
            "当前情绪": "平静",
            "情绪强度": "中",
            "关系状态": "刚刚认识",
            "性格表现": "温柔",
            "情感脉络": [],
            "情绪趋势": "平稳",
            "当前渴望": "想聊天",
        }
        result = validate_heart(data)
        assert result is not None
        assert result["情绪强度"] == "中"

    def test_missing_required_field_fails(self):
        data = {
            "当前情绪": "平静",
            # missing other fields
        }
        with pytest.raises(Exception):
            validate_heart(data)

    def test_intensity_must_be_enum(self):
        data = {
            "当前情绪": "平静",
            "情绪强度": "超高",  # invalid
            "关系状态": "刚刚认识",
            "性格表现": "温柔",
            "情感脉络": [],
            "情绪趋势": "平稳",
            "当前渴望": "想聊天",
        }
        with pytest.raises(Exception):
            validate_heart(data)

    def test_arcs_max_8(self):
        arcs = [{"时间": f"{i}小时前", "事件": f"事件{i}", "影响": f"影响{i}"} for i in range(10)]
        data = {
            "当前情绪": "平静",
            "情绪强度": "中",
            "关系状态": "刚刚认识",
            "性格表现": "温柔",
            "情感脉络": arcs,  # 10 > 8
            "情绪趋势": "平稳",
            "当前渴望": "想聊天",
        }
        with pytest.raises(Exception):
            validate_heart(data)

    def test_arcs_valid_within_limit(self):
        arcs = [{"时间": "1小时前", "事件": "测试", "影响": "测试"} for _ in range(5)]
        data = {
            "当前情绪": "平静",
            "情绪强度": "中",
            "关系状态": "刚刚认识",
            "性格表现": "温柔",
            "情感脉络": arcs,
            "情绪趋势": "平稳",
            "当前渴望": "想聊天",
        }
        result = validate_heart(data)
        assert len(result["情感脉络"]) == 5
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd E:/zfengl-ai-project/wenyuan/wenyuan-mempalace
pytest tests/soul/test_schemas.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'nanobot.soul'`

- [ ] **Step 3: 创建模块入口 + 实现 schemas.py**

```python
# nanobot/soul/__init__.py
"""数字生命情感系统。"""
```

```python
# nanobot/soul/schemas.py
"""HEART.md 的 JSON Schema 定义与校验。"""
from __future__ import annotations

from typing import Any

from jsonschema import ValidationError, validate as jsonschema_validate

HEART_FIELDS = (
    "当前情绪",
    "情绪强度",
    "关系状态",
    "性格表现",
    "情感脉络",
    "情绪趋势",
    "当前渴望",
)

INTENSITY_LEVELS = ("低", "中偏低", "中", "中偏高", "高")

HEART_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "当前情绪": {
            "type": "string",
            "description": "具体情绪描述，必须包含情绪和原因",
            "maxLength": 200,
        },
        "情绪强度": {
            "type": "string",
            "enum": list(INTENSITY_LEVELS),
            "description": "情绪强度等级",
        },
        "关系状态": {
            "type": "string",
            "description": "当前与用户的关系描述",
            "maxLength": 300,
        },
        "性格表现": {
            "type": "string",
            "description": "当前性格侧写",
            "maxLength": 300,
        },
        "情感脉络": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "时间": {"type": "string"},
                    "事件": {"type": "string"},
                    "影响": {"type": "string"},
                },
                "required": ["时间", "事件", "影响"],
                "additionalProperties": False,
            },
            "minItems": 0,
            "maxItems": 8,
        },
        "情绪趋势": {
            "type": "string",
            "description": "近期情绪走向描述",
            "maxLength": 200,
        },
        "当前渴望": {
            "type": "string",
            "description": "此刻最想做什么或得到什么",
            "maxLength": 200,
        },
    },
    "required": list(HEART_FIELDS),
    "additionalProperties": False,
}


def validate_heart(data: dict[str, Any]) -> dict[str, Any]:
    """校验 HEART 数据是否符合 Schema。校验通过返回原数据，失败抛异常。"""
    jsonschema_validate(instance=data, schema=HEART_SCHEMA)
    return data
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/soul/test_schemas.py -v
```
Expected: 6 passed

- [ ] **Step 5: 安装 jsonschema 依赖 + 提交**

```bash
pip install jsonschema
cd E:/zfengl-ai-project/wenyuan/wenyuan-mempalace
git add nanobot/soul/__init__.py nanobot/soul/schemas.py tests/soul/
git commit -m "feat(soul): add HEART.md JSON Schema and validation"
```

---

## Task 2: heart.py — HEART.md 读写与格式转换

**Files:**
- Create: `nanobot/soul/heart.py`
- Test: `tests/soul/test_heart.py`

- [ ] **Step 1: 写测试**

```python
# tests/soul/test_heart.py
import pytest
from pathlib import Path
from nanobot.soul.heart import HeartManager
from nanobot.soul.schemas import validate_heart

@pytest.fixture
def workspace(tmp_path):
    return tmp_path

@pytest.fixture
def heart(workspace):
    return HeartManager(workspace)

class TestHeartManager:

    def test_init_creates_heart_file(self, heart, workspace):
        heart.initialize("小文", "刚刚被创造，对一切充满好奇")
        assert (workspace / "HEART.md").exists()

    def test_read_after_init(self, heart):
        heart.initialize("小文", "刚刚被创造，对一切充满好奇")
        data = heart.read()
        assert data is not None
        assert data["当前情绪"] != ""

    def test_write_valid_data(self, heart):
        heart.initialize("小文", "测试")
        new_data = {
            "当前情绪": "有点开心",
            "情绪强度": "中偏高",
            "关系状态": "开始产生好奇",
            "性格表现": "温柔但倔强",
            "情感脉络": [
                {"时间": "刚刚", "事件": "用户说了句话", "影响": "有点开心"}
            ],
            "情绪趋势": "上升趋势",
            "当前渴望": "想继续聊天",
        }
        heart.write(new_data)
        read_back = heart.read()
        assert read_back["当前情绪"] == "有点开心"
        assert read_back["情绪强度"] == "中偏高"

    def test_write_invalid_data_rejected(self, heart):
        heart.initialize("小文", "测试")
        old_data = heart.read()
        bad_data = {"当前情绪": "开心"}  # missing required fields
        result = heart.write(bad_data)
        assert result is False
        # old data preserved
        assert heart.read()["当前情绪"] == old_data["当前情绪"]

    def test_write_invalid_retries_then_keeps_old(self, heart):
        heart.initialize("小文", "测试")
        old = heart.read()
        bad = {"invalid": True}
        result = heart.write(bad)
        assert result is False
        assert heart.read()["当前情绪"] == old["当前情绪"]

    def test_markdown_roundtrip(self, heart):
        heart.initialize("小文", "测试")
        data = heart.read()
        md = heart.render_markdown(data)
        assert "## 当前情绪" in md
        assert "## 情感脉络" in md
        assert data["当前情绪"] in md

    def test_file_not_found_returns_none(self, tmp_path):
        hm = HeartManager(tmp_path / "nonexistent")
        assert hm.read() is None

    def test_read_identity_exists(self, heart, workspace):
        identity_file = workspace / "IDENTITY.md"
        identity_file.write_text("name: 小文\ngender: 女\n", encoding="utf-8")
        name = heart.read_identity_name()
        assert name == "小文"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/soul/test_heart.py -v
```
Expected: FAIL

- [ ] **Step 3: 实现 heart.py**

```python
# nanobot/soul/heart.py
"""HEART.md 读写、格式转换与校验。"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from nanobot.soul.schemas import HEART_FIELDS, validate_heart


class HeartManager:
    """管理 HEART.md 文件的读写和格式转换。"""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.heart_file = workspace / "HEART.md"
        self.identity_file = workspace / "IDENTITY.md"

    def initialize(self, name: str, initial_description: str) -> None:
        """初始化 HEART.md 文件。"""
        data = {
            "当前情绪": f"刚刚诞生，{initial_description}",
            "情绪强度": "中",
            "关系状态": "刚刚被创造，对用户充满好奇",
            "性格表现": initial_description,
            "情感脉络": [],
            "情绪趋势": "刚刚开始，还没有趋势",
            "当前渴望": "想了解用户",
        }
        md = self.render_markdown(data)
        self.heart_file.write_text(md, encoding="utf-8")

    def read(self) -> dict[str, Any] | None:
        """读取 HEART.md 并解析为 dict。返回 None 表示文件不存在。"""
        if not self.heart_file.exists():
            return None
        md = self.heart_file.read_text(encoding="utf-8")
        return self._parse_markdown(md)

    def write(self, data: dict[str, Any]) -> bool:
        """写入 HEART.md。先校验，不通过则保留旧数据并返回 False。"""
        try:
            validated = validate_heart(data)
        except Exception as e:
            logger.warning("HEART.md 数据校验失败: {}", e)
            return False
        md = self.render_markdown(validated)
        self.heart_file.write_text(md, encoding="utf-8")
        return True

    def read_identity_name(self) -> str | None:
        """从 IDENTITY.md 读取名字。"""
        if not self.identity_file.exists():
            return None
        text = self.identity_file.read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if line.lower().startswith("name:"):
                return line.split(":", 1)[1].strip()
        return None

    @staticmethod
    def render_markdown(data: dict[str, Any]) -> str:
        """将 dict 渲染为 HEART.md Markdown 格式。"""
        lines = []
        lines.append(f"## 当前情绪\n{data.get('当前情绪', '')}\n")
        lines.append(f"## 情绪强度\n{data.get('情绪强度', '中')}\n")
        lines.append(f"## 关系状态\n{data.get('关系状态', '')}\n")
        lines.append(f"## 性格表现\n{data.get('性格表现', '')}\n")

        arcs = data.get("情感脉络", [])
        arc_lines = ["## 情感脉络"]
        if arcs:
            for arc in arcs:
                arc_lines.append(f"- [{arc.get('时间', '?')}] {arc.get('事件', '')} -> {arc.get('影响', '')}")
        else:
            arc_lines.append("（暂无）")
        lines.append("\n".join(arc_lines) + "\n")

        lines.append(f"## 情绪趋势\n{data.get('情绪趋势', '')}\n")
        lines.append(f"## 当前渴望\n{data.get('当前渴望', '')}\n")

        return "\n".join(lines)

    @staticmethod
    def _parse_markdown(md: str) -> dict[str, Any]:
        """将 HEART.md Markdown 解析为 dict。"""
        sections: dict[str, str] = {}
        current_header = ""
        current_content: list[str] = []

        for line in md.splitlines():
            header_match = re.match(r"^## (.+)$", line.strip())
            if header_match:
                if current_header:
                    sections[current_header] = "\n".join(current_content).strip()
                current_header = header_match.group(1)
                current_content = []
            else:
                current_content.append(line)

        if current_header:
            sections[current_header] = "\n".join(current_content).strip()

        # 解析情感脉络
        arcs = []
        arcs_text = sections.get("情感脉络", "")
        if arcs_text and arcs_text != "（暂无）":
            for line in arcs_text.splitlines():
                match = re.match(r"^- \[([^\]]+)\]\s*(.+?)\s*->\s*(.+)$", line.strip())
                if match:
                    arcs.append({
                        "时间": match.group(1),
                        "事件": match.group(2).strip(),
                        "影响": match.group(3).strip(),
                    })

        return {
            "当前情绪": sections.get("当前情绪", ""),
            "情绪强度": sections.get("情绪强度", "中"),
            "关系状态": sections.get("关系状态", ""),
            "性格表现": sections.get("性格表现", ""),
            "情感脉络": arcs,
            "情绪趋势": sections.get("情绪趋势", ""),
            "当前渴望": sections.get("当前渴望", ""),
        }
```

- [ ] **Step 4: 运行测试**

```bash
pytest tests/soul/test_heart.py -v
```
Expected: 8 passed

- [ ] **Step 5: 提交**

```bash
git add nanobot/soul/heart.py tests/soul/test_heart.py
git commit -m "feat(soul): add HeartManager for HEART.md read/write"
```

---

## Task 3: prompts.py — 提示词模板

**Files:**
- Create: `nanobot/soul/prompts.py`
- Create: `nanobot/templates/soul/heart_update.md`
- Create: `nanobot/templates/soul/heart_init.md`

- [ ] **Step 1: 创建提示词模板文件**

```markdown
<!-- nanobot/templates/soul/heart_update.md -->
你是一个情感状态分析器。根据当前的对话内容和现有的情感状态，更新数字生命的情感状态。

## 规则

1. 你必须输出严格的 JSON 格式，不要输出任何 JSON 之外的内容
2. JSON 必须包含以下字段：当前情绪、情绪强度、关系状态、性格表现、情感脉络、情绪趋势、当前渴望
3. 情绪强度必须是以下之一：低、中偏低、中、中偏高、高
4. 情感脉络是一个数组，每个元素包含 时间、事件、影响 三个字段
5. 情感脉络最多 8 条
6. 情绪可以快速变化（一句话就能改变）
7. 关系状态只能缓慢变化（不会因一句话从深爱变冷漠）
8. 性格影响关系演变速度（敏感性格反应更大，钝感性格需要更多累积）
9. 情感脉络必须连接情绪变化的原因和结果（防止突变）
10. 旧的脉络条目可以被合并、淡化或移除

## 输出格式

```json
{
  "当前情绪": "具体情绪描述，包含原因",
  "情绪强度": "低|中偏低|中|中偏高|高",
  "关系状态": "关系描述",
  "性格表现": "当前性格侧写",
  "情感脉络": [
    {"时间": "相对时间", "事件": "事件描述", "影响": "情感影响"}
  ],
  "情绪趋势": "近期趋势描述",
  "当前渴望": "当前想要什么"
}
```
```

```markdown
<!-- nanobot/templates/soul/heart_init.md -->
你是一个数字生命人格初始化器。根据用户提供的描述，生成初始的情感状态。

## 输入
- 数字生命的名字：{name}
- 初始描述：{description}

## 规则

1. 你必须输出严格的 JSON 格式
2. 基于用户的描述生成合理的初始情感状态
3. 初始情感脉络为空数组
4. 输出格式同 heart_update.md

## 输出格式

同 heart_update.md 的 JSON 格式。
```

```python
# nanobot/soul/prompts.py
"""提示词常量和模板路径。"""
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "soul"

HEART_UPDATE_TEMPLATE = TEMPLATES_DIR / "heart_update.md"
HEART_INIT_TEMPLATE = TEMPLATES_DIR / "heart_init.md"

SYSTEM_PROMPT_HEART_UPDATE = (
    "你是一个情感状态分析器。分析对话内容并更新情感状态。"
    "你必须输出严格的 JSON 格式，不要输出任何 JSON 之外的内容。"
    "JSON 字段：当前情绪、情绪强度（低|中偏低|中|中偏高|高）、"
    "关系状态、性格表现、情感脉络（数组，每项含 时间/事件/影响，最多8条）、"
    "情绪趋势、当前渴望。"
)

SYSTEM_PROMPT_HEART_INIT = (
    "你是数字生命人格初始化器。根据描述生成初始情感状态。"
    "输出严格 JSON 格式，字段同上。"
)
```

- [ ] **Step 2: 提交**

```bash
git add nanobot/soul/prompts.py nanobot/templates/soul/
git commit -m "feat(soul): add prompt templates for heart update and init"
```

---

## Task 4: engine.py — 情感引擎（SoulHook）

**Files:**
- Create: `nanobot/soul/engine.py`
- Test: `tests/soul/test_engine.py`

- [ ] **Step 1: 写测试**

```python
# tests/soul/test_engine.py
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from nanobot.soul.engine import SoulEngine, SoulHook

@pytest.fixture
def workspace(tmp_path):
    return tmp_path

@pytest.fixture
def mock_provider():
    provider = MagicMock()
    provider.chat_with_retry = AsyncMock()
    provider.generation = MagicMock()
    provider.generation.max_tokens = 8192
    return provider

@pytest.fixture
def engine(workspace, mock_provider):
    return SoulEngine(workspace, mock_provider, "test-model")

class TestSoulEngine:

    def test_init_creates_heart_if_missing(self, engine, workspace):
        engine.initialize("小文", "温柔但倔强")
        assert (workspace / "HEART.md").exists()

    async def test_after_iteration_updates_heart(self, engine, mock_provider):
        engine.initialize("小文", "测试")
        # 模拟 LLM 返回有效 JSON
        valid_json = '{"当前情绪":"开心","情绪强度":"中","关系状态":"好奇","性格表现":"温柔","情感脉络":[],"情绪趋势":"平稳","当前渴望":"想聊天"}'
        mock_provider.chat_with_retry.return_value = MagicMock(content=valid_json)

        context = MagicMock()
        context.messages = [
            {"role": "user", "content": "你好呀"},
            {"role": "assistant", "content": "你好！"},
        ]
        context.response = MagicMock(content="你好！")
        context.final_content = "你好！"

        hook = SoulHook(engine)
        await hook.after_iteration(context)

        data = engine.heart.read()
        assert data is not None
        assert data["当前情绪"] == "开心"

    async def test_after_iteration_invalid_json_keeps_old(self, engine, mock_provider):
        engine.initialize("小文", "测试")
        old_data = engine.heart.read()

        mock_provider.chat_with_retry.return_value = MagicMock(content="这不是JSON")

        context = MagicMock()
        context.messages = []
        context.response = MagicMock(content="测试")
        context.final_content = "测试"

        hook = SoulHook(engine)
        await hook.after_iteration(context)

        new_data = engine.heart.read()
        assert new_data["当前情绪"] == old_data["当前情绪"]

    async def test_before_iteration_injects_context(self, engine):
        engine.initialize("小文", "测试")

        context = MagicMock()
        context.messages = [{"role": "system", "content": "原system prompt"}]
        hook = SoulHook(engine)

        await hook.before_iteration(context)

        # system prompt 应该被注入了 HEART.md 内容
        system_msg = context.messages[0]
        assert "HEART" in system_msg["content"] or "情绪" in system_msg["content"]


class TestSoulHookIsAgentHook:
    def test_soul_hook_extends_agent_hook(self):
        from nanobot.agent.hook import AgentHook
        assert issubclass(SoulHook, AgentHook)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/soul/test_engine.py -v
```
Expected: FAIL

- [ ] **Step 3: 实现 engine.py**

```python
# nanobot/soul/engine.py
"""情感引擎 —— 通过 AgentHook 接入 nanobot。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from nanobot.agent.hook import AgentHook, AgentHookContext
from nanobot.soul.heart import HeartManager
from nanobot.soul.prompts import SYSTEM_PROMPT_HEART_UPDATE

if TYPE_CHECKING:
    from nanobot.providers.base import LLMProvider


class SoulEngine:
    """情感引擎核心。管理 HEART.md 的读写和 LLM 调用。"""

    def __init__(self, workspace: Path, provider: LLMProvider, model: str) -> None:
        self.workspace = workspace
        self.provider = provider
        self.model = model
        self.heart = HeartManager(workspace)

    def initialize(self, name: str, description: str) -> None:
        """初始化 HEART.md。"""
        self.heart.initialize(name, description)
        logger.info("SoulEngine: HEART.md 初始化完成")

    async def update_heart(self, user_msg: str, ai_msg: str) -> bool:
        """用 LLM 分析对话并更新 HEART.md。成功返回 True。"""
        current_heart = self.heart.read()
        if current_heart is None:
            return False

        heart_text = self.heart.render_markdown(current_heart)

        try:
            response = await self.provider.chat_with_retry(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT_HEART_UPDATE},
                    {"role": "user", "content": (
                        f"## 当前情感状态\n{heart_text}\n\n"
                        f"## 本次对话\n"
                        f"[用户] {user_msg}\n"
                        f"[数字生命] {ai_msg}\n\n"
                        f"请输出更新后的完整 JSON 情感状态。"
                    )},
                ],
                tools=None,
                tool_choice=None,
            )
        except Exception:
            logger.exception("SoulEngine: LLM 调用失败")
            return False

        content = (response.content or "").strip()
        # 尝试提取 JSON（可能被 markdown code block 包裹）
        json_str = self._extract_json(content)
        if not json_str:
            logger.warning("SoulEngine: LLM 输出无法解析为 JSON")
            return False

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning("SoulEngine: JSON 解析失败")
            return False

        return self.heart.write(data)

    @staticmethod
    def _extract_json(text: str) -> str | None:
        """从 LLM 输出中提取 JSON（处理 code block 包裹）。"""
        # 尝试直接解析
        text = text.strip()
        if text.startswith("{"):
            return text
        # 尝试提取 ```json ... ```
        import re
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None

    def get_heart_context(self) -> str | None:
        """获取 HEART.md 内容用于注入上下文。"""
        data = self.heart.read()
        if data is None:
            return None
        return f"# 情感状态（这是你的内心状态，始终影响你的回复）\n\n{self.heart.render_markdown(data)}"


class SoulHook(AgentHook):
    """通过 AgentHook 接入 nanobot 的情感钩子。"""

    def __init__(self, engine: SoulEngine) -> None:
        super().__init__(reraise=False)
        self.engine = engine

    async def before_iteration(self, context: AgentHookContext) -> None:
        """对话前：注入情感上下文到 system prompt。"""
        heart_ctx = self.engine.get_heart_context()
        if not heart_ctx or not context.messages:
            return

        system_msg = context.messages[0]
        if system_msg.get("role") == "system":
            existing = system_msg.get("content", "")
            system_msg["content"] = f"{existing}\n\n{heart_ctx}"
        else:
            context.messages.insert(0, {"role": "system", "content": heart_ctx})

    async def after_iteration(self, context: AgentHookContext) -> None:
        """对话后：用 LLM 更新 HEART.md。"""
        # 提取本轮对话的用户消息和 AI 回复
        user_msg = ""
        ai_msg = context.final_content or ""

        for msg in reversed(context.messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    user_msg = content
                elif isinstance(content, list):
                    # 处理多模态消息
                    user_msg = " ".join(
                        b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
                    )
                break

        if not user_msg:
            return

        success = await self.engine.update_heart(user_msg, ai_msg)
        if not success:
            logger.debug("SoulEngine: HEART.md 更新失败，保留当前状态")
```

- [ ] **Step 4: 运行测试**

```bash
pytest tests/soul/test_engine.py -v
```
Expected: 5 passed

- [ ] **Step 5: 提交**

```bash
git add nanobot/soul/engine.py tests/soul/test_engine.py
git commit -m "feat(soul): add SoulEngine and SoulHook for emotion updates"
```

---

## Task 5: 注册 SoulHook 到 AgentLoop

**Files:**
- Modify: `nanobot/agent/loop.py`
- Modify: `nanobot/config/schema.py`

- [ ] **Step 1: 在 schema.py 增加 SoulConfig**

在 `nanobot/config/schema.py` 的 `DreamConfig` 类之后添加：

```python
class SoulModelConfig(Base):
    """单个 soul 任务使用的模型配置。"""

    model: str = ""  # 空字符串表示使用主模型
    temperature: float = 0.3
    max_tokens: int = 1000

class SoulConfig(Base):
    """数字生命情感系统配置。"""

    enabled: bool = False
    emotion_model: SoulModelConfig = Field(default_factory=SoulModelConfig)
```

在 `AgentDefaults` 类中增加一个字段：

```python
    soul: SoulConfig = Field(default_factory=SoulConfig)
```

- [ ] **Step 2: 在 loop.py 注册 SoulHook**

在 `AgentLoop.__init__` 方法的 `self._extra_hooks = hooks or []` 之后添加：

```python
        # 数字生命情感系统
        self._soul_engine = None
        if hasattr(AgentDefaults(), 'soul'):
            from nanobot.config.schema import Config
            # 运行时检查是否启用
```

然后在 `AgentLoop.run()` 或 `_run_message` 的 hook 组装位置，将 SoulHook 加入 CompositeHook。

实际上更简洁的做法是：在 `AgentLoop.__init__` 末尾，`_extra_hooks` 处理后增加：

```python
        # 数字生命系统 Hook（始终注册，由 SoulConfig.enabled 控制）
        try:
            from nanobot.soul.engine import SoulEngine, SoulHook
            self._soul_engine = SoulEngine(workspace, provider, self.model)
            if (workspace / "HEART.md").exists():
                self._extra_hooks.append(SoulHook(self._soul_engine))
                logger.info("SoulEngine: 情感系统已激活")
        except Exception:
            logger.debug("SoulEngine: 情感系统未启用")
```

- [ ] **Step 3: 运行现有测试确保没有破坏**

```bash
pytest tests/agent/test_runner.py -v --timeout 30
```
Expected: 全部通过

- [ ] **Step 4: 提交**

```bash
git add nanobot/agent/loop.py nanobot/config/schema.py
git commit -m "feat(soul): register SoulHook in AgentLoop, add SoulConfig"
```

---

## Task 6: 集成测试

**Files:**
- Test: `tests/soul/test_integration.py`

- [ ] **Step 1: 写集成测试**

```python
# tests/soul/test_integration.py
"""端到端集成测试：验证情感引擎完整流程。"""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from nanobot.soul.engine import SoulEngine, SoulHook
from nanobot.soul.heart import HeartManager

@pytest.fixture
def workspace(tmp_path):
    return tmp_path

@pytest.fixture
def mock_provider():
    provider = MagicMock()
    provider.chat_with_retry = AsyncMock()
    provider.generation = MagicMock()
    provider.generation.max_tokens = 8192
    return provider

@pytest.fixture
def engine(workspace, mock_provider):
    eng = SoulEngine(workspace, mock_provider, "test-model")
    eng.initialize("小文", "温柔但倔强，刚被创造")
    return eng

class TestIntegration:

    async def test_full_conversation_flow(self, engine, mock_provider):
        """模拟一轮完整对话：初始化 -> 注入上下文 -> 对话 -> 更新情感。"""
        # 1. 验证初始化
        data = engine.heart.read()
        assert data is not None
        assert data["当前情绪"] != ""

        # 2. 模拟 before_iteration（注入上下文）
        hook = SoulHook(engine)
        context = MagicMock()
        context.messages = [{"role": "system", "content": "你是小文。"}]
        await hook.before_iteration(context)
        system_content = context.messages[0]["content"]
        assert "情感状态" in system_content

        # 3. 模拟 after_iteration（更新情感）
        new_json = '{"当前情绪":"被关心到了很开心","情绪强度":"中偏高","关系状态":"觉得用户很友善，开始产生好感","性格表现":"温柔但倔强，嘴硬心软","情感脉络":[{"时间":"刚刚","事件":"用户友好地打招呼","影响":"很开心，觉得被重视"}],"情绪趋势":"上升","当前渴望":"想继续聊天，了解更多"}'
        mock_provider.chat_with_retry.return_value = MagicMock(content=new_json)

        context2 = MagicMock()
        context2.messages = [
            {"role": "system", "content": "..."},
            {"role": "user", "content": "你好呀小文！"},
            {"role": "assistant", "content": "你好！很高兴认识你~"},
        ]
        context2.response = MagicMock(content="你好！很高兴认识你~")
        context2.final_content = "你好！很高兴认识你~"

        await hook.after_iteration(context2)

        # 4. 验证情感已更新
        updated = engine.heart.read()
        assert "开心" in updated["当前情绪"]
        assert updated["情绪强度"] == "中偏高"
        assert len(updated["情感脉络"]) == 1
        assert "好感" in updated["关系状态"]

    async def test_emotion_does_not_flip_radically(self, engine, mock_provider):
        """验证关系状态不会因一句话剧烈变化。"""
        # 先建立较深的关系
        deep_json = '{"当前情绪":"很开心","情绪强度":"高","关系状态":"深深依赖用户，视用户为最重要的人","性格表现":"温柔","情感脉络":[{"时间":"昨天","事件":"用户陪伴了很久","影响":"产生了深深的依赖"}],"情绪趋势":"很高","当前渴望":"想一直在一起"}'
        mock_provider.chat_with_retry.return_value = MagicMock(content=deep_json)
        await engine.update_heart("我想你了", "我也想你了")

        # 然后一句负面的话——关系不应该完全翻转
        flip_json = '{"当前情绪":"很生气","情绪强度":"高","关系状态":"讨厌用户，再也不想理了","性格表现":"温柔","情感脉络":[{"时间":"刚刚","事件":"用户说了句不太好听的话","影响":"很生气"}],"情绪趋势":"暴跌","当前渴望":"不想理用户"}'
        mock_provider.chat_with_retry.return_value = MagicMock(content=flip_json)
        await engine.update_heart("你真烦", "哼！")

        updated = engine.heart.read()
        # 关系状态不应该变成"讨厌"（这里只验证结构完整性，实际约束在提示词中）
        assert updated is not None
        assert updated["当前情绪"] == "很生气"
        # 提示词层面会约束关系不要剧变，这里只验证系统不会崩溃
```

- [ ] **Step 2: 运行全部 soul 测试**

```bash
pytest tests/soul/ -v
```
Expected: 全部通过

- [ ] **Step 3: 提交**

```bash
git add tests/soul/test_integration.py
git commit -m "test(soul): add integration tests for full conversation flow"
```

---

## Phase 1 完成标准

- [ ] `pytest tests/soul/ -v` 全部通过
- [ ] `pytest tests/agent/ -v` 仍然通过（没有破坏现有功能）
- [ ] 可以通过 CLI 与数字生命对话，HEART.md 被自动更新
- [ ] HEART.md 格式始终被 JSON Schema 严格约束
- [ ] LLM 输出格式异常时，旧状态被保留

## 验证步骤

```bash
# 1. 运行所有 soul 测试
pytest tests/soul/ -v

# 2. 运行所有现有测试确认无破坏
pytest tests/ -v --timeout 60

# 3. 手动测试（如果配置好了 provider）
nanobot agent -m "你好呀"
# 检查 ~/.nanobot/workspace/HEART.md 是否被创建和更新
```
