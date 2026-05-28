from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


INVALID_FILENAME_CHARS = r'[<>:"/\\|?*\x00-\x1f]'


def safe_filename(value: str, fallback: str = "project") -> str:
    cleaned = re.sub(INVALID_FILENAME_CHARS, "_", value or "").strip()
    cleaned = re.sub(r"\s+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("._ ")
    return cleaned[:80] or fallback


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M")


def ensure_dir(path: str | Path) -> Path:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def write_text(path: str | Path, content: str) -> Path:
    target = Path(path)
    ensure_dir(target.parent)
    target.write_text(content or "", encoding="utf-8")
    return target


def read_text(path: str | Path, default: str = "") -> str:
    target = Path(path)
    if not target.exists():
        return default
    return target.read_text(encoding="utf-8")


def save_json(path: str | Path, data: Any) -> Path:
    target = Path(path)
    ensure_dir(target.parent)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def load_json(path: str | Path, default: Any = None) -> Any:
    target = Path(path)
    if not target.exists():
        return default
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def copy_file(source: str | Path, destination: str | Path) -> Path | None:
    src = Path(source)
    if not src.exists() or not src.is_file():
        return None
    dst = Path(destination)
    ensure_dir(dst.parent)
    shutil.copy2(src, dst)
    return dst


def unique_path(path: str | Path) -> Path:
    target = Path(path)
    if not target.exists():
        return target
    stem, suffix = target.stem, target.suffix
    for index in range(1, 1000):
        candidate = target.with_name(f"{stem}_{index}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not create unique path for {target}")
