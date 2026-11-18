#!/usr/bin/env python3
"""Convert an official CFF-outline OTF into a TrueType-outline TTF.

Minecraft 26.1 的 `ttf` 字体提供器只接受 TrueType 轮廓，官方发行版是 CFF 轮廓的 OTF，
所以要把三次贝塞尔转成二次贝塞尔（glyf）。转换后的字体按 OFL 保留字体名条款改名。

Requires: fonttools
"""

import argparse
from pathlib import Path
from typing import Any

from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable

from build_common import ROOT, fail, require_file

DEFAULT_OUTPUT = ROOT / "assets" / "minecraft" / "font" / "siyuan_hei_sc.ttf"
MAX_ERR = 0.5  # 三次转二次的误差上限（字体单位，等于 1/2000 em）


def quadratic_glyphs(glyph_set: Any) -> dict[str, Any]:
    """把 CFF 的三次曲线轮廓转成 TrueType 的二次曲线轮廓。"""
    glyphs = {}
    for name in glyph_set:
        pen = TTGlyphPen(glyph_set)
        glyph_set[name].draw(Cu2QuPen(pen, MAX_ERR, reverse_direction=True))
        glyphs[name] = pen.glyph()
    return glyphs


def rename(font: TTFont, family: str, style: str) -> None:
    full = f"{family} {style}"
    postscript = f"{family.replace(' ', '')}-{style}"
    values = {1: family, 2: style, 4: full, 6: postscript, 16: family, 17: style}
    table = font["name"]
    for record in table.names:
        if record.nameID in values:
            table.setName(values[record.nameID], record.nameID, record.platformID, record.platEncID, record.langID)


def convert(source: Path, output: Path, family: str, style: str) -> None:
    with TTFont(source) as font:
        if "CFF " not in font and "CFF2" not in font:
            fail(f"{source.name} is not a CFF font; nothing to convert")

        glyph_order = font.getGlyphOrder()
        glyf = newTable("glyf")
        glyf.glyphOrder = glyph_order
        glyf.glyphs = quadratic_glyphs(font.getGlyphSet())
        font["glyf"] = glyf
        font["loca"] = newTable("loca")

        # 游戏只用到字形、度量和 cmap，GSUB/GPOS 等排版表在加载时会被丢弃，这里直接不带走
        for tag in ("CFF ", "CFF2", "VORG", "DSIG", "GSUB", "GPOS", "GDEF", "BASE", "vhea", "vmtx"):
            if tag in font:
                del font[tag]

        # 先编译 glyf，得到每个字的包围盒，maxp/post 的重新计算依赖它
        glyf.compile(font)

        maxp = font["maxp"]
        maxp.tableVersion = 0x00010000
        maxp.maxZones = 1
        maxp.maxTwilightPoints = 0
        maxp.maxStorage = 0
        maxp.maxFunctionDefs = 0
        maxp.maxInstructionDefs = 0
        maxp.maxStackElements = 0
        maxp.maxSizeOfInstructions = 0
        maxp.maxComponentElements = max(
            (len(glyph.components) for glyph in glyf.glyphs.values() if glyph.numberOfContours < 0),
            default=0,
        )
        maxp.numGlyphs = len(glyph_order)

        font["head"].glyphDataFormat = 0
        font["post"].formatType = 3.0
        font.sfntVersion = "\x00\x01\x00\x00"
        rename(font, family, style)

        output.parent.mkdir(parents=True, exist_ok=True)
        font.save(output)
    print(f"built {output} ({output.stat().st_size / 1024 / 1024:.2f} MiB, {len(glyph_order)} glyphs)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="官方发行版的 CFF OTF（例如 Medium 字重）")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="输出路径，默认为资源包内的字体文件")
    parser.add_argument("--family", default="Siyuan Hei SC")
    parser.add_argument("--style", default="Medium")
    args = parser.parse_args()

    require_file(args.source, "source font")
    convert(args.source, args.output, args.family, args.style)


if __name__ == "__main__":
    main()
