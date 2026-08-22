"""Parser for the subset of text CUE needed by the single-FLAC workflow."""

from __future__ import annotations

import re
from pathlib import Path

from music_converter.models import CueAlbum, CueTrack

_REM_DATE = re.compile(r"^REM\s+DATE\s+(?:\"(?P<quoted>.*)\"|(?P<plain>\S+))\s*$", re.I)
_FIELD = re.compile(r"^(?P<field>PERFORMER|TITLE)\s+(?:\"(?P<quoted>.*)\"|(?P<plain>.+?))\s*$", re.I)
_TRACK = re.compile(r"^TRACK\s+(?P<number>\d{1,3})\s+AUDIO\s*$", re.I)
_INDEX = re.compile(r"^INDEX\s+01\s+(?P<time>\d{1,3}:\d{2}:\d{2})\s*$", re.I)
_FILE = re.compile(r"^FILE\s+(?:\"(?P<quoted>.*)\"|(?P<plain>\S+))\s+\S+\s*$", re.I)


def parse_cue(path: Path) -> CueAlbum:
    lines = _read_text(path).splitlines()
    album_title: str | None = None
    album_performer: str | None = None
    year: str | None = None
    file_name: str | None = None
    tracks: list[CueTrack] = []
    current_number: int | None = None
    current_performer: str | None = None
    current_title: str | None = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        date_match = _REM_DATE.match(line)
        if date_match and current_number is None:
            year = _value(date_match)
            continue
        file_match = _FILE.match(line)
        if file_match:
            file_name = _value(file_match)
            continue
        track_match = _TRACK.match(line)
        if track_match:
            if current_number is not None:
                raise ValueError(f"CUE sheet has TRACK {current_number:02d} without INDEX 01.")
            current_number = int(track_match.group("number"))
            current_performer = None
            current_title = None
            continue
        field_match = _FIELD.match(line)
        if field_match:
            value = _value(field_match)
            if current_number is None:
                if field_match.group("field").upper() == "TITLE":
                    album_title = value
                else:
                    album_performer = value
            elif field_match.group("field").upper() == "PERFORMER":
                current_performer = value
            else:
                current_title = value
            continue
        index_match = _INDEX.match(line)
        if index_match and current_number is not None:
            tracks.append(
                CueTrack(
                    current_number,
                    cue_time_to_seconds(index_match.group("time")),
                    current_title,
                    current_performer,
                )
            )
            current_number = None

    if current_number is not None:
        raise ValueError(f"CUE sheet has TRACK {current_number:02d} without INDEX 01.")
    if not tracks:
        raise ValueError("CUE sheet contains no AUDIO tracks with INDEX 01.")
    expected = list(range(1, len(tracks) + 1))
    if [track.number for track in tracks] != expected:
        raise ValueError("CUE track numbers must be consecutive and start at 01.")
    return CueAlbum(album_title, album_performer, year, file_name, tuple(tracks))


def cue_time_to_seconds(value: str) -> float:
    minutes, seconds, frames = (int(part) for part in value.split(":"))
    if seconds >= 60 or frames >= 75:
        raise ValueError(f"Invalid CUE timestamp: {value}")
    return minutes * 60 + seconds + frames / 75


def _read_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            pass
    raise ValueError(f"Cannot decode CUE sheet as UTF-8 or Windows-1252: {path}")


def _value(match: re.Match[str]) -> str:
    return (match.group("quoted") or match.group("plain") or "").strip()
