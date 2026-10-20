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

## TMD 歌曲 tagging 規範

歌曲的可搜尋分類應寫在**主旋律 TMD** 的 metadata；鋼琴伴奏 TMD 不重複歌曲分類，除非該檔案本身代表不同的版本或編曲。使用 TMD 的 `~` metadata 語法，每個 tag 一行：

```tmd
~ "tag: collection:shokacho"
~ "tag: volume:vol_07"
~ "tag: source:horai_shokashu"
~ "tag: source_page:P246"
~ "tag: provenance:manuscript_copy"
~ "tag: evidence:scan_verified"
~ "tag: genre:children_song"
~ "tag: theme:animal"
~ "tag: theme:taiwan"
```

### 命名規則

- 格式固定為 `tag: namespace:value`；`namespace` 與 `value` 使用小寫 ASCII `snake_case`。
- 一行只放一個 tag；不要用逗號串接多個 tag，也不要在 value 中加入自由描述。
- 優先使用下列受控詞彙；找不到合適詞彙時先補充本節，不要自行創造同義詞。
- 只標註有史料或樂譜依據的事實。推測、分類與後來編配必須使用 `evidence:inferred` 或 `evidence:editorial` 明確區分。
- 調性、拍號、速度、音域與五聲音階比例等可由 TMD 或分析腳本計算的欄位，不要重複寫成 tag；只有在需要表達「分析結論」時才加入 `analysis:*`。

### 受控詞彙

| namespace | 用途 | 建議 value |
| --- | --- | --- |
| `collection` | 教材／資料集 | `kogakko_shoka`, `shintei_jido_shoka`, `shokacho` |
| `volume` | 冊別或學年 | 目錄使用的資料夾名稱，例如 `vol_01`, `vol_07`, `grade_3_2020_006_0847_0003` |
| `source` | 原始出版物或來源 | `horai_shokashu`, `school_textbook`, `shokacho_notebook`, `ichijo_kashu`, `unknown` |
| `source_page` | 原始頁碼 | `P246`, `P229a`；保留原書頁碼，不寫網站頁碼 |
| `date` | 明確的抄錄／出版／創作年代 | `1927`, `1920s`, `showa_02` |
| `provenance` | 資料來源型態 | `manuscript_copy`, `printed_text`, `clipping`, `unknown` |
| `evidence` | 編輯判斷的證據層級 | `scan_verified`, `transcription_verified`, `inferred`, `editorial` |
| `genre` | 曲種或音樂功能 | `children_song`, `lullaby`, `march`, `dance`, `work_song`, `ceremonial`, `patriotic`, `folk_tune`, `traditional_theater`, `instrumental` |
| `theme` | 歌詞／題材主題 | `taiwan`, `nature`, `landscape`, `weather`, `animal`, `plant`, `water`, `transport`, `school_life`, `family`, `friendship`, `work`, `military`, `imperial`, `festival`, `seasons`, `time_of_day`, `folklore`, `history`, `technology`, `food`, `travel`, `emotion`, `religion`, `community`, `music`, `place`, `sport`, `unclassified` |
| `form` | 聲部或曲式 | `strophic`, `unison`, `two_part`, `round`, `question_answer`, `instrumental` |
| `version` | 檔案代表的版本 | `source_transcription`, `piano_arrangement`, `duplicate_version`, `modern_editorial` |
| `analysis` | 經分析得到的音樂特徵 | `pentatonic`, `major`, `minor`, `modal`, `repeated_melody`, `wide_range` |

題材標記要區分：`theme:weather` 只用於雨、雷、雲、霧、露、風等實際天候現象；四季與季節性景物使用 `theme:seasons`；朝、夕、夜、月夜等時間意象使用 `theme:time_of_day`。

### 使用原則

一首歌可以有多個 `theme`，但同一 namespace 不要放互相矛盾的值。例如一首描寫水牛的臺灣童謠可以是：

```tmd
~ "tag: collection:shokacho"
~ "tag: volume:vol_07"
~ "tag: source:horai_shokashu"
~ "tag: source_page:P246"
~ "tag: provenance:manuscript_copy"
~ "tag: evidence:scan_verified"
~ "tag: genre:children_song"
~ "tag: theme:animal"
~ "tag: theme:taiwan"
~ "tag: theme:work"
~ "tag: version:source_transcription"
~ "tag: analysis:major"
```

若是後來新增的鋼琴伴奏檔，使用：

```tmd
~ "tag: version:piano_arrangement"
~ "tag: evidence:editorial"
```

`scripts/generate_song_markdown.py` 必須辨識 `tag:`，將 tags 從一般來源欄位分離；tags 不應被列入歌曲頁面的「出處」。若未來要在網站顯示或篩選 tags，再另外將 tags 加入產生器的結構化輸出。

## 修改後檢查

修改樂譜後，應先使用 TMD 工具檢查語法與小節拍數：

```bash
tmd check path/to/song.tmd
tmd path/to/song.tmd -p
```

接著重新產生頁面，並用 `git diff` 檢查產生結果是否符合預期。若修改的是歌曲標題或其他顯示文字，確認冊別索引、歌曲頁面與跨冊連結中的名稱一致。

## 例外

只有在確認內容本來就是人工維護、且不會被 `scripts/generate_song_markdown.py` 覆寫時，才直接修改 Markdown。若不確定某個檔案是否為產生檔，先檢查產生器是否會寫入該路徑。
