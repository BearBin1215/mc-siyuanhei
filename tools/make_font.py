#!/usr/bin/env python3
"""Convert an official CFF-outline OTF into a TrueType-outline TTF.

Minecraft 26.1 的 `ttf` 字体提供器只接受 TrueType 轮廓，官方发行版是 CFF 轮廓的 OTF，
所以要把三次贝塞尔转成二次贝塞尔（glyf）。可变字体（`Variable/` 下的 `-VF` 文件）先在
`wght` 轴上取静态实例，再走同一条转换路径，这样可以做出官方没有的中间字重（例如 450）。
转换后的字体按 OFL 保留字体名条款改名。

Requires: fonttools
"""

import argparse
from pathlib import Path
from typing import Any

from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.varLib.instancer import instantiateVariableFont

from build_common import ROOT, fail, require_file

DEFAULT_OUTPUT = ROOT / "assets" / "minecraft" / "font" / "siyuan_hei_sc.ttf"
MAX_ERR = 0.5  # 三次转二次的误差上限（字体单位，等于 1/2000 em）
CFF_TABLES = ("CFF ", "CFF2")
# 游戏只用到字形、度量和 cmap；排版表、DSIG 与可变字体遗留的元数据都直接不带走
DROP_TABLES = ("CFF ", "CFF2", "VORG", "DSIG", "GSUB", "GPOS", "GDEF", "BASE", "STAT", "vhea", "vmtx")


def quadratic_glyphs(glyph_set: Any) -> dict[str, Any]:
    """把 CFF 的三次曲线轮廓转成 TrueType 的二次曲线轮廓。"""
    glyphs = {}
    for name in glyph_set:
        pen = TTGlyphPen(glyph_set)
        glyph_set[name].draw(Cu2QuPen(pen, MAX_ERR, reverse_direction=True))
        glyphs[name] = pen.glyph()
    return glyphs


def weight_axis(font: TTFont) -> Any:
    """取 `wght` 轴的定义，只有可变字体才有。"""
    axis = next((axis for axis in font["fvar"].axes if axis.axisTag == "wght"), None)
    if axis is None:
        fail("variable font has no wght axis")
    return axis


def instance_at(font: TTFont, weight: float) -> TTFont:
    """在 `wght` 轴上取静态实例，返回新的字体对象。"""
    axis = weight_axis(font)
    if not axis.minValue <= weight <= axis.maxValue:
        fail(f"weight {weight:g} is outside the wght axis ({axis.minValue:g}-{axis.maxValue:g})")
    return instantiateVariableFont(font, {"wght": weight})


def default_style(font: TTFont, weight: float | None) -> str:
    """默认样式名：官方档位沿用实例名，中间字重按数值命名为 Weight<值>。"""
    if weight is None:
        return font["name"].getDebugName(2) or "Regular"
    for named in font["fvar"].instances:
        if named.coordinates.get("wght") == weight:
            return font["name"].getDebugName(named.subfamilyNameID) or f"Weight{weight:g}"
    return f"Weight{weight:g}"


def rename(font: TTFont, family: str, style: str) -> None:
    full = f"{family} {style}"
    postscript = f"{family.replace(' ', '')}-{style}"
    values = {1: family, 2: style, 4: full, 6: postscript, 16: family, 17: style}
    table = font["name"]
    for record in table.names:
        if record.nameID in values:
            table.setName(values[record.nameID], record.nameID, record.platformID, record.platEncID, record.langID)
        elif record.nameID == 3:
            # 唯一标识里也嵌着 PostScript 名，不改会残留官方名字和源字体的字重
            parts = str(record).split(";")
            if len(parts) == 4:
                parts[2] = postscript
                table.setName(";".join(parts), 3, record.platformID, record.platEncID, record.langID)


def convert(source: Path, output: Path, family: str, style: str | None, weight: float | None) -> None:
    with TTFont(source) as loaded:
        variable = "fvar" in loaded
        if variable and weight is None:
            axis = weight_axis(loaded)
            fail(f"{source.name} is a variable font; pass --weight ({axis.minValue:g}-{axis.maxValue:g})")
        if not variable and weight is not None:
            fail(f"{source.name} is a static font; --weight only applies to variable fonts")

        style = style or default_style(loaded, weight)
        font = instance_at(loaded, weight) if variable else loaded
        if not any(tag in font for tag in CFF_TABLES):
            fail(f"{source.name} is not a CFF font; nothing to convert")

        glyph_order = font.getGlyphOrder()
        glyf = newTable("glyf")
        glyf.glyphOrder = glyph_order
        glyf.glyphs = quadratic_glyphs(font.getGlyphSet())
        font["glyf"] = glyf
        font["loca"] = newTable("loca")

        for tag in DROP_TABLES:
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
        if weight is not None:
            # 静态源文件的字重号本来就对，只有实例化时源值仍是轴的默认档
            font["OS/2"].usWeightClass = round(weight)
        rename(font, family, style)

        output.parent.mkdir(parents=True, exist_ok=True)
        font.save(output)
    print(f"built {output} ({output.stat().st_size / 1024 / 1024:.2f} MiB, {len(glyph_order)} glyphs)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="官方发行版的 CFF OTF，或 Variable 目录下的 -VF 文件")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="输出路径，默认为资源包内的字体文件")
    parser.add_argument("--family", default="Siyuan Hei SC")
    parser.add_argument("--style", help="样式名，默认沿用源字体的名称；中间字重命名为 Weight<值>")
    parser.add_argument("--weight", type=float, help="wght 轴取值，可变字体必填（例如 450）")
    args = parser.parse_args()

    require_file(args.source, "source font")
    convert(args.source, args.output, args.family, args.style, args.weight)


if __name__ == "__main__":
    main()
