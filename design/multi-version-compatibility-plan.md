# Minecraft 字体资源包多版本兼容方案

更新日期：2026-11-25

## 兼容结论与发布范围

根据用户提供的测试结果，资源包兼容 Minecraft Java 版 1.20.1–26.1.2 的所有正式版。构建和发布按字体提供器 `filter` 的引入版本分为两个包，各版本共用源字体、排版参数和位图图集。

| 构建目标 | 支持版本 | 资源包格式范围 | 字体配置 |
| --- | --- | --- | --- |
| `1.20.5` | 1.20.5–26.1.2 | `32`–`84` | 使用 `filter: {"uniform": false}` |
| `1.20.1` | 1.20.1–1.20.4 | `15`–`22` | 不含 `filter` |

1.20.5–1.21.11 与 26.1–26.1.2 使用同一套字体配置，合并为同一个发布包。资源包元数据在 1.21.9 发生变化，通过同时生成新旧字段兼容各版本。

## 构建入口

默认命令一次生成两个资源包，图集只生成一次：

```bash
pip install -r requirements.txt
python tools/build_bitmap_pack.py
```

需要单独构建时，使用 `--target`：

```bash
python tools/build_bitmap_pack.py --target 1.20.5
python tools/build_bitmap_pack.py --target 1.20.1
```

移除独立的 `26.1` 目标。无需通过重复的 `--target` 参数选择全部产物，也无需维护默认目标、手动目标校验或目标去重逻辑。参数有效性由 `argparse` 的 `choices` 检查。

## 配置与构建流程

`tools/build_common.py` 集中维护目标名称、支持版本列表、格式范围和是否启用字体 `filter`。产物名称从支持列表的首尾版本生成，`pack_format` 使用最低格式编号，省去独立的基准格式字段。

`tools/build_bitmap_pack.py` 的流程为：

1. 解析目标参数，校验源字体、图标、README 和许可文件。
2. 生成共享位图图集及 `siyuan_bitmap.json`。
3. 为所选目标生成独立的 `pack.mcmeta` 与 `default.json`。
4. 将共享文件和目标配置分别打包到 `dist/`。

共享文件列表只枚举一次。各目标配置放在 `.work/bitmap_targets/`，图集放在 `.work/bitmap_build/`，保留临时目录清理路径校验。ZIP 继续固定条目顺序和时间戳，确保相同输入可复现。

## 资源包元数据

1.20.1–1.20.4 使用旧元数据字段：

```json
{
  "pack": {
    "pack_format": 15,
    "supported_formats": {
      "min_inclusive": 15,
      "max_inclusive": 22
    },
    "description": "§6思源黑体 SC§r"
  }
}
```

1.20.5–26.1.2 同时包含新旧元数据字段：

```json
{
  "pack": {
    "pack_format": 32,
    "supported_formats": {
      "min_inclusive": 32,
      "max_inclusive": 84
    },
    "min_format": 32,
    "max_format": 84,
    "description": "§6思源黑体 SC§r"
  }
}
```

支持范围跨越格式 `65` 时，旧版本通过 `pack_format` 与 `supported_formats` 读取兼容范围，新版本通过 `min_format` 与 `max_format` 读取。两个范围保持一致。

格式范围可能包含快照使用的编号，发布页面只列出已确认兼容的正式版。

## 字体行为

默认字体的提供器顺序保持为：原版空格、思源位图、原版默认字体、Unifont。思源覆盖的字符优先显示，其余字符回退原版。

- 1.20.5–26.1.2 对思源位图和原版默认字体引用添加 `filter: {"uniform": false}`。
- 1.20.1–1.20.4 使用相同引用顺序，省略 `filter`。

原版 `uniform.json` 保持可用，开启强制 Unicode 字体后使用原版字体。合并产物不改变图集、字号、基线、字宽和标点排版。

## 发布产物与文档

```text
dist/SiyuanHei-SC-MC1.20.5-26.1.2-v<version>.zip
dist/SiyuanHei-SC-MC1.20.1-1.20.4-v<version>.zip
```

两个文件共用项目版本号，本次发布版本为 `1.0`，Git 标签为 `v1.0`。README 列出文件名、支持范围、默认构建命令和可选的单目标命令。Release 和 Modrinth 对每个文件分别填写对应的正式版列表。

原有三包构建产物属于历史文件，不纳入本次发布。构建脚本仅生成当前两个目标，避免自动删除已有本地产物。

## 验证安排

| 检查项 | 通过标准 |
| --- | --- |
| 构建入口 | 默认选择两个目标；指定目标只构建对应包；未知目标与移除的 `26.1` 目标立即报错 |
| 元数据 | 旧包为格式 `15`–`22`；新包为 `32`–`84`，同时包含一致的新旧范围字段 |
| 字体配置 | 新包保留 `filter`，旧包不含 `filter`，引用顺序不变 |
| 图集与字符映射 | 两个包使用完全相同的图集和 `siyuan_bitmap.json`，内容与合并前一致 |
| ZIP 完整性 | 文件条目不重复，引用图集存在，压缩文件可完整读取 |
| 可复现构建 | 相同输入重复构建，两份 ZIP 的 SHA-256 分别一致 |
| 静态与自动检查 | Ruff 和仓库单元测试通过 |

```bash
python -m ruff check tools/
python -m ruff format --check tools/
python -m unittest discover -s tools
```

用户提供的全版本测试作为兼容依据。本次改造完成构建与产物检查；最终合并 ZIP 的游戏内加载可在 1.20.5、1.21.9 和 26.1.2 复查，重点确认版本识别、字体回退及字体选项切换。

2026-11-25 改造验证结果：Ruff 检查通过，15 项单元测试通过；默认完整构建生成两个 ZIP，元数据、字体配置、引用文件和 ZIP 完整性检查通过。图集及字符映射与合并前逐文件 SHA-256 一致，现代默认字体配置一致；重复完整构建后，两份 ZIP 的 SHA-256 分别一致。详细结果保存在 `.work/two-pack-validation.json`。本次未重新进行游戏内验收。

## 参考资料

- [Minecraft 版本格式索引](https://raw.githubusercontent.com/misode/mcmeta/summary/versions/data.json)
- [Mojang 1.20.5 更新说明：字体提供器筛选条件](https://www.minecraft.net/en-us/article/minecraft-java-edition-1-20-5)
- [Mojang 1.21.9 更新说明：资源包元数据格式](https://www.minecraft.net/en-us/article/minecraft-java-edition-1-21-9)
