#!/usr/bin/env python3
"""五聲音階與音階結構統計腳本（分資料來源、分冊別／學年、分學期／單元）。

Usage:
    python3 scripts/stats_pentatonic.py
    python3 scripts/stats_pentatonic.py -o docs/stats_pentatonic.md
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shoka_data import SongRecord, VOLUME_LABELS, load_all_songs


CATEGORY_ORDER = [
    "嚴格五聲音階（≤5 音）",
    "準五聲音階（6–7 音，核心 5 音 ≥95%）",
    "六聲音階（6 音自然音階）",
    "標準七聲自然音階（7 音）",
    "含變化音之七聲以上音階",
]

SEMESTER_ORDER = [
    "儀式歌",
    "第一學期",
    "第二學期",
    "第三學期",
    "參考／補充教材",
    "輪唱",
    "重音（合唱）",
    "全學年正課（公學校唱歌）",
]


def is_broad_pentatonic(r: SongRecord) -> bool:
    return r.pentatonic_category in {
        "嚴格五聲音階（≤5 音）",
        "準五聲音階（6–7 音，核心 5 音 ≥95%）",
    }


def generate_report(records: list[SongRecord]) -> str:
    total = len(records)
    cat_counter = Counter(r.pentatonic_category for r in records)
    sub_counter = Counter((r.pentatonic_category, r.scale_subtype) for r in records)

    strict_count = cat_counter["嚴格五聲音階（≤5 音）"]
    quasi_count = cat_counter["準五聲音階（6–7 音，核心 5 音 ≥95%）"]
    broad_count = strict_count + quasi_count

    # Scale degree 4 (semitone 5) and 7 (semitone 11) absence / low usage
    no_fa = sum(1 for r in records if r.degree_weights.get(5, 0.0) == 0.0)
    no_ti = sum(1 for r in records if r.degree_weights.get(11, 0.0) == 0.0)
    no_fa_and_ti = sum(
        1
        for r in records
        if r.degree_weights.get(5, 0.0) == 0.0 and r.degree_weights.get(11, 0.0) == 0.0
    )
    avg_penta_ratio = statistics.mean(r.major_penta_ratio for r in records)

    lines: list[str] = [
        "# 五聲音階與音階型態統計報告（Re:shoka 全站曲目）",
        "",
        f"- **總曲目數**：{total} 首",
        f"- **嚴格五聲音階（全曲僅使用 ≤5 個音級）**：**{strict_count} 首（{strict_count*100/total:.1f}%）**",
        f"- **準五聲音階（6–7 音，但核心 5 音時值佔比 ≥95%，第 4/7 音僅為點綴經過音）**：**{quasi_count} 首（{quasi_count*100/total:.1f}%）**",
        f"- **廣義五聲音階合計（嚴格＋準五聲）**：**{broad_count} 首（{broad_count*100/total:.1f}%）**",
        f"- **全體曲目「ヨナ抜き五聲（1-2-3-5-6）」平均時值佔比**：**{avg_penta_ratio:.1f}%**",
        f"- **完全不使用第 4 音（Fa）曲數**：{no_fa} 首（{no_fa*100/total:.1f}%）",
        f"- **完全不使用第 7 音（Ti）曲數**：{no_ti} 首（{no_ti*100/total:.1f}%）",
        f"- **同時不使用 4 與 7（典型ヨナ抜き）曲數**：{no_fa_and_ti} 首（{no_fa_and_ti*100/total:.1f}%）",
        "",
        "## 1. 音階型態分類總覽",
        "",
        "| 音階大類 | 細分類型 | 曲數 | 佔全體比例 |",
        "| :--- | :--- | ---: | ---: |",
    ]

    for cat in CATEGORY_ORDER:
        c_tot = cat_counter.get(cat, 0)
        if c_tot == 0:
            continue
        lines.append(f"| **{cat}** | **（小計）** | **{c_tot}** | **{c_tot*100/total:.1f}%** |")
        subs = [
            (sub, cnt)
            for (c_name, sub), cnt in sub_counter.items()
            if c_name == cat
        ]
        for sub, cnt in sorted(subs, key=lambda x: -x[1]):
            lines.append(f"| ↳ | {sub} | {cnt} | {cnt*100/total:.1f}% |")

    # 2. 按資料來源統計
    lines.extend(
        [
            "",
            "## 2. 按資料來源（教材叢書）統計",
            "",
            "| 資料來源 | 總數 | 嚴格五聲 (≤5音) | 準五聲 (≥95%) | 廣義五聲合計 | 六聲音階 | 七聲自然音階 | 含變化音 | 1-2-3-5-6 平均佔比 |",
            "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )

    by_col: dict[str, list[SongRecord]] = defaultdict(list)
    for r in records:
        by_col[r.collection_label].append(r)

    for col_label, group in by_col.items():
        g_tot = len(group)
        gc = Counter(r.pentatonic_category for r in group)
        s_cnt = gc["嚴格五聲音階（≤5 音）"]
        q_cnt = gc["準五聲音階（6–7 音，核心 5 音 ≥95%）"]
        b_cnt = s_cnt + q_cnt
        h_cnt = gc["六聲音階（6 音自然音階）"]
        d_cnt = gc["標準七聲自然音階（7 音）"]
        c_cnt = gc["含變化音之七聲以上音階"]
        avg_r = statistics.mean(r.major_penta_ratio for r in group)
        lines.append(
            f"| **{col_label}** | {g_tot} | {s_cnt} ({s_cnt*100/g_tot:.1f}%) | "
            f"{q_cnt} ({q_cnt*100/g_tot:.1f}%) | **{b_cnt} ({b_cnt*100/g_tot:.1f}%)** | "
            f"{h_cnt} ({h_cnt*100/g_tot:.1f}%) | {d_cnt} ({d_cnt*100/g_tot:.1f}%) | "
            f"{c_cnt} ({c_cnt*100/g_tot:.1f}%) | {avg_r:.1f}% |"
        )

    # 3. 按冊別／學年統計
    lines.extend(
        [
            "",
            "## 3. 按冊別／學年統計（由低年級至高年級之音階演進）",
            "",
            "| 冊別／學年 | 總數 | 嚴格五聲 (≤5音) | 準五聲 (≥95%) | 廣義五聲合計 | 六聲音階 | 七聲自然音階 | 含變化音 | 1-2-3-5-6 平均佔比 |",
            "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )

    by_vol: dict[str, list[SongRecord]] = defaultdict(list)
    for r in records:
        by_vol[r.volume].append(r)

    for vol_key in VOLUME_LABELS:
        group = by_vol.get(vol_key, [])
        if not group:
            continue
        g_tot = len(group)
        gc = Counter(r.pentatonic_category for r in group)
        s_cnt = gc["嚴格五聲音階（≤5 音）"]
        q_cnt = gc["準五聲音階（6–7 音，核心 5 音 ≥95%）"]
        b_cnt = s_cnt + q_cnt
        h_cnt = gc["六聲音階（6 音自然音階）"]
        d_cnt = gc["標準七聲自然音階（7 音）"]
        c_cnt = gc["含變化音之七聲以上音階"]
        avg_r = statistics.mean(r.major_penta_ratio for r in group)
        lines.append(
            f"| **{VOLUME_LABELS[vol_key]}** | {g_tot} | {s_cnt} ({s_cnt*100/g_tot:.1f}%) | "
            f"{q_cnt} ({q_cnt*100/g_tot:.1f}%) | **{b_cnt} ({b_cnt*100/g_tot:.1f}%)** | "
            f"{h_cnt} ({h_cnt*100/g_tot:.1f}%) | {d_cnt} ({d_cnt*100/g_tot:.1f}%) | "
            f"{c_cnt} ({c_cnt*100/g_tot:.1f}%) | {avg_r:.1f}% |"
        )

    # 4. 按學期／單元分類統計
    lines.extend(
        [
            "",
            "## 4. 按學期／單元分類統計",
            "",
            "| 學期／單元 | 總數 | 嚴格五聲 (≤5音) | 準五聲 (≥95%) | 廣義五聲合計 | 六聲音階 | 七聲自然音階 | 含變化音 | 1-2-3-5-6 平均佔比 |",
            "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )

    by_sem: dict[str, list[SongRecord]] = defaultdict(list)
    for r in records:
        by_sem[r.semester].append(r)

    sem_keys = [s for s in SEMESTER_ORDER if s in by_sem] + [
        s for s in by_sem if s not in SEMESTER_ORDER
    ]
    for sem_label in sem_keys:
        group = by_sem[sem_label]
        g_tot = len(group)
        gc = Counter(r.pentatonic_category for r in group)
        s_cnt = gc["嚴格五聲音階（≤5 音）"]
        q_cnt = gc["準五聲音階（6–7 音，核心 5 音 ≥95%）"]
        b_cnt = s_cnt + q_cnt
        h_cnt = gc["六聲音階（6 音自然音階）"]
        d_cnt = gc["標準七聲自然音階（7 音）"]
        c_cnt = gc["含變化音之七聲以上音階"]
        avg_r = statistics.mean(r.major_penta_ratio for r in group)
        lines.append(
            f"| **{sem_label}** | {g_tot} | {s_cnt} ({s_cnt*100/g_tot:.1f}%) | "
            f"{q_cnt} ({q_cnt*100/g_tot:.1f}%) | **{b_cnt} ({b_cnt*100/g_tot:.1f}%)** | "
            f"{h_cnt} ({h_cnt*100/g_tot:.1f}%) | {d_cnt} ({d_cnt*100/g_tot:.1f}%) | "
            f"{c_cnt} ({c_cnt*100/g_tot:.1f}%) | {avg_r:.1f}% |"
        )

    # 5. 首調各音級（1..7）全站平均時值權重
    lines.extend(
        [
            "",
            "## 5. 首調音級（Movable-Do Scale Degrees）全站平均時值分佈",
            "",
            "| 首調音級 | 半音差 | 全站平均時值佔比 | 出現曲數（佔比） | 角色說明 |",
            "| :--- | ---: | ---: | ---: | :--- |",
        ]
    )
    deg_labels = [
        (0, "1 (Do)", "主音／宮音（核心骨幹音）"),
        (2, "2 (Re)", "上主音／商音（核心骨幹音）"),
        (4, "3 (Mi)", "中音／角音（核心骨幹音）"),
        (5, "4 (Fa)", "下屬音（ヨナ抜き省略音）"),
        (7, "5 (Sol)", "屬音／徵音（核心骨幹音）"),
        (9, "6 (La)", "下中音／羽音（核心骨幹音／小調主音）"),
        (11, "7 (Ti)", "導音（ヨナ抜き省略音）"),
    ]
    for semitone, label, role in deg_labels:
        avg_w = statistics.mean(r.degree_weights.get(semitone, 0.0) for r in records)
        present_cnt = sum(1 for r in records if r.degree_weights.get(semitone, 0.0) > 0.0)
        lines.append(
            f"| **{label}** | +{semitone} | {avg_w:.2f}% | {present_cnt} ({present_cnt*100/total:.1f}%) | {role} |"
        )

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs", type=Path, default=Path("docs"), help="docs 目錄路徑")
    parser.add_argument("--collection", type=str, default=None, help="僅統計指定教材叢書（如 shintei_jido_shoka）")
    parser.add_argument("--deduplicate", action="store_true", help="排除跨冊重複（同曲）曲目")
    parser.add_argument("--output", "-o", type=Path, help="將 Markdown 報告輸出至指定檔案")
    args = parser.parse_args()

    records = load_all_songs(args.docs, collection=args.collection, deduplicate=args.deduplicate)
    report = generate_report(records)
    if args.output:
        args.output.write_text(report, encoding="utf-8")
        print(f"已輸出五聲音階統計報告至：{args.output}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
