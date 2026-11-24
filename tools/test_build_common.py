"""构建目标、元数据与字体配置的自动检查。"""

import unittest
from contextlib import redirect_stderr
from io import StringIO

from build_bitmap_pack import font_config, parse_targets
from build_common import DESCRIPTION, TARGETS, VERSION, Target, output_path, pack_meta

PROVIDER_IDS = [
    "minecraft:include/space",
    "minecraft:siyuan_bitmap",
    "minecraft:include/default",
    "minecraft:include/unifont",
]


def make_target(
    versions: tuple[str, ...] = ("1.21",),
    low: int = 34,
    high: int = 34,
    *,
    uniform_filter: bool = True,
) -> Target:
    return Target("test", versions, low, high, uniform_filter)


class ParseTargetsTest(unittest.TestCase):
    def test_default_builds_both_packs(self):
        self.assertEqual([target.name for target in parse_targets([])], ["1.20.5", "1.20.1"])

    def test_single_target(self):
        for name in TARGETS:
            with self.subTest(target=name):
                self.assertEqual([target.name for target in parse_targets(["--target", name])], [name])

    def test_unknown_or_removed_target_lists_available_targets(self):
        for name in ("1.22", "26.1"):
            with self.subTest(target=name):
                stderr = StringIO()
                with redirect_stderr(stderr), self.assertRaises(SystemExit) as ctx:
                    parse_targets(["--target", name])
                self.assertEqual(ctx.exception.code, 2)
                for available in TARGETS:
                    self.assertIn(available, stderr.getvalue())


class PackMetaTest(unittest.TestCase):
    def test_single_legacy_format_has_no_range_fields(self):
        meta = pack_meta(make_target(("1.21.1",)))["pack"]
        self.assertEqual(meta, {"pack_format": 34, "description": DESCRIPTION})

    def test_registered_1201_covers_1201_to_1204(self):
        meta = pack_meta(TARGETS["1.20.1"])["pack"]
        self.assertEqual(meta["pack_format"], 15)
        self.assertEqual(meta["supported_formats"], {"min_inclusive": 15, "max_inclusive": 22})
        self.assertNotIn("min_format", meta)
        self.assertNotIn("max_format", meta)

    def test_registered_1205_covers_1205_to_2612(self):
        meta = pack_meta(TARGETS["1.20.5"])["pack"]
        self.assertEqual(meta["pack_format"], 32)
        self.assertEqual(meta["supported_formats"], {"min_inclusive": 32, "max_inclusive": 84})
        self.assertEqual((meta["min_format"], meta["max_format"]), (32, 84))

    def test_legacy_range_uses_supported_formats(self):
        meta = pack_meta(make_target(("1.21", "1.21.8"), low=34, high=64))["pack"]
        self.assertEqual(meta["supported_formats"], {"min_inclusive": 34, "max_inclusive": 64})
        self.assertNotIn("min_format", meta)
        self.assertNotIn("max_format", meta)

    def test_cross_format_range_keeps_both_field_sets(self):
        meta = pack_meta(make_target(("1.21", "1.21.11"), low=34, high=75))["pack"]
        self.assertEqual(meta["pack_format"], 34)
        self.assertEqual(meta["supported_formats"], {"min_inclusive": 34, "max_inclusive": 75})
        self.assertEqual((meta["min_format"], meta["max_format"]), (34, 75))

    def test_modern_range_drops_supported_formats(self):
        meta = pack_meta(make_target(low=69, high=84))["pack"]
        self.assertEqual(meta["pack_format"], 69)
        self.assertNotIn("supported_formats", meta)
        self.assertEqual((meta["min_format"], meta["max_format"]), (69, 84))

    def test_format_range_must_not_be_reversed(self):
        with self.assertRaises(ValueError):
            make_target(low=42, high=34)


class OutputNameTest(unittest.TestCase):
    def test_registered_target_names(self):
        self.assertEqual(output_path(TARGETS["1.20.5"]).name, f"SiyuanHei-SC-MC1.20.5-26.1.2-v{VERSION}.zip")
        self.assertEqual(output_path(TARGETS["1.20.1"]).name, f"SiyuanHei-SC-MC1.20.1-1.20.4-v{VERSION}.zip")

    def test_label_uses_first_and_last_version(self):
        self.assertEqual(TARGETS["1.20.5"].label, "1.20.5-26.1.2")

    def test_modern_pack_includes_mc26_versions(self):
        self.assertEqual(TARGETS["1.20.5"].versions[-3:], ("26.1", "26.1.1", "26.1.2"))
        self.assertEqual(len(TARGETS), 2)


class FontConfigTest(unittest.TestCase):
    def test_modern_pack_keeps_uniform_filter(self):
        providers = font_config(TARGETS["1.20.5"])["providers"]
        self.assertEqual([provider["id"] for provider in providers], PROVIDER_IDS)
        filtered = [provider for provider in providers if "filter" in provider]
        self.assertEqual(
            [provider["id"] for provider in filtered],
            ["minecraft:siyuan_bitmap", "minecraft:include/default"],
        )
        for provider in filtered:
            self.assertEqual(provider["filter"], {"uniform": False})

    def test_registered_1201_omits_filter(self):
        providers = font_config(TARGETS["1.20.1"])["providers"]
        self.assertEqual([provider["id"] for provider in providers], PROVIDER_IDS)
        self.assertTrue(all("filter" not in provider for provider in providers))


if __name__ == "__main__":
    unittest.main()
