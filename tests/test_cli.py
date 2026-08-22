import unittest

from music_converter.cli import build_parser


class CliTests(unittest.TestCase):
    def test_single_flac_workflow_accepts_source_directory(self) -> None:
        args = build_parser().parse_args(["single-flac-album", "/music/album"])
        self.assertEqual(args.workflow, "single-flac-album")
        self.assertEqual(str(args.source_directory), "/music/album")

    def test_single_flac_workflow_accepts_output_root(self) -> None:
        args = build_parser().parse_args(
            ["single-flac-album", "/music/album", "--output-root", "/music/output"]
        )
        self.assertEqual(str(args.output_root), "/music/output")
