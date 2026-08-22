from pathlib import Path
import tempfile
import unittest

from music_converter.discovery import discover_source_files
from music_converter.media import build_ffmpeg_command
from music_converter.models import ConversionTrack, TrackMetadata
from music_converter.naming import DEFAULT_OUTPUT_ROOT, output_directory, output_filename


class OperationTests(unittest.TestCase):
    def test_output_filename_is_stable_and_safe(self) -> None:
        self.assertEqual(output_filename(1, 'A/B: "Song"'), "01 - A-B- -Song-.m4a")

    def test_empty_safe_filename_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            output_filename(1, "///")

    def test_ffmpeg_command_has_aac_tags_and_attached_cover(self) -> None:
        metadata = TrackMetadata("Song", 1, 2, "Album", "Album Artist", "Track Artist", "1990")
        track = ConversionTrack(metadata, 0.0, 120.0, Path("/output/01 - Song.m4a"))
        command = build_ffmpeg_command(Path("/input.flac"), Path("/cover.jpg"), track)
        self.assertEqual(command[:2], ["ffmpeg", "-hide_banner"])
        self.assertIn("attached_pic", command)
        self.assertIn("track=1/2", command)
        self.assertIn("album_artist=Album Artist", command)
        self.assertEqual(command[-1], "/output/01 - Song.m4a")

    def test_discovery_requires_one_of_each_input(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            for name in ("album.flac", "album.cue", "foo_dr.txt", "cover.jpg"):
                (temporary_path / name).touch()
            source = discover_source_files(temporary_path)
        self.assertEqual(source.flac.name, "album.flac")

    def test_discovery_allows_folder_art_without_a_title_list(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            for name in ("album.flac", "album.cue", "folder.jpg"):
                (temporary_path / name).touch()
            source = discover_source_files(temporary_path)
        self.assertIsNone(source.titles)
        self.assertEqual(source.cover.name, "folder.jpg")

    def test_metadata_has_apple_music_grouping_defaults(self) -> None:
        metadata = TrackMetadata("Song", 3, 12, "Album", "Artist", "Artist", "1990")
        self.assertEqual((metadata.track_number, metadata.track_total), (3, 12))
        self.assertEqual((metadata.disc_number, metadata.disc_total), (1, 1))

    def test_output_directory_can_use_an_explicit_root(self) -> None:
        self.assertEqual(
            output_directory(Path("/source/album"), Path("/music")),
            Path("/music/album - AAC M4A"),
        )

    def test_output_directory_uses_music_root_by_default(self) -> None:
        self.assertEqual(
            output_directory(Path("/source/album")),
            DEFAULT_OUTPUT_ROOT / "album - AAC M4A",
        )
