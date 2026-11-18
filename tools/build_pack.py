#!/usr/bin/env python3
"""Build the TTF-based resource pack variant."""

import json
import struct

from build_common import (
    ROOT,
    SHARED_FILES,
    check_readme,
    fail,
    iter_files,
    load_pack_meta,
    output_path,
    require_file,
    write_zip,
)

OUTPUT = output_path("TTF")
FONT = ROOT / "assets" / "minecraft" / "font" / "siyuan_hei_sc.ttf"
FONT_DEF = ROOT / "assets" / "minecraft" / "font" / "default.json"
INCLUDE_IN_ZIP = ("pack.mcmeta", "pack.png", *SHARED_FILES, "assets")
TRUE_TYPE_SFNT = b"\x00\x01\x00\x00"
SFNT_PREFIX_SIZE = 6  # sfntVersion + numTables


def validate() -> None:
    load_pack_meta(ROOT / "pack.mcmeta", "pack.mcmeta")
    require_file(FONT_DEF)

    providers = json.loads(FONT_DEF.read_text(encoding="utf-8")).get("providers", [])
    ttf = next((p for p in providers if p.get("type") == "ttf"), None)
    if ttf is None or ttf.get("file") != "minecraft:siyuan_hei_sc.ttf":
        fail("default.json does not reference minecraft:siyuan_hei_sc.ttf")
    require_file(FONT, "font file")

    with FONT.open("rb") as fh:
        header = fh.read(SFNT_PREFIX_SIZE)
    if len(header) < SFNT_PREFIX_SIZE:
        fail(f"{FONT.name} is truncated ({len(header)} bytes)")
    sfnt_version, num_tables = struct.unpack(">4sH", header)
    if sfnt_version != TRUE_TYPE_SFNT:
        fail("font is not a TrueType-outline font (Minecraft 26.1 rejects CFF outlines)")
    if num_tables == 0:
        fail("font has no tables")
    print(f"font OK: {FONT.stat().st_size / 1024 / 1024:.2f} MiB, {num_tables} tables")


def build() -> None:
    entries = []
    for entry in INCLUDE_IN_ZIP:
        path = ROOT / entry
        if path.is_dir():
            entries.extend(iter_files(path, ROOT))
        elif path.is_file():
            entries.append((path, entry))
        else:
            fail(f"missing build input: {entry}")

    write_zip(OUTPUT, entries, compresslevel=9)


def main() -> None:
    check_readme(OUTPUT)
    validate()
    build()


if __name__ == "__main__":
    main()
