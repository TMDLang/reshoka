#!/usr/bin/env python3
"""Generate an index of the same melody used with different lyrics."""

from __future__ import annotations

from difflib import SequenceMatcher
import json
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from generate_duplicate_songs import load_all_song_entries
from generate_same_lyrics_songs import (
    MIN_LYRICS_LENGTH,
    MELODY_SIMILARITY,
    lyric_similarity,
)
from generate_same_title_songs import year_from_entry


LYRICS_VERSION_SIMILARITY = 0.72
MELODY_SIMILARITY = 0.86
MELODY_LENGTH_RATIO = 0.78


def melody_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left[:64], right[:64]).ratio()


def melodies_match(left: str, right: str) -> bool:
    length_ratio = min(len(left), len(right)) / max(len(left), len(right))
    return length_ratio >= MELODY_LENGTH_RATIO and melody_similarity(left, right) >= MELODY_SIMILARITY


def build_melody_groups(entries) -> list[dict]:
    candidates = [
        entry
        for entry in entries
        if len(entry.lyrics_hira) >= MIN_LYRICS_LENGTH and entry.melody_degrees
    ]
    parent: dict[str, str] = {}

    def find(value: str) -> str:
        parent.setdefault(value, value)
        if parent[value] != value:
            parent[value] = find(parent[value])
        return parent[value]

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for entry in candidates:
        find(entry.rel_dir)

    # Most matching melodies share their opening movable-do pattern.  Use
    # prefix/suffix buckets to avoid an expensive all-pairs comparison while
    # still allowing anacrusis or a changed opening note.
    buckets: dict[str, list] = {}
    for entry in candidates:
        for bucket in {
            f"prefix:{entry.melody_degrees[:4]}",
            f"suffix:{entry.melody_degrees[-4:]}",
        }:
            buckets.setdefault(bucket, []).append(entry)
    pairs: set[tuple[str, str]] = set()
    for bucket_entries in buckets.values():
        for index, entry in enumerate(bucket_entries):
            for other in bucket_entries[index + 1 :]:
                pairs.add(tuple(sorted((entry.rel_dir, other.rel_dir))))
    entry_by_path = {entry.rel_dir: entry for entry in candidates}
    for left_path, right_path in pairs:
        if melodies_match(
            entry_by_path[left_path].melody_degrees,
            entry_by_path[right_path].melody_degrees,
        ):
            union(left_path, right_path)

    melody_components: dict[str, list] = {}
    for entry in candidates:
        melody_components.setdefault(find(entry.rel_dir), []).append(entry)

    result: list[dict] = []
    for component in melody_components.values():
        if len(component) < 2:
            continue

        lyrics_parent: dict[str, str] = {}

        def lyrics_find(value: str) -> str:
            lyrics_parent.setdefault(value, value)
            if lyrics_parent[value] != value:
                lyrics_parent[value] = lyrics_find(lyrics_parent[value])
            return lyrics_parent[value]

        def lyrics_union(left: str, right: str) -> None:
            left_root, right_root = lyrics_find(left), lyrics_find(right)
            if left_root != right_root:
                lyrics_parent[right_root] = left_root

        for index, entry in enumerate(component):
            lyrics_find(entry.rel_dir)
            for other in component[index + 1 :]:
                if lyric_similarity(entry.lyrics_hira, other.lyrics_hira) >= LYRICS_VERSION_SIMILARITY:
                    lyrics_union(entry.rel_dir, other.rel_dir)

        lyric_versions: dict[str, list] = {}
        for entry in component:
            lyric_versions.setdefault(lyrics_find(entry.rel_dir), []).append(entry)
        if len(lyric_versions) < 2:
            continue

        versions = []
        for lyric_key, lyric_entries in lyric_versions.items():
            occurrences = [
                {
                    "rel_dir": entry.rel_dir,
                    "md_file": entry.md_file,
                    "book_label": entry.book_label,
                    "raw_title": entry.raw_title,
                    "year": year_from_entry(entry),
                }
                for entry in lyric_entries
            ]
            occurrences.sort(key=lambda occurrence: (occurrence["year"], occurrence["book_label"]))
            titles = []
            for entry in lyric_entries:
                if entry.jp_title not in titles:
                    titles.append(entry.jp_title)
            versions.append(
                {
                    "id": lyric_key,
                    "lyrics": max((entry.lyrics_hira for entry in lyric_entries), key=len),
                    "titles": titles,
                    "year": occurrences[0]["year"],
                    "occurrences": occurrences,
                }
            )
        versions.sort(key=lambda version: (version["year"], version["id"]))
        result.append({"versions": versions})

    return sorted(result, key=lambda group: (group["versions"][0]["year"], group["versions"][0]["id"]))


def render_markdown(groups: list[dict], total_songs: int, total_volumes: int) -> str:
    lines = [
        "---",
        f"title: 同曲異詞歌曲（{len(groups)} 組）",
        f"description: 全站 {total_volumes} 冊、{total_songs} 首曲目中，相同旋律搭配不同歌詞的歌曲候選。",
        "keywords: 同曲異詞, 歷史歌曲, 旋律版本, 歌詞版本",
        "---",
        "",
        "# 同曲異詞歌曲",
        "",
        f"本表以旋律音級序列比對全站 **{total_volumes} 冊、{total_songs} 首曲目**，再依歌詞分出不同版本。目前找到 **{len(groups)} 組候選**。這是自動比對結果，仍應回看原始樂譜確認。",
        "",
        "| # | 旋律 | 歌詞版本與出現處 |",
        "| :---: | :--- | :--- |",
    ]
    for index, group in enumerate(groups, 1):
        versions = []
        for version_index, version in enumerate(group["versions"], 1):
            title = "／".join(version["titles"])
            lyrics_preview = version["lyrics"][:36] + ("…" if len(version["lyrics"]) > 36 else "")
            locations = "、".join(
                f"**{occurrence['book_label']}**：[〈{occurrence['raw_title']}〉]({occurrence['md_file']})"
                for occurrence in version["occurrences"]
            )
            versions.append(
                f"**歌詞版本 {version_index}** **{title}** `<{lyrics_preview}>` {locations}"
            )
        lines.append(f"| {index} | 同一旋律 | {'<br>'.join(versions)} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    repo_root = SCRIPT_DIR.parent
    docs_dir = repo_root / "docs"
    entries = load_all_song_entries(docs_dir)
    groups = build_melody_groups(entries)
    total_volumes = len({f"{entry.collection}/{entry.volume}".rstrip("/") for entry in entries})
    payload = {
        "total_corpus_songs": len(entries),
        "same_melody_different_lyrics_group_count": len(groups),
        "groups": groups,
    }
    json_path = docs_dir / "same_melody_songs.json"
    md_path = docs_dir / "same_melody_songs.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(groups, len(entries), total_volumes), encoding="utf-8")
    print(f"Scanned {len(entries)} songs -> {len(groups)} same-melody/different-lyrics groups.")
    print(f"Updated {md_path.relative_to(repo_root)} and {json_path.relative_to(repo_root)}.")


if __name__ == "__main__":
    main()
