#!/usr/bin/env python3
"""Classify and tag song origins (`tag: origin:<category>`) and missing base tags across all TMD files."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
DUP_JSON = DOCS / "duplicate_songs.json"

ORIGIN_ORDER = [
    "monbusho",
    "meiji_textbook",
    "western_melody",
    "taisho_showa_mainland",
    "taiwan_official",
    "taiwan_teacher",
    "taiwan_contest_1933",
    "traditional_east_asian",
    "unidentified",
]

WESTERN_PAT = re.compile(
    r"西洋曲|歐洲曲|歐州曲|獨國風|英國風|佛國風|國風歌（獨）|獨國民謠|獨逸民歌|民歌（獨）|民歌（瑞典）|"
    r"露國國歌|露國民歌|佛國民歌|佛國國歌|英國國歌|蘇格蘭民謠|スコットランド民謠|"
    r"歐米小學唱歌|歐洲傳統民謠|Home!?\s*Sweet\s*Home|Auld\s*Lang\s*Syne|Comin.\s*Thro|"
    r"Bishop|Silcher|シルヘル|Groos|グロース|Haydn|ハイドン|Schubert|シユーベルト|"
    r"Schumann|シューマン|Wagner|ワグナー|Mendelssohn|Mozart|モツアルト|Weber|ウエーベル|"
    r"Bellini|ベリニー|Donizetti|ドニツェッチイ|Mazzinghi|モッツインギ|Arne|アーン|"
    r"Lisle|リール|Lwoff|ルボツフ|Wilhelm|ウイルヘルム|Mason|メーソン|Work|ウオーク|"
    r"Root|ルート|Tomer|Schulz|Nägeli|ネーゲリ|Neithardt|ナイハルト|Hanitsch|ハニツチユ|"
    r"Stuntz|シユトウンツ|W\.\s*Scott|スコツト|Lewis|リユーイス|Düringer|Berg（德國曲）|"
    r"Wrighton|Campbell|ゲルスバハ|Webster"
)

EXPLICIT_WESTERN_RELS = {
    "kyoeki_shoka/kan_2_854863/1_kitare_asobe",
    "kyoeki_shoka/kan_3_854864/11_koronbusu",
    "shokacho/vol_10/p203_koronbusu",
    "shoka_kyozai_shu_1923/koto_1_2/06_kocho",
    "shoka_kyozai_shu_1923/koto_1_2/08_sobetsu_no_uta",
    "shokacho/vol_10/p197_sobetsu_no_uta",
    "shoka_kyozai_shu_1923/koto_1_2/20_dosokai",
    "shoka_kyozai_shu_1923/koto_1_2/37_gunkan",
    "shintei_jido_shoka/grade_5_2020.006.0847.0005/3_04_gunkan",
    "shokacho/vol_08/p012_gunkan",
    "kogakko_shokashu_1915/6_09_sotsugyo_no_uta",
    "shintei_jido_shoka/grade_6_2020.006.0847.0006/3_06_aogeba_totoshi",
    "shintei_jido_shoka/grade_6_2020.006.0847.0006/2_01_kokyo_no_sora",
    "shoka_kyozai_shu_1923/grade_5_6/35_tasukebune",
    "kogakko_shoka/grade_5/15_tasukebune",
}

EXPLICIT_CONTEST_1933_RELS = {
    "kogakko_shoka/grade_1/3_mejiro_no_ko",
    "kogakko_shoka/grade_1/4_yudachi_yanda",
    "kogakko_shoka/grade_1/9_janken",
    "kogakko_shoka/grade_1/11_karen",
    "kogakko_shoka/grade_1/13_kosuzume",
    "kogakko_shoka/grade_2/4_takenoko",
    "kogakko_shoka/grade_2/5_petako",
    "kogakko_shoka/grade_3/2_daisha",
    "kogakko_shoka/grade_3/4_gyusha",
    "kogakko_shoka/grade_3/7_suiren",
    "kogakko_shoka/grade_3/13_ojiisan",
    "kogakko_shoka/grade_3/15_shirasagi",
    "kogakko_shoka/grade_4/6_kagerou",
    "kogakko_shoka/grade_5/12_sekikanjo",
    "kogakko_shoka/grade_6/3_kochoran",
    "kogakko_shoka/grade_6/18_sendan_namiki",
    "utanohon/ge_2006.006.0878/9_kaaren",
    "utanohon/ge_2006.006.0878/13_petako",
}

VERIFIED_MONBUSHO_RELS = {
    "shoka_kyozai_shu_1923/grade_1_2/17_hiraita_hiraita",
    "shoka_kyozai_shu_1923/grade_1_2/29_hotaru",
    "shoka_kyozai_shu_1923/grade_1_2/32_hibari",
    "shoka_kyozai_shu_1923/grade_1_2/38_hanabi",
    "shoka_kyozai_shu_1923/grade_3_4/36_hibari",
    "shoka_kyozai_shu_1923/grade_5_6/19_gyosen",
    "shoka_kyozai_shu_1923/grade_5_6/28_migakazuba",
    "shoka_kyozai_shu_1923/grade_5_6/48_hasuike",
    "shoka_kyozai_shu_1923/koto_1_2/10_kigan",
    "shoka_kyozai_shu_1923/koto_1_2/21_haru_no_no",
    "shoka_kyozai_shu_1923/koto_1_2/28_iwama_shimizu",
    "shoka_kyozai_shu_1923/koto_1_2/34_sho_nanko",
    "shokacho/vol_10/p198_kigan",
    "shintei_jido_shoka/grade_2_2020.006.0847.0002/1_07_hiyoko",
    "shintei_jido_shoka/grade_3_2020.006.0847.0003/1_05_cho",
    "shintei_jido_shoka/grade_3_2020.006.0847.0003/2_03_hinomaru_no_hata",
    "shintei_jido_shoka/grade_5_2020.006.0847.0005/4_04_myogisan",
    "shintei_jido_shoka/grade_5_2020.006.0847.0005/4_15_matsushima",
    "shintei_jido_shoka/grade_5_2020.006.0847.0005/4_17_hoten_kaisen",
    "shintei_jido_shoka/grade_6_2020.006.0847.0006/1_07_sho_nanko",
    "shintei_jido_shoka/grade_6_2020.006.0847.0006/4_02_kojima_takanori",
    "shintei_jido_shoka/grade_6_2020.006.0847.0006/4_10_kojo_no_tsuki",
    "shintei_jido_shoka/koto_boys_2020.006.0848/1_3_06_tsuki_no_se",
    "shintei_jido_shoka/koto_boys_2020.006.0848/1_5_02_muramatsuri",
    "shintei_jido_shoka/koto_boys_2020.006.0848/1_5_03_chushin",
    "shintei_jido_shoka/koto_girls_2020.006.0849/2_2_08_nara_no_miyako",
    "kogakko_shoka/grade_3/1_awoba",
    "kogakko_shoka/grade_4/2_otedama",
    "kogakko_shoka/grade_4/5_hanabi",
    "kogakko_shoka/grade_4/12_nogiku",
    "kogakko_shoka/grade_4/19_hinamatsuri",
    "kogakko_shoka/grade_6/7_ware_wa_umi_no_ko",
    "kogakko_shoka/grade_6/10_nihon_sankei",
    "kogakko_shoka/grade_6/14_nanigoto_mo_seishin",
    "utanohon/ge_2006.006.0878/3_koinobori",
    "utanohon/ge_2006.006.0878/4_gunkan",
    "utanohon/ge_2006.006.0878/5_heitaisan",
    "utanohon/ge_2006.006.0878/12_ushiwakamaru",
    "utanohon/ge_2006.006.0878/15_kunibiki",
    "utanohon/ge_2006.006.0878/16_ike_no_koi",
    "utanohon/ge_2006.006.0878/18_nippon",
    "shokacho/vol_10/p196_ninomiya_sontoku",
}

VERIFIED_MEIJI_TEXTBOOK_RELS = {
    "shoka_kyozai_shu_1923/grade_1_2/25_kobutori",
    "shoka_kyozai_shu_1923/grade_1_2/41_saru_to_kani",
    "shoka_kyozai_shu_1923/grade_1_2/56_suzume_no_oyado",
    "shoka_kyozai_shu_1923/koto_1_2/10_kigan",
    "shoka_kyozai_shu_1923/koto_1_2/23_tanoshiki_wagaya",
    "shoka_kyozai_shu_1923/koto_1_2/26_tsuki",
    "shoka_kyozai_shu_1923/koto_1_2/30_enbetsuri",
    "shokacho/vol_10/p198_kigan",
    "shokacho/vol_10/p199_enbetsuri",
}

VERIFIED_TAIWAN_OFFICIAL_RELS = {
    "shoka_kyozai_shu_1923/grade_1_2/16_ichinensei",
    "shoka_kyozai_shu_1923/grade_1_2/20_karensan",
    "shoka_kyozai_shu_1923/grade_3_4/44_suigyu",
    "shoka_kyozai_shu_1923/grade_3_4/49_kyabetsu",
    "shoka_kyozai_shu_1923/grade_3_4/50_hikoki",
    "shoka_kyozai_shu_1923/grade_5_6/43_nanyo_no_uta",
    "shoka_kyozai_shu_1923/koto_1_2/12_shizangan",
    "shoka_kyozai_shu_1923/koto_1_2/17_niitakayama",
    "shoka_kyozai_shu_1923/koto_1_2/39_tansuigawa",
    "shintei_jido_shoka/grade_1_2020.006.0847.0001/3_04_hikoki",
    "shintei_jido_shoka/grade_1_2020.006.0847.0001/4_02_ichinensei",
    "shintei_jido_shoka/grade_1_2020.006.0847.0001/4_06_kazaguruma_mizuguruma",
    "shintei_jido_shoka/grade_2_2020.006.0847.0002/1_03_mizuguruma",
    "shintei_jido_shoka/grade_2_2020.006.0847.0002/2_07_ahiru",
    "shintei_jido_shoka/grade_3_2020.006.0847.0003/1_09_nagai_oyasumi",
    "shintei_jido_shoka/grade_3_2020.006.0847.0003/2_04_omatsuribi",
    "shintei_jido_shoka/grade_3_2020.006.0847.0003/2_08_undokai",
    "shintei_jido_shoka/grade_3_2020.006.0847.0003/3_04_sumiyaki",
    "shintei_jido_shoka/grade_3_2020.006.0847.0003/4_21_kyabetsu",
    "shintei_jido_shoka/grade_4_2020.006.0847.0004/2_06_tsuyu_to_mushi",
    "shintei_jido_shoka/grade_4_2020.006.0847.0004/2_09_noka_no_aki",
    "shintei_jido_shoka/grade_5_2020.006.0847.0005/1_01_haru_no_no",
    "shintei_jido_shoka/grade_5_2020.006.0847.0005/1_10_noryo",
    "shintei_jido_shoka/grade_5_2020.006.0847.0005/2_01_asa_no_uta",
    "shintei_jido_shoka/grade_5_2020.006.0847.0005/2_02_shukei",
    "shintei_jido_shoka/grade_6_2020.006.0847.0006/4_03_nanyo_no_uta",
    "shintei_jido_shoka/koto_boys_2020.006.0848/1_4_02_funako",
    "kogakko_shoka/grade_1/12_hikoki",
    "kogakko_shoka/grade_2/1_mizuguruma",
    "kogakko_shoka/grade_2/2_tori_no_su",
    "kogakko_shoka/grade_2/3_ari",
    "kogakko_shoka/grade_2/10_ahiru",
    "kogakko_shoka/grade_2/11_rajio",
    "kogakko_shoka/grade_2/14_nazonazo",
    "kogakko_shoka/grade_3/5_nagaioyasumi",
    "kogakko_shoka/grade_3/6_semi",
    "kogakko_shoka/grade_3/8_omatsuribi",
    "kogakko_shoka/grade_3/10_undokai",
    "kogakko_shoka/grade_3/14_sumiyaki",
    "kogakko_shoka/grade_4/3_minami_no_kaze",
    "kogakko_shoka/grade_4/11_tsuyu_to_mushi",
    "kogakko_shoka/grade_4/14_toriire_no_uta",
    "kogakko_shoka/grade_4/17_komoriuta",
    "kogakko_shoka/grade_4/18_showa_no_kodomo",
    "kogakko_shoka/grade_5/2_tane",
    "kogakko_shoka/grade_5/5_kuchusen",
    "kogakko_shoka/grade_5/6_sanjo_no_ie",
    "kogakko_shoka/grade_5/8_furin",
    "kogakko_shoka/grade_5/11_asa_no_uta",
    "kogakko_shoka/grade_5/13_yama_ni_noborite",
    "utanohon/ge_2006.006.0878/6_semi",
    "utanohon/ge_2006.006.0878/10_hikoki",
    "utanohon/ge_2006.006.0878/11_omatsuri",
    "utanohon/ge_2006.006.0878/17_kumo",
    "utanohon/ge_2006.006.0878/19_obaasan",
    "shokacho/vol_03/p044_kotaishi_denka_hogei_no_uta",
    "shokacho/vol_03/p057_chichibunomiya_denka_hogei_koshinka",
    "shokacho/vol_10/p195b_shingun",
    "shokacho/vol_10/p204_aki_no_minori",
    "shokacho/vol_10/p205_nami_to_iso_no_ishi",
    "shokacho/vol_10/p208_tsubame",
}


def classify_single_text(t: str, col: str, rel: str) -> set[str]:
    origins: set[str] = set()
    t_clean = re.sub(r"並非[^\n。]*", "", t)
    t_clean = re.sub(r"注意(?:此曲|本曲)[^\n。]*為同名異曲", "", t_clean)
    t_clean = re.sub(r"本曲與[^\n。]*皆為同名異曲", "", t_clean)
    t_clean = re.sub(r"異於[^\n。]*", "", t_clean)

    # 1. Western melody
    if WESTERN_PAT.search(t_clean) or rel in EXPLICIT_WESTERN_RELS:
        origins.add("western_melody")

    # 2. 1933 Taiwan Contest
    if re.search(r"懸賞募集[^\n]*入選|公學校唱歌歌詞懸賞", t_clean) or rel in EXPLICIT_CONTEST_1933_RELS:
        origins.add("taiwan_contest_1933")
        origins.add("taiwan_official")

    # 3. Taiwan teacher compositions
    if re.search(r"郭水返|陳英聲|陳英声|大稻埕女子公學校校歌", t_clean):
        origins.add("taiwan_teacher")
    if rel == "shokacho/vol_07/p231_mizuguruma":
        origins.add("taiwan_official")

    # 4. Traditional East Asian / Beiguan / Chinese
    if col == "shokacho" and (
        "vol_09/" in rel or "p081_tan_yenhua" in rel or "p074_kankanbutsu" in rel
    ):
        origins.add("traditional_east_asian")

    # 5. Monbusho
    if (
        re.search(
            r"~\s*\"文部省\"|~\s*\"小學唱歌集\"|詞：文部省|曲：文部省|文部省《|文部省編|文部省唱歌|文部省選定|文部省（|文部省讀本|"
            r"出處：（?小學唱歌集）?|出處：小學唱歌集|幼稚園唱歌|國定高等小學讀本|昭憲皇太后|明治天皇御製",
            t_clean,
        )
        or re.search(
            r"古歌.*林廣守|千家尊福.*上[真眞]行|高崎正風.*伊澤修二|黒川[眞真]頼.*奥好義",
            t_clean,
            re.S,
        )
        or rel in VERIFIED_MONBUSHO_RELS
    ):
        origins.add("monbusho")

    # 6. Meiji textbook
    if (
        col == "kyoeki_shoka"
        or rel in VERIFIED_MEIJI_TEXTBOOK_RELS
        or re.search(
            r"共益商社|明治唱歌|幼年唱歌|鐵道唱歌|中學唱歌|中等唱歌|教育唱歌集|教育幼稚唱歌集|檢定唱歌集|少年唱歌|"
            r"田村虎藏|納所辨次郎|石原和三郎|大和田建樹|小山作之助|奥好義|奧好義|奧山朝恭|"
            r"伊澤修二|多梅稚|瀧廉太郎|永井建子|三善和氣|鳥居忱|楠美恩三郎|楠見恩三郎|"
            r"栗林宇一|東儀鐵笛|落合直文|上真行|上眞行|東儀季芳|旗野十一郎|旗野士良|"
            r"山田源一郎|山田美妙|佐[々佐]木信綱|佐々木の信綱|岡野貞一|高野辰之|巖谷小波|武笠三|"
            r"里見義|大和田愛羅|蘆田惠之助|杉谷代水|杉谷虎藏|武島又次郎|武島羽衣|中村秋香|土井晩翠|土井林吉|"
            r"犬童球溪|瀨戶口藤吉|鳥山啓|加藤義清|田中銀之助|天谷秀|田中穗積|勝安芳",
            t_clean,
        )
    ):
        origins.add("meiji_textbook")

    # 7. Taisho / Showa mainland (only for collections after 1915!)
    if col not in ("kyoeki_shoka", "taiwan_shuyu_shoka", "kogakko_shokashu_1915") and re.search(
        r"大正幼年唱歌|新作唱歌|新作楽譜|特選樂譜|新特選楽譜|小学新唱歌|小學唱歌五十曲集|重音唱歌集|中等音樂教科書|中等音楽教科書|大正女學唱歌|"
        r"女子教育音樂教科書|女子音樂教科書|現代女子音樂|實科女學唱歌|女子リードアルバム|唱歌学習帳|音楽新潮|音楽新智識|中華唱歌|青年唱歌|愛吟抄|子供の國|りす|澄宮|"
        r"野口雨情|本居長世|北原白秋|中山晉平|中山晋平|山田耕筰|山田耕作|葛原|小松耕輔|梁田貞|"
        r"吉丸一昌|室崎琴月|弘田龍太郎|成田為三|成田爲三|草川信|山本壽|永井幸次|北村季晴|"
        r"福井直秋|信時潔|西條八十|相馬御風|林柳波|三木露風|松岸寬一|松岸寛一|杉江秀|桑田春風|"
        r"原田比古士良|大橋銅造|近藤朔風|今中楓溪|東くめ|藤井清水|井上武士|園山民平|中村雨紅|"
        r"河井醉茗|島崎藤村|白上貞利|近藤義次|佐々木英|佐々木すぐる|水田月人|西郷果|西郷景|"
        r"町田櫻園|小野竹三|山本正夫|富原義徳|真田梅村|黒澤隆朝|横山静子|山口季次郎|西木紫雪|橋本正夫|森谷武夫|三角錫子",
        t_clean,
    ):
        origins.add("taisho_showa_mainland")

    # 8. Taiwan official / Kokugo Reader / Taiwan-specific educator songs
    if (
        col in ("taiwan_shuyu_shoka", "taiwan_no_uta")
        or re.search(
            r"宮島慎三郎|一條氏|一條歌集|詞：臺灣總督府|臺灣總督府改作|臺灣總督府始政|公學校用國民讀本|公學校用國語讀本|"
            r"高橋二三四|芝葛鎮|昭和6年臺灣教育會選歌|臺灣の風景|新高山|淡水河|鄭成功|"
            r"芝山巖|六氏先生|にぎみたま|始政[紀記]念日|水牛|スヰギウ|カーレン|鵞鑾鼻|いかだかづら|"
            r"神木|つり橋|ジヤンク",
            t_clean,
        )
        or rel in VERIFIED_TAIWAN_OFFICIAL_RELS
    ):
        origins.add("taiwan_official")

    return origins


def compute_all_origins() -> tuple[dict[str, Path], dict[str, str], dict[str, set[str]]]:
    dup = json.loads(DUP_JSON.read_text(encoding="utf-8"))
    all_paths: dict[str, Path] = {}
    all_texts: dict[str, str] = {}
    for p in sorted(DOCS.rglob("*.tmd")):
        if (
            p.name.endswith("_piano.tmd")
            or "recreations" in p.parts
            or "fun" in p.parts
        ):
            continue
        rel = str(p.parent.relative_to(DOCS))
        all_paths[rel] = p
        all_texts[rel] = p.read_text(encoding="utf-8")

    raw_origins = {
        rel: classify_single_text(txt, rel.split("/")[0], rel)
        for rel, txt in all_texts.items()
    }

    # Propagate early origins across exact duplicate groups (respecting chronology)
    for g in dup["duplicate_groups"]:
        union_o: set[str] = set()
        for e in g["entries"]:
            union_o |= raw_origins.get(e["rel_dir"], set())
        for e in g["entries"]:
            r = e["rel_dir"]
            col = r.split("/")[0]
            allowed = set(union_o)
            if col in ("kyoeki_shoka", "taiwan_shuyu_shoka", "kogakko_shokashu_1915"):
                allowed.discard("taisho_showa_mainland")
                allowed.discard("taiwan_contest_1933")
            if col == "kyoeki_shoka":
                allowed.discard("taiwan_official")
            raw_origins[r] |= allowed

    # Second pass for textbook-specific or notebook-specific defaults
    for rel, o in raw_origins.items():
        col = rel.split("/")[0]
        if not o:
            if col == "shintei_jido_shoka":
                o.add("taisho_showa_mainland")
            elif col == "shokacho":
                txt = all_texts[rel]
                if re.search(r"一條|公學校唱歌帳\s*\(P2", txt):
                    o.add("taiwan_official")
                elif re.search(r"蓬萊|蓬集|蓬唱|蓬\s*-?\d+頁", txt):
                    o.add("taisho_showa_mainland")

    # Propagate again across exact duplicate groups (respecting chronology)
    for g in dup["duplicate_groups"]:
        union_o = set()
        for e in g["entries"]:
            union_o |= raw_origins.get(e["rel_dir"], set())
        for e in g["entries"]:
            r = e["rel_dir"]
            col = r.split("/")[0]
            allowed = set(union_o)
            if col in ("kyoeki_shoka", "taiwan_shuyu_shoka", "kogakko_shokashu_1915"):
                allowed.discard("taisho_showa_mainland")
                allowed.discard("taiwan_contest_1933")
            if col == "kyoeki_shoka":
                allowed.discard("taiwan_official")
            raw_origins[r] |= allowed

    for rel, o in raw_origins.items():
        if not o:
            o.add("unidentified")

    return all_paths, all_texts, raw_origins


def update_tmd_origin_tags(text: str, origins: set[str]) -> str:
    ordered = [tag for tag in ORIGIN_ORDER if tag in origins]
    new_tag_lines = [f'~ "tag: origin:{tag}"' for tag in ordered]

    lines = text.splitlines()
    # Remove any existing `tag: origin:...` lines
    filtered_lines = [
        ln for ln in lines if not re.match(r'^\s*~\s*"tag:\s*origin:[^"]+"\s*$', ln)
    ]

    # Find insertion point: right after the last `~ "tag: ..."` line before `** Title **`,
    # or right after `::SCORE::` if no tag lines exist yet.
    header_end = len(filtered_lines)
    for i, ln in enumerate(filtered_lines):
        if re.match(r"^\s*\*\*.*\*\*\s*$", ln) or "{" in ln:
            header_end = i
            break

    last_tag_idx = None
    score_idx = 0
    for i in range(header_end):
        if filtered_lines[i].strip() == "::SCORE::":
            score_idx = i
        if re.match(r'^\s*~\s*"tag:[^"]+"\s*$', filtered_lines[i]):
            last_tag_idx = i

    insert_at = (last_tag_idx + 1) if last_tag_idx is not None else (score_idx + 1)
    updated_lines = (
        filtered_lines[:insert_at] + new_tag_lines + filtered_lines[insert_at:]
    )
    return "\n".join(updated_lines) + ("\n" if text.endswith("\n") else "")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write tag: origin:... to all TMD files")
    args = parser.parse_args()

    all_paths, all_texts, raw_origins = compute_all_origins()

    modified_count = 0
    if args.apply:
        for rel, p in all_paths.items():
            old_txt = all_texts[rel]
            new_txt = update_tmd_origin_tags(old_txt, raw_origins[rel])
            if new_txt != old_txt:
                p.write_text(new_txt, encoding="utf-8")
                modified_count += 1
        print(f"Updated {modified_count}/{len(all_paths)} TMD files with tag: origin:...")

    for col in [
        "kyoeki_shoka",
        "taiwan_shuyu_shoka",
        "kogakko_shokashu_1915",
        "shoka_kyozai_shu_1923",
        "shokacho",
        "taiwan_no_uta",
        "shintei_jido_shoka",
        "kogakko_shoka",
        "utanohon",
    ]:
        rels = [r for r in all_texts if r.startswith(col + "/")]
        cnt = Counter()
        for r in rels:
            for tag in raw_origins[r]:
                cnt[tag] += 1
        print(f"=== {col} (total {len(rels)}) ===")
        for k in ORIGIN_ORDER:
            if cnt[k]:
                print(f"  {k:24s}: {cnt[k]:3d} ({cnt[k]*100/len(rels):5.1f}%)")


if __name__ == "__main__":
    main()
