#!/usr/bin/env python3
"""調性統計腳本（分資料來源、分冊別／學年、分學期／單元）。

Usage:
    python3 scripts/stats_tonality.py
    python3 scripts/stats_tonality.py --markdown
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shoka_data import SongRecord, VOLUME_LABELS, load_all_songs


KEY_ORDER = ["C", "G", "D", "A", "E", "F", "Bb", "Eb", "Ab", "Db"]

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


def format_counter_row(counter: Counter[str], total: int, keys: list[str]) -> list[str]:
    cells = []
    for k in keys:
        c = counter.get(k, 0)
        if c == 0:
            cells.append("—")
        else:
            cells.append(f"{c} ({c * 100 / total:.1f}%)")
    return cells


def generate_report(records: list[SongRecord]) -> str:
    total = len(records)
    overall_key = Counter(r.declared_key for r in records)
    overall_mode = Counter(r.inferred_mode for r in records)
    overall_inf = Counter(r.inferred_tonality for r in records)

    active_keys = [k for k in KEY_ORDER if overall_key.get(k, 0) > 0] + [
        k for k in sorted(overall_key) if k not in KEY_ORDER
    ]

    lines: list[str] = [
        "# 調性統計報告（Re:shoka 全站曲目）",
        "",
        f"- **總曲目數**：{total} 首",
        f"- **大小調分布（依 `tmd inspect` 調性診斷）**：大調 {overall_mode['大調']} 首（{overall_mode['大調']*100/total:.1f}%）／小調 {overall_mode['小調']} 首（{overall_mode['小調']*100/total:.1f}%）",
        "",
        "## 1. 全體調號（首調基準 `?=`）總覽",
        "",
        "| 調號 (`?=`) | 曲數 | 佔比 | 升降記號數 |",
        "| :--- | ---: | ---: | :--- |",
    ]

    sig_desc = {
        "C": "0（無升降）",
        "G": "1♯",
        "D": "2♯",
        "A": "3♯",
        "E": "4♯",
        "F": "1♭",
        "Bb": "2♭",
        "Eb": "3♭",
        "Ab": "4♭",
        "Db": "5♭",
    }

    for k, count in overall_key.most_common():
        lines.append(
            f"| **{k}** | {count} | {count * 100 / total:.1f}% | {sig_desc.get(k, '—')} |"
        )

    # 2. 分資料來源
    lines.extend(
        [
            "",
            "## 2. 按資料來源（教材叢書）統計",
            "",
            "| 資料來源 | 總數 | 大調 | 小調 | " + " | ".join(active_keys) + " |",
            "| :--- | ---: | ---: | ---: | " + " | ".join("---:" for _ in active_keys) + " |",
        ]
    )

    by_col: dict[str, list[SongRecord]] = defaultdict(list)
    for r in records:
        by_col[r.collection_label].append(r)

    for col_label, group in by_col.items():
        g_tot = len(group)
        g_key = Counter(r.declared_key for r in group)
        g_mode = Counter(r.inferred_mode for r in group)
        maj_str = f"{g_mode['大調']} ({g_mode['大調']*100/g_tot:.1f}%)"
        min_str = f"{g_mode['小調']} ({g_mode['小調']*100/g_tot:.1f}%)"
        cells = [str(g_key.get(k, 0)) if g_key.get(k, 0) else "—" for k in active_keys]
        lines.append(
            f"| **{col_label}** | {g_tot} | {maj_str} | {min_str} | " + " | ".join(cells) + " |"
        )

    # 3. 分冊別／學年
    lines.extend(
        [
            "",
            "## 3. 按冊別／學年統計",
            "",
            "| 冊別／學年 | 總數 | 大調 | 小調 | " + " | ".join(active_keys) + " |",
            "| :--- | ---: | ---: | ---: | " + " | ".join("---:" for _ in active_keys) + " |",
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
        g_key = Counter(r.declared_key for r in group)
        g_mode = Counter(r.inferred_mode for r in group)
        maj_str = f"{g_mode['大調']} ({g_mode['大調']*100/g_tot:.1f}%)"
        min_str = f"{g_mode['小調']} ({g_mode['小調']*100/g_tot:.1f}%)"
        cells = [str(g_key.get(k, 0)) if g_key.get(k, 0) else "—" for k in active_keys]
        lines.append(
            f"| **{VOLUME_LABELS[vol_key]}** | {g_tot} | {maj_str} | {min_str} | "
            + " | ".join(cells)
            + " |"
        )

    # 4. 分學期／單元
    lines.extend(
        [
            "",
            "## 4. 按學期／單元分類統計",
            "",
            "| 學期／單元 | 總數 | 大調 | 小調 | " + " | ".join(active_keys) + " |",
            "| :--- | ---: | ---: | ---: | " + " | ".join("---:" for _ in active_keys) + " |",
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
        g_key = Counter(r.declared_key for r in group)
        g_mode = Counter(r.inferred_mode for r in group)
        maj_str = f"{g_mode['大調']} ({g_mode['大調']*100/g_tot:.1f}%)"
        min_str = f"{g_mode['小調']} ({g_mode['小調']*100/g_tot:.1f}%)"
        cells = [str(g_key.get(k, 0)) if g_key.get(k, 0) else "—" for k in active_keys]
        lines.append(
            f"| **{sem_label}** | {g_tot} | {maj_str} | {min_str} | " + " | ".join(cells) + " |"
        )

    # 5. 各冊 × 各學期交叉統計（前三名常見調號）
    lines.extend(
        [
            "",
            "## 5. 各冊 × 各學期調性分佈明細",
            "",
            "| 冊別 | 第一學期（主要調號） | 第二學期（主要調號） | 第三學期（主要調號） | 參考／補充／合唱（主要調號） |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]
    )

    for vol_key in VOLUME_LABELS:
        group = by_vol.get(vol_key, [])
        if not group:
            continue
        if vol_key == "grade_3":
            c = Counter(r.declared_key for r in group)
            top_str = ", ".join(f"{k}:{v}" for k, v in c.most_common(4))
            lines.append(f"| **{VOLUME_LABELS[vol_key]}** | {top_str}（全學年 15 首） | — | — | — |")
            continue

        sem_cells = []
        for target_sems in (
            {"第一學期"},
            {"第二學期"},
            {"第三學期"},
            {"參考／補充教材", "輪唱", "重音（合唱）"},
        ):
            sub = [r for r in group if r.semester in target_sems]
            if not sub:
                sem_cells.append("—")
            else:
                c = Counter(r.declared_key for r in sub)
                top_str = ", ".join(f"{k}:{v}" for k, v in c.most_common(4))
                sem_cells.append(f"共 {len(sub)} 首（{top_str}）")
        lines.append(f"| **{VOLUME_LABELS[vol_key]}** | " + " | ".join(sem_cells) + " |")

    # 6. tmd inspect 實測調性排行前 15 名
    lines.extend(
        [
            "",
            "## 6. `tmd inspect` 實測調性診斷排行（Top 15）",
            "",
            "| 排名 | 實測調性 | 曲數 | 佔比 |",
            "| ---: | :--- | ---: | ---: |",
        ]
    )
    for idx, (inf_t, count) in enumerate(overall_inf.most_common(15), start=1):
        lines.append(f"| {idx} | **{inf_t}** | {count} | {count * 100 / total:.1f}% |")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs", type=Path, default=Path("docs"), help="docs 目錄路徑")
    parser.add_argument("--output", "-o", type=Path, help="將 Markdown 報告輸出至指定檔案")
    args = parser.parse_args()

    records = load_all_songs(args.docs)
    report = generate_report(records)
    if args.output:
        args.output.write_text(report, encoding="utf-8")
        print(f"已輸出調性統計報告至：{args.output}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
