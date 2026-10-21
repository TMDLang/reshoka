#!/usr/bin/env python3
"""Find repeated melodic motifs in TMD scores.

The script works on TMD's movable-do notation instead of rendered audio.  By
default it prefers Vocal/Main/Melody/Voice tracks and falls back to the first
Piano track when a score has no obvious melody track.

Examples:

    python3 scripts/find_tmd_motifs.py docs/shokacho --window 8
    python3 scripts/find_tmd_motifs.py docs/shokacho --mode degree --json
    python3 scripts/find_tmd_motifs.py docs/recreations --window 10 --ignore-rhythm

``degree`` compares relative-scale tokens directly.  ``interval`` is
transposition-invariant even when the same idea starts on another scale
degree.  ``contour`` keeps only up/down/repeated motion and is the loosest
comparison.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence


TRACK_PRIORITY = ("vocal", "main", "melody", "voice", "lead", "solo")
PIANO_NAMES = ("piano", "keyboard")
IGNORED_INSTRUMENTS = {
    "bass",
    "chord",
    "chords",
    "drum",
    "drums",
    "groove",
    "percussion",
}

TRACK_START = re.compile(
    r"(?m)^\s*(?P<section>[^:\s{}]+):(?P<instrument>[^@\s{}]+)@[^{}]*\{"
)
NOTE = re.compile(r"(?<![A-Za-z0-9_])(?P<degree>[1-7])(?P<acc>[',]*)(?P<oct>[\^_]*)(?![A-Za-z0-9_])")


@dataclass(frozen=True)
class Event:
    token: str
    pitch_value: int
    duration: int
    position: int


@dataclass(frozen=True)
class Occurrence:
    path: str
    section: str
    instrument: str
    start_note: int
    source_line: int
    excerpt: str


@dataclass(frozen=True)
class Track:
    section: str
    instrument: str
    body: str
    body_start: int


def strip_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)


def extract_tracks(text: str) -> list[Track]:
    """Extract assignment blocks while respecting nested directive braces."""
    clean = strip_comments(text)
    tracks: list[Track] = []
    for match in TRACK_START.finditer(clean):
        depth = 1
        index = match.end()
        while index < len(clean) and depth:
            if clean[index] == "{":
                depth += 1
            elif clean[index] == "}":
                depth -= 1
            index += 1
        if depth == 0:
            tracks.append(
                Track(
                    section=match.group("section"),
                    instrument=match.group("instrument"),
                    body=clean[match.end() : index - 1],
                    body_start=match.end(),
                )
            )
    return tracks


def token_pitch(token: str) -> int:
    match = re.fullmatch(r"(?P<degree>[1-7])(?P<acc>[',]*)(?P<oct>[\^_]*)", token)
    if not match:
        raise ValueError(f"invalid TMD note token: {token}")
    degree = int(match.group("degree"))
    octave = match.group("oct")
    accidental = match.group("acc")
    # Four units per quarter-tone keeps sharps/flats distinct without floats.
    scale_value = (degree - 1) * 4 + (octave.count("^") - octave.count("_")) * 7 * 4
    return scale_value + (accidental.count("'") - accidental.count(",")) * 4


def parse_events(body: str, include_rests: bool = False) -> list[Event]:
    """Parse melody events, collapsing ties into note durations.

    Rhythm-grid declarations, directives, chord literals and tuplet duration
    markers are removed before tokenization.  Rests are omitted by default so
    a phrase can still match when the source uses different breathing spaces.
    """
    body = re.sub(r"<[^>]*>", " ", body)
    body = re.sub(r"\{[^{}]*\}", " ", body)
    body = re.sub(r"\[[^\]]*\]", " ", body)
    body = re.sub(r"%\([^)]*\)", " ", body)
    raw = re.findall(r"[1-7][',]*[\^_]*|0|-", body)
    events: list[Event] = []
    index = 0
    while index < len(raw):
        item = raw[index]
        if item == "-":
            index += 1
            continue
        if item == "0":
            duration = 1
            index += 1
            while index < len(raw) and raw[index] == "-":
                duration += 1
                index += 1
            if include_rests:
                events.append(Event("R", -10_000, duration, len(events)))
            continue
        duration = 1
        index += 1
        while index < len(raw) and raw[index] == "-":
            duration += 1
            index += 1
        events.append(Event(item, token_pitch(item), duration, len(events)))
    return events


def selected_tracks(tracks: Sequence[Track], mode: str) -> list[Track]:
    if mode != "auto":
        wanted = {name.strip().lower() for name in mode.split(",") if name.strip()}
        return [track for track in tracks if track.instrument.lower() in wanted]

    preferred = [
        track
        for track in tracks
        if track.instrument.lower() in TRACK_PRIORITY
        or track.section.lower() in TRACK_PRIORITY
    ]
    if preferred:
        return preferred
    piano = [track for track in tracks if track.instrument.lower() in PIANO_NAMES]
    if piano:
        return [piano[0]]
    return [
        track
        for track in tracks
        if track.instrument.lower() not in IGNORED_INSTRUMENTS
    ][:1]


def signature(events: Sequence[Event], mode: str, ignore_rhythm: bool) -> tuple[str, ...]:
    values: list[str] = []
    previous: Event | None = None
    for event in events:
        if mode == "degree":
            pitch = event.token
        elif mode == "interval":
            pitch = "*" if previous is None else str(event.pitch_value - previous.pitch_value)
        elif mode == "contour":
            if previous is None:
                pitch = "*"
            else:
                delta = event.pitch_value - previous.pitch_value
                pitch = ">" if delta > 0 else "<" if delta < 0 else "="
        else:
            raise ValueError(f"unknown mode: {mode}")
        values.append(pitch if ignore_rhythm else f"{pitch}:{event.duration}")
        previous = event
    return tuple(values)


def excerpt(events: Sequence[Event], mode: str, ignore_rhythm: bool) -> str:
    return " ".join(signature(events, mode, ignore_rhythm))


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def iter_files(paths: Iterable[Path]) -> Iterator[Path]:
    for path in paths:
        if path.is_file() and path.suffix.lower() == ".tmd":
            yield path
        elif path.is_dir():
            yield from sorted(path.rglob("*.tmd"))


def find_motifs(
    paths: Iterable[Path],
    window: int,
    mode: str,
    track_mode: str,
    ignore_rhythm: bool,
    include_rests: bool,
    include_piano_files: bool,
) -> tuple[dict[tuple[str, ...], list[Occurrence]], int]:
    groups: dict[tuple[str, ...], list[Occurrence]] = defaultdict(list)
    files_checked = 0
    for path in sorted(set(iter_files(paths))):
        if path.name.endswith("_piano.tmd") and not include_piano_files:
            continue
        files_checked += 1
        text = path.read_text(encoding="utf-8")
        for track in selected_tracks(extract_tracks(text), track_mode):
            events = parse_events(track.body, include_rests=include_rests)
            if len(events) < window:
                continue
            for start in range(len(events) - window + 1):
                chunk = events[start : start + window]
                key = signature(chunk, mode, ignore_rhythm)
                groups[key].append(
                    Occurrence(
                        path=str(path),
                        section=track.section,
                        instrument=track.instrument,
                        start_note=start,
                        source_line=line_number(text, track.body_start),
                        excerpt=excerpt(chunk, mode, ignore_rhythm),
                    )
                )
    return groups, files_checked


def useful_groups(
    groups: dict[tuple[str, ...], list[Occurrence]], min_files: int
) -> list[tuple[tuple[str, ...], list[Occurrence]]]:
    result = []
    for key, occurrences in groups.items():
        distinct_files = {item.path for item in occurrences}
        if len(distinct_files) >= min_files:
            result.append((key, occurrences))
    return sorted(
        result,
        key=lambda item: (-len({o.path for o in item[1]}), -len(item[1]), item[0]),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="+", type=Path, help="TMD files or directories to scan")
    parser.add_argument("--window", type=int, default=8, help="motif length in notes (default: 8)")
    parser.add_argument("--mode", choices=("degree", "interval", "contour"), default="interval", help="fingerprint mode (default: interval)")
    parser.add_argument("--tracks", default="auto", help="comma-separated instrument names, or auto (default: auto)")
    parser.add_argument("--ignore-rhythm", action="store_true", help="compare melodic shape without note durations")
    parser.add_argument("--include-rests", action="store_true", help="include rests as motif events")
    parser.add_argument("--include-piano-files", action="store_true", help="include files whose name ends with _piano.tmd")
    parser.add_argument("--min-files", type=int, default=2, help="minimum distinct files per result (default: 2)")
    parser.add_argument("--limit", type=int, default=50, help="maximum motif groups to print (default: 50)")
    parser.add_argument("--json", action="store_true", help="write machine-readable JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.window < 2:
        raise SystemExit("--window must be at least 2")
    if args.min_files < 2:
        raise SystemExit("--min-files must be at least 2")
    groups, files_checked = find_motifs(
        args.paths,
        args.window,
        args.mode,
        args.tracks,
        args.ignore_rhythm,
        args.include_rests,
        args.include_piano_files,
    )
    matches = useful_groups(groups, args.min_files)[: args.limit]
    if args.json:
        payload = {
            "files_checked": files_checked,
            "window": args.window,
            "mode": args.mode,
            "ignore_rhythm": args.ignore_rhythm,
            "matches": [
                {
                    "fingerprint": list(key),
                    "files": len({item.path for item in occurrences}),
                    "occurrences": [item.__dict__ for item in occurrences],
                }
                for key, occurrences in matches
            ],
        }
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        print()
        return 0

    print(f"files checked: {files_checked}")
    print(f"window: {args.window} notes; mode: {args.mode}; rhythm: {'ignored' if args.ignore_rhythm else 'included'}")
    print(f"motif groups: {len(matches)}")
    for number, (key, occurrences) in enumerate(matches, 1):
        distinct = sorted({item.path for item in occurrences})
        print(f"\n[{number}] {len(distinct)} files / {len(occurrences)} occurrences")
        print("  fingerprint:", " ".join(key))
        for item in occurrences[:20]:
            print(
                f"  - {item.path}:{item.source_line} "
                f"({item.section}:{item.instrument}, note {item.start_note + 1})"
            )
        if len(occurrences) > 20:
            print(f"  ... {len(occurrences) - 20} more occurrences")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
