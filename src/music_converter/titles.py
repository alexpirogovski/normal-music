"""Extract authoritative track titles from foobar2000 DR reports."""

from __future__ import annotations

import re
from pathlib import Path

_TRACK_ROW = re.compile(r"^\s*DR\d+.*?\s+(?P<number>\d{1,3})-(?P<title>.+?)\s*$", re.I)


def parse_foobar_dr_titles(path: Path) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except UnicodeDecodeError:
        lines = path.read_text(encoding="cp1252").splitlines()
    titles: list[str] = []
    for line in lines:
        match = _TRACK_ROW.match(line)
        if match:
            expected_number = len(titles) + 1
            number = int(match.group("number"))
            title = match.group("title").strip()
            if number != expected_number or not title:
                raise ValueError(f"Invalid track row in {path.name}: {line}")
            titles.append(title)
    if not titles:
        raise ValueError(f"No foobar2000 Dynamic Range track rows found in {path.name}.")
    return titles
