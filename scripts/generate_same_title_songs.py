#!/usr/bin/env python3
"""Generate an index of songs sharing the same normalized title.

This is intentionally separate from ``generate_duplicate_songs.py``.  It does
not decide whether two scores are the same song: it only groups appearances
whose Japanese title reading is the same, so same-song versions and
same-title/different-song versions are both visible.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from generate_duplicate_songs import (
    build_clusters,
    build_duplicate_groups,
    load_all_song_entries,
)


def year_from_entry(entry) -> int:
    """Return publication year; catalog numbers such as 2020.006 are not years."""
    fixed_years = {
        "kogakko_shokashu": 1915,
        "shoka_kyozai_shu_1923": 1923,
        "taiwan_shuyu_shoka": 1910,
        "taiwan_no_uta": 1929,
        "shokacho": 1923,
        "shintei_jido_shoka": 1934,
        "utanohon": 1943,
    }
    if entry.collection in fixed_years:
        return fixed_years[entry.collection]
    if entry.collection == "kyoeki_shoka":
        return 1905 if entry.volume.startswith("kan_1") else 1900

    years = [int(value) for value in re.findall(r"\b(?:18|19)\d{2}\b", entry.book_label)]
    return min(years) if years else 9999


def build_same_title_groups(entries, duplicate_groups: list[dict]) -> list[dict]:
    version_by_path: dict[str, str] = {}
    for group in duplicate_groups:
        for occurrence in group["entries"]:
            version_by_path[occurrence["rel_dir"]] = f"same-song:{group['id']}"

    groups: dict[str, list] = {}
    for entry in entries:
        title_key = entry.hira_reading or entry.hira_title
        if title_key:
            groups.setdefault(title_key, []).append(entry)

    result: list[dict] = []
    for title_key, group in groups.items():
        if len(group) < 2:
            continue
        titles: list[str] = []
        versions: dict[str, list[dict]] = {}
        for entry in group:
            if entry.jp_title not in titles:
                titles.append(entry.jp_title)
            version_key = version_by_path.get(entry.rel_dir, f"single:{entry.rel_dir}")
            versions.setdefault(version_key, []).append(
                {
                    "rel_dir": entry.rel_dir,
                    "md_file": entry.md_file,
                    "book_label": entry.book_label,
                    "raw_title": entry.raw_title,
                    "year": year_from_entry(entry),
                }
            )
        sorted_versions = []
        for key, occurrences in versions.items():
            occurrences.sort(key=lambda occurrence: (occurrence["year"], occurrence["book_label"]))
            sorted_versions.append(
                {
                    "id": key,
                    "year": occurrences[0]["year"],
                    "occurrences": occurrences,
                }
            )
        result.append(
            {
                "title_key": title_key,
                "title": "／".join(titles),
                "versions": sorted(
                    sorted_versions,
                    key=lambda version: (version["year"], version["id"]),
                ),
            }
        )

    return sorted(result, key=lambda group: (group["title"], group["title_key"]))


def render_markdown(groups: list[dict], total_songs: int, total_volumes: int) -> str:
    lines = [
        "---",
        f"title: 同一歌名的多個版本（{len(groups)} 組）",
        f"description: 全站 {total_volumes} 冊、{total_songs} 首曲目中，具有相同歌名讀音的歌曲與版本。",
        "keywords: 同名歌曲, 歌曲版本, 歷史歌曲",
        "---",
        "",
        "# 同一歌名的多個版本",
        "",
        f"本表先以歌名的日文讀音正規化分組，再把同一首歌曲的重複出現集中在同一個版本下。全站 **{total_volumes} 冊、{total_songs} 首曲目**共找出 **{len(groups)} 組**同歌名歌曲。",
        "",
        "| # | 歌名 | 版本與出現處 |",
        "| :---: | :--- | :--- |",
    ]
    for index, group in enumerate(groups, 1):
        version_lines = []
        for version_index, version in enumerate(group["versions"], 1):
            locations = "、".join(
                f"**{occurrence['book_label']}**：[〈{occurrence['raw_title']}〉]({occurrence['md_file']})"
                for occurrence in version["occurrences"]
            )
            if len(group["versions"]) > 1:
                version_lines.append(f"**版本 {version_index}** {locations}")
            else:
                version_lines.append(locations)
        locations = "<br>".join(version_lines)
        lines.append(f"| {index} | **{group['title']}** | {locations} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    repo_root = SCRIPT_DIR.parent
    docs_dir = repo_root / "docs"
    entries = load_all_song_entries(docs_dir)
    duplicate_groups = build_duplicate_groups(build_clusters(entries))
    groups = build_same_title_groups(entries, duplicate_groups)

    payload = {
        "total_corpus_songs": len(entries),
        "same_title_group_count": len(groups),
        "groups": groups,
    }
    json_path = docs_dir / "same_title_songs.json"
    md_path = docs_dir / "same_title_songs.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    total_volumes = len({f"{entry.collection}/{entry.volume}".rstrip("/") for entry in entries})
    md_path.write_text(render_markdown(groups, len(entries), total_volumes), encoding="utf-8")
    print(f"Scanned {len(entries)} songs -> {len(groups)} same-title groups.")
    print(f"Updated {md_path.relative_to(repo_root)} and {json_path.relative_to(repo_root)}.")


if __name__ == "__main__":
    main()
