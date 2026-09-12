"""Read-only checks for albums intended for transfer to an iPhone music library."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from music_converter.naming import output_filename


# These are the normal local-file formats accepted by the Apple Music/iPhone
# music library.  FLAC is deliberately absent: it may play in third-party apps,
# but cannot be synced as a Music-library track without conversion.
IPHONE_AUDIO_FORMATS = {
    (".m4a", "aac"),
    (".m4a", "alac"),
    (".mp3", "mp3"),
    (".wav", "pcm_s16le"),
    (".wav", "pcm_s24le"),
    (".wav", "pcm_s32le"),
    (".aif", "pcm_s16be"),
    (".aiff", "pcm_s16be"),
}
SUPPORTED_AUDIO_SUFFIXES = {suffix for suffix, _ in IPHONE_AUDIO_FORMATS} | {".flac"}
REQUIRED_TAGS = ("title", "artist", "album", "album_artist", "date", "track", "disc")
TRACK_FILENAME = re.compile(r"^(?P<number>\d{1,3})\.\s+(?P<artist>.+?)\s+-\s+(?P<title>.+)$")
OUTPUT_FILENAME = re.compile(r"^(?P<number>\d{1,3})\s+-\s+(?P<title>.+)$")
NUMBER_PAIR = re.compile(r"^(?P<number>\d+)(?:\s*/\s*(?P<total>\d+))?$")


@dataclass(frozen=True)
class VerificationIssue:
    path: Path
    message: str


@dataclass(frozen=True)
class VerificationReport:
    tracks_checked: int
    issues: tuple[VerificationIssue, ...]

    @property
    def ready_for_iphone(self) -> bool:
        return not self.issues


def _probe(path: Path) -> tuple[str, dict[str, str]]:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=format_name:format_tags:stream=codec_type,codec_name", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise ValueError(f"ffprobe could not read {path}: {result.stderr.strip()}")
    try:
        data = json.loads(result.stdout)
        audio = next(stream for stream in data["streams"] if stream["codec_type"] == "audio")
        return str(audio["codec_name"]), {
            str(key).lower(): str(value).strip() for key, value in data["format"].get("tags", {}).items()
        }
    except (KeyError, StopIteration, TypeError, json.JSONDecodeError) as error:
        raise ValueError(f"ffprobe returned no usable audio stream for {path}.") from error


def _number_pair(value: str) -> tuple[int, int | None] | None:
    match = NUMBER_PAIR.fullmatch(value.strip())
    if not match:
        return None
    return int(match["number"]), int(match["total"]) if match["total"] else None


def _tag_number_pair(tags: dict[str, str], name: str) -> tuple[int, int | None] | None:
    """Read either ``1/13`` or the Vorbis ``NUMBER``/``NUMBERTOTAL`` form."""
    pair = _number_pair(tags.get(name, ""))
    if pair is None:
        return None
    separate_total = _number_pair(tags.get(f"{name}total", ""))
    if separate_total is not None:
        if separate_total[1] is not None or separate_total[0] <= 0:
            return None
        return pair[0], separate_total[0]
    return pair


def verify_iphone_album(album_directory: Path) -> VerificationReport:
    """Check Disc 1/Disc 2 audio files and their iPhone-library metadata.

    The directory is never changed.  Metadata is checked for presence,
    disc/track numbering, consistency across the release, and agreement with
    the numbered ``Artist - Title`` file names.
    """
    album_directory = album_directory.expanduser()
    disc_directories = [path for path in sorted(album_directory.iterdir()) if path.is_dir() and re.fullmatch(r"Disc \d+", path.name)]
    if not disc_directories:
        disc_directories = [album_directory]

    issues: list[VerificationIssue] = []
    albums: set[str] = set()
    album_artists: set[str] = set()
    dates: set[str] = set()
    tracks_checked = 0
    disc_total = len(disc_directories)

    for expected_disc, disc_directory in enumerate(disc_directories, start=1):
        audio_files = sorted(
            path for path in disc_directory.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_AUDIO_SUFFIXES
        )
        if not audio_files:
            issues.append(VerificationIssue(disc_directory, "contains no audio files"))
            continue
        for expected_track, path in enumerate(audio_files, start=1):
            tracks_checked += 1
            codec, tags = _probe(path)
            if (path.suffix.lower(), codec) not in IPHONE_AUDIO_FORMATS:
                issues.append(VerificationIssue(path, f"{path.suffix} / {codec} is not transferable to the iPhone Music library; convert to AAC/M4A, ALAC/M4A, or MP3"))
            for tag in REQUIRED_TAGS:
                if not tags.get(tag):
                    issues.append(VerificationIssue(path, f"missing {tag} metadata"))
            if tags.get("album"):
                albums.add(tags["album"])
            if tags.get("album_artist"):
                album_artists.add(tags["album_artist"])
            if tags.get("date"):
                dates.add(tags["date"])
            track = _tag_number_pair(tags, "track")
            if track is None or track[0] != expected_track or track[1] != len(audio_files):
                found = tags.get("track", "missing")
                if tags.get("tracktotal"):
                    found += f" (total {tags['tracktotal']})"
                issues.append(VerificationIssue(path, f"track metadata must be {expected_track}/{len(audio_files)} (found {found})"))
            disc = _tag_number_pair(tags, "disc")
            if disc is None or disc[0] != expected_disc or disc[1] != disc_total:
                found = tags.get("disc", "missing")
                if tags.get("disctotal"):
                    found += f" (total {tags['disctotal']})"
                issues.append(VerificationIssue(path, f"disc metadata must be {expected_disc}/{disc_total} (found {found})"))
            filename = TRACK_FILENAME.fullmatch(path.stem)
            converted_filename = OUTPUT_FILENAME.fullmatch(path.stem)
            if filename or converted_filename:
                expected_title = filename["title"] if filename else None
                if converted_filename and tags.get("title"):
                    expected_title = output_filename(int(converted_filename["number"]), tags["title"]).removesuffix(".m4a").split(" - ", 1)[1]
                if tags.get("title") and tags["title"] != expected_title:
                    if filename:
                        issues.append(VerificationIssue(path, "title metadata does not match the filename"))
                if converted_filename and tags.get("title") and path.name != output_filename(int(converted_filename["number"]), tags["title"]):
                    issues.append(VerificationIssue(path, "filename is not the project's safe title-based output name"))
                if filename and tags.get("artist") and tags["artist"] != filename["artist"]:
                    issues.append(VerificationIssue(path, "artist metadata does not match the filename"))
            else:
                issues.append(VerificationIssue(path, "filename is not in 'NN. Artist - Title' or 'NN - Title' form"))

    for label, values in (("album", albums), ("album_artist", album_artists), ("date", dates)):
        if len(values) > 1:
            issues.append(VerificationIssue(album_directory, f"{label} metadata is inconsistent across discs: {', '.join(sorted(values))}"))
    return VerificationReport(tracks_checked, tuple(issues))
