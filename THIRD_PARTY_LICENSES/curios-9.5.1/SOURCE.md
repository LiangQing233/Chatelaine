# Curios 素材来源与许可

Chatelaine（垂佩）的标准空槽纹使用 C4 的 Curios 9.5.1+1.21.1 alpha 轮廓并修改颜色；四张背包按钮直接复制，未修改文件内容。原始素材版权为 `Copyright (C) 2018-2024 C4`；槽纹颜色修改版权为 `Copyright (c) 2026 LiangQing233`。

| 项目 | 内容 |
| --- | --- |
| 上游构件 | `top.theillusivec4.curios:curios-neoforge:9.5.1+1.21.1` |
| 槽纹路径 | `assets/curios/textures/slot/` |
| 按钮路径 | `assets/curios/textures/gui/curios/` |
| 修改内容 | 槽纹不透明像素从 RGBA `(85, 85, 85, 255)` 改为网易 3.9 原生槽颜色 `(25, 32, 34, 255)`；透明像素统一为 `(0, 0, 0, 0)` |
| 许可证 | GNU Lesser General Public License，版本 3 或更新版本 |

## 可编辑来源与逐文件对应

[ASSETS.json](ASSETS.json) 列出全部 14 张发行 PNG 的原始路径、源文件、修改内容和 SHA-256，以及取材 JAR 的完整下载地址与哈希。`source/assets/curios/textures/slot/` 保存十张原始槽纹，`source/assets/curios/textures/gui/curios/` 保存四张原始按钮。`source/slot_masks.json` 是实际修改使用的可编辑文本轮廓；这些源素材及修改版均为 LGPL-3.0-or-later。

颜色变换由[生成程序](../../tools/generate_standard_slot_textures.py)执行。程序代码为 MIT，轮廓数据的 LGPL 授权独立保留。PNG 是上游提供的像素素材；本项目未取得或声称存在额外的 PSD 等源工程。

从 Chatelaine 目录运行，仅需 Python 3 标准库：

```powershell
python -B tools/generate_standard_slot_textures.py --check
python -B tools/generate_standard_slot_textures.py
```

第一条校验生产槽纹；第二条在 `build/slot_textures/` 重建十张 PNG。需要替换生产文件时，显式传入 `--output-dir addon/resource_pack_chatelaine/textures/ui/chatelaine`。四张按钮无需加工，按 `ASSETS.json` 的对应关系复制原始 PNG 即可。来源不依赖开发者本机 Gradle 缓存，也无需再下载整个模组。

更名仅改变本项目的发行路径，不改变 Curios 的上游名称、构件坐标和许可证。本地构建分别生成核心与 Beta 的运行 ZIP，仅含各自行为包和资源包；本目录及生成程序在仓库保留，对外分发相关素材时需同步提供。完整分发要求见[许可清单](../../LICENSES.md)。

分发相关素材时，请保留来源、修改说明及本目录的 [LICENSE](LICENSE)、[COPYING](COPYING) 和 [COPYING.LESSER](COPYING.LESSER)。许可证原文保持不变。
