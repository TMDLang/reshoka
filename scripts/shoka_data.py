#!/usr/bin/env python3
"""Shared data loader and musical feature extractor for Re:shoka statistics scripts."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from pathlib import Path


PITCH_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

KEY_TO_PC: dict[str, int] = {
    "C": 0,
    "C#": 1,
    "Db": 1,
    "D,": 1,
    "D": 2,
    "D#": 3,
    "Eb": 3,
    "E,": 3,
    "E": 4,
    "F": 5,
    "F#": 6,
    "Gb": 6,
    "G,": 6,
    "G": 7,
    "G#": 8,
    "Ab": 8,
    "A,": 8,
    "A": 9,
    "A#": 10,
    "Bb": 10,
    "B,": 10,
    "B": 11,
    "Cb": 11,
}

NORMALIZED_KEY_NAMES: dict[str, str] = {
    "C": "C",
    "C#": "C#",
    "Db": "Db",
    "D,": "Db",
    "D": "D",
    "D#": "Eb",
    "Eb": "Eb",
    "E,": "Eb",
    "E": "E",
    "F": "F",
    "F#": "F#",
    "Gb": "Gb",
    "G,": "Gb",
    "G": "G",
    "G#": "Ab",
    "Ab": "Ab",
    "A,": "Ab",
    "A": "A",
    "A#": "Bb",
    "Bb": "Bb",
    "B,": "Bb",
    "B": "B",
    "Cb": "B",
}

COLLECTION_LABELS: dict[str, str] = {
    "kogakko_shoka": "《公學校唱歌》",
    "shintei_jido_shoka": "《新定兒童唱歌》",
    "utanohon": "《うたのほん》（唱歌課本）",
    "shokacho": "《楊金土手抄唱歌帖》",
}

VOLUME_LABELS: dict[str, str] = {
    "grade_3": "公學校唱歌・第三學年",
    "ge_2006.006.0878": "うたのほん・下卷（初等科第二學年）",
    "grade_1_2020.006.0847.0001": "新定・尋常科第一學年",
    "grade_2_2020.006.0847.0002": "新定・尋常科第二學年",
    "grade_3_2020.006.0847.0003": "新定・尋常科第三學年",
    "grade_4_2020.006.0847.0004": "新定・尋常科第四學年",
    "grade_5_2020.006.0847.0005": "新定・尋常科第五學年",
    "grade_6_2020.006.0847.0006": "新定・尋常科第六學年",
    "koto_boys_2020.006.0848": "新定・高等科男子一二年",
    "koto_girls_2020.006.0849": "新定・高等科女子一二年",
    "vol_01": "唱歌帖・第 1 冊（選定唱歌筆記帳）",
    "vol_02": "唱歌帖・第 2 冊（II）",
    "vol_03": "唱歌帖・第 3 冊（I）",
    "vol_07": "唱歌帖・第 7 冊（VII・蓬萊唱歌集上）",
    "vol_08": "唱歌帖・第 8 冊（VIII・蓬萊唱歌集下）",
    "vol_09": "唱歌帖・第 9 冊（IX・支那曲）",
    "vol_10": "唱歌帖・第 10 冊（X）",
}

TITLE_RE = re.compile(r"^\s*\*\*\s*(.*?)\s*\*\*\s*$")
KEY_RE = re.compile(r"^\s*\?=\s*(\S+)\s*$")
TEMPO_RE = re.compile(r"^\s*!=\s*([0-9.]+)\s*$")
METER_RE = re.compile(r"^\s*<(\d+/\d+)>\s*$")
INFERRED_KEY_RE = re.compile(r"🗝\s*調性診斷：\s*([A-G][#b]?\s*(?:大調|小調))")
PC_LINE_RE = re.compile(r"^\s*([A-G]#?)\s*:\s*[█\s]*([0-9.]+)%\s*$")
SPAN_RE = re.compile(r"跨度:\s*(\d+)\s*個半音")


@dataclass
class SongRecord:
    collection: str
    collection_label: str
    volume: str
    volume_label: str
    folder_name: str
    semester: str
    title: str
    declared_key_raw: str
    declared_key: str
    inferred_tonality: str
    inferred_mode: str
    time_signature: str
    tempo_bpm: float
    span_semitones: int
    pc_weights: dict[str, float]  # Pitch class ("C".."B") -> percentage (0..100)
    degree_weights: dict[int, float]  # Semitone offset (0..11) from declared_key -> percentage
    active_pcs: list[str]
    active_degrees: list[int]
    pentatonic_category: str
    scale_subtype: str
    major_penta_ratio: float


def natural_sort_key(text: str) -> list[int | str]:
    return [int(tok) if tok.isdigit() else tok.lower() for tok in re.split(r"(\d+)", text)]


def classify_semester(collection: str, volume: str, folder_name: str) -> str:
    if collection == "kogakko_shoka":
        # 公學校唱歌 第三學年用（全一冊 15 課，未分學期標號，或依課次歸為全學年正課）
        return "全學年正課（公學校唱歌）"
    if collection == "shokacho":
        return "手抄唱歌帖"

    parts = folder_name.split("_")
    if volume.startswith("koto_"):
        # e.g. 1_1_01 (year 1, sem 1), 2_4_01 (year 2, category 4)
        if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
            yr = parts[0]
            cat = parts[1]
            if cat in {"1", "2", "3"}:
                return f"第{['','一','二','三'][int(cat)]}學期"
            if yr == "1" and cat == "4":
                return "輪唱"
            if (yr == "1" and cat == "5") or (yr == "2" and cat == "4"):
                return "重音（合唱）"
    else:
        if parts[0] == "0":
            return "儀式歌"
        if parts[0] == "1":
            return "第一學期"
        if parts[0] == "2":
            return "第二學期"
        if parts[0] == "3":
            return "第三學期"
        if parts[0] == "4":
            return "參考／補充教材"
    return "其他"


def classify_scale(
    degree_weights: dict[int, float],
    active_pcs_count: int,
) -> tuple[str, str, float]:
    """Classify scale into pentatonic / quasi-pentatonic / hexatonic / heptatonic / chromatic.

    degree_weights maps semitone offset (0..11) relative to declared movable-do tonic (`?=`)
    to its percentage weight (0..100).
    """
    # Diatonic semitone offsets in major: 0(1), 2(2), 4(3), 5(4), 7(5), 9(6), 11(7)
    major_penta = {0, 2, 4, 7, 9}  # 1, 2, 3, 5, 6 (ヨナ抜き長音階 / 宮調式・羽調式)
    ritsu_1 = {0, 2, 5, 7, 9}      # 1, 2, 4, 5, 6 (律音階 C-D-F-G-A)
    ritsu_2 = {2, 4, 7, 9, 11}     # 2, 3, 5, 6, 7 (律音階 D-E-G-A-B)
    in_scale_1 = {4, 5, 9, 11, 0}  # 3, 4, 6, 7, 1 (都節／陰音階 E-F-A-B-C)
    in_scale_2 = {9, 10, 2, 4, 5}  # A-Bb-D-E-F
    diatonic = {0, 2, 4, 5, 7, 9, 11}

    active = {deg for deg, w in degree_weights.items() if w > 0.0}
    non_diatonic_weight = sum(w for deg, w in degree_weights.items() if deg not in diatonic)
    major_penta_ratio = sum(degree_weights.get(d, 0.0) for d in major_penta)
    ritsu_ratio = max(
        sum(degree_weights.get(d, 0.0) for d in ritsu_1),
        sum(degree_weights.get(d, 0.0) for d in ritsu_2),
    )
    in_ratio = max(
        sum(degree_weights.get(d, 0.0) for d in in_scale_1),
        sum(degree_weights.get(d, 0.0) for d in in_scale_2),
    )

    # Top 5 pitch classes total weight
    top5_weight = sum(sorted(degree_weights.values(), reverse=True)[:5])

    if len(active) <= 5:
        category = "嚴格五聲音階（≤5 音）"
        if active <= major_penta:
            subtype = "ヨナ抜き五聲（1-2-3-5-6，無 4/7）"
        elif active <= ritsu_1 or active <= ritsu_2:
            subtype = "律音階五聲（含四度、無三度或七度）"
        elif active <= in_scale_1 or active <= in_scale_2:
            subtype = "都節／陰音階五聲（含半音）"
        else:
            subtype = "其他五聲音階"
        return category, subtype, major_penta_ratio

    if top5_weight >= 95.0:
        category = "準五聲音階（6–7 音，核心 5 音 ≥95%）"
        if major_penta_ratio >= 95.0:
            subtype = "準ヨナ抜き五聲（4/7 僅為經過／輔助音 <5%）"
        elif ritsu_ratio >= 95.0:
            subtype = "準律音階五聲"
        elif in_ratio >= 95.0:
            subtype = "準陰音階五聲"
        else:
            subtype = "其他準五聲音階"
        return category, subtype, major_penta_ratio

    if len(active) == 6 and non_diatonic_weight == 0.0:
        category = "六聲音階（6 音自然音階）"
        missing = diatonic - active
        if missing == {5}:
            subtype = "六聲（缺 4 / Fa）"
        elif missing == {11}:
            subtype = "六聲（缺 7 / Ti）"
        else:
            subtype = "六聲（缺其他單一音級）"
        return category, subtype, major_penta_ratio

    if non_diatonic_weight > 0.0:
        category = "含變化音之七聲以上音階"
        if non_diatonic_weight < 3.0:
            subtype = "微幅變化音／臨時經過音（變化音佔比 <3%）"
        else:
            subtype = "局部轉調／臨時升降音（變化音佔比 ≥3%）"
        return category, subtype, major_penta_ratio

    category = "標準七聲自然音階（7 音）"
    if major_penta_ratio >= 85.0:
        subtype = "五聲骨幹型七聲（五聲佔比 85%–95%）"
    else:
        subtype = "典型西洋七聲自然音階（五聲佔比 <85%）"
    return category, subtype, major_penta_ratio


def load_duplicate_root_map(docs_dir: Path) -> dict[str, str]:
    """Build a union-find root map for songs linked by relation == '同曲' in duplicate_songs.json."""
    dup_json = docs_dir / "duplicate_songs.json"
    if not dup_json.exists():
        return {}
    data = json.loads(dup_json.read_text(encoding="utf-8"))
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for cluster in data.get("clusters", []):
        for entry in cluster.get("entries", []):
            src = entry.get("rel_dir", "")
            for peer in entry.get("peers", []):
                if peer.get("relation") == "同曲":
                    dst = peer.get("rel_dir", "")
                    if src and dst:
                        union(src, dst)

    return {k: find(k) for k in list(parent)}


def load_all_songs(
    docs_dir: Path = Path("docs"),
    collection: str | None = None,
    deduplicate: bool = False,
) -> list[SongRecord]:
    docs_dir = docs_dir.resolve()
    records: list[SongRecord] = []

    tmd_files = sorted(
        (p for p in docs_dir.rglob("*.tmd") if not p.name.endswith("_piano.tmd")),
        key=lambda p: natural_sort_key(str(p)),
    )

    for main_tmd in tmd_files:
        folder = main_tmd.parent
        volume = folder.parent.name
        col_name = folder.parent.parent.name
        if collection and col_name != collection:
            continue
        index_md = folder / "index.md"

        tmd_text = main_tmd.read_text(encoding="utf-8")
        md_text = index_md.read_text(encoding="utf-8") if index_md.exists() else ""

        title = folder.name
        declared_key_raw = "C"
        tempo_bpm = 100.0
        time_signature = "4/4"

        for line in tmd_text.split("{", 1)[0].splitlines():
            m_title = TITLE_RE.match(line)
            if m_title and title == folder.name:
                title = m_title.group(1)
            m_key = KEY_RE.match(line)
            if m_key:
                declared_key_raw = m_key.group(1)
            m_tempo = TEMPO_RE.match(line)
            if m_tempo:
                tempo_bpm = float(m_tempo.group(1))
            m_meter = METER_RE.match(line)
            if m_meter:
                time_signature = m_meter.group(1)

        declared_key = NORMALIZED_KEY_NAMES.get(declared_key_raw, declared_key_raw)
        tonic_pc = KEY_TO_PC.get(declared_key_raw, 0)

        inferred_tonality = f"{declared_key} 大調"
        m_inf = INFERRED_KEY_RE.search(md_text)
        if m_inf:
            inferred_tonality = m_inf.group(1).strip()
        inferred_mode = "小調" if "小調" in inferred_tonality else "大調"

        span_semitones = 0
        m_span = SPAN_RE.search(md_text)
        if m_span:
            span_semitones = int(m_span.group(1))

        pc_weights: dict[str, float] = {pc: 0.0 for pc in PITCH_NAMES}
        for line in md_text.splitlines():
            m_pc = PC_LINE_RE.match(line)
            if m_pc:
                pc_weights[m_pc.group(1)] = float(m_pc.group(2))

        degree_weights: dict[int, float] = {}
        for idx, pc in enumerate(PITCH_NAMES):
            deg = (idx - tonic_pc) % 12
            degree_weights[deg] = pc_weights.get(pc, 0.0)

        active_pcs = [pc for pc in PITCH_NAMES if pc_weights.get(pc, 0.0) > 0.0]
        active_degrees = sorted(deg for deg, w in degree_weights.items() if w > 0.0)

        penta_cat, scale_sub, major_penta_ratio = classify_scale(
            degree_weights, len(active_pcs)
        )

        records.append(
            SongRecord(
                collection=col_name,
                collection_label=COLLECTION_LABELS.get(col_name, col_name),
                volume=volume,
                volume_label=VOLUME_LABELS.get(volume, volume),
                folder_name=folder.name,
                semester=classify_semester(col_name, volume, folder.name),
                title=title,
                declared_key_raw=declared_key_raw,
                declared_key=declared_key,
                inferred_tonality=inferred_tonality,
                inferred_mode=inferred_mode,
                time_signature=time_signature,
                tempo_bpm=tempo_bpm,
                span_semitones=span_semitones,
                pc_weights=pc_weights,
                degree_weights=degree_weights,
                active_pcs=active_pcs,
                active_degrees=active_degrees,
                pentatonic_category=penta_cat,
                scale_subtype=scale_sub,
                major_penta_ratio=major_penta_ratio,
            )
        )

    if deduplicate:
        root_map = load_duplicate_root_map(docs_dir)
        seen_roots: set[str] = set()
        dedup_records: list[SongRecord] = []
        for r in records:
            rel_dir = f"{r.collection}/{r.volume}/{r.folder_name}"
            root = root_map.get(rel_dir, rel_dir)
            if root not in seen_roots:
                seen_roots.add(root)
                dedup_records.append(r)
        return dedup_records

    return records
