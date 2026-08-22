"""Command-line entry point."""

from __future__ import annotations

import argparse
from pathlib import Path

from music_converter.workflows.single_flac_album import SingleFlacAlbumWorkflow


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="music-converter")
    subparsers = parser.add_subparsers(dest="workflow", required=True)
    single_flac = subparsers.add_parser(
        "single-flac-album",
        help="Convert one album-length FLAC described by a CUE sheet.",
    )
    single_flac.add_argument("source_directory", type=Path)
    single_flac.add_argument(
        "--output-root",
        type=Path,
        help="Directory in which to create the named album output directory.",
    )
    single_flac.add_argument(
        "--plan",
        action="store_true",
        help="Validate input and display the conversion plan without writing files.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.workflow == "single-flac-album":
        try:
            return SingleFlacAlbumWorkflow().run(
                args.source_directory,
                output_root=args.output_root,
                plan_only=args.plan,
            )
        except ValueError as error:
            parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
