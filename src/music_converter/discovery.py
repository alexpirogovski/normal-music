"""Input layout discovery and validation."""

from __future__ import annotations

from pathlib import Path

from music_converter.models import SourceFiles


def discover_source_files(directory: Path) -> SourceFiles:
    directory = directory.expanduser()
    if not directory.is_dir():
        raise ValueError(f"Source directory does not exist or is not a directory: {directory}")

    files = [path for path in directory.iterdir() if path.is_file()]
    flacs = [path for path in files if path.suffix.casefold() == ".flac"]
    cues = [path for path in files if path.suffix.casefold() == ".cue"]
    title_files = [path for path in files if path.name.casefold() == "foo_dr.txt"]
    covers = [
        path
        for path in files
        if path.stem.casefold() in {"cover", "folder"} and path.suffix.casefold() in {".jpg", ".jpeg"}
    ]
    _require_exactly_one("FLAC file", flacs, directory)
    _require_exactly_one("CUE sheet", cues, directory)
    if len(title_files) > 1:
        _require_exactly_one("foo_dr.txt file", title_files, directory)
    _require_exactly_one("cover image named cover.jpg, cover.jpeg, folder.jpg, or folder.jpeg", covers, directory)
    return SourceFiles(directory, flacs[0], cues[0], title_files[0] if title_files else None, covers[0])


def _require_exactly_one(kind: str, matches: list[Path], directory: Path) -> None:
    if len(matches) != 1:
        found = ", ".join(path.name for path in matches) or "none"
        raise ValueError(f"Expected exactly one {kind} in {directory}; found: {found}.")
