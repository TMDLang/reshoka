# Re:shōka 專案代理人指引

## 必要技能（Required Skills）

- **啟動時載入 `tmd` skill**：代理人在啟動或處理本專案的任何樂譜掃描、轉錄、編修與除錯時，**必須優先載入並參考 `tmd` skill**，以精確遵循 TMD 語法規則、時值與小節驗證機制，並善用 `tmd check` 進行校對。
- **樂譜掃描與轉錄時載入專屬 `shoka-score-grounding` skill**：當進行任何樂譜掃描、校對、圖檔光學轉錄或防止模型先驗幻覺時，**必須載入本專案專屬之 `.agents/skills/shoka-score-grounding` skill**，嚴格落實高解析切片定位、雙通道盲審轉錄與常理審查工具。

## 代理人互動與行為準則

- **人類詢問操作時立即回話**：當人類詢問「你在做什麼」、「你要幹嘛」或對操作提出疑問時，AI **必須立刻停止呼叫任何額外工具或背景指令，第一時間以文字清楚回覆**目前的行為、目的與進度，絕對不可繼續在背景執行指令或延遲回覆。

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

## 樂譜掃描與轉錄防幻覺規範（Score Transcription Grounding Rules）

在依據樂譜掃描圖檔（`.jpg` / `.png`）建立或校對樂譜（`.tmd`、`.abc`）時，AI 代理人必須嚴格遵循以下「零先驗（Zero-Prior）」與「封閉世界（Closed-World）」原則：

### 1. 唯一資料來源原則（Single Source of Truth）
* **以圖為本，閉門轉錄**：掃描圖檔是轉錄的**唯一真實來源（Ground Truth）**。轉錄行為必須等同於「光學符號識別與結構化」，嚴禁引入圖檔以外的外部資訊。
* **所見即所得**：只有在圖檔中肉眼明確可見的音符、休止符、拍號、調號、小節線、歌詞與反覆記號才能被轉錄。
* **模糊處理原則**：若掃描模糊、缺角或難以辨識，必須標記待查或以註釋說明，**絕對嚴禁自行猜測補齊**。

### 2. 阻斷歌名先驗知識（Anti-Prior / Anti-Recognition Rule）
* **歌名去語意化**：樂譜上的「歌名」僅為圖檔中的一段文字標記，**不得作為提取模型內部知識的觸發詞**。
* **嚴禁調取傳唱記憶**：
  * 面對極高知名度的曲目（如《春の小川》、《故郷の空》、《蛍の光》等），模型內部通常儲存了現代標準版或民間廣為流傳的版本。**嚴禁依賴預訓練記憶中的旋律、拍子、節奏型或歌詞填入 TMD**。
  * 歷史教材（如臺灣總督府各時期唱歌集、各版次尋常科教材）常有專門的教材改編、音域調整、節奏簡化、甚至變奏。**「長得像知名歌曲」不等於「音符完全相同」，必須一拍一音逐一核對圖檔上的符頭與符桿**。
* **禁止現代化歌詞**：歌詞字元必須嚴格按照掃描頁上的文字抄錄，保留歷史假名遣（如「かうべ」、「けふ」）與原書漢字／異體字，不得自動轉為現代日文假名或進行簡體/繁體轉換。

> [!IMPORTANT]
> **歷史假名遣（歴史的仮名遣）不可侵犯原則**：
> 本專案所有戰前教材一律使用歷史假名遣（如「さへぎる」、「けふ」、「くわん」、「せちゑ」）與舊字體，且活字鉛印常省略濁點（如「むら雲（くも）」）或使用大字促音／拗音（如「シヨ」、「きつ」）。**嚴禁 AI 依據現代日語文法或現代發音自動修正、現代化或私自補上濁點**（詳見 `.agents/skills/shoka-score-grounding/references/historical_kana.md`）。

### 3. 機械化分步轉錄與自檢流程（Measure-by-Measure Verification）
為避免整體性記憶取代局部性觀察，轉錄時必須依序分步執行：

1. **元資料抽取**：
   * 調號（Key Signature）：數出譜表上的升降記號數量，確認調性。
   * 拍號（Time Signature）：記錄譜表開頭標示的拍號（例如 4/4、2/4、6/8、3/4）。
2. **小節拆解與視覺對齊**：
   * 逐行、逐小節核對。轉錄每一小節時，僅關注該小節內的符頭位置（Pitch）與符尾／符槓長度（Duration）。
   * 每一小節完成時，計算該小節拍數總和，必須與拍號嚴格相等（弱起小節除外）。
3. **歌詞音節對位**：
   * 逐字核對字元與音符的垂直對應關係，不得遺漏或自行挪動拍位。
4. **反覆與結構**：
   * 譜上印有反覆記號、D.C.、Fine 才做標記；譜面上沒有印刷的段落，嚴禁依據「這首歌通常有副歌／第二段」自行補全。

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

| namespace     | 用途                       | 建議 value                                                                                                                                                                                                                                                                                                                             |
| ------------- | -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `collection`  | 教材／資料集               | `kogakko_shoka`, `shintei_jido_shoka`, `utanohon`, `shokacho`, `kyoeki_shoka`                                                                                                                                                                                                                                                          |
| `volume`      | 冊別或學年                 | 目錄使用的資料夾名稱，例如 `vol_01`, `vol_07`, `grade_3_2020_006_0847_0003`, `kan_1_854862`～`kan_4_854865`                                                                                                                                                                                                                            |
| `source`      | 原始出版物或來源           | `horai_shokashu`, `school_textbook`, `shokacho_notebook`, `ichijo_kashu`, `unknown`                                                                                                                                                                                                                                                    |
| `source_page` | 原始頁碼                   | `P246`, `P229a`；保留原書頁碼，不寫網站頁碼                                                                                                                                                                                                                                                                                            |
| `date`        | 明確的抄錄／出版／創作年代 | `1927`, `1920s`, `showa_02`                                                                                                                                                                                                                                                                                                            |
| `provenance`  | 資料來源型態               | `manuscript_copy`, `printed_text`, `clipping`, `unknown`                                                                                                                                                                                                                                                                               |
| `evidence`    | 編輯判斷的證據層級         | `scan_verified`, `transcription_verified`, `inferred`, `editorial`                                                                                                                                                                                                                                                                     |
| `genre`       | 曲種或音樂功能             | `children_song`, `lullaby`, `march`, `dance`, `work_song`, `ceremonial`, `patriotic`, `folk_tune`, `traditional_theater`, `instrumental`                                                                                                                                                                                               |
| `theme`       | 歌詞／題材主題             | `taiwan`, `nature`, `landscape`, `weather`, `animal`, `plant`, `water`, `transport`, `school_life`, `family`, `friendship`, `work`, `military`, `imperial`, `festival`, `seasons`, `time_of_day`, `folklore`, `history`, `technology`, `food`, `travel`, `emotion`, `religion`, `community`, `music`, `place`, `sport`, `unclassified` |
| `form`        | 聲部或曲式                 | `strophic`, `unison`, `two_part`, `round`, `question_answer`, `instrumental`                                                                                                                                                                                                                                                           |
| `version`     | 檔案代表的版本             | `source_transcription`, `piano_arrangement`, `duplicate_version`, `modern_editorial`                                                                                                                                                                                                                                                   |
| `orthography` | 歌詞假名遣與正字法         | `historical_kana`, `modern_kana`                                                                                                                                                                                                                                                                                                      |
| `analysis`    | 經分析得到的音樂特徵       | `pentatonic`, `major`, `minor`, `modal`, `repeated_melody`, `wide_range`                                                                                                                                                                                                                                                               |

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

## 歷史文件與史料引用規範

在新增或更新本專案的人工維護歷史文件（如 `docs/shokacho/research_notes.md`、`docs/shokacho/horai_shokashu.md`、`docs/archives/index.md`、`archives_research.md` 等）時，**凡引用或提及任何史料、館藏文物、檔案、原典書籍、唱片或資料庫紀錄，皆必須附上原始資料 URL**（例如：國立臺灣歷史博物館典藏網連結、國家文化記憶庫連結、中研院《臺灣總督府職員錄系統》查詢網址、日本國立國會圖書館 NDL Digital Collections PID／NDL Lab 網址、高解析掃描原圖 URL 或本地歸檔圖檔連結），確保所有整理敘述皆可追溯並直接查核原始出處。
