# Normal Music Converter

A command-line converter organised as explicit release workflows. The first
workflow, `single-flac-album`, converts one album-length FLAC plus a CUE sheet
into tagged AAC/M4A tracks for Apple Music and iPhone.

## Status

The project scaffold is in place. Parsing will be adapted to the supplied
release's real CUE and `foo_dr.txt` syntax before the workflow is finalised.

## Intended invocation

Install from a checkout with Python 3.11 or newer:

```bash
python3 -m pip install .
```

Then run:

```bash
music-converter single-flac-album "/mnt/c/path/to/source"
```

To inspect the detected album and FFmpeg work without creating files, add
`--plan`.

By default the output directory is created beneath `/mnt/f/Music`. To place it
under another existing directory, use `--output-root`, for example
`--output-root "/mnt/f/Music"`.

The source directory is never modified. Successful conversions will be written
to a clearly named sibling output directory. Existing outputs will not be
overwritten.

## Expected input layout

```text
Album.cue
Album.flac
cover.jpg
```

`foo_dr.txt` is optional. When present, its foobar2000 DR report titles are
authoritative; otherwise the workflow uses every track `TITLE` in the CUE
sheet. Artwork may be named `cover.jpg`/`cover.jpeg` or `folder.jpg`/`folder.jpeg`.
Other files and directories are ignored. `ffmpeg` and `ffprobe` must be on
`PATH`.

## Behaviour and limitations

The workflow validates all files, metadata, title count, CUE boundaries, and
output names before conversion begins. It writes into a temporary sibling
directory and only renames it to the final output directory when every track
has been encoded. The currently supported CUE subset is album-level `TITLE`,
`PERFORMER`, optional `REM DATE`, consecutive `TRACK nn AUDIO` blocks, and
`INDEX 01` boundaries. `foo_dr.txt` must be a foobar2000 Dynamic Range Meter
report containing numbered `NN-Title` rows.

Each result is AAC LC at 256 kbit/s in `.m4a`, with M4A metadata for track,
album, artist, disc, date (when supplied), and an attached JPEG cover. Existing
output directories are never overwritten.
