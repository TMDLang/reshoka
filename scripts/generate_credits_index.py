#!/usr/bin/env python3
"""Generate a songwriter/composer index from song-page frontmatter."""

from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import re
import sys


REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_ROOT = REPO_ROOT / "docs"
DUPLICATE_JSON = DOCS_ROOT / "duplicate_songs.json"
OUTPUT = DOCS_ROOT / "credits_index.md"

ROLE_RE = re.compile(r"(?:作詞|作歌|作曲|編曲|詞曲|詞|曲)")
SONG_TITLE_RE = re.compile(r'^song_title:\s*["\']?(.*?)["\']?\s*$')
SONG_ID_RE = re.compile(r'^song_id:\s*["\']?(.*?)["\']?\s*$')
TITLE_RE = re.compile(r'^title:\s*["\']?(.*?)["\']?\s*$')
VOLUME_RE = re.compile(r'^volume:\s*["\']?(.*?)["\']?\s*$')
COLLECTION_RE = re.compile(r'^collection:\s*["\']?(.*?)["\']?\s*$')

import unicodedata

# Canonicalize known historical spelling/alias variants to a single author entry.
PERSON_ALIASES: dict[str, str] = {
    "佐々木の信綱": "佐々木信綱",
    "佐佐木信綱": "佐々木信綱",
    "一條慎三郎": "一條愼三郎",
    "村橋靖彦": "村橋靖彥",
    "土井林吉": "土井晩翠",
    "松谷代水": "杉谷代水",
    "旗野士良": "旗野十一郎",
    "幼年唱歌": "石原和三郎",
    "山田美妙齋": "山田美妙",
    "川路柳江": "川路柳虹",
    "武島又次郎": "武島羽衣",
    "葛原𦱳": "葛原しげる",
    "文部省《尋常小學唱歌》": "文部省",
    "文部省《中學唱歌》": "文部省",
    "文部省唱歌": "文部省",
    "文部省國語讀本": "文部省",
    "文部省尋常小學唱歌": "文部省",
    "文部省讀本": "文部省",
    "東京音樂學校編《中等唱歌》": "東京音樂學校",
    "臺灣總督府《公學校唱歌集》": "臺灣總督府",
    "臺灣教育會選曲": "臺灣教育會",
    "奧特姆": "奧特姆（Autumn）",
}

# Non-person entries (folk traditions, textbook sources, unknown) excluded from person index.
EXCLUDED_NON_PERSONS: set[str] = {
    "不詳",
    "作者不詳",
    "未署",
    "佚名",
    "古歌",
    "佛蘭西童謠",
    "公學校用國民讀本",
    "國定讀本歌",
    "國定高等小學讀本",
    "國定高等小學讀本所載",
    "國語讀本",
    "大正幼年唱歌",
    "新特選樂譜",
}

CJK_VARIANT_TABLE = str.maketrans({
    "慎": "愼",
    "彦": "彥",
    "沢": "澤",
    "広": "廣",
    "辺": "邊",
    "学": "學",
    "桜": "櫻",
    "国": "國",
    "滝": "瀧",
    "稲": "稻",
    "頴": "穎",
    "内": "內",
    "嶋": "島",
    "寛": "寬",
    "渓": "溪",
    "真": "眞",
    "頼": "賴",
    "黒": "黑",
    "徳": "德",
    "浜": "濱",
    "酔": "醉",
})

_CJK_SPACE_RE = re.compile(r"(?<=[\u3040-\u30ff\u3400-\u9fff])\s+(?=[\u3040-\u30ff\u3400-\u9fff])")
_LEADING_VERSE_RE = re.compile(r"^[（(][一二三四五六七八九十\d]+[）)]\s*")
_TRAILING_PAREN_RE = re.compile(r"\s*[（(][^）)]*[）)]?\s*$")
_HONORIFIC_RE = re.compile(r"(?:\s*(?:君等|君|氏|先生|教諭|御歌|御製|選曲|作歌|作詞|作曲|編曲|採譜|譯詞|訳詞|譯|訳|改作))+$")
_NORM_TITLE_PAREN_RE = re.compile(r"[（(][^）)]*[）)]")


def normalize_person_name(raw: str) -> str:
    """Normalize honorifics, parenthetical notes, CJK spacing, and kanji variants."""
    person = unicodedata.normalize("NFC", raw)
    person = re.sub(r"[\u200b-\u200d\ufeff\ufe00-\ufe0f]", "", person)
    person = re.sub(r"\s+", " ", person).strip(" ：:，,、")
    if not person:
        return ""
    person = _LEADING_VERSE_RE.sub("", person).strip()
    if person == "幼年唱歌（石原和三郎）":
        return "石原和三郎"
    # Strip trailing parenthetical annotations (possibly nested/repeated)
    while True:
        stripped = _TRAILING_PAREN_RE.sub("", person).strip()
        if stripped == person or not stripped:
            break
        person = stripped
    # Strip trailing honorifics / role suffixes (e.g. 氏, 君, 御歌, 選曲, 作歌, 譯)
    if len(person) >= 3:
        person = _HONORIFIC_RE.sub("", person).strip(" ：:，,、")
    # Remove spaces between CJK characters (preserve spaces in Latin names)
    person = _CJK_SPACE_RE.sub("", person)
    # Normalize common kyujitai/shinjitai variants (except 々)
    person = person.translate(CJK_VARIANT_TABLE)
    person = PERSON_ALIASES.get(person, person)
    if person in EXCLUDED_NON_PERSONS:
        return ""
    return person


def load_duplicate_map() -> tuple[dict[str, tuple[str, str]], dict[str, str]]:
    """Return (md_file -> (group_id, group_title), md_file -> book_label)."""
    if not DUPLICATE_JSON.exists():
        return {}, {}
    data = json.loads(DUPLICATE_JSON.read_text(encoding="utf-8"))
    dup_map: dict[str, tuple[str, str]] = {}
    book_map: dict[str, str] = {}
    for group in data.get("duplicate_groups", []):
        gid = str(group.get("id", ""))
        gtitle = str(group.get("title", ""))
        for entry in group.get("entries", []):
            md_file = str(entry.get("md_file", ""))
            if not md_file:
                continue
            dup_map[md_file] = (gid, gtitle)
            if entry.get("book_label"):
                book_map[md_file] = str(entry["book_label"])
    return dup_map, book_map


def _normalize_title_key(title: str) -> str:
    # Keep numbering/variant suffixes like （第一）/（第二）/（曲第一） distinct
    if re.search(r"[（(](?:曲)?第?[一二三四五六七八九十\d]+[）)]", title):
        return re.sub(r"[\s・　]+", "", title).casefold()
    base = _NORM_TITLE_PAREN_RE.sub("", title)
    return re.sub(r"[\s・　]+", "", base).casefold()


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
    # Split multi-author strings separated by 、 (e.g. "花井貞雄君（第一）、村橋靖彥")
    for part in re.split(r"、", person):
        norm = normalize_person_name(part)
        if not norm:
            continue
        index[role].setdefault(norm, []).append((title, link))


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
    dup_map, book_map = load_duplicate_map()
    lines = [
        "---",
        'title: "詞曲作者索引"',
        'description: "依作詞者、作曲者與編曲者整理 Re:shōka 歌曲索引（已合併同作者異寫與跨冊重複收錄曲目）。"',
        "---",
        "# 詞曲作者索引",
        "",
        f"> 本頁由 `scripts/generate_credits_index.py` 產生；目前掃描 {pages} 首歌曲、整理 {credits_count} 筆作者標註，並自動合併同作者異體字／敬稱（如 `氏`、`君`、括號註記）與跨冊重複收錄曲目。",
        "",
    ]
    for role in ("作詞者", "作曲者", "編曲者"):
        people = index[role]
        if not people:
            continue
        lines.extend([f"## {role}", ""])
        for person in sorted(people, key=lambda value: value.casefold()):
            raw_songs = sorted(set(people[person]), key=lambda item: (item[0], item[1]))
            # Deduplicate songs by duplicate_songs.json group ID, falling back to normalized title
            grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
            group_titles: dict[str, str] = {}
            for title, link in raw_songs:
                if link in dup_map:
                    gid, gtitle = dup_map[link]
                    key = f"dup:{gid}"
                    group_titles.setdefault(key, gtitle or title)
                else:
                    key = f"title:{_normalize_title_key(title)}"
                    group_titles.setdefault(key, title)
                grouped[key].append((title, link))

            unique_count = len(grouped)
            total_count = len(raw_songs)
            if total_count > unique_count:
                lines.append(f"### {person}（{unique_count} 首，跨冊 {total_count} 筆）")
            else:
                lines.append(f"### {person}（{unique_count} 首）")
            lines.append("")

            for key in sorted(grouped, key=lambda k: group_titles[k]):
                items = grouped[key]
                if len(items) == 1:
                    title, link = items[0]
                    lines.append(f"- [{title}]({link})")
                else:
                    display_title = group_titles[key]
                    refs = []
                    for title, link in items:
                        label = book_map.get(link) or title
                        refs.append(f"[{label}]({link})")
                    lines.append(f"- **{display_title}**（{len(items)} 冊收錄）：" + " ／ ".join(refs))
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    index, pages, credits_count = collect()
    OUTPUT.write_text(render(index, pages, credits_count), encoding="utf-8")
    print(f"generated {OUTPUT.relative_to(REPO_ROOT)} from {pages} songs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
