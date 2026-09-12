# 许可清单

更新：2026-09-12。作者署名：**LiangQing233**。

本项目按文件来源分别授权；根目录 [MIT LICENSE](LICENSE) 只覆盖自有实现，不覆盖下面列出的第三方内容。

| 文件或内容 | 许可与归属 |
| --- | --- |
| `addon/behavior_pack_chatelaine_aggregator/` 的自有 Python、命令和包定义 | MIT，Copyright © 2026 LiangQing233 |
| 自有文档、测试、`tools/` 中的程序及包配置 | MIT，Copyright © 2026 LiangQing233 |
| `addon/resource_pack_chatelaine/ui/chatelaine_inventory_proxy.json` 与自有 UI 接入修改 | MIT，Copyright © 2026 LiangQing233；引用引擎内置控件不转授引擎资源 |
| `addon/resource_pack_chatelaine/textures/ui/chatelaine/` 的 14 张 PNG | LGPL-3.0-or-later；上游 C4，槽纹颜色修改 LiangQing233 |
| `THIRD_PARTY_LICENSES/curios-9.5.1/source/` 中的原始 PNG 和可编辑槽纹 | LGPL-3.0-or-later；保留上游版权及修改记录 |
| `inventory_screen.json`、`inventory_screen_pocket.json` 中保留的原版背包定义 | 原版 Minecraft／网易内容；本项目 MIT 不覆盖其原始部分，发布平台的资源使用规则仍适用 |
| `provider_beta/` 中的自有接入代码、物品定义和语言条目 | MIT，Copyright © 2026 LiangQing233；只引用游戏内置 emerald 图标，不分发其原图 |

`LICENSE`、`COPYING`、`COPYING.LESSER` 是上游随附的许可原文，保持逐字节不变。不得把整个资源包标为全部原创或全部 MIT。

## 分发与修改

分发 Chatelaine 时，同时保留根目录 `LICENSE`、`NOTICE.md`、本清单、完整 `THIRD_PARTY_LICENSES/curios-9.5.1/` 以及 `tools/generate_standard_slot_textures.py`。这使接收者同时取得原始像素、实际修改用的文本槽纹、生成程序和复现说明；不能只附一个上游链接或只附许可证。

复用或修改上述 LGPL 素材时保留相应许可、版权和修改说明，并按 LGPL-3.0-or-later 提供对应可编辑来源。自有 Python 与第三方素材分别维护授权；接入模组的自有代码由其作者自行选择许可。

运行 `python -B tools/build_release.py` 会校验仓库中的许可和核心素材来源，分别生成核心与 Provider Beta 两个本地运行 ZIP。每个 ZIP 只包含对应的行为包和资源包；源码用 `.gitkeep` 保存 `entities/`，ZIP 过滤占位文件并保留空目录。许可文档、素材来源和生成程序保留在仓库，不装入运行 ZIP；用于对外分发时，另行随附前述材料。脚本不上传或发布，也不把平台审核、UI 权利核对或多人实机验收标记为完成。
