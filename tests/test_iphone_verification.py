import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from music_converter.iphone_verification import verify_iphone_album


def probe(codec: str, **tags: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        [], 0,
        json.dumps({"format": {"tags": tags}, "streams": [{"codec_type": "audio", "codec_name": codec}]}),
        "",
    )


class IPhoneVerificationTests(unittest.TestCase):
    def make_album(self, root: Path) -> Path:
        for disc in ("Disc 1", "Disc 2"):
            directory = root / disc
            directory.mkdir()
            (directory / "01. Artist - Song.m4a").touch()
        return root

    @patch("music_converter.iphone_verification.subprocess.run")
    def test_reports_a_complete_m4a_album_as_ready(self, run: unittest.mock.Mock) -> None:
        def result(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            disc = "1/2" if "Disc 1" in str(command[-1]) else "2/2"
            return probe("aac", title="Song", artist="Artist", album="Album", album_artist="Artist", date="2018", track="1/1", disc=disc)

        run.side_effect = result
        with tempfile.TemporaryDirectory() as temporary:
            report = verify_iphone_album(self.make_album(Path(temporary)))
        self.assertTrue(report.ready_for_iphone)

    @patch("music_converter.iphone_verification.subprocess.run")
    def test_reports_flac_and_missing_metadata(self, run: unittest.mock.Mock) -> None:
        run.return_value = probe("flac", title="Song")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for disc in ("Disc 1", "Disc 2"):
                directory = root / disc
                directory.mkdir()
                (directory / "01. Artist - Song.flac").touch()
            report = verify_iphone_album(root)
        messages = [issue.message for issue in report.issues]
        self.assertTrue(any("not transferable" in message for message in messages))
        self.assertTrue(any("missing artist" in message for message in messages))

    @patch("music_converter.iphone_verification.subprocess.run")
    def test_accepts_vorbis_separate_total_tags(self, run: unittest.mock.Mock) -> None:
        def result(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            disc = "1" if "Disc 1" in str(command[-1]) else "2"
            return probe("aac", title="Song", artist="Artist", album="Album", album_artist="Artist", date="2018", track="1", tracktotal="1", disc=disc, disctotal="2")

        run.side_effect = result
        with tempfile.TemporaryDirectory() as temporary:
            report = verify_iphone_album(self.make_album(Path(temporary)))
        self.assertTrue(report.ready_for_iphone)

    @patch("music_converter.iphone_verification.subprocess.run")
    def test_accepts_project_m4a_filename_style(self, run: unittest.mock.Mock) -> None:
        run.return_value = probe("aac", title="Song", artist="Artist", album="Album", album_artist="Artist", date="2018", track="1/1", disc="1/1")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            disc = root / "Disc 1"
            disc.mkdir()
            (disc / "01 - Song.m4a").touch()
            report = verify_iphone_album(root)
        self.assertTrue(report.ready_for_iphone)

    @patch("music_converter.iphone_verification.subprocess.run")
    def test_accepts_single_disc_tracks_at_album_root(self, run: unittest.mock.Mock) -> None:
        run.return_value = probe("aac", title="Song", artist="Artist", album="Album", album_artist="Artist", date="2018", track="1/1", disc="1/1")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "01 - Song.m4a").touch()
            (root / "album.m3u").touch()
            report = verify_iphone_album(root)
        self.assertTrue(report.ready_for_iphone)
