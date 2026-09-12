from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from music_converter.workflows.single_flac_album import SingleFlacAlbumWorkflow


class MultiTrackWorkflowTests(unittest.TestCase):
    @patch("music_converter.workflows.single_flac_album.run_command")
    @patch("music_converter.workflows.single_flac_album.probe_duration", return_value=120.0)
    @patch("music_converter.workflows.single_flac_album.probe_tags")
    @patch("music_converter.workflows.single_flac_album.require_media_tools")
    def test_converts_split_flacs_with_per_disc_totals(self, _tools, tags, _duration, run) -> None:
        tags.side_effect = [
            {"title": "One", "artist": "Artist", "album": "Album", "album_artist": "Artist", "date": "2018"},
            {"title": "Two", "artist": "Artist", "album": "Album", "album_artist": "Artist", "date": "2018"},
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            for disc, name in (("Disc 1", "01. Artist - One.flac"), ("Disc 2", "01. Artist - Two.flac")):
                directory = root / disc
                directory.mkdir(parents=True)
                (directory / name).touch()
            (root / "cover.jpg").touch()
            output_root = Path(temporary) / "output"
            output_root.mkdir()
            SingleFlacAlbumWorkflow().run(root, output_root=output_root)
        self.assertEqual(run.call_count, 2)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertIn("track=1/1", commands[0])
        self.assertIn("disc=1/2", commands[0])
        self.assertIn("disc=2/2", commands[1])

    @patch("music_converter.workflows.single_flac_album.run_command")
    @patch("music_converter.workflows.single_flac_album.probe_duration", return_value=120.0)
    @patch("music_converter.workflows.single_flac_album.probe_tags", return_value={"title": "Song", "artist": "Artist", "album": "Album"})
    @patch("music_converter.workflows.single_flac_album.require_media_tools")
    def test_uses_track_artist_when_album_artist_is_missing(self, _tools, _tags, _duration, run) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            root.mkdir()
            (root / "01. Artist - Song.flac").touch()
            (root / "cover.jpg").touch()
            output_root = Path(temporary) / "output"
            output_root.mkdir()
            SingleFlacAlbumWorkflow().run(root, output_root=output_root)
        self.assertIn("album_artist=Artist", run.call_args.args[0])
