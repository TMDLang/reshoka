# Re:shoka 專案代理人指引

## 資料來源與產生檔

本專案以 TMD（`.tmd`）檔案作為歌曲資料的主要來源。歌曲頁面的 Markdown、ABC 樂譜、分析文字與音訊，都是由 `scripts/generate_song_markdown.py` 從 TMD 與相關素材產生。

因此，修正歌曲資料時不要直接修改產生出的 Markdown 檔案，例如：

- 歌曲標題：修改歌曲主旋律 TMD 檔案中的 `**歌曲標題**`
- 歌詞、詞曲作者、出處與樂譜資訊：修改主旋律 TMD 的 metadata 或歌詞內容
- 音符、節奏、拍號、調性與速度：修改對應的主旋律或鋼琴伴奏 TMD
- 書訊與卷首／卷末掃描頁的說明：若該頁由產生器重建，應修改產生器或相關來源資料，而不是只修改 `0_book_info/index.md`

修改 TMD 後，重新執行：

```bash
python3 scripts/generate_song_markdown.py <目標資料夾>
```

若需要重建所有衍生檔案，可執行：

```bash
python3 scripts/generate_song_markdown.py --force
```

產生器會更新歌曲資料夾中的 `index.md`、`.abc`、音訊，以及相關的冊別索引與網站導覽。不要把手動修改直接留在這些產生檔中，否則下次重新產生時會被覆蓋。

## 修改後檢查

修改樂譜後，應先使用 TMD 工具檢查語法與小節拍數：

```bash
tmd check path/to/song.tmd
tmd path/to/song.tmd -p
```

接著重新產生頁面，並用 `git diff` 檢查產生結果是否符合預期。若修改的是歌曲標題或其他顯示文字，確認冊別索引、歌曲頁面與跨冊連結中的名稱一致。

## 例外

只有在確認內容本來就是人工維護、且不會被 `scripts/generate_song_markdown.py` 覆寫時，才直接修改 Markdown。若不確定某個檔案是否為產生檔，先檢查產生器是否會寫入該路徑。
