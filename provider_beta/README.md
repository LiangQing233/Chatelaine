# Provider Beta 最小接入示例

Provider Beta 提供一个可放入标准戒指槽的测试物品，用于验证注册、背包转移和手持快捷装备。图标使用游戏内置的 `emerald`。

## 加载与验证

Chatelaine 的 `.mcdev.json` 同时挂载 `./addon` 与 `./provider_beta`。手动加载时启用核心行为包、核心资源包，以及本目录的两个包：

| 包 | 路径 |
| --- | --- |
| Beta 行为包 | `behavior_pack_chatelaine_provider_beta` |
| Beta 资源包 | `resource_pack_chatelaine_provider_beta` |

```mcfunction
/give @s chatelaine_provider_beta:test_ring 1
```

打开垂佩页面，确认戒指可放入两个标准戒指槽并取回背包；手持戒指使用时应尝试快捷装备。示例不增加属性、页面或佩戴模型。

[注册入口](behavior_pack_chatelaine_provider_beta/chatelaine_provider_beta/server_system.py)在 `LoadServerAddonScriptsAfter` 内同步向 `chatelaine_api` 提交配置。详细契约见[注册者接入教程](../Chatelaine注册者接入教程.md)。

## 构建

从 Chatelaine 根目录运行 `python -B tools/build_release.py`，分别生成核心和 Beta 两个 ZIP。`Chatelaine-Provider-Beta-1.0.0-dev.zip` 根目录直接包含本示例的行为包与资源包。

源码中的行为包 `entities/` 仅含空 `.gitkeep` 占位；构建会过滤 `.gitkeep`，在 ZIP 中显式保留空 `entities/`。本说明、文档、工具和测试不进入运行 ZIP。

自有代码、物品定义和语言条目采用 [MIT](../LICENSE)，Copyright © 2026 LiangQing233。引用游戏内置图标不分发其原图；完整许可范围见[许可清单](../LICENSES.md)。
