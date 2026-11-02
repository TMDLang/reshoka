#!/usr/bin/env python3
"""
slice_score.py: 樂譜掃描圖檔無損切片工具
用途：將歷史樂譜掃描圖檔（如 P025.jpg）無損切分為各行五線譜與歌詞區塊，
避免多模態 AI 在縮圖下因解析度不足造成五線與符頭粘連、音高集體平移之幻覺。
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


def get_image_dimensions(image_path: Path) -> tuple[int, int]:
    """使用 macOS 內建 sips 或 ffmpeg 取得圖片寬度與高度。"""
    try:
        res = subprocess.run(
            ["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(image_path)],
            capture_output=True,
            text=True,
            check=True,
        )
        w_match = re.search(r"pixelWidth:\s*(\d+)", res.stdout)
        h_match = re.search(r"pixelHeight:\s*(\d+)", res.stdout)
        if w_match and h_match:
            return int(w_match.group(1)), int(h_match.group(1))
    except Exception:
        pass

    # Fallback to ffprobe
    res = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=s=x:p=0",
            str(image_path),
        ],
        capture_output=True,
        text=True,
    )
    if "x" in res.stdout:
        parts = res.stdout.strip().split("x")
        return int(parts[0]), int(parts[1])

    raise RuntimeError(f"無法讀取圖片尺寸：{image_path}")


def crop_image(
    src: Path, dst: Path, width: int, height: int, offset_x: int, offset_y: int
):
    """使用 sips 裁剪指定矩形區域（寬高與偏移量）。"""
    dst.parent.mkdir(parents=True, exist_ok=True)
    # sips -c height width --cropOffset offsetY offsetX
    subprocess.run(
        [
            "sips",
            "-c",
            str(height),
            str(width),
            "--cropOffset",
            str(offset_y),
            str(offset_x),
            str(src),
            "--out",
            str(dst),
        ],
        capture_output=True,
        check=True,
    )


def slice_score(
    image_path: Path, output_dir: Path, num_staves: int = 4
) -> list[Path]:
    width, height = get_image_dimensions(image_path)
    print(f"📷 來源圖檔：{image_path} ({width} x {height} px)")
    output_dir.mkdir(parents=True, exist_ok=True)

    cropped_files = []

    # 針對日治時期《新定兒童唱歌》、《公學校唱歌》典型書頁版型比例
    # 標題與版權：0% ~ 18%
    # 五線譜與各行歌詞：約 18% ~ 66%
    # 底欄全文歌詞：約 66% ~ 95%
    score_top_ratio = 0.17
    score_bottom_ratio = 0.67
    lyrics_bottom_ratio = 0.96

    score_top = int(height * score_top_ratio)
    score_bottom = int(height * score_bottom_ratio)
    score_height = score_bottom - score_top
    staff_band_height = int(score_height / num_staves)
    # 增加上下 15% 的重疊邊界以避免切斷加線或歌詞
    overlap = int(staff_band_height * 0.15)

    margin_x = int(width * 0.05)
    crop_w = width - (2 * margin_x)

    print(f"✂️  開始切分 {num_staves} 行五線譜與底欄歌詞...")

    for i in range(num_staves):
        y_start = score_top + (i * staff_band_height) - overlap
        y_end = score_top + ((i + 1) * staff_band_height) + overlap
        y_start = max(0, y_start)
        y_end = min(height, y_end)
        crop_h = y_end - y_start
        offset_y = y_start
        offset_x = margin_x

        dst = output_dir / f"staff_{i+1}.png"
        crop_image(image_path, dst, crop_w, crop_h, offset_x, offset_y)
        cropped_files.append(dst)
        print(f"   [行 {i+1}] 已輸出：{dst.name} (Y: {y_start}..{y_end})")

    # 底欄歌詞全文
    lyrics_top = int(height * 0.65)
    lyrics_bot = int(height * lyrics_bottom_ratio)
    lyrics_h = lyrics_bot - lyrics_top
    offset_y = lyrics_top
    offset_x = margin_x

    dst_lyrics = output_dir / "bottom_lyrics.png"
    crop_image(image_path, dst_lyrics, crop_w, lyrics_h, offset_x, offset_y)
    cropped_files.append(dst_lyrics)
    print(f"   [底欄歌詞] 已輸出：{dst_lyrics.name} (Y: {lyrics_top}..{lyrics_bot})")

    return cropped_files


def main():
    parser = argparse.ArgumentParser(description="樂譜圖檔切片工具")
    parser.add_argument("target", help="目標圖片路徑或歌曲目錄")
    parser.add_argument("-n", "--staves", type=int, default=4, help="五線譜行數（預設 4）")
    parser.add_argument("-o", "--output", help="輸出資料夾（預設在目標旁的 _slices/）")

    args = parser.parse_args()
    target_path = Path(args.target)

    if target_path.is_dir():
        # 尋找目錄中的 P*.jpg 或第一張 jpg
        imgs = sorted(target_path.glob("P*.jpg")) or sorted(target_path.glob("*.jpg"))
        if not imgs:
            print(f"錯誤：在 {target_path} 找不到 jpg 圖檔", file=sys.stderr)
            sys.exit(1)
        image_path = imgs[0]
        out_dir = Path(args.output) if args.output else target_path / "_slices"
    else:
        image_path = target_path
        out_dir = Path(args.output) if args.output else image_path.parent / "_slices"

    slice_score(image_path, out_dir, args.staves)
    print(f"✅ 切片完成！請檢視 {out_dir} 內的高解析局部切片。")


if __name__ == "__main__":
    main()
