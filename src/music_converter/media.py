"""Media probing and FFmpeg command construction/execution."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Sequence

from music_converter.models import ConversionTrack


def require_media_tools() -> None:
    missing = [tool for tool in ("ffmpeg", "ffprobe") if shutil.which(tool) is None]
    if missing:
        raise ValueError(f"Required executable(s) not found on PATH: {', '.join(missing)}.")


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise ValueError(f"ffprobe could not read {path.name}: {result.stderr.strip()}")
    try:
        duration = float(json.loads(result.stdout)["format"]["duration"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError(f"ffprobe returned no usable duration for {path.name}.") from error
    if duration <= 0:
        raise ValueError(f"ffprobe returned an invalid duration for {path.name}.")
    return duration


def probe_tags(path: Path) -> dict[str, str]:
    """Return normalized container tags for one audio file."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format_tags", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise ValueError(f"ffprobe could not read {path.name}: {result.stderr.strip()}")
    try:
        return {
            str(key).lower(): str(value).strip()
            for key, value in json.loads(result.stdout)["format"].get("tags", {}).items()
        }
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError(f"ffprobe returned no usable metadata for {path.name}.") from error


def build_ffmpeg_command(source: Path, cover: Path, track: ConversionTrack) -> list[str]:
    metadata = track.metadata
    command = [
        "ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-ss", f"{track.start_seconds:.6f}",
        "-t", f"{track.duration_seconds:.6f}", "-i", str(source), "-i", str(cover),
        "-map", "0:a:0", "-map", "1:v:0", "-c:a", "aac", "-b:a", "256k", "-c:v", "mjpeg",
        "-disposition:v:0", "attached_pic", "-metadata", f"title={metadata.title}",
        "-metadata", f"track={metadata.track_number}/{metadata.track_total}",
        "-metadata", f"album={metadata.album_title}", "-metadata", f"album_artist={metadata.album_artist}",
        "-metadata", f"artist={metadata.track_artist}",
        "-metadata", f"disc={metadata.disc_number}/{metadata.disc_total}",
    ]
    if metadata.year:
        command.extend(["-metadata", f"date={metadata.year}"])
    command.extend(["-movflags", "+faststart", str(track.output_path)])
    return command


def run_command(command: Sequence[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        detail = result.stderr.strip() or "unknown FFmpeg error"
        raise ValueError(f"FFmpeg failed: {detail}")
