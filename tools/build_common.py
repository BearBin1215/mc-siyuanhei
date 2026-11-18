"""两个构建脚本共用的路径、校验与打包逻辑。"""

import json
import operator
import sys
import zipfile
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parent.parent
VERSION = "0.1.0"
VERSION_PLACEHOLDER = "<version>"  # README 里代替具体版本号
PACK_FORMAT = 84
FIXED_DATE_TIME = (1980, 1, 1, 0, 0, 0)
SHARED_FILES = ("README.md", "LICENSE", "LICENSE-OFL.txt")  # 两个变体都随包分发


def fail(message: str) -> NoReturn:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def output_path(variant: str) -> Path:
    return ROOT / "dist" / f"SiyuanHei-SC-{variant}-MC26.1-v{VERSION}.zip"


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


def load_pack_meta(path: Path, label: str) -> None:
    """校验 pack.mcmeta：三个格式字段必须同为 PACK_FORMAT，且不得使用 supported_formats。"""
    require_file(path)
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))["pack"]
    except (OSError, TypeError, ValueError, KeyError) as exc:
        fail(f"{label} is not a readable pack.mcmeta: {exc}")
    if not isinstance(meta, dict):
        fail(f'{label} has no "pack" object')
    for key in ("pack_format", "min_format", "max_format"):
        if meta.get(key) != PACK_FORMAT:
            fail(f"{label} {key} must be {PACK_FORMAT} (Minecraft 26.1.x)")
    if "supported_formats" in meta:
        fail(f"{label} must not use supported_formats for resource pack format >= 65")


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
