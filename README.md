<div align="center">
  <img src="nanobot_logo.png" alt="nanobot-wenyuan" width="500">
  <h1>nanobot-wenyuan: 个人定制版 AI Agent</h1>
  <p>
    <img src="https://img.shields.io/badge/python-≥3.11-blue" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
    <img src="https://img.shields.io/badge/based_on-nanobot-purple" alt="Based on">
  </p>
</div>

> 基于 [HKUDS/nanobot](https://github.com/HKUDS/nanobot) 的个人定制版本，集成 ReMe 向量记忆系统。

## 与原版的区别

| 特性 | 原版 nanobot | nanobot-wenyuan |
|------|-------------|-----------------|
| 长期记忆 | 文件型 (MEMORY.md) | **ReMe 向量记忆**（语义检索） |
| 记忆检索 | 自动注入 prompt | **工具化**（LLM 决定何时检索） |
| 记忆写入 | Dream 编辑文件 | Dream + **ReMe 自动提炼** |
| 用户归因 | 无 | **基于 USER.md 的用户名归因** |

## 主要改动

### 1. ReMe 向量记忆集成

- **语义检索**: 通过 `retrieve_memory` 工具进行语义化记忆搜索
- **自动提炼**: 对话压缩时自动提取关键信息存入向量库
- **断路器保护**: 防止记忆系统故障影响主流程

### 2. 记忆工具化

新增 5 个记忆工具，由 LLM 自主决定调用：

| 工具 | 功能 |
|------|------|
| `retrieve_memory` | 语义检索长期记忆 |
| `add_memory` | 存储重要信息到长期记忆 |
| `list_memories` | 列出最近存储的记忆 |
| `delete_memory` | 删除指定记忆 |
| `get_memory_status` | 检查记忆系统状态 |

### 3. 用户归因

所有记忆都会根据 USER.md 中的用户名进行归因，例如：
- 原版: `default_user拥有一辆电动车...`
- 本版: `烽林拥有一辆电动车...`

## 快速开始

### 安装

```bash
# 克隆仓库
git clone -b wenyuan https://github.com/ZZFFLL/nanobot-wenyuan.git
cd nanobot-wenyuan

# 安装依赖
pip install -e .
```

### 配置

1. **基础配置** - 同原版 nanobot，编辑 `~/.nanobot/config.json`

2. **ReMe 配置** - 在 config.json 同级目录创建 `reme.yaml`：

```yaml
# LLM 配置（自动继承 nanobot 配置，无需重复）
# llm:
#   model_name: ""
#   api_key: ""
#   base_url: ""

# Embedding 配置（必须配置）
embedding:
  model_name: "text-embedding-v4"
  api_key: "your-embedding-api-key"
  base_url: "https://api.example.com/v1"
  dimensions: 1024

# 向量存储
vector_store:
  backend: "chroma"
  collection_name: "nanobot_memory"
  persist_directory: ""  # 留空使用默认路径

# 检索配置
retrieve_top_k: 10
enable_time_filter: true

# 记忆类型
enable_personal_memory: true
enable_procedural_memory: false
enable_tool_memory: false
```

### 运行

```bash
nanobot gateway
```

## 新增命令

| 命令 | 功能 |
|------|------|
| `/memory` | 查看记忆系统状态 |
| `/memory list` | 列出所有记忆 |
| `/memory search <query>` | 语义搜索记忆 |
| `/memory add <content>` | 手动添加记忆 |
| `/memory delete <id>` | 删除记忆 |
| `/memory clear` | 清空所有记忆 |

## 记忆触发时机

| 触发点 | 写入位置 | 自动/手动 |
|--------|---------|----------|
| `/new` 命令 | ReMe | 自动 |
| Token 超限 | ReMe | 自动 |
| Agent 调用 `add_memory` | ReMe | 手动 |
| Dream 定时任务 | USER.md/SOUL.md + ReMe | 自动 |

## 分支说明

| 分支 | 用途 |
|------|------|
| `main` | 同步上游 (HKUDS/nanobot) 更新 |
| `wenyuan` | 个人开发分支（当前） |

### 同步上游更新

```bash
# 更新 main
git checkout main
git fetch upstream
git merge upstream/main
git push origin main

# 合并到 wenyuan
git checkout wenyuan
git merge main
git push origin wenyuan
```

详细说明请参考 [docs/GIT_WORKFLOW.md](./docs/GIT_WORKFLOW.md)

## 相关文档

- [ReMe 集成开发记录](./docs/REME_DEV_LOG.md)
- [ReMe 部署指南](./docs/REME_INTEGRATION.md)
- [Git 分支管理工作流程](./docs/GIT_WORKFLOW.md)

## 致谢

- [HKUDS/nanobot](https://github.com/HKUDS/nanobot) - 原版 nanobot 项目
- [ReMe](https://github.com/HKUDS/ReMe) - 记忆增强框架

## License

MIT