# Minecraft 思源黑体资源包

用[思源黑体](https://github.com/adobe-fonts/source-han-sans)替换 Minecraft 默认字体，无需额外安装模组。支持 Minecraft Java 版 1.20.1–26.1.2。

[Modrinth 地址](https://modrinth.com/resourcepack/siyuanhei-sans)

![游戏内预览：书本界面中的简体中文、繁体中文、日文、韩文、拉丁字母与数字](preview.jpg)

## 安装

前往 [release](https://github.com/BearBin1215/mc-siyuanhei/releases) 下载对应游戏版本的文件，放入 `.minecraft/resourcepacks/` 后启用即可。

| 文件 | 支持的游戏版本 |
| --- | --- |
| `SiyuanHei-SC-MC1.20.5-26.1.2-v<version>.zip` | 1.20.5–26.1.2 |
| `SiyuanHei-SC-MC1.20.1-1.20.4-v<version>.zip` | 1.20.1–1.20.4 |

资源包使用位图图集：文字清晰、平滑，小字号下笔画更实。包约 21 MiB，图集常驻约 211 MiB 内存。

## 排版说明

- 汉字、假名、韩文：36×36 单元，9px 行高，优先用 33px 字号采样；放不下的字形回退到较小字号。汉字步进 9px。
- 拉丁字母与符号：36×48 单元，12px 行高，在原字体字宽基础上收紧间距，保留完整笔画；数字保持 6px 等宽步进。
- 常用全角标点：36×40 单元，10px 行高，步进 6px；开括号靠近后面的文字，闭括号靠近前面的文字。其他全角标点沿用汉字样式。
- 位图字体叠加在原版字体之上：思源覆盖的字形优先显示，其余字符回退原版默认字体和 Unifont；开启强制 Unicode 字体时使用原版字体。

## 构建

```bash
pip install -r requirements.txt

# 一次生成两个资源包，图集只生成一次
python tools/build_bitmap_pack.py

# 可选：只构建 1.20.5–26.1.2
python tools/build_bitmap_pack.py --target 1.20.5

# 可选：只构建 1.20.1–1.20.4
python tools/build_bitmap_pack.py --target 1.20.1
```

脚本先校验源字体、图标与 README，再把共享图集连同各目标的 `pack.mcmeta`、`default.json`、图标和许可文件打包到 `dist/`。`pack.mcmeta` 由构建脚本按目标格式范围生成，不再作为源文件维护。zip 固定了条目顺序和时间戳，同一份输入得到同一份文件，重新构建不会带来无意义的二进制改动。

两个包共用图集；1.20.1–1.20.4 的字体配置省略 `filter`，1.20.5–26.1.2 使用 `filter`，并同时包含新旧资源包格式声明。

字体文件已随仓库提供；需要从官方 OTF 重新生成时运行 `python tools/make_font.py <官方 Medium OTF>`，脚本把结果写入 `assets/minecraft/font/siyuan_hei_sc.ttf`。

## 代码检查

```bash
pip install -r requirements-dev.txt
python -m ruff check tools/
python -m ruff format --check tools/
python -m unittest discover -s tools
```

## 目录结构

```text
requirements.txt                    # 构建依赖
requirements-dev.txt                # 静态检查依赖
ruff.toml                           # 静态检查配置
preview.jpg                         # 游戏内预览图
bitmap/pack.png                     # 资源包图标，各目标共用
assets/minecraft/font/...           # 位图采样用的源字体
tools/build_common.py               # 构建目标、版本号、元数据与打包的公共实现
tools/test_build_common.py          # 目标选择、元数据与字体配置的自动检查
tools/make_font.py                  # 官方 CFF OTF → TrueType TTF
tools/build_bitmap_pack.py          # 图集生成与按目标打包
dist/                               # 本地构建产物，不入库，随 Release 与 Modrinth 分发
```

## 许可

- 基于思源黑体 2.005R Medium 转换，转换后字体内部名为 `Siyuan Hei SC Medium`，非官方发行版。
- 字体按 SIL OFL 1.1 分发，见 [LICENSE-OFL.txt](LICENSE-OFL.txt)；资源包结构与构建脚本按 MIT 分发，见 [LICENSE](LICENSE)。
- 字体设计版权归 Adobe；本项目与 Mojang Studios、Adobe 无关联。
