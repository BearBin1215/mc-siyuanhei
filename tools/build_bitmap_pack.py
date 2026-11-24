#!/usr/bin/env python3
"""Build font resource packs sharing a 4x supersampled bitmap atlas.

Requires: fonttools, pillow
"""

import argparse
import json
import math
import shutil
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

from build_common import (
    ROOT,
    SHARED_FILES,
    TARGETS,
    Target,
    check_readme,
    fail,
    iter_files,
    output_path,
    pack_meta,
    require_file,
    write_zip,
)

TTF = ROOT / "assets" / "minecraft" / "font" / "siyuan_hei_sc.ttf"
PACK_PNG = ROOT / "bitmap" / "pack.png"
BUILD = ROOT / ".work" / "bitmap_build"  # 各目标共用的图集
CONFIG_BUILD = ROOT / ".work" / "bitmap_targets"  # 各目标的 pack.mcmeta 与 default.json

FONT_ID = "siyuan_bitmap"
COLS = 64
BMP_MAX = 0xFFFF
CJK_START = 0x2E80  # 此码位及以上按汉字样式排版（含全角标点、假名）
HANGUL_JAMO = (0x1100, 0x11FF)
SPACE = 0x20
GLYPH_PAD = 12  # 超采样画布四周留白，容纳 ascender/descender 与左侧溢出
SENTINEL_ALPHA = 1
CJK_OPEN = frozenset("（［｛「『【〈《〔")
CJK_CLOSE = frozenset("）］｝」』】〉》〕")
CJK_PUNCTUATION = CJK_OPEN | CJK_CLOSE | frozenset("、。，．！？：；")


@dataclass(frozen=True)
class Style:
    """一套图集参数：4x 单元尺寸、行高与基线的游戏单位、候选字号（从大到小）。"""

    cell: tuple[int, int]
    height: int
    ascent: int
    sizes: tuple[int, ...]
    max_ink: int
    max_rows: int


LATIN = Style(
    cell=(36, 48),
    height=12,
    ascent=9,
    sizes=(34, 33, 32, 31, 30, 29, 28),
    max_ink=36,
    max_rows=85,
)
CJK = Style(
    cell=(36, 36),
    height=9,
    ascent=8,
    sizes=(33, 32, 31, 30, 29, 28),
    max_ink=33,
    max_rows=109,
)
PUNCTUATION = Style(
    cell=(36, 40),
    height=10,
    ascent=8,
    sizes=(33, 32, 31, 30, 29, 28),
    max_ink=33,
    max_rows=102,
)


def font_config(target: Target) -> dict[str, object]:
    """默认字体配置：只有在目标版本支持字体提供器 filter 时才启用。"""
    providers: list[dict[str, object]] = [{"type": "reference", "id": "minecraft:include/space"}]
    for font in (f"minecraft:{FONT_ID}", "minecraft:include/default"):
        provider: dict[str, object] = {"type": "reference", "id": font}
        if target.uniform_filter:
            provider["filter"] = {"uniform": False}
        providers.append(provider)
    providers.append({"type": "reference", "id": "minecraft:include/unifont"})
    return {"providers": providers}


def reset_dir(path: Path) -> None:
    if path.is_dir():
        if path.resolve().parent != (ROOT / ".work").resolve():
            fail(f"build directory must be directly inside {ROOT / '.work'}")
        shutil.rmtree(path)


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_target_config(target: Target) -> Path:
    """把目标独有的元数据和字体配置写入独立目录，避免混入其他目标的 ZIP。"""
    root = CONFIG_BUILD / target.name
    font_dir = root / "assets" / "minecraft" / "font"
    font_dir.mkdir(parents=True)
    write_json(root / "pack.mcmeta", pack_meta(target))
    write_json(font_dir / "default.json", font_config(target))
    return root


def adjust_spacing(
    char: str, cell: Image.Image, ink_left: int, ink_right: int, width: int, style: Style
) -> tuple[Image.Image, int]:
    """保留全部笔画，减少英文留白，并为中文标点设置占位与对齐。"""
    if char in CJK_PUNCTUATION:
        # 标点目标步进为 6px；4x 图集中宽度 20px 经游戏取整并加 1 后得到 6px。
        width = 20
        ink_width = ink_right - ink_left
        if ink_width > width:
            return cell, max(width, ink_right)
        if char in CJK_OPEN:
            target_left = width - ink_width  # 开括号靠近后面的文字
        elif char in CJK_CLOSE:
            target_left = 0  # 闭括号靠近前面的文字
        else:
            target_left = min(max(ink_left, 0), 2)
        shift = target_left - ink_left
    elif style == LATIN and char not in "0123456789":
        # 最多去掉 0.5px 左侧留白；字宽补偿位图提供器额外加的 1px，且不裁笔画。
        shift = -min(max(ink_left, 0), 2)
        width = max(ink_right + shift, width - 4)
    else:
        return cell, width
    shifted = Image.new("RGBA", cell.size, (0, 0, 0, 0))
    shifted.alpha_composite(cell, (shift, 0))
    return shifted, width


@cache
def get_font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(TTF), size)


def is_cjk(cp: int) -> bool:
    return cp >= CJK_START or HANGUL_JAMO[0] <= cp <= HANGUL_JAMO[1]


def draw_glyph(char: str, style: Style) -> Image.Image | None:
    """把一个字形渲染成 (cw, cell_h) 的 4x 单元，返回 None 表示当前样式放不下。"""
    cw, cell_h = style.cell
    baseline = round(style.ascent * cell_h / style.height)

    for size in style.sizes:
        font = get_font(size)
        tmp = Image.new("RGBA", (cw + GLYPH_PAD * 2, cell_h + GLYPH_PAD * 2), (0, 0, 0, 0))
        draw = ImageDraw.Draw(tmp)
        try:
            draw.text((GLYPH_PAD, GLYPH_PAD + baseline), char, font=font, fill=(255, 255, 255, 255), anchor="ls")
        except (OSError, ValueError):  # 个别字形渲染失败时换更小字号
            continue

        bbox = tmp.getchannel("A").getbbox()
        advance = font.getlength(char)
        if bbox is None:
            width = min(round(advance), style.max_ink, cw)
            if width <= 0:
                return None
            cell = Image.new("RGBA", (cw, cell_h), (0, 0, 0, 0))
            cell.putpixel((width - 1, 0), (255, 255, 255, SENTINEL_ALPHA))
            return cell

        ink_left = bbox[0] - GLYPH_PAD
        ink_top = bbox[1] - GLYPH_PAD
        ink_right = bbox[2] - GLYPH_PAD
        ink_bottom = bbox[3] - GLYPH_PAD

        # 墨迹越过左边界时整幅右移：留白足够，横向溢出总能消解，只需平移不放弃
        crop_x = GLYPH_PAD
        if ink_left < 0:
            crop_x += ink_left
            ink_right -= ink_left
            ink_left = 0
        if ink_top < 0 or ink_right > cw or ink_bottom > cell_h:
            continue

        width = max(ink_right, round(advance))
        if width > style.max_ink or width > cw:
            continue
        cell = tmp.crop((crop_x, GLYPH_PAD, crop_x + cw, GLYPH_PAD + cell_h))
        cell, width = adjust_spacing(char, cell, ink_left, ink_right, width, style)
        if width > 0 and cell.getpixel((width - 1, 0))[3] == 0:
            # Minecraft 按最右非透明列推算字宽，用一个几乎不可见的像素把宽度撑到目标值
            cell.putpixel((width - 1, 0), (255, 255, 255, SENTINEL_ALPHA))
        return cell

    return None


def build_pages(
    chars: Sequence[int], style: Style, page_start: int
) -> tuple[list[dict[str, object]], int, list[int], int]:
    cw, cell_h = style.cell
    capacity = COLS * style.max_rows
    providers: list[dict[str, object]] = []
    mapped = 0
    skipped: list[int] = []
    page_no = page_start

    for offset in range(0, len(chars), capacity):
        chunk = chars[offset : offset + capacity]
        rows = math.ceil(len(chunk) / COLS)
        atlas = Image.new("RGBA", (COLS * cw, rows * cell_h), (0, 0, 0, 0))
        grid = [["\u0000"] * COLS for _ in range(rows)]
        page_mapped = 0

        for i, cp in enumerate(chunk):
            char = chr(cp)
            cell = draw_glyph(char, style)
            if cell is None:
                skipped.append(cp)
                continue
            col, row = i % COLS, i // COLS
            atlas.alpha_composite(cell, (col * cw, row * cell_h))
            grid[row][col] = char
            page_mapped += 1

        filename = f"{FONT_ID}_{page_no:02d}.png"
        atlas.save(BUILD / "assets" / "minecraft" / "textures" / "font" / filename, compress_level=6)
        providers.append(
            {
                "type": "bitmap",
                "file": f"minecraft:font/{filename}",
                "height": style.height,
                "ascent": style.ascent,
                "chars": ["".join(row) for row in grid],
            }
        )
        print(f"  page {filename}: {page_mapped} glyphs, {rows}x{COLS} cells, {atlas.width}x{atlas.height}px")
        mapped += page_mapped
        page_no += 1

    return providers, mapped, skipped, page_no


def parse_targets(argv: Sequence[str] | None = None) -> list[Target]:
    """默认构建全部资源包；指定 --target 时只构建对应版本范围。"""
    parser = argparse.ArgumentParser(description="构建思源黑体位图资源包")
    parser.add_argument(
        "--target",
        choices=TARGETS,
        help="只构建指定目标；默认构建全部资源包",
    )
    args = parser.parse_args(argv)
    return [TARGETS[args.target]] if args.target else list(TARGETS.values())


def main() -> None:
    targets = parse_targets()

    # 廉价校验全部前置，避免几分钟图集生成之后才发现缺文件
    for target in targets:
        check_readme(output_path(target))
    require_file(TTF, "source font")
    require_file(PACK_PNG, "bitmap/pack.png")
    for name in SHARED_FILES:
        require_file(ROOT / name)

    with TTFont(TTF) as font:
        cmap = font.getBestCmap()
    if not cmap:
        fail(f"{TTF.name} has no usable cmap")

    bmp = []
    for cp in sorted(cmap):
        if cp > BMP_MAX:
            continue
        char = chr(cp)
        category = unicodedata.category(char)
        if category in ("Cc", "Cs", "Cf", "Co", "Cn", "Zl", "Zp") or category.startswith("M"):
            continue
        if cp == SPACE:  # 空格无墨迹，交由 vanilla 的 include/space 提供
            continue
        bmp.append(cp)

    latin_chars = [cp for cp in bmp if not is_cjk(cp)]
    cjk_chars = [cp for cp in bmp if is_cjk(cp)]
    print(f"BMP characters: {len(bmp)} (latin/symbols {len(latin_chars)}, CJK {len(cjk_chars)})")

    reset_dir(BUILD)
    reset_dir(CONFIG_BUILD)
    (BUILD / "assets" / "minecraft" / "font").mkdir(parents=True)
    (BUILD / "assets" / "minecraft" / "textures" / "font").mkdir(parents=True)

    providers: list[dict[str, object]] = []
    all_mapped = 0
    all_skipped: list[int] = []
    next_page = 0
    groups = [
        (LATIN, latin_chars),
        (CJK, [cp for cp in cjk_chars if chr(cp) not in CJK_PUNCTUATION]),
        (PUNCTUATION, [cp for cp in cjk_chars if chr(cp) in CJK_PUNCTUATION]),
    ]
    for style, chars in groups:
        pages, mapped, skipped, next_page = build_pages(chars, style, next_page)
        providers.extend(pages)
        all_mapped += mapped
        all_skipped.extend(skipped)

    bitmap_font = {"providers": providers}
    (BUILD / "assets" / "minecraft" / "font" / f"{FONT_ID}.json").write_text(
        json.dumps(bitmap_font, ensure_ascii=True, separators=(",", ":")),
        encoding="utf-8",
    )

    vram = 0
    for path in (BUILD / "assets" / "minecraft" / "textures" / "font").glob("*.png"):
        with Image.open(path) as img:
            vram += img.width * img.height * 4

    print(f"mapped {all_mapped} glyphs, skipped {len(all_skipped)}")
    if all_skipped:
        sample = " ".join(f"U+{cp:04X}" for cp in all_skipped[:20])
        print(f"skipped sample (fall back to unifont): {sample}")
    print(f"atlas pages: {len(providers)}, uncompressed atlas data: {vram / 1024 / 1024:.0f} MiB (RAM)")

    shared_entries = [*iter_files(BUILD, BUILD), (PACK_PNG, "pack.png")]
    shared_entries += [(ROOT / name, name) for name in SHARED_FILES]
    for target in targets:
        config_root = write_target_config(target)
        entries = shared_entries + iter_files(config_root, config_root)
        print(f"packing target {target.name} (game versions: {', '.join(target.versions)})")
        write_zip(output_path(target), entries, compresslevel=6)


if __name__ == "__main__":
    main()
