#!/usr/bin/env python3
"""
slice_score.py: 樂譜掃描圖檔精確五線譜切片工具
用途：自動透過水平黑色像素投影定位五線譜真實 Y 座標，
並精準裁剪各行五線譜與歌詞，徹底解決固定比例切斷譜線與引發模型幻覺之問題。
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="樂譜圖檔切片工具（自動五線偵測版）")
    parser.add_argument("target", help="目標圖片路徑或歌曲目錄")
    parser.add_argument("-n", "--staves", type=int, default=4, help="五線譜行數提示（若未指定由投影自動判斷）")
    parser.add_argument("-o", "--output", help="輸出資料夾（預設在目標旁的 _slices/）")

    args = parser.parse_args()
    target_path = Path(args.target).resolve()

    if target_path.is_dir():
        imgs = sorted(target_path.glob("P*.jpg")) or sorted(target_path.glob("*.jpg"))
        if not imgs:
            print(f"錯誤：在 {target_path} 找不到 jpg 圖檔", file=sys.stderr)
            sys.exit(1)
        image_path = imgs[0]
        out_dir = Path(args.output).resolve() if args.output else target_path / "_slices"
    else:
        image_path = target_path
        out_dir = Path(args.output).resolve() if args.output else image_path.parent / "_slices"

    swift_script = Path(__file__).parent / "slice_score.swift"
    if not swift_script.exists():
        print(f"錯誤：找不到切片腳本 {swift_script}", file=sys.stderr)
        sys.exit(1)

    print(f"📷 來源圖檔：{image_path}")
    print(f"✂️  執行五線譜水平投影自動偵測與無損切片...")
    res = subprocess.run(["swift", str(swift_script), str(image_path), str(out_dir)], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"❌ 切片失敗：\n{res.stderr or res.stdout}", file=sys.stderr)
        sys.exit(1)

    print(res.stdout.strip())
    print(f"✅ 切片完成！請檢視 {out_dir} 內的高解析局部切片。")


if __name__ == "__main__":
    main()
