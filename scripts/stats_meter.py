#!/usr/bin/env python3
"""節拍與速度統計腳本（分資料來源、分冊別／學年、分學期／單元）。

Usage:
    python3 scripts/stats_meter.py
    python3 scripts/stats_meter.py -o docs/stats_meter.md
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shoka_data import SongRecord, VOLUME_LABELS, load_all_songs


METER_ORDER = ["2/4", "4/4", "3/4", "6/8", "3/8", "2/2"]

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


def generate_report(records: list[SongRecord]) -> str:
    total = len(records)
    overall_meter = Counter(r.time_signature for r in records)
    tempos = [r.tempo_bpm for r in records]

    active_meters = [m for m in METER_ORDER if overall_meter.get(m, 0) > 0] + [
        m for m in sorted(overall_meter) if m not in METER_ORDER
    ]

    lines: list[str] = [
        "# 節拍與速度統計報告（Re:shoka 全站曲目）",
        "",
        f"- **總曲目數**：{total} 首",
        f"- **全體平均速度（BPM）**：{statistics.mean(tempos):.1f} BPM（中位數 {statistics.median(tempos):.0f} BPM，範圍 {min(tempos):.0f}–{max(tempos):.0f} BPM）",
        "",
        "## 1. 全體拍號（Time Signature）總覽",
        "",
        "| 拍號 | 曲數 | 佔比 | 平均速度 (BPM) | 速度範圍 (BPM) | 拍號性質 |",
        "| :--- | ---: | ---: | ---: | :--- | :--- |",
    ]

    meter_desc = {
        "2/4": "單拍子・二拍子（行進曲／童謠最常見）",
        "4/4": "單拍子・四拍子（抒情／儀式／合唱）",
        "3/4": "單拍子・三拍子（圓舞曲／搖曳律動）",
        "6/8": "複拍子・六八拍（舟歌／田園／跳躍律動）",
        "3/8": "單拍子・三八拍",
        "2/2": "單拍子・二二拍",
    }

    for m, count in overall_meter.most_common():
        m_tempos = [r.tempo_bpm for r in records if r.time_signature == m]
        avg_t = statistics.mean(m_tempos)
        rng_t = f"{min(m_tempos):.0f}–{max(m_tempos):.0f}"
        lines.append(
            f"| **`<{m}>`** | {count} | {count * 100 / total:.1f}% | {avg_t:.1f} | {rng_t} | {meter_desc.get(m, '—')} |"
        )

    # 2. 按資料來源統計
    lines.extend(
        [
            "",
            "## 2. 按資料來源（教材叢書）統計",
            "",
            "| 資料來源 | 總數 | " + " | ".join(f"`<{m}>`" for m in active_meters) + " | 平均 BPM |",
            "| :--- | ---: | " + " | ".join("---:" for _ in active_meters) + " | ---: |",
        ]
    )

    by_col: dict[str, list[SongRecord]] = defaultdict(list)
    for r in records:
        by_col[r.collection_label].append(r)

    for col_label, group in by_col.items():
        g_tot = len(group)
        g_meter = Counter(r.time_signature for r in group)
        cells = [
            f"{g_meter[m]} ({g_meter[m]*100/g_tot:.1f}%)" if g_meter.get(m, 0) else "—"
            for m in active_meters
        ]
        avg_bpm = statistics.mean(r.tempo_bpm for r in group)
        lines.append(
            f"| **{col_label}** | {g_tot} | " + " | ".join(cells) + f" | {avg_bpm:.1f} |"
        )

    # 3. 按冊別／學年統計
    lines.extend(
        [
            "",
            "## 3. 按冊別／學年統計",
            "",
            "| 冊別／學年 | 總數 | " + " | ".join(f"`<{m}>`" for m in active_meters) + " | 平均 BPM |",
            "| :--- | ---: | " + " | ".join("---:" for _ in active_meters) + " | ---: |",
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
        g_meter = Counter(r.time_signature for r in group)
        cells = [
            f"{g_meter[m]} ({g_meter[m]*100/g_tot:.1f}%)" if g_meter.get(m, 0) else "—"
            for m in active_meters
        ]
        avg_bpm = statistics.mean(r.tempo_bpm for r in group)
        lines.append(
            f"| **{VOLUME_LABELS[vol_key]}** | {g_tot} | "
            + " | ".join(cells)
            + f" | {avg_bpm:.1f} |"
        )

    # 4. 按學期／單元統計
    lines.extend(
        [
            "",
            "## 4. 按學期／單元分類統計",
            "",
            "| 學期／單元 | 總數 | " + " | ".join(f"`<{m}>`" for m in active_meters) + " | 平均 BPM |",
            "| :--- | ---: | " + " | ".join("---:" for _ in active_meters) + " | ---: |",
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
        g_meter = Counter(r.time_signature for r in group)
        cells = [
            f"{g_meter[m]} ({g_meter[m]*100/g_tot:.1f}%)" if g_meter.get(m, 0) else "—"
            for m in active_meters
        ]
        avg_bpm = statistics.mean(r.tempo_bpm for r in group)
        lines.append(
            f"| **{sem_label}** | {g_tot} | " + " | ".join(cells) + f" | {avg_bpm:.1f} |"
        )

    # 5. 特殊拍號（3/4 與 6/8 等非 2/4、4/4）代表曲目列表
    special_songs = [r for r in records if r.time_signature not in {"2/4", "4/4"}]
    if special_songs:
        lines.extend(
            [
                "",
                f"## 5. 三拍子與複拍子（`<3/4>`、`<6/8>` 等）曲目一覽（共 {len(special_songs)} 首）",
                "",
                "| 冊別 | 學期／單元 | 目錄 | 曲名 | 拍號 | 速度 (BPM) | 調號 |",
                "| :--- | :--- | :--- | :--- | :--- | ---: | :--- |",
            ]
        )
        for r in special_songs:
            lines.append(
                f"| {r.volume_label} | {r.semester} | `{r.folder_name}` | **{r.title}** | `<{r.time_signature}>` | {r.tempo_bpm:.0f} | `{r.declared_key}` |"
            )

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
        print(f"已輸出節拍統計報告至：{args.output}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
