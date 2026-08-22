"""Typed data shared by conversion operations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CueTrack:
    number: int
    index_seconds: float
    title: str | None = None
    performer: str | None = None


@dataclass(frozen=True)
class CueAlbum:
    title: str | None
    performer: str | None
    year: str | None
    file_name: str | None
    tracks: tuple[CueTrack, ...]


@dataclass(frozen=True)
class SourceFiles:
    directory: Path
    flac: Path
    cue: Path
    titles: Path | None
    cover: Path


@dataclass(frozen=True)
class TrackMetadata:
    title: str
    track_number: int
    track_total: int
    album_title: str
    album_artist: str
    track_artist: str
    year: str | None
    disc_number: int = 1
    disc_total: int = 1


@dataclass(frozen=True)
class ConversionTrack:
    metadata: TrackMetadata
    start_seconds: float
    duration_seconds: float
    output_path: Path
