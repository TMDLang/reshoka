import os
import re

base_url = "https://tmdlang.github.io/reshoka/"

with open("scratch/sing.md", "r", encoding="utf-8") as f:
    text = f.read()

# Verify all links exist in docs/
broken_links = []


def link(url_path, display_text):
    full_url = base_url + url_path
    # check doc path
    doc_path = os.path.join("docs", url_path.rstrip("/"))
    if not (
        os.path.exists(doc_path)
        or os.path.exists(doc_path + ".md")
        or os.path.exists(os.path.join(doc_path, "index.md"))
    ):
        broken_links.append((display_text, full_url, doc_path))
    return f"[{display_text}]({full_url})"


# 1. Early text
text = text.replace(
    "郭明峰的《水牛》", f"郭明峰的{link('taiwan_no_uta/3_suigyu/', '《水牛》')}"
)
text = text.replace(
    "1915 年台灣總督府的《公學校唱歌集》與 1934 年的《公學校唱歌》",
    f"1915 年台灣總督府的{link('kogakko_shokashu_1915/', '《公學校唱歌集》')}與 1934 年的{link('kogakko_shoka/', '《公學校唱歌》')}",
)
text = text.replace(
    "1929 年的《臺灣の歌》", f"1929 年的{link('taiwan_no_uta/', '《臺灣の歌》')}"
)
text = text.replace(
    "1932-1933 年的唱歌歌詞懸賞",
    f"1932-1933 年的{link('kogakko_shoka/lyrics_contest/', '唱歌歌詞懸賞')}",
)

# 2. 楊金土手抄唱歌帖
text = text.replace(
    "抄了一首《近眼のしくじり》，寫大正 13 年 2 月 10 日邱粟花抄",
    f"抄了一首{link('shokacho/vol_02/p080_kingan_no_shikujiri/', '《近眼のしくじり》')}，寫大正 13 年 2 月 10 日邱粟花抄",
)
text = text.replace(
    "大正 13 年（1924）五月抄的〈天然の美〉",
    f"大正 13 年（1924）五月抄的{link('shokacho/vol_01/p131_tennen_no_bi/', '〈天然の美〉')}",
)
text = text.replace(
    "這本筆記本自己就印有〈君が代〉、〈始政紀念日〉這些儀式歌",
    f"這本筆記本自己就印有{link('shokacho/vol_01/p120_kimigayo/', '〈君が代〉')}、{link('shokacho/vol_01/p125_shisei_kinenbi/', '〈始政紀念日〉')}這些儀式歌",
)
text = text.replace(
    "儀式用歌〈大禮奉祝唱歌〉",
    f"儀式用歌{link('shokacho/vol_01/p184_tairei_hoshuku_shoka/', '〈大禮奉祝唱歌〉')}",
)

# Upgrade http to https in lines 33-35
text = text.replace(
    "http://tmdlang.github.io/reshoka/", "https://tmdlang.github.io/reshoka/"
)

# Ceremony songs in vol 2/3
text = text.replace(
    "他又把《君が代》、《始政紀念日》抄了一次，夾了大正天皇的《銀婚式奉祝行進歌》、昭和天皇的《皇太子殿下御成婚奉祝提燈行列進行歌》",
    f"他又把{link('shokacho/vol_03/p048a_kimi_ga_yo/', '《君が代》')}、{link('shokacho/vol_03/p047_shisei_kinembi/', '《始政紀念日》')}抄了一次，夾了大正天皇的{link('shokacho/vol_03/p056_ginkonshiki_hoshuku_koshinka/', '《銀婚式奉祝行進歌》')}、昭和天皇的{link('shokacho/vol_03/p061_kotaishi_denka_chochin_gyoretsu_shinkoka/', '《皇太子殿下御成婚奉祝提燈行列進行歌》')}",
)

# Table of 大正幼年唱歌
table_replacements = [
    (
        "| オサル（お猿）     |",
        f"| {link('shokacho/vol_02/p069_osaru/', 'オサル（お猿）')} |",
    ),
    (
        "| トンボ（蜻蛉）     |",
        f"| {link('shokacho/vol_02/p070a_tonbo/', 'トンボ（蜻蛉）')} |",
    ),
    (
        "| ヒヨコ（雛）       |",
        f"| {link('shokacho/vol_02/p070b_hiyoko/', 'ヒヨコ（雛）')} |",
    ),
    ("| 汽車               |", f"| {link('shokacho/vol_02/p071_kisha/', '汽車')} |"),
    (
        "| ピアノ（鋼琴）     |",
        f"| {link('shokacho/vol_02/p072_piano/', 'ピアノ（鋼琴）')} |",
    ),
    (
        "| オ日様（お日様）   |",
        f"| {link('shokacho/vol_02/p073_ohisama/', 'オ日様（お日様）')} |",
    ),
    ("| 軍艦               |", f"| {link('shokacho/vol_02/p074_gunkan/', '軍艦')} |"),
    ("| 大砲               |", f"| {link('shokacho/vol_02/p075_taiho/', '大砲')} |"),
    (
        "| ゴモン（御門）     |",
        f"| {link('shokacho/vol_02/p078_gomon/', 'ゴモン（御門）')} |",
    ),
    (
        "| カタツムリ（蝸牛） |",
        f"| {link('shokacho/vol_02/p079_katatsumuri/', 'カタツムリ（蝸牛）')} |",
    ),
    ("| 太陽               |", f"| {link('shokacho/vol_02/p107_taiyo/', '太陽')} |"),
]
for old, new in table_replacements:
    assert old in text, f"Missing table entry: {old}"
    text = text.replace(old, new)

# 藝旦曲與支那曲
text = text.replace(
    "楊金土也抄錄了藝旦曲〈嘆煙花〉，另外也有一冊叫做《支那曲》的筆記本，抄了〈思春〉、〈小紅桃〉等傳統曲",
    f"楊金土也抄錄了藝旦曲{link('shokacho/vol_02/p081_tan_yenhua/', '〈嘆煙花〉')}，另外也有一冊叫做《支那曲》的筆記本，抄了{link('shokacho/vol_09/0844_p006_sichun/', '〈思春〉')}、{link('shokacho/vol_09/0844_p010_xiaohongtao/', '〈小紅桃〉')}等傳統曲",
)

# 3. 蓬萊唱集
text = text.replace(
    "知名水彩畫家陳英聲創作詞曲的〈牛よ牛よ〉，還有另外一位台籍教師郭水返根據國文課本課文作詞的〈水グルマ〉（水車）。",
    f"知名水彩畫家陳英聲創作詞曲的{link('shokacho/vol_07/p246_ushi_yo_ushi_yo/', '〈牛よ牛よ〉')}，還有另外一位台籍教師郭水返根據國文課本課文作詞的{link('shokacho/vol_07/p231_mizuguruma/', '〈水グルマ〉（水車）')}。",
)
text = text.replace(
    "成了後來寫出〈水牛〉，贏得《臺灣の歌》懸賞",
    f"成了後來寫出{link('taiwan_no_uta/3_suigyu/', '〈水牛〉')}，贏得《臺灣の歌》懸賞",
)
text = text.replace(
    "《蓬萊唱集》第 29 頁，就是野口雨情詞/中山晉平曲的〈シャボン玉〉（肥皂泡，[Wikipedia 連結](<https://ja.wikipedia.org/wiki/%E3%82%B7%E3%83%A3%E3%83%9C%E3%83%B3%E7%8E%89_(%E5%94%B1%E6%AD%8C)>)）",
    f"《蓬萊唱集》第 29 頁，就是野口雨情詞/中山晉平曲的{link('shokacho/vol_07/p233_shabondama/', '〈シャボン玉〉')}（肥皂泡，[Wikipedia 連結](<https://ja.wikipedia.org/wiki/%E3%82%B7%E3%83%A3%E3%83%9C%E3%83%B3%E7%8E%89_(%E5%94%B1%E6%AD%8C)>)）",
)
text = text.replace(
    "第 66 頁有同名的〈しゃぼん玉〉，則是横山静子詩/黒澤隆朝的版本。",
    f"第 66 頁有同名的{link('shokacho/vol_07/p252_shabondama/', '〈しゃぼん玉〉')}，則是横山静子詩/黒澤隆朝的版本。",
)
text = text.replace(
    "第 37 頁，是北原白秋詩/山田耕筰曲的〈兎の電報〉",
    f"第 37 頁，是北原白秋詩/山田耕筰曲的{link('shokacho/vol_07/p237_usagi_no_denpo/', '〈兎の電報〉')}",
)
text = text.replace(
    "40 頁是中山晉平作曲的〈南京玉〉，50 頁是三木露風作詩的〈菜の花〉，三年級用；61 頁是三木露風詩的〈春風のをどり〉，四年級用。",
    f"40 頁是中山晉平作曲的{link('shokacho/vol_07/p238_nankin_dama/', '〈南京玉〉')}，50 頁是三木露風作詩的{link('shokacho/vol_07/p242_nanohana/', '〈菜の花〉')}，三年級用；61 頁是三木露風詩的{link('shokacho/vol_07/p247a_harukaze_no_odori/', '〈春風のをどり〉')}，四年級用。",
)
target_line102 = "然後是葛原しげる、室崎琴月、黑澤隆朝、梁田貞的這批《大正幼年唱歌》作者的童謠。36 頁上是〈夕日〉（葛原しげる詩/室崎琴月曲），76 頁是梁田貞的〈近眼のしくじり〉，楊金土在第一冊已經抄過一次，但可能覺得當時抄的不完整，又抄了一次。31 頁〈螢の學校〉沒寫作者，但是可以從詞曲查到，是室崎琴月的作品。富原義德、真田梅村、西郷景的作品則包括：49 頁富原義德詩的〈初鶯〉、65 頁富原義德詩〈夕立小立〉、69 頁富原義德詩〈ひとりぼっち〉；47 頁真田梅村詩〈ワニの子〉、77 頁真田梅村詩〈銀杏の樹〉、51 頁西郷景詩〈どんぶりこ〉。"
replacement_line102 = f"然後是葛原しげる、室崎琴月、黑澤隆朝、梁田貞的這批《大正幼年唱歌》作者的童謠。36 頁上是{link('shokacho/vol_07/p236_yuhi/', '〈夕日〉')}（葛原しげる詩/室崎琴月曲），76 頁是梁田貞的{link('shokacho/vol_07/p257_chikame_no_shikujiri/', '〈近眼のしくじり〉')}，楊金土在第一冊已經抄過一次，但可能覺得當時抄的不完整，又抄了一次。31 頁{link('shokacho/vol_07/p234_hotaru_no_gakko/', '〈螢の學校〉')}沒寫作者，但是可以從詞曲查到，是室崎琴月的作品。富原義德、真田梅村、西郷景的作品則包括：49 頁富原義德詩的{link('shokacho/vol_07/p241_hatsu_uguisu/', '〈初鶯〉')}、65 頁富原義德詩{link('shokacho/vol_07/p250_yudachi_kodachi/', '〈夕立小立〉')}、69 頁富原義德詩{link('shokacho/vol_07/p254_hitoribocchi/', '〈ひとりぼっち〉')}；47 頁真田梅村詩{link('shokacho/vol_07/p240_wani_no_ko/', '〈ワニの子〉')}、77 頁真田梅村詩{link('shokacho/vol_08/p005_icho_no_ki/', '〈銀杏の樹〉')}、51 頁西郷景詩{link('shokacho/vol_07/p243_donburiko/', '〈どんぶりこ〉')}。"
assert target_line102 in text, "Missing target_line102"
text = text.replace(target_line102, replacement_line102)
text = text.replace(
    "其他還有來自大正幼兒唱歌的〈オ友達〉與〈三羽ノ雀〉，大阪音樂學校校長永井幸次〈雨〉、大阪天王寺師範學校教諭山本壽的〈大日本〉、原田比古士良/彥四郎〈富士の山〉與〈繪本〉、杉江秀〈怒るな働け〉。",
    f"其他還有來自大正幼兒唱歌的{link('shokacho/vol_07/p232_otomodachi/', '〈オ友達〉')}與{link('shokacho/vol_07/p235_sanba_no_suzume/', '〈三羽ノ雀〉')}，大阪音樂學校校長永井幸次{link('shokacho/vol_07/p229a_ame/', '〈雨〉')}、大阪天王寺師範學校教諭山本壽的{link('shokacho/vol_08/p008_dainippon/', '〈大日本〉')}、原田比古士良/彥四郎{link('shokacho/vol_07/p255_fuji_no_yama/', '〈富士の山〉')}與{link('shokacho/vol_08/p006_ehon/', '〈繪本〉')}、杉江秀{link('shokacho/vol_08/p017_ikaruna_hatarake/', '〈怒るな働け〉')}。",
)

# 4. 新定兒童唱歌
text = text.replace(
    "收錄了八冊《新定兒童唱歌》",
    f"收錄了八冊{link('shintei_jido_shoka/', '《新定兒童唱歌》')}",
)

# 新定兒童唱歌 bullets
shintei_bullets = [
    # Grade 1
    (
        "- チヨダノオシロ（千代田城）（野口雨情 詞/藤井清水 曲）",
        f"- {link('shintei_jido_shoka/grade_1_2020.006.0847.0001/4_20_chiyoda_no_oshiro/', 'チヨダノオシロ（千代田城）')}（野口雨情 詞/藤井清水 曲）",
    ),
    (
        "- ユフヤケコヤケ（晚霞）（中村雨紅 詞/草川信 曲）",
        f"- {link('shintei_jido_shoka/grade_1_2020.006.0847.0001/4_16_yuyake_koyake/', 'ユフヤケコヤケ（晚霞）')}（中村雨紅 詞/草川信 曲）",
    ),
    (
        "- モチツキ（搗麻糬）（葛原しげる 詞/小松耕輔 曲）",
        f"- {link('shintei_jido_shoka/grade_1_2020.006.0847.0001/4_18_mochitsuki/', 'モチツキ（搗麻糬）')}（葛原しげる 詞/小松耕輔 曲）",
    ),
    (
        "- デンシヤ（電車）（葛原しげる 詞/小松耕輔 曲）",
        f"- {link('shintei_jido_shoka/grade_1_2020.006.0847.0001/4_11_densha/', 'デンシヤ（電車）')}（葛原しげる 詞/小松耕輔 曲）",
    ),
    (
        "- スズメ（麻雀）（葛原しげる 詞/小松耕輔 曲）",
        f"- {link('shintei_jido_shoka/grade_1_2020.006.0847.0001/4_22_suzume/', 'スズメ（麻雀）')}（葛原しげる 詞/小松耕輔 曲）",
    ),
    (
        "- アリ（螞蟻）（葛原しげる 詞/梁田貞 曲）",
        f"- {link('shintei_jido_shoka/grade_1_2020.006.0847.0001/4_09_ari/', 'アリ（螞蟻）')}（葛原しげる 詞/梁田貞 曲）",
    ),
    (
        "- ムシノコヱ（蟲的聲音）（小松耕輔 曲）",
        f"- {link('shintei_jido_shoka/grade_1_2020.006.0847.0001/4_13_mushi_no_koe/', 'ムシノコヱ（蟲的聲音）')}（小松耕輔 曲）",
    ),
    (
        "- オサル（猴子）（葛原しげる 詞/梁田貞 曲）",
        f"- {link('shintei_jido_shoka/grade_1_2020.006.0847.0001/4_21_osaru/', 'オサル（猴子）')}（葛原しげる 詞/梁田貞 曲）",
    ),
    (
        "- フンスヰ（噴泉）（葛原しげる 詞/梁田貞 曲）",
        f"- {link('shintei_jido_shoka/grade_1_2020.006.0847.0001/2_02_funsui/', 'フンスヰ（噴泉）')}（葛原しげる 詞/梁田貞 曲）",
    ),
    (
        "- オヤウシコウシ（母牛與小牛）（三木露風 詞）",
        f"- {link('shintei_jido_shoka/grade_1_2020.006.0847.0001/2_06_oyaushi_koushi/', 'オヤウシコウシ（母牛與小牛）')}（三木露風 詞）",
    ),
    (
        "- チンコロヘイタイ（小小兵）（草川信 曲）",
        f"- {link('shintei_jido_shoka/grade_1_2020.006.0847.0001/4_17_chinkoro_heitai/', 'チンコロヘイタイ（小小兵）')}（草川信 曲）",
    ),
    (
        "- アメ（雨）（北原白秋 詞/成田為三 曲）",
        f"- {link('shintei_jido_shoka/grade_1_2020.006.0847.0001/4_05_ame/', 'アメ（雨）')}（北原白秋 詞/成田為三 曲）",
    ),
    (
        "- イヌノシバヰ（狗的戲劇）（北原白秋 詞/成田為三 曲）",
        f"- {link('shintei_jido_shoka/grade_1_2020.006.0847.0001/4_12_inu_no_shibai/', 'イヌノシバヰ（狗的戲劇）')}（北原白秋 詞/成田為三 曲）",
    ),
    (
        "- フタリノヘイタイサン（兩個小兵）（北原白秋 詞/成田為三 曲）",
        f"- {link('shintei_jido_shoka/grade_1_2020.006.0847.0001/4_10_futari_no_heitaisan/', 'フタリノヘイタイサン（兩個小兵）')}（北原白秋 詞/成田為三 曲）",
    ),
    # Grade 2
    (
        "- だるま（達摩）（葛原しげる 詞/小松耕輔 曲）",
        f"- {link('shintei_jido_shoka/grade_2_2020.006.0847.0002/3_01_daruma/', 'だるま（達摩）')}（葛原しげる 詞/小松耕輔 曲）",
    ),
    (
        "- 七面鳥（葛原しげる 詞/梁田貞 曲）",
        f"- {link('shintei_jido_shoka/grade_2_2020.006.0847.0002/3_06_shichimencho/', '七面鳥')}（葛原しげる 詞/梁田貞 曲）",
    ),
    (
        "- ユフヒ（夕陽）（葛原しげる 詞/室崎琴月 曲）",
        f"- {link('shintei_jido_shoka/grade_2_2020.006.0847.0002/4_10_yuhi/', 'ユフヒ（夕陽）')}（葛原しげる 詞/室崎琴月 曲）",
    ),
    (
        "- キンギヨ（金魚）（葛原𦱳 詞/梁田貞 曲）",
        f"- {link('shintei_jido_shoka/grade_2_2020.006.0847.0002/1_09_kingyo/', 'キンギヨ（金魚）')}（葛原𦱳 詞/梁田貞 曲）",
    ),
    (
        "- 一ツボシ（一顆星）（室崎琴月 曲）",
        f"- {link('shintei_jido_shoka/grade_2_2020.006.0847.0002/4_11_hitotsuboshi/', '一ツボシ（一顆星）')}（室崎琴月 曲）",
    ),
    (
        "- テフトハルカゼ（蝴蝶與春風）（葛原しげる 詞/梁田貞 曲）",
        f"- {link('shintei_jido_shoka/grade_2_2020.006.0847.0002/4_02_cho_to_harukaze/', 'テフトハルカゼ（蝴蝶與春風）')}（葛原しげる 詞/梁田貞 曲）",
    ),
    (
        "- アワテトコヤ（匆忙理髮店）（北原白秋 詞/成田為三 曲）",
        f"- {link('shintei_jido_shoka/grade_2_2020.006.0847.0002/4_04_awate_tokoya/', 'アワテトコヤ（匆忙理髮店）')}（北原白秋 詞/成田為三 曲）",
    ),
    (
        "- 十五ヤ（十五夜）（三木露風 詞/山田耕筰 曲）",
        f"- {link('shintei_jido_shoka/grade_2_2020.006.0847.0002/2_02_jugoya/', '十五ヤ（十五夜）')}（三木露風 詞/山田耕筰 曲）",
    ),
    (
        "- おきやくさま（客人）（葛原しげる 詞/梁田貞 曲）",
        f"- {link('shintei_jido_shoka/grade_2_2020.006.0847.0002/4_16_okyaku_sama/', 'おきやくさま（客人）')}（葛原しげる 詞/梁田貞 曲）",
    ),
    (
        "- 半カケオ月サン（西條八十 詞/草川信 曲）",
        f"- {link('shintei_jido_shoka/grade_2_2020.006.0847.0002/4_12_hankake_otsukisan/', '半カケオ月サン')}（西條八十 詞/草川信 曲）",
    ),
    (
        "- ハコニハ（箱庭）（小松耕輔 曲）",
        f"- {link('shintei_jido_shoka/grade_2_2020.006.0847.0002/4_05_hakoniwa/', 'ハコニハ（箱庭）')}（小松耕輔 曲）",
    ),
    (
        "- ヒバリ（雲雀）（三木露風 詞/山田耕筰 曲）",
        f"- {link('shintei_jido_shoka/grade_2_2020.006.0847.0002/4_01_hibari/', 'ヒバリ（雲雀）')}（三木露風 詞/山田耕筰 曲）",
    ),
    (
        "- カヘル（青蛙）（葛原しげる 詞/小松耕輔 曲）",
        f"- {link('shintei_jido_shoka/grade_2_2020.006.0847.0002/4_07_kaeru/', 'カヘル（青蛙）')}（葛原しげる 詞/小松耕輔 曲）",
    ),
    (
        "- デンシンバシラ（電線桿）（河井醉茗 詞/草川信 曲）",
        f"- {link('shintei_jido_shoka/grade_2_2020.006.0847.0002/4_09_denshin_bashira/', 'デンシンバシラ（電線桿）')}（河井醉茗 詞/草川信 曲）",
    ),
    (
        "- フウリン（風鈴）（川路柳虹 詞/草川信 曲）",
        f"- {link('shintei_jido_shoka/grade_2_2020.006.0847.0002/4_08_furin/', 'フウリン（風鈴）')}（川路柳虹 詞/草川信 曲）",
    ),
    # Grade 3
    (
        "- 鯉のぼり（葛原しげる 詞/小松耕輔 曲）",
        f"- {link('shintei_jido_shoka/grade_3_2020.006.0847.0003/1_06_koinobori/', '鯉のぼり')}（葛原しげる 詞/小松耕輔 曲）",
    ),
    (
        "- 猿の猿眞似（野口雨情 詞/室崎琴月 曲）",
        f"- {link('shintei_jido_shoka/grade_3_2020.006.0847.0003/4_15_saru_no_sarumane/', '猿の猿眞似')}（野口雨情 詞/室崎琴月 曲）",
    ),
    (
        "- 蓮の葉の露（葛原しげる 詞/梁田貞 曲）",
        f"- {link('shintei_jido_shoka/grade_3_2020.006.0847.0003/4_09_hasu_no_ha_no_tsuyu/', '蓮の葉の露')}（葛原しげる 詞/梁田貞 曲）",
    ),
    (
        "- 遠足の歌（葛原しげる 詞/小松耕輔 曲）",
        f"- {link('shintei_jido_shoka/grade_3_2020.006.0847.0003/4_10_ensoku_no_uta/', '遠足の歌')}（葛原しげる 詞/小松耕輔 曲）",
    ),
    (
        "- けむり（三木露風 詞/山田耕筰 曲）",
        f"- {link('shintei_jido_shoka/grade_3_2020.006.0847.0003/4_05_kemuri/', 'けむり')}（三木露風 詞/山田耕筰 曲）",
    ),
    (
        "- 冬の朝（三木露風 詞/山田耕筰 曲）",
        f"- {link('shintei_jido_shoka/grade_3_2020.006.0847.0003/4_20_fuyu_no_asa/', '冬の朝')}（三木露風 詞/山田耕筰 曲）",
    ),
    (
        "- 進軍（葛原しげる 詞/梁田貞 曲）",
        f"- {link('shintei_jido_shoka/grade_3_2020.006.0847.0003/4_17_shingun/', '進軍')}（葛原しげる 詞/梁田貞 曲）",
    ),
    (
        "- 花瓶の花（葛原しげる 詞）",
        f"- {link('shintei_jido_shoka/grade_3_2020.006.0847.0003/4_02_kabin_no_hana/', '花瓶の花')}（葛原しげる 詞）",
    ),
    (
        "- 天の岩屋（葛原しげる 詞/小松耕輔 曲）",
        f"- {link('shintei_jido_shoka/grade_3_2020.006.0847.0003/1_02_ama_no_iwaya/', '天の岩屋')}（葛原しげる 詞/小松耕輔 曲）",
    ),
    (
        "- 波がざんぶりこ（野口雨情 詞/佐々木のぼる 曲）",
        f"- {link('shintei_jido_shoka/grade_3_2020.006.0847.0003/4_11_nami_ga_zanburiko/', '波がざんぶりこ')}（野口雨情 詞/佐々木のぼる 曲）",
    ),
    (
        "- 梅に鶯（葛原しげる 詞/小松耕輔 曲）",
        f"- {link('shintei_jido_shoka/grade_3_2020.006.0847.0003/4_16_ume_ni_uguisu/', '梅に鶯')}（葛原しげる 詞/小松耕輔 曲）",
    ),
    (
        "- ねむり人形（葛原しげる 詞/本居長世 曲）",
        f"- {link('shintei_jido_shoka/grade_3_2020.006.0847.0003/4_04_nemuri_ningyo/', 'ねむり人形')}（葛原しげる 詞/本居長世 曲）",
    ),
    (
        "- お庭のラヂオ（清水かつら 詞/草川信 曲）",
        f"- {link('shintei_jido_shoka/grade_3_2020.006.0847.0003/4_07_oniwa_no_rajio/', 'お庭のラヂオ')}（清水かつら 詞/草川信 曲）",
    ),
    (
        "- 活動寫眞（葛原しげる 詞/小松耕輔 曲）",
        f"- {link('shintei_jido_shoka/grade_3_2020.006.0847.0003/4_14_katsudo_shashin/', '活動寫眞')}（葛原しげる 詞/小松耕輔 曲）",
    ),
    # Grade 4
    (
        "- 黃金虫（西條八十 詞/室崎琴月 曲）",
        f"- {link('shintei_jido_shoka/grade_4_2020.006.0847.0004/4_08_kogane_mushi/', '黃金虫')}（西條八十 詞/室崎琴月 曲）",
    ),
    (
        "- かなりや（西條八十 詞/成田為三 曲）",
        f"- {link('shintei_jido_shoka/grade_4_2020.006.0847.0004/4_19_kanariya/', 'かなりや')}（西條八十 詞/成田為三 曲）",
    ),
    (
        "- 春の丘（川路柳虹 詞/草川信 曲）",
        f"- {link('shintei_jido_shoka/grade_4_2020.006.0847.0004/4_02_haru_no_oka/', '春の丘')}（川路柳虹 詞/草川信 曲）",
    ),
    (
        "- 花ざかり（葛原しげる 詞/梁田貞 曲）",
        f"- {link('shintei_jido_shoka/grade_4_2020.006.0847.0004/4_01_hanazakari/', '花ざかり')}（葛原しげる 詞/梁田貞 曲）",
    ),
    (
        "- さみだれ（葛原しげる 詞/小松耕輔 曲）",
        f"- {link('shintei_jido_shoka/grade_4_2020.006.0847.0004/4_07_samidare/', 'さみだれ')}（葛原しげる 詞/小松耕輔 曲）",
    ),
    (
        "- 百舌鳥（葛原しげる 詞/小松耕輔 曲）",
        f"- {link('shintei_jido_shoka/grade_4_2020.006.0847.0004/4_17_mozu/', '百舌鳥')}（葛原しげる 詞/小松耕輔 曲）",
    ),
    (
        "- 二つの蝶（室崎琴月 曲）",
        f"- {link('shintei_jido_shoka/grade_4_2020.006.0847.0004/4_03_futatsu_no_cho/', '二つの蝶')}（室崎琴月 曲）",
    ),
    (
        "- 航海（山田耕筰 曲）",
        f"- {link('shintei_jido_shoka/grade_4_2020.006.0847.0004/4_10_kokai/', '航海')}（山田耕筰 曲）",
    ),
    (
        "- 競馬（葛原しげる 詞/小松耕輔 曲）",
        f"- {link('shintei_jido_shoka/grade_4_2020.006.0847.0004/3_06_keiba/', '競馬')}（葛原しげる 詞/小松耕輔 曲）",
    ),
    (
        "- 鷲（葛原しげる 詞/小松耕輔 曲）",
        f"- {link('shintei_jido_shoka/grade_4_2020.006.0847.0004/2_01_washi/', '鷲')}（葛原しげる 詞/小松耕輔 曲）",
    ),
    (
        "- 流れ星（本居長世 曲）",
        f"- {link('shintei_jido_shoka/grade_4_2020.006.0847.0004/4_11_nagareboshi/', '流れ星')}（本居長世 曲）",
    ),
    (
        "- とんび（葛原しげる 詞/梁田貞 曲）",
        f"- {link('shintei_jido_shoka/grade_4_2020.006.0847.0004/4_15_tonbi/', 'とんび')}（葛原しげる 詞/梁田貞 曲）",
    ),
    (
        "- 羽衣（葛原しげる 詞/梁田貞 曲）",
        f"- {link('shintei_jido_shoka/grade_4_2020.006.0847.0004/4_04_hagoromo/', '羽衣')}（葛原しげる 詞/梁田貞 曲）",
    ),
    (
        "- お月さん（西川勉 詞/本居長世 曲）",
        f"- {link('shintei_jido_shoka/grade_4_2020.006.0847.0004/4_13_otsukisan/', 'お月さん')}（西川勉 詞/本居長世 曲）",
    ),
    # Grade 5
    (
        "- 航海（葛原しげる 詞/小松耕輔 曲）",
        f"- {link('shintei_jido_shoka/grade_5_2020.006.0847.0005/2_05_kokai/', '航海')}（葛原しげる 詞/小松耕輔 曲）",
    ),
    (
        "- もみぢ（平尾白暮 詞/室崎琴月 曲）",
        f"- {link('shintei_jido_shoka/grade_5_2020.006.0847.0005/2_08_momiji/', 'もみぢ')}（平尾白暮 詞/室崎琴月 曲）",
    ),
    (
        "- 平和なる村（三木露風 詞/山田耕筰 曲）",
        f"- {link('shintei_jido_shoka/grade_5_2020.006.0847.0005/3_06_heiwa_naru_mura/', '平和なる村')}（三木露風 詞/山田耕筰 曲）",
    ),
    # Grade 6
    (
        "- 乃木大將の歌（小松耕輔 曲）",
        f"- {link('shintei_jido_shoka/grade_6_2020.006.0847.0006/2_04_nogi_taisho_no_uta/', '乃木大將の歌')}（小松耕輔 曲）",
    ),
    # Koto Boys
    (
        "- 青年の歌（山田耕筰 曲）",
        f"- {link('shintei_jido_shoka/koto_boys_2020.006.0848/2_3_06_seinen_no_uta/', '青年の歌')}（山田耕筰 曲）",
    ),
    # Koto Girls
    (
        "- 野川のしらべ（成田為三 曲）",
        f"- {link('shintei_jido_shoka/koto_girls_2020.006.0849/2_1_02_nogawa_no_shirabe/', '野川のしらべ')}（成田為三 曲）",
    ),
    (
        "- 世界の平和（成田為三 曲）",
        f"- {link('shintei_jido_shoka/koto_girls_2020.006.0849/2_3_06_sekai_no_heiwa/', '世界の平和')}（成田為三 曲）",
    ),
]

for old, new in shintei_bullets:
    assert old in text, f"Missing shintei bullet: {old}"
    text = text.replace(old, new, 1)

# 5. 蕃童教育所
text = text.replace(
    "1935 年台灣總督府警務局編輯的《教育所用唱歌教材集》的時候",
    f"1935 年台灣總督府警務局編輯的{link('kyoyusho_shoka_1935/', '《教育所用唱歌教材集》')}的時候",
)
text = text.replace(
    "在教育所用教材中收入了〈水牛〉、〈これぞ臺灣〉、〈常夏の島〉",
    f"在教育所用教材中收入了{link('kyoyusho_shoka_1935/2_11_suigyu/', '〈水牛〉')}、{link('kyoyusho_shoka_1935/5_15_korezo_taiwan/', '〈これぞ臺灣〉')}、{link('kyoyusho_shoka_1935/6_12_tokonatsu_no_shima/', '〈常夏の島〉')}",
)
text = text.replace(
    "特別引人注意的包括〈日の丸音頭〉、〈豐年踊〉、〈林投節〉、〈蕃山踊の歌〉這些嘗試將日本的盆踊代替原本原住民歌舞的祭典歌曲，許多出自赤尾寅吉之手。",
    f"特別引人注意的包括{link('kyoyusho_shoka_1935/5_19_hinomaru_ondo/', '〈日の丸音頭〉')}、{link('kyoyusho_shoka_1935/5_18_honen_odori/', '〈豐年踊〉')}、{link('kyoyusho_shoka_1935/5_20_rinto_bushi/', '〈林投節〉')}、{link('kyoyusho_shoka_1935/7_21_banzan_odori_no_uta/', '〈蕃山踊の歌〉')}這些嘗試將日本的盆踊代替原本原住民歌舞的祭典歌曲，許多出自赤尾寅吉之手。",
)
text = text.replace(
    "御船武作詞、郭明峰作曲的〈水牛〉，講一頭水牛喜歡在池塘洗澡",
    f"御船武作詞、郭明峰作曲的{link('taiwan_no_uta/3_suigyu/', '〈水牛〉')}，講一頭水牛喜歡在池塘洗澡",
)

# 蕃童教育所 大正童謠清單
kyoyusho_taisho_bullets = [
    (
        "- 一年 (9) **〈ほたる〉**",
        f"- 一年 (9) **{link('kyoyusho_shoka_1935/1_09_hotaru/', '〈ほたる〉')}**",
    ),
    (
        "- 二年 (8) **〈しやぼん玉〉**",
        f"- 二年 (8) **{link('kyoyusho_shoka_1935/2_08_shabondama/', '〈しやぼん玉〉')}**",
    ),
    (
        "- 二年 (5) **〈さよなら さよなら〉**",
        f"- 二年 (5) **{link('kyoyusho_shoka_1935/2_05_sayonara_sayonara/', '〈さよなら さよなら〉')}**",
    ),
    (
        "- 二年 (20) **〈雀をどり〉**",
        f"- 二年 (20) **{link('kyoyusho_shoka_1935/2_20_suzume_odori/', '〈雀をどり〉')}**",
    ),
    (
        "- 四年 (2) **〈櫻と小鳥〉**",
        f"- 四年 (2) **{link('kyoyusho_shoka_1935/4_02_sakura_to_kotori/', '〈櫻と小鳥〉')}**",
    ),
    (
        "- 四年 (12) **〈猿の猿眞似〉**",
        f"- 四年 (12) **{link('kyoyusho_shoka_1935/4_12_saru_no_sarumane/', '〈猿の猿眞似〉')}**",
    ),
    (
        "- 四年 (14) **〈あの町この町〉**",
        f"- 四年 (14) **{link('kyoyusho_shoka_1935/4_14_ano_machi_kono_machi/', '〈あの町この町〉')}**",
    ),
    (
        "- 一年 (21) **〈靴が鳴る〉**",
        f"- 一年 (21) **{link('kyoyusho_shoka_1935/1_21_kutsu_ga_naru/', '〈靴が鳴る〉')}**",
    ),
    (
        "- 一年 (26) **〈雀の學校〉**",
        f"- 一年 (26) **{link('kyoyusho_shoka_1935/1_26_suzume_no_gakko/', '〈雀の學校〉')}**",
    ),
    (
        "- 二年 (18) **〈夕燒小燒〉**",
        f"- 二年 (18) **{link('kyoyusho_shoka_1935/2_18_yuyake_koyake/', '〈夕燒小燒〉')}**",
    ),
    (
        "- 三年 (27) **〈電信柱〉**",
        f"- 三年 (27) **{link('kyoyusho_shoka_1935/3_27_denshin_bashira/', '〈電信柱〉')}**",
    ),
    (
        "- 三年 (15) **〈親牛子牛〉**",
        f"- 三年 (15) **{link('kyoyusho_shoka_1935/3_15_oyaushi_koushi/', '〈親牛子牛〉')}**",
    ),
    (
        "- 三年 (19) **〈十五夜〉**",
        f"- 三年 (19) **{link('kyoyusho_shoka_1935/3_19_jugoya/', '〈十五夜〉')}**",
    ),
    (
        "- 四年 (10) **〈兎の電報〉**",
        f"- 四年 (10) **{link('kyoyusho_shoka_1935/4_10_usagi_no_denpo/', '〈兎の電報〉')}**",
    ),
    (
        "- 女子青年部 (9) **〈里心〉**",
        f"- 女子青年部 (9) **{link('kyoyusho_shoka_1935/7_09_satogokoro/', '〈里心〉')}**",
    ),
    (
        "- 一年 (19) **〈夕やけ〉**",
        f"- 一年 (19) **{link('kyoyusho_shoka_1935/1_19_yuyake/', '〈夕やけ〉')}**",
    ),
    (
        "- 二年 (1) **〈お早う〉**",
        f"- 二年 (1) **{link('kyoyusho_shoka_1935/2_01_ohayo/', '〈お早う〉')}**",
    ),
    (
        "- 二年 (6) **〈ちくおんき〉**",
        f"- 二年 (6) **{link('kyoyusho_shoka_1935/2_06_chikuonki/', '〈ちくおんき〉')}**",
    ),
    (
        "- 二年 (19) **〈私の妹〉**",
        f"- 二年 (19) **{link('kyoyusho_shoka_1935/2_19_watashi_no_imoto/', '〈私の妹〉')}**",
    ),
    (
        "- 二年 (28) **〈すゞめ〉**",
        f"- 二年 (28) **{link('kyoyusho_shoka_1935/2_28_suzume/', '〈すゞめ〉')}**",
    ),
    (
        "- 三年 (3) **〈花瓶の花〉**",
        f"- 三年 (3) **{link('kyoyusho_shoka_1935/3_03_kabin_no_hana/', '〈花瓶の花〉')}**",
    ),
    (
        "- 三年 (7) **〈夕日〉**",
        f"- 三年 (7) **{link('kyoyusho_shoka_1935/3_07_yuhi/', '〈夕日〉')}**",
    ),
    (
        "- 四年 (5) **〈お庭の草花〉**",
        f"- 四年 (5) **{link('kyoyusho_shoka_1935/4_05_oniwa_no_kusabana/', '〈お庭の草花〉')}**",
    ),
    (
        "- 四年 (6) **〈夏の朝〉**",
        f"- 四年 (6) **{link('kyoyusho_shoka_1935/4_06_natsu_no_asa/', '〈夏の朝〉')}**",
    ),
    (
        "- 四年 (25) **〈とんび〉**",
        f"- 四年 (25) **{link('kyoyusho_shoka_1935/4_25_tonbi/', '〈とんび〉')}**",
    ),
    (
        "- 七年 (13) **〈野の幸〉**",
        f"- 七年 (13) **{link('kyoyusho_shoka_1935/7_13_no_no_sachi/', '〈野の幸〉')}**",
    ),
    (
        "- 一年 (11) **〈とんぼ〉**",
        f"- 一年 (11) **{link('kyoyusho_shoka_1935/1_11_tonbo/', '〈とんぼ〉')}**",
    ),
    (
        "- 三年 (6) **〈夕立〉**",
        f"- 三年 (6) **{link('kyoyusho_shoka_1935/3_06_yudachi/', '〈夕立〉')}**",
    ),
    (
        "- 三年 (13) **〈ささの舟〉**",
        f"- 三年 (13) **{link('kyoyusho_shoka_1935/3_13_sasa_no_fune/', '〈ささの舟〉')}**",
    ),
    (
        "- 三年 (23) **〈月夜の兎〉**",
        f"- 三年 (23) **{link('kyoyusho_shoka_1935/3_23_tsukiyo_no_usagi/', '〈月夜の兎〉')}**",
    ),
    (
        "- 四年 (32) **〈二つの蝶〉**",
        f"- 四年 (32) **{link('kyoyusho_shoka_1935/4_32_futatsu_no_cho/', '〈二つの蝶〉')}**",
    ),
    (
        "- 四年 (37) **〈ほたる〉**",
        f"- 四年 (37) **{link('kyoyusho_shoka_1935/4_37_hotaru/', '〈ほたる〉')}**",
    ),
]

for old, new in kyoyusho_taisho_bullets:
    assert old in text, f"Missing kyoyusho bullet: {old}"
    text = text.replace(old, new, 1)

# 軍事主題歌清單
military_bullets = [
    (
        "- **6_09 守れ臺灣**",
        f"- **{link('kyoyusho_shoka_1935/6_09_mamore_taiwan/', '6_09 守れ臺灣')}**",
    ),
    (
        "- **6_10 銀翼光る**",
        f"- **{link('kyoyusho_shoka_1935/6_10_ginyoku_hikaru/', '6_10 銀翼光る')}**",
    ),
    (
        "- **6_11 臺灣軍の歌**",
        f"- **{link('kyoyusho_shoka_1935/6_11_taiwangun_no_uta/', '6_11 臺灣軍の歌')}**",
    ),
    (
        "- **6_15 大日本行進曲**",
        f"- **{link('kyoyusho_shoka_1935/6_15_dainippon_koshinkyoku/', '6_15 大日本行進曲')}**",
    ),
    (
        "- **6_16 帝國青年の歌**",
        f"- **{link('kyoyusho_shoka_1935/6_16_teikoku_seinen_no_uta/', '6_16 帝國青年の歌')}**",
    ),
    (
        "- **6_05 青年團行進歌**",
        f"- **{link('kyoyusho_shoka_1935/6_05_seinendan_koshinka/', '6_05 青年團行進歌')}**",
    ),
    (
        "- **6_06 進め健兒**",
        f"- **{link('kyoyusho_shoka_1935/6_06_susume_kenji/', '6_06 進め健兒')}**",
    ),
    (
        "- **6_01 青年の歌**",
        f"- **{link('kyoyusho_shoka_1935/6_01_seinen_no_uta/', '6_01 青年の歌')}**",
    ),
    (
        "- **6_02 日本青年の歌**",
        f"- **{link('kyoyusho_shoka_1935/6_02_nihon_seinen_no_uta/', '6_02 日本青年の歌')}**",
    ),
    (
        "- **5_11 日本國民歌**",
        f"- **{link('kyoyusho_shoka_1935/5_11_nihon_kokuminka/', '5_11 日本國民歌')}**",
    ),
    (
        "- **5_13 躍進日本**",
        f"- **{link('kyoyusho_shoka_1935/5_13_yakushin_nihon/', '5_13 躍進日本')}**",
    ),
    (
        "- **5_14 日の丸の歌**",
        f"- **{link('kyoyusho_shoka_1935/5_14_hinomaru_no_uta/', '5_14 日の丸の歌')}**",
    ),
    (
        "- **5_19 日の丸音頭**",
        f"- **{link('kyoyusho_shoka_1935/5_19_hinomaru_ondo/', '5_19 日の丸音頭')}**",
    ),
    (
        "- **7_03 女子青年團歌** / **7_04 臺灣女子青年團歌**",
        f"- **{link('kyoyusho_shoka_1935/7_03_joshi_seinendanka/', '7_03 女子青年團歌')}** / **{link('kyoyusho_shoka_1935/7_04_taiwan_joshi_seinendanka/', '7_04 臺灣女子青年團歌')}**",
    ),
    (
        "- **6_03 臺灣青年歌**",
        f"- **{link('kyoyusho_shoka_1935/6_03_taiwan_seinen_ka/', '6_03 臺灣青年歌')}**",
    ),
    (
        "- **4_04 皇太子さま**",
        f"- **{link('kyoyusho_shoka_1935/4_04_kotaishisama/', '4_04 皇太子さま')}**",
    ),
    (
        "- **4_30 昭和の御代**",
        f"- **{link('kyoyusho_shoka_1935/4_30_showa_no_miyo/', '4_30 昭和の御代')}**",
    ),
    (
        "- **4_13 臺灣少年行進曲**",
        f"- **{link('kyoyusho_shoka_1935/4_13_taiwan_shonen_koshinkyoku/', '4_13 臺灣少年行進曲')}**",
    ),
]

for old, new in military_bullets:
    assert old in text, f"Missing military bullet: {old}"
    text = text.replace(old, new, 1)

# 後續文字提及
text = text.replace(
    "北原白秋還直接為台灣的少年們做歌，創作〈臺灣少年行進曲〉。",
    f"北原白秋還直接為台灣的少年們做歌，創作{link('kyoyusho_shoka_1935/4_13_taiwan_shonen_koshinkyoku/', '〈臺灣少年行進曲〉')}。",
)
text = text.replace(
    "〈臺灣少年行進曲〉還有姊妹作〈臺灣青年歌〉：",
    f"{link('kyoyusho_shoka_1935/4_13_taiwan_shonen_koshinkyoku/', '〈臺灣少年行進曲〉')}還有姊妹作{link('kyoyusho_shoka_1935/6_03_taiwan_seinen_ka/', '〈臺灣青年歌〉')}：",
)

# Additional song mentions
text = text.replace(
    "陳英聲在 1922 年將〈牛よ牛よ〉投稿台灣教育會",
    f"陳英聲在 1922 年將{link('shokacho/vol_07/p246_ushi_yo_ushi_yo/', '〈牛よ牛よ〉')}投稿台灣教育會",
)
text = text.replace(
    "寫〈水車〉的郭水返的則似乎找不到多少相關資料",
    f"寫{link('shokacho/vol_07/p231_mizuguruma/', '〈水車〉')}的郭水返的則似乎找不到多少相關資料",
)
text = text.replace(
    "也就是，寫出〈水車〉的郭水返，在 1925 年改了名字",
    f"也就是，寫出{link('shokacho/vol_07/p231_mizuguruma/', '〈水車〉')}的郭水返，在 1925 年改了名字",
)
text = text.replace(
    "蓬萊公學校將北原白秋的〈兎の電報〉編入教材，楊金土還在筆記本上手抄，1935 年時，〈兎の電報〉不但直接編入台灣總督府官方教材",
    f"蓬萊公學校將北原白秋的{link('shokacho/vol_07/p237_usagi_no_denpo/', '〈兎の電報〉')}編入教材，楊金土還在筆記本上手抄，1935 年時，{link('kyoyusho_shoka_1935/4_10_usagi_no_denpo/', '〈兎の電報〉')}不但直接編入台灣總督府官方教材",
)
text = text.replace(
    "這次收入了〈台車〉。",
    f"這次收入了{link('kyoyusho_shoka_1935/4_03_daisha/', '〈台車〉')}。",
)
text = text.replace(
    "例如〈青葉〉、〈村のかぢや〉、〈春が來た〉、〈春の小川〉等。",
    f"例如{link('kyoyusho_shoka_1935/3_01_haru_ga_kita/', '〈春が來た〉')}、{link('kyoyusho_shoka_1935/4_01_haru_no_ogawa/', '〈春の小川〉')}等。",
)

print("Broken links count:", len(broken_links))
if broken_links:
    for b in broken_links:
        print("BROKEN:", b)
else:
    print("All links verified successfully!")

with open("scratch/sing_with_links.md", "w", encoding="utf-8") as f:
    f.write(text)
print("Saved scratch/sing_with_links.md, size:", len(text))
