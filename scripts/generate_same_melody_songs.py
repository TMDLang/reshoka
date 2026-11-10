#!/usr/bin/env python3
"""Generate an index of the same melody used with different lyrics."""

from __future__ import annotations

from difflib import SequenceMatcher
import json
from pathlib import Path
import re
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
        detail_file = f"same_melody_songs/{group['id']}.md"
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
        lines.append(f"| {index} | [同一旋律]({detail_file}) | {'<br>'.join(versions)} |")
    return "\n".join(lines) + "\n"


def safe_file_id(group: dict, index: int) -> str:
    first = group["versions"][0]["occurrences"][0]["rel_dir"].split("/")[-1]
    first = re.sub(r"[^A-Za-z0-9_-]+", "_", first).strip("_")
    return f"{index:03d}_{first or 'song'}"


def guess_difference_reason(group: dict) -> str:
    collections = {
        occurrence["rel_dir"].split("/", 1)[0]
        for version in group["versions"]
        for occurrence in version["occurrences"]
    }
    paths = [
        occurrence["rel_dir"]
        for version in group["versions"]
        for occurrence in version["occurrences"]
    ]
    has_manuscript = "shokacho" in collections
    has_kyoeki = "kyoeki_shoka" in collections
    has_boys = any("koto_boys" in path for path in paths)
    has_girls = any("koto_girls" in path for path in paths)
    has_official = bool(
        {"kogakko_shoka", "kogakko_shokashu_1915", "shintei_jido_shoka"}
        & collections
    )
    titles = set()
    for version in group["versions"]:
        titles.update(version["titles"])
    content_reasons = {
        "雨": "兩個版本保留相同的雨景與行進意象，但楊金土本的句子較短、部分語句不同，較像從另一歌集或手抄流傳本節錄，而不是單純男女教材改詞。",
        "始政紀念日": "官方版本歌頌「扶桑」與天皇政事；楊金土本改以「高砂島の民草」與臺灣島民受恩復甦為中心，顯示歌詞被重新地方化，以配合臺灣的始政紀念場合。",
        "明治天皇御製": "三個版本的歌詞內容都不同，並非同一首詩的異寫；「明治天皇御製」更像是作者／體裁標籤，同一旋律被套用到不同御製詩上。",
        "汽車と汽船": "兩版本都以汽車、汽船與交通速度為題材，但楊金土本的文字較像另一套交通歌詞或節錄本，可能反映不同歌集的編排，而不是抄寫失誤。",
        "秋の風": "兩版本描寫同一秋日落葉景象，但楊金土本出現字句縮短與用字變化，較可能是手抄時依記憶或口傳版本整理。",
        "みそらの鏡": "兩版本都以月亮／天空與母親或親情意象為核心，但敘事內容差距很大，可能是同一旋律下的不同兒童歌曲，而非同一歌詞的異體字。",
        "停車場の鈴": "兩版本都保留車站鐘聲與催促旅人的場景，但句序和動作描寫不同，可能是同一教材曲在不同歌集中的改寫或縮編。",
        "送別の歌": "三個版本都使用送別旋律，但歌詞分別採用不同的畢業、惜別與《螢之光》文本；這是同一旋律跨文化、跨教材重新填詞的典型例子。",
        "螢の光": "三個版本都使用送別旋律，但歌詞分別採用不同的畢業、惜別與《螢之光》文本；這是同一旋律跨文化、跨教材重新填詞的典型例子。",
        "告別": "三個版本都使用送別旋律，但歌詞分別採用不同的畢業、惜別與《螢之光》文本；這是同一旋律跨文化、跨教材重新填詞的典型例子。",
        "コロンブス": "兩版本都敘述哥倫布航海，但楊金土本較像把原歌詞改寫成更口語、敘事節奏更短的版本，可能是手抄本或教學用的節錄。",
        "陣營の月": "印刷教材從戰事、炮火與軍隊行進描寫戰場；楊金土本轉為高山月色、軍營夜景與士兵安眠，顯示同一旋律被換成較抒情的軍歌歌詞。",
        "四季の散歩": "印刷版以四季景物與散步路線鋪陳，楊金土本則呈現較短、較口語的遊行／散步歌詞，可能是兒童實際演唱時使用的簡化版本。",
        "天然の美": "兩版本都歌詠自然聲響與景色，但文字不是逐句改寫，而是不同歌詞配在同一旋律上；曲名也從「天然の美」轉成「美しき天然」，反映流通版本的題名與填詞差異。",
        "美しき天然": "兩版本都歌詠自然聲響與景色，但文字不是逐句改寫，而是不同歌詞配在同一旋律上；曲名也從「天然の美」轉成「美しき天然」，反映流通版本的題名與填詞差異。",
        "とんび": "楊金土本幾乎只保留「ぴんよろ」的飛翔叫聲與反覆句，印刷教材則有完整敘事歌詞，可能是抄本為教學或演唱而摘錄副歌／核心段落。",
        "田舎の夕暮／田舍の夕暮": "兩版本都描寫鄉村黃昏，但楊金土本與《新定》保存的是不同段落或不同來源的歌詞；同曲異詞可能源於中等唱歌教材的流通改編。",
        "秋ノ湖上": "兩版本共享湖上秋景與夕陽意象，但楊金土本較像節錄開頭，《新定》則保存另一段完整歌詞，可能是抄本摘錄與教材定本的差異。",
        "秋の湖上": "兩版本共享湖上秋景與夕陽意象，但楊金土本較像節錄開頭，《新定》則保存另一段完整歌詞，可能是抄本摘錄與教材定本的差異。",
        "助船": "兩版本都描寫暴風雨中救援小舟，但用字與敘事焦點不同，可能是同一救難題材在不同官方教材版本中的改寫。",
    }
    for title, reason in content_reasons.items():
        if title in titles or any(title in candidate for candidate in titles):
            return reason
    if has_manuscript and has_kyoeki:
        return "楊金土手抄本與《共益商社唱歌教科書》可能取自不同流通底本；手抄時保留了另一套既有歌詞，或依當時教學場合重新填詞。"
    if has_manuscript and has_official:
        return "楊金土手抄本與官方教材的來源或使用場合不同，可能保存了民間／校內流通的另一歌詞版本，而非單純抄寫錯誤。"
    if has_boys and has_girls:
        return "男子用／女子用的差異不一定是單純改詞：可能同時受到男女音域、換聲區、歌詞音節配置、合唱場合與性別化課程內容影響；也不排除兩冊沿用不同底本。需再對照原書編者、歌詞來源與實際音域確認。"
    if has_official:
        return "同一旋律被不同時期的官方教材重新編排，可能因教材主題、年級或時代宣傳內容而改寫歌詞。"
    return "這些版本可能來自不同歌集、抄本或教學場合；同一旋律在傳抄與教材編纂過程中被配上另一套歌詞。"


def render_detail_markdown(group: dict, index: int) -> str:
    titles = []
    for version in group["versions"]:
        titles.extend(version["titles"])
    display_title = "／".join(dict.fromkeys(titles))
    lines = [
        "---",
        f"title: 同曲異詞：{display_title}",
        f"description: {display_title} 的同曲異詞版本比較。",
        "keywords: 同曲異詞, 旋律版本, 歌詞版本",
        "---",
        "",
        f"# 同曲異詞：{display_title}",
        "",
        "> 這是旋律相似度比對產生的研究候選，仍應回看各版本原始掃描與樂譜確認。",
        "",
        "## 版本比較",
        "",
        "| 版本 | 年代 | 歌名 | 歌詞（正規化讀音） | 出現處 |",
        "| :---: | :---: | :--- | :--- | :--- |",
    ]
    for version_index, version in enumerate(group["versions"], 1):
        locations = "<br>".join(
            f"**{occurrence['book_label']}**：[〈{occurrence['raw_title']}〉]({occurrence['md_file']})"
            for occurrence in version["occurrences"]
        )
        title = "／".join(version["titles"])
        lines.append(
            f"| {version_index} | {version['year'] if version['year'] != 9999 else '—'} | **{title}** | `{version['lyrics']}` | {locations} |"
        )
    lines.extend(
        [
            "",
            "## 差異原因（推測）",
            "",
            guess_difference_reason(group),
            "",
            "## 判讀",
            "",
            "各版本的旋律音級序列達到自動比對門檻，但歌詞正規化後仍分成不同版本。這裡的「同曲」是資料分析候選，不取代逐小節的人工校勘。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    repo_root = SCRIPT_DIR.parent
    docs_dir = repo_root / "docs"
    entries = load_all_song_entries(docs_dir)
    groups = build_melody_groups(entries)
    detail_dir = docs_dir / "same_melody_songs"
    detail_dir.mkdir(exist_ok=True)
    for old_md in detail_dir.glob("*.md"):
        old_md.unlink()
    for index, group in enumerate(groups, 1):
        group["id"] = safe_file_id(group, index)
        (detail_dir / f"{group['id']}.md").write_text(
            render_detail_markdown(group, index), encoding="utf-8"
        )
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
