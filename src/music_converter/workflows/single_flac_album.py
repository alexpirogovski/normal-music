"""Convert a single-FLAC album described by a CUE sheet."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
import re

from music_converter.cue import parse_cue
from music_converter.discovery import discover_source_files
from music_converter.media import build_ffmpeg_command, probe_duration, probe_tags, require_media_tools, run_command
from music_converter.models import ConversionTrack, CueAlbum, SourceFiles, TrackMetadata
from music_converter.naming import output_directory, output_filename
from music_converter.titles import parse_foobar_dr_titles


class SingleFlacAlbumWorkflow:
    def run(
        self,
        source_directory: Path,
        *,
        output_root: Path | None = None,
        plan_only: bool = False,
    ) -> int:
        require_media_tools()
        source_directory = source_directory.expanduser()
        if not source_directory.is_dir():
            raise ValueError(f"Source directory does not exist or is not a directory: {source_directory}")
        if not list(source_directory.glob("*.cue")):
            return self._run_multiple_tracks(source_directory, output_root, plan_only)
        source = discover_source_files(source_directory)
        cue = parse_cue(source.cue)
        cue_file_name = Path(cue.file_name.replace("\\", "/")).name if cue.file_name else None
        if cue_file_name and cue_file_name.casefold() != source.flac.name.casefold():
            raise ValueError(
                f"CUE references {cue.file_name!r}, but the discovered FLAC is {source.flac.name!r}."
            )
        titles = parse_foobar_dr_titles(source.titles) if source.titles else self._cue_titles(cue)
        if len(titles) != len(cue.tracks):
            raise ValueError(
                f"Track count differs: CUE has {len(cue.tracks)}, foo_dr.txt has {len(titles)}."
            )
        if not cue.title or not cue.performer:
            raise ValueError("CUE sheet must provide album TITLE and PERFORMER.")
        duration = probe_duration(source.flac)
        plan = self._build_plan(source.directory, cue, titles, duration)
        if output_root is not None and not output_root.expanduser().is_dir():
            raise ValueError(f"Output root does not exist or is not a directory: {output_root}")
        destination = output_directory(source.directory, output_root)
        self._validate_destination(destination, plan)
        self._print_plan(cue.title, cue.performer, source, plan, destination)
        if plan_only:
            return 0

        temporary = destination.parent / f".{destination.name}.partial-{uuid.uuid4().hex}"
        temporary.mkdir()
        try:
            for track in plan:
                output = temporary / track.output_path.name
                runnable = ConversionTrack(track.metadata, track.start_seconds, track.duration_seconds, output)
                print(
                    f"Converting {track.metadata.track_number}/{track.metadata.track_total}: {track.metadata.title}",
                    flush=True,
                )
                run_command(build_ffmpeg_command(source.flac, source.cover, runnable))
            temporary.rename(destination)
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise
        print(f"Created: {destination}", flush=True)
        return 0

    def _run_multiple_tracks(self, source_directory: Path, output_root: Path | None, plan_only: bool) -> int:
        """Convert separately ripped FLAC tracks, including ``Disc N`` folders."""
        flacs = sorted(path for path in source_directory.rglob("*") if path.is_file() and path.suffix.casefold() == ".flac")
        if not flacs:
            raise ValueError(f"No FLAC tracks found in {source_directory}.")
        cover = self._find_cover(source_directory)
        disc_paths = sorted({path.parent for path in flacs})
        if len(disc_paths) > 1 and any(not re.fullmatch(r"Disc \d+", path.name) for path in disc_paths):
            raise ValueError("Multiple-track albums may use only 'Disc N' directories beneath the source directory.")
        disc_numbers = {directory: index for index, directory in enumerate(disc_paths, start=1)}
        plan: list[ConversionTrack] = []
        sources: dict[Path, Path] = {}
        for directory in disc_paths:
            tracks = sorted(path for path in flacs if path.parent == directory)
            for number, source in enumerate(tracks, start=1):
                tags = probe_tags(source)
                missing = [tag for tag in ("title", "artist", "album") if not tags.get(tag)]
                if missing:
                    raise ValueError(f"{source.name} is missing required metadata: {', '.join(missing)}.")
                metadata = TrackMetadata(
                    title=tags["title"], track_number=number, track_total=len(tracks),
                    album_title=tags["album"], album_artist=tags.get("album_artist") or tags["artist"],
                    track_artist=tags["artist"], year=tags.get("date") or tags.get("year"),
                    disc_number=disc_numbers[directory], disc_total=len(disc_paths),
                )
                relative_parent = directory.relative_to(source_directory)
                output = relative_parent / output_filename(number, metadata.title)
                plan.append(ConversionTrack(metadata, 0.0, probe_duration(source), output))
                sources[output] = source
        albums = {track.metadata.album_title for track in plan}
        album_artists = {track.metadata.album_artist for track in plan}
        if len(albums) != 1 or len(album_artists) != 1:
            raise ValueError("Multiple-track album metadata must use one album title and one album artist.")
        if output_root is not None and not output_root.expanduser().is_dir():
            raise ValueError(f"Output root does not exist or is not a directory: {output_root}")
        destination = output_directory(source_directory, output_root)
        self._validate_destination(destination, plan)
        print(f"Album: {plan[0].metadata.album_artist} — {plan[0].metadata.album_title}", flush=True)
        print(f"Input: {len(plan)} FLAC track(s); cover: {cover.name}", flush=True)
        print(f"Output: {destination}", flush=True)
        if plan_only:
            return 0
        temporary = destination.parent / f".{destination.name}.partial-{uuid.uuid4().hex}"
        temporary.mkdir()
        try:
            for track in plan:
                output = temporary / track.output_path
                output.parent.mkdir(parents=True, exist_ok=True)
                source = sources[track.output_path]
                print(f"Converting disc {track.metadata.disc_number}, {track.metadata.track_number}/{track.metadata.track_total}: {track.metadata.title}", flush=True)
                runnable = ConversionTrack(track.metadata, 0.0, track.duration_seconds, output)
                run_command(build_ffmpeg_command(source, cover, runnable))
            temporary.rename(destination)
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise
        print(f"Created: {destination}", flush=True)
        return 0

    def _find_cover(self, directory: Path) -> Path:
        covers = [
            path for path in directory.iterdir() if path.is_file()
            and path.stem.casefold() in {"cover", "folder"}
            and path.suffix.casefold() in {".jpg", ".jpeg"}
        ]
        if len(covers) != 1:
            found = ", ".join(path.name for path in covers) or "none"
            raise ValueError(f"Expected exactly one cover image in {directory}; found: {found}.")
        return covers[0]

    def _cue_titles(self, cue: CueAlbum) -> list[str]:
        missing = [str(track.number) for track in cue.tracks if not track.title]
        if missing:
            raise ValueError(
                "No foo_dr.txt was found and the CUE sheet has no TITLE for track(s): "
                f"{', '.join(missing)}."
            )
        return [track.title for track in cue.tracks if track.title]

    def _build_plan(self, directory: Path, cue: CueAlbum, titles: list[str], album_duration: float) -> list[ConversionTrack]:
        tracks = cue.tracks
        plan: list[ConversionTrack] = []
        for index, cue_track in enumerate(tracks):
            start = cue_track.index_seconds
            end = tracks[index + 1].index_seconds if index + 1 < len(tracks) else album_duration
            if end <= start:
                raise ValueError(f"CUE timestamps are not increasing at track {cue_track.number:02d}.")
            metadata = TrackMetadata(
                title=titles[index], track_number=cue_track.number, track_total=len(tracks),
                album_title=cue.title, album_artist=cue.performer,
                track_artist=cue_track.performer or cue.performer, year=cue.year,
            )
            plan.append(ConversionTrack(metadata, start, end - start, directory / output_filename(cue_track.number, titles[index])))
        return plan

    def _validate_destination(self, destination: Path, plan: list[ConversionTrack]) -> None:
        if destination.exists():
            raise ValueError(f"Output directory already exists and will not be overwritten: {destination}")
        names = [track.output_path.name.casefold() for track in plan]
        if len(set(names)) != len(names):
            raise ValueError("Track titles would produce duplicate output filenames.")

    def _print_plan(self, title: str, artist: str, source: SourceFiles, plan: list[ConversionTrack], destination: Path) -> None:
        print(f"Album: {artist} — {title}", flush=True)
        print(f"Input: {source.flac.name}; cover: {source.cover.name}", flush=True)
        print(f"Output: {destination}", flush=True)
        for track in plan:
            print(
                f"  {track.metadata.track_number:02d}. {track.metadata.title} ({track.duration_seconds:.2f}s)",
                flush=True,
            )
