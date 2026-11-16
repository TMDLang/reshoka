#!/usr/bin/env python3
"""Generate a songwriter/composer index from song-page frontmatter."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re
import sys


REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_ROOT = REPO_ROOT / "docs"
OUTPUT = DOCS_ROOT / "credits_index.md"

ROLE_RE = re.compile(r"(?:作詞|作歌|作曲|編曲|詞曲|詞|曲)")
SONG_TITLE_RE = re.compile(r'^song_title:\s*["\']?(.*?)["\']?\s*$')
SONG_ID_RE = re.compile(r'^song_id:\s*["\']?(.*?)["\']?\s*$')
TITLE_RE = re.compile(r'^title:\s*["\']?(.*?)["\']?\s*$')


def _scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    return value.replace('\\"', '"').strip()


def parse_frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end < 0:
        return {}
    lines = text[4:end].splitlines()
    result: dict[str, object] = {}
    credits: list[str] = []
    in_credits = False
    for line in lines:
        if line == "credits:":
            in_credits = True
            continue
        if in_credits:
            if line.startswith("  - "):
                credits.append(_scalar(line[4:]))
                continue
            in_credits = False
        for key, pattern in (
            ("song_title", SONG_TITLE_RE),
            ("song_id", SONG_ID_RE),
            ("title", TITLE_RE),
        ):
            match = pattern.match(line)
            if match:
                result[key] = _scalar(match.group(1))
                break
    if credits:
        result["credits"] = credits
    return result


def _add_credit(
    index: dict[str, dict[str, list[tuple[str, str]]]],
    role: str,
    person: str,
    title: str,
    link: str,
) -> None:
    person = re.sub(r"\s+", " ", person).strip(" ：:，,、")
    if not person:
        return
    index[role].setdefault(person, []).append((title, link))


def parse_credit_value(value: str) -> list[tuple[str, str]]:
    """Return (role, person) pairs from one credits entry."""
    value = value.strip()
    pairs: list[tuple[str, str]] = []
    chunks = re.split(r"\s*[/／]\s*", value)
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        prefix = re.match(r"^(詞曲|作詞|作歌|作曲|編曲|詞|曲)\s*[：:]\s*(.+)$", chunk)
        if prefix:
            label, person = prefix.groups()
            roles = {"詞曲": ("作詞", "作曲"), "詞": ("作詞",), "作歌": ("作詞",)}
            for role in roles.get(label, (label,)):
                pairs.append((role, person.strip()))
            continue
        suffix = re.search(r"(?:^|\s)(作詞|作歌|作曲|編曲|詞|曲)\s*$", chunk)
        if suffix:
            role = suffix.group(1)
            if role in {"詞", "作歌"}:
                role = "作詞"
            pairs.append((role, chunk[: suffix.start()].strip()))
    return pairs


def collect() -> tuple[dict[str, dict[str, list[tuple[str, str]]]], int, int]:
    index: dict[str, dict[str, list[tuple[str, str]]]] = {
        "作詞者": defaultdict(list),
        "作曲者": defaultdict(list),
        "編曲者": defaultdict(list),
    }
    seen_ids: set[str] = set()
    pages = 0
    credits_count = 0
    for path in sorted(DOCS_ROOT.rglob("index.md")):
        metadata = parse_frontmatter(path)
        song_id = str(metadata.get("song_id", ""))
        if not song_id or song_id in seen_ids:
            continue
        seen_ids.add(song_id)
        pages += 1
        title = str(metadata.get("song_title") or metadata.get("title") or path.parent.name)
        link = path.relative_to(DOCS_ROOT).as_posix()
        for raw in metadata.get("credits", []):
            pairs = parse_credit_value(str(raw))
            credits_count += len(pairs)
            for role, person in pairs:
                if role == "作詞":
                    _add_credit(index, "作詞者", person, title, link)
                elif role == "作曲":
                    _add_credit(index, "作曲者", person, title, link)
                elif role == "編曲":
                    _add_credit(index, "編曲者", person, title, link)
    return index, pages, credits_count


def render(index: dict[str, dict[str, list[tuple[str, str]]]], pages: int, credits_count: int) -> str:
    lines = [
        "---",
        'title: "詞曲作者索引"',
        'description: "依作詞者、作曲者與編曲者整理 Re:shōka 歌曲索引。"',
        "---",
        "# 詞曲作者索引",
        "",
        f"> 本頁由 `scripts/generate_credits_index.py` 產生；目前掃描 {pages} 首歌曲、整理 {credits_count} 筆作者標註。",
        "",
        "作者名稱依歌曲頁現有 credits 欄位整理；括號中的版本、來源或考證註記會保留在歌曲頁，不在此頁另行推定。",
        "",
    ]
    for role in ("作詞者", "作曲者", "編曲者"):
        people = index[role]
        if not people:
            continue
        lines.extend([f"## {role}", ""])
        for person in sorted(people, key=lambda value: value.casefold()):
            songs = sorted(set(people[person]), key=lambda item: (item[0], item[1]))
            lines.append(f"### {person}（{len(songs)} 首）")
            lines.append("")
            for title, link in songs:
                lines.append(f"- [{title}]({link})")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    index, pages, credits_count = collect()
    OUTPUT.write_text(render(index, pages, credits_count), encoding="utf-8")
    print(f"generated {OUTPUT.relative_to(REPO_ROOT)} from {pages} songs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
