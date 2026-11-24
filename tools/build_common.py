"""构建目标、元数据，以及构建脚本共用的路径、校验与打包逻辑。"""

import operator
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parent.parent
VERSION = "1.0"
VERSION_PLACEHOLDER = "<version>"  # README 里代替具体版本号
DESCRIPTION = "§6思源黑体 SC§r"
LEGACY_FORMAT_MAX = 64  # 格式 65 起使用 min_format/max_format；兼容旧版时仍须保留旧字段
FIXED_DATE_TIME = (1980, 1, 1, 0, 0, 0)
SHARED_FILES = ("README.md", "LICENSE", "LICENSE-OFL.txt")  # 随资源包分发


@dataclass(frozen=True)
class Target:
    """一个构建目标：共用配置的游戏版本、资源包格式范围与字体配置差异。"""

    name: str  # --target 参数
    versions: tuple[str, ...]  # 已验收的正式版；首尾用于产物命名
    min_format: int
    max_format: int
    uniform_filter: bool  # 字体提供器是否带 filter: {"uniform": false}

    def __post_init__(self) -> None:
        if not self.versions:
            raise ValueError(f"target {self.name} lists no game versions")
        if self.min_format > self.max_format:
            raise ValueError(f"target {self.name}: min_format must not exceed max_format")

    @property
    def label(self) -> str:
        first, last = self.versions[0], self.versions[-1]
        return first if first == last else f"{first}-{last}"


TARGETS = {
    target.name: target
    for target in (
        # 1.20.5–26.1.2 共用字体 filter，格式 32–84 跨新旧元数据。
        Target(
            "1.20.5",
            (
                "1.20.5",
                "1.20.6",
                "1.21",
                "1.21.1",
                "1.21.2",
                "1.21.3",
                "1.21.4",
                "1.21.5",
                "1.21.6",
                "1.21.7",
                "1.21.8",
                "1.21.9",
                "1.21.10",
                "1.21.11",
                "26.1",
                "26.1.1",
                "26.1.2",
            ),
            32,
            84,
            uniform_filter=True,
        ),
        # 1.20.1–1.20.4 的字体提供器不支持 filter（格式 15–22）
        Target("1.20.1", ("1.20.1", "1.20.2", "1.20.3", "1.20.4"), 15, 22, uniform_filter=False),
    )
}


def fail(message: str) -> NoReturn:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def output_path(target: Target) -> Path:
    return ROOT / "dist" / f"SiyuanHei-SC-MC{target.label}-v{VERSION}.zip"


def pack_meta(target: Target) -> dict[str, object]:
    """按目标格式范围生成 pack.mcmeta。

    旧格式（< 65）用 pack_format；范围跨多个旧格式时加 supported_formats。
    范围包含新格式（>= 65）时加 min_format/max_format，且不再禁止 supported_formats。
    """
    pack: dict[str, object] = {"pack_format": target.min_format}
    if target.min_format <= LEGACY_FORMAT_MAX and target.min_format != target.max_format:
        pack["supported_formats"] = {
            "min_inclusive": target.min_format,
            "max_inclusive": target.max_format,
        }
    if target.max_format > LEGACY_FORMAT_MAX:
        pack["min_format"] = target.min_format
        pack["max_format"] = target.max_format
    pack["description"] = DESCRIPTION
    return {"pack": pack}


def require_file(path: Path, label: str = "") -> None:
    """校验必需输入存在，缺失时以统一格式退出。"""
    if not path.is_file():
        fail(f"missing {label or path.relative_to(ROOT).as_posix()}")


def iter_files(root: Path, base: Path) -> list[tuple[Path, str]]:
    """枚举 root 下所有文件，附带相对 base 的 posix 路径作为 zip 条目名。"""
    return [(path, path.relative_to(base).as_posix()) for path in sorted(root.rglob("*")) if path.is_file()]


def check_readme(output: Path) -> None:
    """README 必须提到产物文件名：当前版本或带占位符的模板均可。"""
    readme = ROOT / "README.md"
    require_file(readme)
    text = readme.read_text(encoding="utf-8")
    templated = output.name.replace(f"v{VERSION}", f"v{VERSION_PLACEHOLDER}")
    if output.name not in text and templated not in text:
        fail(f"README.md must mention {templated}")


def write_zip(output: Path, entries: list[tuple[Path, str]], compresslevel: int) -> None:
    """写入 zip：条目按名排序并统一时间戳，相同输入得到相同字节。"""
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_name(output.name + ".tmp")
    try:
        with zipfile.ZipFile(tmp, "w") as zf:
            for source, arcname in sorted(entries, key=operator.itemgetter(1)):
                info = zipfile.ZipInfo(arcname, date_time=FIXED_DATE_TIME)
                info.create_system = 3
                info.external_attr = 0o644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(info, source.read_bytes(), compresslevel=compresslevel)
        tmp.replace(output)
    finally:
        tmp.unlink(missing_ok=True)
    print(f"built {output} ({output.stat().st_size / 1024 / 1024:.2f} MiB)")
