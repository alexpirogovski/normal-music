"""Convert a single-FLAC album described by a CUE sheet."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from music_converter.cue import parse_cue
from music_converter.discovery import discover_source_files
from music_converter.media import build_ffmpeg_command, probe_duration, require_media_tools, run_command
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
