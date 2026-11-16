#!/usr/bin/env python3
"""Generate an index of identical lyrics set to different melodies.

The comparison is title-independent.  Lyrics are normalized by the existing
CoreFoundation/Japanese-kana pipeline; melody versions are grouped by their
movable-do degree sequence.  This produces research candidates, not a final
musicological judgment.
"""

from __future__ import annotations

from difflib import SequenceMatcher
import json
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from generate_duplicate_songs import load_all_song_entries
from generate_same_title_songs import year_from_entry


MIN_LYRICS_LENGTH = 18
LYRICS_SIMILARITY = 0.86
MELODY_SIMILARITY = 0.72


def lyric_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left, right).ratio()


def melody_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left[:64], right[:64]).ratio()


def build_lyric_groups(entries) -> list[dict]:
    candidates = [
        entry
        for entry in entries
        if len(entry.lyrics_hira) >= MIN_LYRICS_LENGTH and entry.melody_degrees
    ]
    parent: dict[str, str] = {}
    entry_by_path = {entry.rel_dir: entry for entry in candidates}

    def find(value: str) -> str:
        parent.setdefault(value, value)
        if parent[value] != value:
            parent[value] = find(parent[value])
        return parent[value]

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for index, entry in enumerate(candidates):
        find(entry.rel_dir)
        for other in candidates[index + 1 :]:
            if lyric_similarity(entry.lyrics_hira, other.lyrics_hira) >= LYRICS_SIMILARITY:
                union(entry.rel_dir, other.rel_dir)

    lyric_components: dict[str, list] = {}
    for entry in candidates:
        lyric_components.setdefault(find(entry.rel_dir), []).append(entry)

    result: list[dict] = []
    for component in lyric_components.values():
        if len(component) < 2:
            continue

        # Split one lyric group into melody versions.  Similar melodies are
        # kept together; distinct melodies become separate versions.
        melody_parent: dict[str, str] = {}

        def melody_find(value: str) -> str:
            melody_parent.setdefault(value, value)
            if melody_parent[value] != value:
                melody_parent[value] = melody_find(melody_parent[value])
            return melody_parent[value]

        def melody_union(left: str, right: str) -> None:
            left_root, right_root = melody_find(left), melody_find(right)
            if left_root != right_root:
                melody_parent[right_root] = left_root

        for index, entry in enumerate(component):
            melody_find(entry.rel_dir)
            for other in component[index + 1 :]:
                if melody_similarity(entry.melody_degrees, other.melody_degrees) >= MELODY_SIMILARITY:
                    melody_union(entry.rel_dir, other.rel_dir)

        melody_components: dict[str, list] = {}
        for entry in component:
            melody_components.setdefault(melody_find(entry.rel_dir), []).append(entry)
        if len(melody_components) < 2:
            continue

        versions = []
        for melody_key, melody_entries in melody_components.items():
            occurrences = [
                {
                    "rel_dir": entry.rel_dir,
                    "md_file": entry.md_file,
                    "book_label": entry.book_label,
                    "raw_title": entry.raw_title,
                    "year": year_from_entry(entry),
                }
                for entry in melody_entries
            ]
            occurrences.sort(key=lambda occurrence: (occurrence["year"], occurrence["book_label"]))
            versions.append(
                {
                    "id": melody_key,
                    "year": occurrences[0]["year"],
                    "occurrences": occurrences,
                }
            )
        versions.sort(key=lambda version: (version["year"], version["id"]))

        lyrics = max((entry.lyrics_hira for entry in component), key=len)
        titles = []
        for entry in component:
            if entry.jp_title not in titles:
                titles.append(entry.jp_title)
        result.append(
            {
                "lyrics": lyrics,
                "titles": titles,
                "versions": versions,
            }
        )

    return sorted(result, key=lambda group: (group["lyrics"], group["titles"]))


def render_markdown(groups: list[dict], total_songs: int, total_volumes: int) -> str:
    lines = [
        "---",
        f"title: 同詞異曲歌曲（{len(groups)} 組）",
        f"description: 全站 {total_volumes} 冊、{total_songs} 首曲目中，歌詞相同但旋律不同的歌曲候選。",
        "keywords: 同詞異曲, 歷史歌曲, 歌詞版本, 旋律版本",
        "---",
        "",
        "# 同詞異曲歌曲",
        "",
        f"本表以正規化後的歌詞比對全站 **{total_volumes} 冊、{total_songs} 首曲目**，再依旋律音級序列分出不同旋律版本。目前找到 **{len(groups)} 組候選**。這是自動比對結果，仍應回看原始樂譜確認。",
        "",
        "| # | 歌詞／相關歌名 | 旋律版本與出現處 |",
        "| :---: | :--- | :--- |",
    ]
    for index, group in enumerate(groups, 1):
        version_lines = []
        for version_index, version in enumerate(group["versions"], 1):
            locations = "、".join(
                f"**{occurrence['book_label']}**：[〈{occurrence['raw_title']}〉]({occurrence['md_file']})"
                for occurrence in version["occurrences"]
            )
            version_lines.append(f"**旋律版本 {version_index}** {locations}")
        title = "／".join(group["titles"])
        lyrics_preview = group["lyrics"][:36] + ("…" if len(group["lyrics"]) > 36 else "")
        lines.append(f"| {index} | **{title}**<br>`{lyrics_preview}` | {'<br>'.join(version_lines)} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    repo_root = SCRIPT_DIR.parent
    docs_dir = repo_root / "docs"
    entries = load_all_song_entries(docs_dir)
    groups = build_lyric_groups(entries)
    total_volumes = len({f"{entry.collection}/{entry.volume}".rstrip("/") for entry in entries})
    payload = {
        "total_corpus_songs": len(entries),
        "same_lyrics_different_melody_group_count": len(groups),
        "groups": groups,
    }
    json_path = docs_dir / "same_lyrics_songs.json"
    md_path = docs_dir / "same_lyrics_songs.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(groups, len(entries), total_volumes), encoding="utf-8")
    print(f"Scanned {len(entries)} songs -> {len(groups)} same-lyrics/different-melody groups.")
    print(f"Updated {md_path.relative_to(repo_root)} and {json_path.relative_to(repo_root)}.")


if __name__ == "__main__":
    main()
