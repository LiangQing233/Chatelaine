# Chatelaine · 垂佩

Chatelaine（垂佩）是由 **LiangQing233** 独立开发的网易基岩版饰品 API，提供饰品槽、装备数据和佩戴外观，支持经典与触屏背包界面。物品效果由接入模组实现。

## 安装

在目标世界同时启用以下两个包：

| 包 | 路径 |
| --- | --- |
| 行为包 | `addon/behavior_pack_chatelaine_aggregator` |
| 资源包 | `addon/resource_pack_chatelaine` |

当前为未发布的开发版本，适配网易 3.9；核心与接入方按同一开发版本使用。接入模组还需启用自己的行为包和资源包；模型、贴图、动画、物品定义和语言文件均放在自己的包中。

系统命名空间为 `chatelaine_api`，槽位和注册契约使用 `chatelaine:`。当前开发版本直接使用新名称，不提供旧开发 ID 的兼容、别名或存档迁移。更新时同步更新全部接入方。

## 开始接入

1. 按[注册者接入教程](Chatelaine注册者接入教程.md)注册一个物品。
2. 在[公开接口文档](Chatelaine公开接口文档.md)中查询配置、服务端接口和事件。
3. 需要本地运行的示例时，启用 [Provider Beta](provider_beta/README.md) 的[行为包](provider_beta/behavior_pack_chatelaine_provider_beta)和[资源包](provider_beta/resource_pack_chatelaine_provider_beta)。它提供一个使用内置 `emerald` 图标的测试戒指。

## 功能说明

- 玩家：提供标准槽、自定义页面、背包转移、快捷装备、装备事件和第一／第三人称外观。
- 非玩家：由服务端为具体生物初始化槽位，再通过接口佩戴、取下或更新物品。已有装备可随实体存档恢复。
- 实体外观：优先使用指定实体类型的模型；未指定时，仅附着物名单内的类型使用玩家第三人称模型。模型不会自动适配骨骼和体型。
- 显隐：玩家可设置原生装备遮挡；非玩家不使用原生盔甲遮挡。隐藏模型不会取下装备或停止物品效果。

Chatelaine 使用目标版本的背包 UI；与其他背包界面覆盖包一起使用时，需要确认加载顺序和界面兼容性。移除槽位提供方前，请先取出玩家槽内物品或完成迁移。

## 许可与来源

自有代码和文档采用 [MIT](LICENSE)，署名 **LiangQing233**。标准空槽纹使用原版 Curios 9.5.1 的轮廓并修改颜色，四张按钮原样复用，相关素材继续采用 LGPL-3.0-or-later。项目身份见[署名声明](NOTICE.md)，具体范围与分发要求见[许可清单](LICENSES.md)和[素材来源](THIRD_PARTY_LICENSES/curios-9.5.1/SOURCE.md)。

## 本地构建

从本目录执行 `python -B tools/build_release.py`，在 `build/` 下生成两个独立运行 ZIP：

| ZIP | 根目录内容 |
| --- | --- |
| `Chatelaine-1.0.0-dev.zip` | `behavior_pack_chatelaine_aggregator/`、`resource_pack_chatelaine/` |
| `Chatelaine-Provider-Beta-1.0.0-dev.zip` | `behavior_pack_chatelaine_provider_beta/`、`resource_pack_chatelaine_provider_beta/` |

源码核心双包位于 `addon/`，Beta 双包位于 `provider_beta/`，开发入口同时挂载这两个目录。两个行为包的 `entities/` 均用空 `.gitkeep` 占位；构建过滤 `.gitkeep`，在 ZIP 中保留空 `entities/`。

ZIP 不含外层工程目录、文档、工具、测试或额外清单。许可证、原始素材、可编辑轮廓和生成程序在仓库维护，对外分发所需材料见[许可清单](LICENSES.md)。
