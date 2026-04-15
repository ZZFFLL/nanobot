# SOUL 局部初始化设计说明

> 日期：2026-04-15
> 范围：`soul init` 的 `--only / --force` 局部初始化能力

## 1. 背景

当前 `soul init` 已能完成全量初始化，但在调试和阶段性修复时，经常只需要重建某一个或某几个文件。

因此新增局部初始化能力，同时保留原有全量流程不变。

## 2. 命令形态

全量初始化：

```powershell
python -m nanobot.cli.commands soul init --config C:\Users\Administrator\.nanobot\config.json
```

局部初始化：

```powershell
python -m nanobot.cli.commands soul init --config C:\Users\Administrator\.nanobot\config.json --only CORE_ANCHOR.md
python -m nanobot.cli.commands soul init --config C:\Users\Administrator\.nanobot\config.json --only SOUL.md --only SOUL_PROFILE.md
python -m nanobot.cli.commands soul init --config C:\Users\Administrator\.nanobot\config.json --only CORE_ANCHOR.md --force
```

## 3. 行为规则

- 不传 `--only`
  - 保持原有全量初始化逻辑
- 传 `--only`
  - 只初始化指定文件
- 默认如果文件已存在
  - 跳过
- 传 `--force`
  - 覆盖指定目标文件
- 非法文件名
  - 直接报错退出

## 4. 支持的文件白名单

- `IDENTITY.md`
- `USER.md`
- `AGENTS.md`
- `CORE_ANCHOR.md`
- `SOUL_METHOD.md`
- `SOUL.md`
- `SOUL_PROFILE.md`
- `HEART.md`
- `EVENTS.md`

## 5. 执行顺序

多文件局部初始化时，按固定顺序执行：

1. `IDENTITY.md`
2. `USER.md`
3. `AGENTS.md`
4. `CORE_ANCHOR.md`
5. `SOUL_METHOD.md`
6. `SOUL.md`
7. `SOUL_PROFILE.md`
8. `HEART.md`
9. `EVENTS.md`

这样可以让低层依赖先准备好。

## 6. 依赖补全策略

局部初始化时，程序不会默认把整套表单重新问一遍，而是按以下优先级补全参数：

1. 现有工作区文件
2. 命令默认值
3. 缺失时才向用户提问

例如：

- `--only CORE_ANCHOR.md --force`
  - 若已有 `IDENTITY.md`，则直接读取 `name`
  - 不再重复询问整套初始化问题

## 7. LLM 参与边界

以下目标文件会触发初始化 LLM：

- `SOUL.md`
- `SOUL_PROFILE.md`

逻辑：

- 若 provider 可用
  - 走“LLM 候选 + 程序裁决 + 正式落盘”
- 若 provider 不可用或输出非法
  - 回退程序默认初始化

其它文件不依赖 LLM。

## 8. 不做的事

局部初始化不会隐式连带写入其他文件。

例如：

- `--only CORE_ANCHOR.md`
  - 不会顺手改 `SOUL.md`
- `--only SOUL_PROFILE.md`
  - 不会顺手重建 `HEART.md`

## 9. 结果输出

命令执行后会输出每个目标文件的结果：

- `created: FILE`
- `overwritten: FILE`
- `skipped: FILE`

若配置文件存在，还会继续保证：

- `soul.enabled = true`

## 10. 本节结论

局部初始化能力让 `soul init` 从“只能全量初始化”升级为“全量与局部兼容”的初始化入口，适合后续阶段性调试、局部修复和工作区文件重建，同时不破坏既有全量初始化流程。
