# Re:shōka 專案代理人指引

## 必要技能（Required Skills）

- **啟動時載入 `tmd` skill**：代理人在啟動或處理本專案的任何樂譜掃描、轉錄、編修與除錯時，**必須優先載入並參考 `tmd` skill**，以精確遵循 TMD 語法規則、時值與小節驗證機制，並善用 `tmd check` 進行校對。
- **樂譜掃描與轉錄時載入專屬 `shoka-score-grounding` skill**：當進行任何樂譜掃描、校對、圖檔光學轉錄或防止模型先驗幻覺時，**必須載入本專案專屬之 `.agents/skills/shoka-score-grounding` skill**，嚴格落實高解析切片定位、雙通道盲審轉錄與常理審查工具。

## 代理人互動與行為準則

- **人類詢問操作時立即回話**：當人類詢問「你在做什麼」、「你要幹嘛」或對操作提出疑問時，AI **必須立刻停止呼叫任何額外工具或背景指令，第一時間以文字清楚回覆**目前的行為、目的與進度，絕對不可繼續在背景執行指令或延遲回覆。
- **嚴禁將處理中圖檔與暫存檔案放在沙盒（Workspace）之外**：
  - **嚴格限縮在 Workspace 內**：所有要處理的圖片、樂譜掃描圖、PDF 抽頁、局部切片、裁切圖檔、臨時腳本與中間產物，**一律只能存放在當前 Workspace 內部目錄**（例如專案根目錄下的 `.tmp/`、各歌曲資料夾內的 `_slices/`，或直接放在歌曲目錄中）。
  - **絕對禁止使用全域 `/tmp` 或外部路徑**：**嚴禁**輸出至 `/tmp/`、`/var/folders/`、`~/Downloads/` 或任何 Workspace 外部路徑。
  - **理由與目的**：工具在沙盒模式（`BypassSandbox: false`）下對 Workspace 擁有完整的讀寫權限，可完全自動執行無須打擾人類；一旦命令或檔案路徑跨出 Workspace，終端機沙盒會觸發安全警告並反覆彈出視窗要求人類手動授權（`BypassSandbox: true`），造成極大困擾與操作中斷。
  - **切片工具與命令慣例**：使用 `sips`、`gs`、`slice_score.py` 等工具時，輸出目錄務必指定為專案內的 `.tmp/` 或 `_slices/`（例如 `-o .tmp/slices`，絕不可寫 `-o /tmp/slices`），處理完畢後將臨時檔案清理乾淨。

## 樂譜 TMD 語法隔離守則（嚴防 LilyPond 混淆）

在處理本專案的 TMD 樂譜時，**絕對禁止混淆 LilyPond 八度語法**：
- **高八度**：必須使用 `^`（如 `1^`, `3^`）。**嚴禁使用 `'`**（在 TMD 中 `'` 是升記號 ♯，如 `1'` 為 C♯ 升半音！）。
- **低八度**：必須使用 `_`（如 `5_`, `6_`）。**嚴禁使用 `,`**（在 TMD 中 `,` 是降記號 ♭，如 `5,` 為 G♭ 降半音！）。
- **簡譜記憶**：簡譜高音點在數字上方 $\rightarrow$ 箭頭朝上 `^`；簡譜低音點在數字下方 $\rightarrow$ 底線在下 `_`。
- **軌道命名**：單聲部主旋律軌道名稱**一律嚴格命名為 `:Piano`**（例如 `Song:Piano@|0|{`），絕對不得使用或改回 `:Vocal`。

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

### 新增文章與網站導覽（nav）維護規則

若新增了非歌曲的專題分析、史料考證、研究筆記或說明文件（如在 `docs/`、各歌集目錄或 `docs/archives/` 下新增 `.md` 檔案）：

1. **嚴禁直接手動編輯 `mkdocs.yml` 的 `nav:` 區段**：
   `mkdocs.yml` 的整個網站導覽樹（`nav:`）是由 Python 構建腳本 `scripts/song_markdown/site_nav.py` 在執行 `update_site_indexes_and_mkdocs()` 時自動掃描與重新生成的。任何直接寫在 `mkdocs.yml` 的手動修改，在下次執行 `generate_song_markdown.py` 或 `./rebuild_all.sh` 時都會被直接覆蓋洗掉。
2. **新增文章時必須改寫 `scripts/song_markdown/site_nav.py`**：
   - **全站層級文章或說明頁**（置於 `docs/` 根目錄或 `archives/` 等）：
     修改 `scripts/song_markdown/site_nav.py` 中的 `MKDOCS_CONFIG_HEADER` 清單，在 `nav:` 下方（如「資料與說明:」中）加入對應條目：
     ```python
     "      - 你的文章標題: your_article.md",
     ```
   - **特定歌集／教材之專題文章**（置於各 collection 目錄下）：
     修改 `scripts/song_markdown/site_nav.py` 中的 `COLLECTION_EXTRA_NAV_ITEMS` 字典，在對應的 collection slug 清單內加入 `("文章標題", "相對路徑")` 元組：
     ```python
     "shokacho": [
         ("史料整理筆記", "shokacho/research_notes.md"),
         ("你的文章標題", "shokacho/your_article.md"),
     ],
     ```
3. **執行腳本以重建 `mkdocs.yml`**：
   改寫 Python 腳本後，執行：
   ```bash
   python3 scripts/generate_song_markdown.py
   ```
   確認 `mkdocs.yml` 中的 `nav:` 已自動出現新增的條目。

## 批次轉錄與代理分流工作流

批次處理歷史樂譜時，代理的上下文成本與圖片歷史長度必須納入工作量設計。預設採用「每代理 1～2 首歌」的短批次，不採用每代理 5～8 首歌的大批次。

### 1. 每代理 1～2 首歌

- 每個代理工作單位預設只處理 1 首歌；歌曲很短、圖檔簡單且上下文仍乾淨時，最多處理 2 首。
- 一首歌完成 3 張左右的高解析切片讀取、TMD 修改、檢查與產生衍生檔後，代理應結束該工作單位。
- 不要讓代理帶著前幾首歌的切片圖片進入後續幾十輪 tool calls；圖片一旦滾入歷史訊息，後續每輪都會增加上下文負擔與誤讀風險。
- 若一首歌需要大量反覆看圖、存在多處模糊或需要重新切片，應維持單歌批次，不要為了湊數加入第二首歌。

### 2. 先機械篩檢，再直接進入修復

不要為每首歌安排一個獨立的「先視覺審查、再重新轉錄」輪次。標準流程是：

1. 先用本地工具批次執行 `audit_score.py`。
2. 再用正則與結構檢查抓出缺少 metadata、TMD 語法異常、拍數不平衡、歌詞／音符數不一致、產生檔缺失等問題。
3. 只有被機械檢查標記的歌曲才進入需要看圖的修復工作。
4. 修復代理直接從該歌曲的原始掃描切片開始重新判讀、修改與驗證，不另開一個重複的視覺審查輪。

可使用下列命令作為單曲修復前的最低檢查：

```bash
python3 .agents/skills/shoka-score-grounding/scripts/audit_score.py path/to/song.tmd
tmd check path/to/song.tmd
```

正則檢查只能負責找出可機械判斷的疑點，不能取代掃描圖對音符幾何位置的判讀。被標記的歌曲若涉及符頭位置、八度、加線、節奏符尾或模糊反覆記號，仍必須回到高解析切片確認。

### 3. 依任務分流模型等級

在 `run_workflow` 中依任務難度指定模型，不要讓所有步驟都使用主力模型：

- `model="flash"`：純機械檢查、正則／metadata 掃描、補全文歌詞註解、整理索引、簡單伴奏微調，以及不涉及圖像判讀的衍生檔重建。
- 主力模型：五線譜幾何判讀、符頭與加線定位、八度與節奏辨識、掃描模糊處理、反覆記號判讀，以及任何需要依高解析切片做音符決策的修復。
- 若任務同時包含機械檢查與視覺判讀，先用 `flash` 完成篩檢，再將實際需要看圖的歌曲交給主力模型；不要讓 `flash` 猜測圖上的音符。

模型分流不會降低 grounding 要求：無論使用哪個模型，歌曲資料仍必須以掃描圖為唯一事實來源，且所有修改都要回到 TMD source，再重新產生 Markdown、ABC 與音訊。

### 4. 批次完成條件

每個 1～2 首歌的代理工作單位完成前，必須留下：

- 目標歌曲與修改檔案清單。
- `audit_score.py` 與 `tmd check` 的結果。
- 若有看圖修復，記錄使用的掃描頁／切片與仍待確認的疑點。
- 重新產生後的衍生檔狀態。

完成後結束代理工作單位，讓下一個代理從乾淨上下文開始；不要在同一個上下文中無限追加歌曲。

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

### 3. 主旋律 TMD 與鋼琴伴奏 TMD 之歌詞分工（NEUTRINO 發音規範）

本專案將主旋律 TMD 與鋼琴伴奏 TMD 的歌詞用途明確分工：

* **原始主旋律 TMD（`<song>.tmd`）—— 史料忠實還原（SSOT）**：
  * 作為史料數位化與網頁呈現的唯一事實來源。
  * **必須嚴格保持與原書原譜完全相同**：完全保留原書印刷之漢字、舊字體、歷史假名遣（如「さへぎる」「けふ」「てふてふ」「せちゑ」）、大字促音／拗音（「シヨ」「きつ」）以及省略濁點的假名（「むら雲（くも）」）。
  * 嚴禁在主旋律 TMD 中為了合成發音而擅自現代化或替換假名。

* **鋼琴伴奏 TMD（`<song>_piano.tmd`）—— NEUTRINO 人聲合成專用（現代發音導向）**：
  * `scripts/render_neutrino_mix.py` 在呼叫 NEUTRINO 人聲引擎時，**優先讀取 `*_piano.tmd` 上的歌詞軌**作為語音合成標籤（musicXMLtoLabel）。
  * **避免使用漢字與歷史假名**：NEUTRINO 引擎無法自動準確推斷古字與歷史假名的實際歌唱發音，若留有漢字或歷史假名易導致缺音、發音錯誤或合成中斷。
  * **轉為現代純發音假名（平假名或片假名）**：
    1. **漢字全部替換為假名**：如「富士」轉為「フジ」、「先生」轉為「センセイ」、「海」轉為「ウミ」。
    2. **歷史假名轉為現代歌唱實際發音**：
       - 助詞「は」依發音轉為「ワ」（或「わ」）、「へ」轉為「エ」（或「え」）。
       - 詞中／詞尾的「は・ひ・ふ・へ・ほ」轉為「ワ・イ・ウ・エ・オ」（如「てふてふ」轉為「チョウチョ」、「さへぎる」轉為「サエギル」、「たふれて」轉為「タオレテ」）。
       - 「ゐ・ゑ」轉為「イ・エ」（或「い・え」）。
       - 四つ仮名：「ぢ・づ」依發音轉為「ジ・ズ」（或「じ・ず」）。
       - 補上原譜省略的濁點與半濁點（如「むら雲（くも）」轉為「ムラクモ」）。
       - 拗音／促音改用現代小字（如「シヨ」轉為「ショ」、「シヤ」轉為「シャ」）。
  * 音符、節奏、小節拍數與連音線長度仍須與主旋律完全對齊，確保語音與伴奏精準同步。

### 4. 機械化分步轉錄與自檢流程（Measure-by-Measure Verification）
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
