from pathlib import Path
import tempfile
import unittest

from music_converter.cue import cue_time_to_seconds, parse_cue
from music_converter.titles import parse_foobar_dr_titles


class ParsingTests(unittest.TestCase):
    def test_parses_cue_album_and_index_times(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cue = Path(temporary) / "album.cue"
            cue.write_text('REM DATE 1990\nPERFORMER "Artist"\nTITLE "Album"\nTRACK 01 AUDIO\nTITLE "First"\nINDEX 01 00:00:00\nTRACK 02 AUDIO\nTITLE "Second"\nPERFORMER "Guest"\nINDEX 01 01:02:37\n')
            result = parse_cue(cue)
        self.assertEqual((result.title, result.performer, result.year), ("Album", "Artist", "1990"))
        self.assertEqual(result.tracks[1].index_seconds, 62 + 37 / 75)
        self.assertEqual(result.tracks[1].title, "Second")
        self.assertEqual(result.tracks[1].performer, "Guest")

    def test_cue_timestamp_conversion(self) -> None:
        self.assertEqual(cue_time_to_seconds("05:17:67"), 317 + 67 / 75)

    def test_parses_foobar_dynamic_range_titles(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / "foo_dr.txt"
            report.write_text("DR15 -0.48 dB -17.79 dB 5:18 01-First Song\nDR14 -0.62 dB -17.57 dB 4:00 02-Second Song\n")
            result = parse_foobar_dr_titles(report)
        self.assertEqual(result, ["First Song", "Second Song"])
