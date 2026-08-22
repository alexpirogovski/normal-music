"""Stable, filesystem-safe M4A output naming."""

from __future__ import annotations

import re
from pathlib import Path

_UNSAFE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_SPACE = re.compile(r"\s+")
DEFAULT_OUTPUT_ROOT = Path("/mnt/f/Music")


def output_filename(track_number: int, title: str) -> str:
    if not _UNSAFE.sub("", title).strip(" ."):
        raise ValueError(f"Track {track_number} has a title unsuitable for a filename.")
    cleaned = _SPACE.sub(" ", _UNSAFE.sub("-", title)).strip(" .")
    if not cleaned:
        raise ValueError(f"Track {track_number} has a title unsuitable for a filename.")
    return f"{track_number:02d} - {cleaned}.m4a"


def output_directory(source_directory: Path, output_root: Path | None = None) -> Path:
    root = output_root.expanduser() if output_root else DEFAULT_OUTPUT_ROOT
    return root / f"{source_directory.name} - AAC M4A"
