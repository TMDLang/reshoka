#!/usr/bin/env python3
"""
Update source provenance (出處考證) for 57 mapped songs in docs/kyoyusho_shoka_1935/.
Includes:
- 32 core Taisho Doyo songs
- 11 commissioned / youth songs by Taisho Doyo masters
- 6 songs from 1929 Taiwan no Uta (御大典記念事業)
- 8 songs from 1933 Kogakko Shoka contest / 1934-1935 Kogakko Shoka
"""

import os
import re
import subprocess
import sys

PROVENANCE_DATA = {
    # --- 32 首核心大正新童謠 ---
    "1_09_hotaru": {
        "source": "大正11年（1922）童謠雜誌《金の星》，野口雨情作詞、中山晉平作曲之大正新童謠",
        "note": "本曲原出大正 11 年（1922）童謠雜誌《金の星》，野口雨情作詞、中山晉平作曲。描繪溪畔捕螢童趣（「ほたる來い、やまぶきの下…」），採大調五聲音階（ヨナ抜き長音階），旋律輕快流暢。",
    },
    "1_11_tonbo": {
        "source": "大正時期童謠，大和田愛羅作詞作曲之大正新童謠",
        "note": "本曲為大正時期著名童謠，大和田愛羅作詞作曲。描寫蜻蜓飛舞與兒童捕蜻蜓的純真童趣。",
    },
    "1_19_yuyake": {
        "source": "大正時期童謠，葛原しげる作詞、小松耕輔作曲之大正新童謠",
        "note": "本曲為大正時期童謠，葛原しげる作詞、小松耕輔作曲。口語描寫夕陽西下、群鴉歸巢之簡樸祥和景致。",
    },
    "1_21_kutsu_ga_naru": {
        "source": "大正8年（1919）童謠雜誌《少女號》，清水かつら作詞、弘田龍太郎作曲之大正新童謠代表作",
        "note": "本曲原出大正 8 年（1919）童謠雜誌《少女號》，清水かつら作詞、弘田龍太郎作曲。描寫穿著小皮鞋牽手在田間漫步的歡欣景象（「おててつないで 野道を行けば…靴が鳴る 鳴る」），為日本童謠運動初期開拓代表作。",
    },
    "1_26_suzume_no_gakko": {
        "source": "大正10年（1921）童謠雜誌《少女號》，清水かつら作詞、弘田龍太郎作曲之大正新童謠代表作",
        "note": "本曲原出大正 10 年（1921）童謠雜誌《少女號》，清水かつら作詞、弘田龍太郎作曲。以生動的麻雀學校擬聲詞「チイチイパッパ チイパッパ」模仿課堂朗讀，充滿極致童趣。",
    },
    "2_01_ohayo": {
        "source": "大正時期童謠，葛原しげる作詞、小松耕輔作曲之大正新童謠",
        "note": "本曲為大正時期童謠，葛原しげる作詞、小松耕輔作曲。清晨問候禮貌童謠，旋律親切躍動。",
    },
    "2_05_sayonara_sayonara": {
        "source": "大正時期童謠，西條八十作詞、中山晉平作曲之大正新童謠",
        "note": "本曲為象徵派詩人西條八十與名作曲家中山晉平合作之放學惜別童謠，口語重疊「さよなら さよなら」清新哀婉。",
    },
    "2_06_chikuonki": {
        "source": "大正時期童謠，葛原しげる作詞、梁田貞作曲（另載《大正幼年唱歌》）",
        "note": "本曲為大正時期描寫現代文明器物之童謠，葛原しげる作詞、梁田貞作曲（亦有小松耕輔作曲版，收錄於《大正幼年唱歌》等曲集）。",
    },
    "2_08_shabondama": {
        "source": "大正11年（1922）童謠雜誌《金の星》，野口雨情作詞、中山晉平作曲之大正新童謠傳世名作（日本歌百選）",
        "note": "本曲原出大正 11 年（1922）童謠雜誌《金の星》，野口雨情作詞、中山晉平作曲，為日本童謠史上最著名名作之一（後入選日本歌百選）。雨情以悼念夭折長女之深情，寫下純真而帶哀婉的口語童謠。",
    },
    "2_18_yuyake_koyake": {
        "source": "大正12年（1923）發表，中村雨紅作詞、草川信作曲之大正新童謠傳世名作（日本歌百選）",
        "note": "本曲原發表於大正 12 年（1923），中村雨紅作詞、草川信作曲，為日本文化廳評選之「日本歌百選」傳世名曲。「夕燒け小燒けで 日が暮れて 山のお寺の 鐘が鳴る…」，意境遼遠祥和。",
    },
    "2_19_watashi_no_imoto": {
        "source": "大正時期童謠，葛原しげる作詞、小松耕輔作曲之大正新童謠",
        "note": "本曲為大正時期童謠，葛原しげる作詞、小松耕輔作曲。生動描繪背著小妹妹哄睡的溫馨手足童趣。",
    },
    "2_20_suzume_odori": {
        "source": "大正時期童謠，野口雨情作詞、中山晉平作曲之大正新童謠遊戲歌",
        "note": "本曲為野口雨情與中山晉平採集仙台民間雀舞動機創作之童謠遊戲歌，極具跳躍動感與遊戲趣味。",
    },
    "2_28_suzume": {
        "source": "大正時期童謠，葛原しげる作詞、小松耕輔作曲之大正新童謠",
        "note": "本曲為大正時期童謠，葛原しげる作詞、小松耕輔作曲。描寫麻雀跳躍嬉戲之生動自然景致。",
    },
    "3_03_kabin_no_hana": {
        "source": "大正時期學校唱歌，葛原しげる作詞、法國民謠曲調",
        "note": "本曲為大正時期學校唱歌，葛原しげる填詞、採法國民謠曲調，描繪典雅溫馨的教室生活景況。",
    },
    "3_06_yudachi": {
        "source": "大正時期童謠，林柳波作詞、宮原禎次作曲之大正新童謠",
        "note": "本曲為大正時期童謠，林柳波作詞、宮原禎次作曲。生動刻劃夏日午後雷陣雨驟來驟去之自然情態。",
    },
    "3_07_yuhi": {
        "source": "大正10年（1921）童謠雜誌《金の星》，葛原しげる作詞、室崎琴月作曲之大正新童謠代表作",
        "note": "本曲原出大正 10 年（1921）童謠雜誌《金の星》，葛原しげる作詞、室崎琴月作曲。「ぎんぎんぎらぎら夕日が沈む…まっかっかっか空の雲」，以強烈擬態疊字描寫落日，為大正童謠運動代表名作。",
    },
    "3_13_sasa_no_fune": {
        "source": "大正時期童謠，近藤義次作曲之大正新童謠",
        "note": "本曲為大正時期自然遊戲童謠，近藤義次作曲。描寫孩童摺竹葉舟隨溪水漂流的空靈童趣。",
    },
    "3_15_oyaushi_koushi": {
        "source": "大正9年（1920）童謠雜誌《赤い鳥》，三木露風作詞之大正新童謠",
        "note": "本曲原出大正 9 年（1920）鈴木三重吉創辦之《赤い鳥》，三木露風作詞。露風以寧靜筆調描寫牧場母牛舐舔小牛的深情，體現童謠運動「同情與慈愛」的精神核心。",
    },
    "3_19_jugoya": {
        "source": "大正9年（1920）童謠雜誌《赤い鳥》，三木露風作詞、山田耕筰作曲之大正新童謠藝術名作",
        "note": "本曲原出大正 9 年（1920）童謠雜誌《赤い鳥》，三木露風作詞、山田耕筰作曲。山田耕筰以極為細膩的和聲與旋律，刻劃中秋月夜兔子跳躍與秋風靜謐之夜景。",
    },
    "3_23_tsukiyo_no_usagi": {
        "source": "大正時期童謠，浜田廣介作詞、中山晉平作曲之大正新童謠",
        "note": "本曲為童話作家浜田廣介與名作曲家中山晉平合作之大正童謠，描寫月夜下小兔子奔馳嬉戲之詩意景象。",
    },
    "3_27_denshin_bashira": {
        "source": "大正11年（1922）繪本雜誌《コドモノクニ》，河井醉茗作詞、草川信作曲之大正新童謠",
        "note": "本曲原出大正 11 年（1922）婦人之友社繪本雜誌《コドモノクニ》，詩人河井醉茗將現代文明產物「電信柱」擬人化，草川信譜出獨特的跳動五聲節奏。",
    },
    "4_02_sakura_to_kotori": {
        "source": "大正時期童謠雜誌《金の星》，野口雨情作詞、本居長世作曲之大正新童謠抒情名作",
        "note": "本曲原出大正時期童謠雜誌《金の星》，野口雨情與名作曲家本居長世初期合作之抒情精品，生動刻劃春日櫻花林中小鳥啼鳴。",
    },
    "4_05_oniwa_no_kusabana": {
        "source": "大正時期童謠，葛原しげる作詞、小松耕輔作曲之大正新童謠",
        "note": "本曲為大正時期花壇園藝觀察童謠，葛原しげる作詞、小松耕輔作曲。",
    },
    "4_06_natsu_no_asa": {
        "source": "大正時期童謠，葛原しげる作詞、小松耕輔作曲之大正新童謠",
        "note": "本曲為大正時期晨光素描童謠，葛原しげる作詞、小松耕輔作曲，描寫夏日清晨牽牛花綻放之清新景致。",
    },
    "4_10_usagi_no_denpo": {
        "source": "大正8年（1919）童謠雜誌《赤い鳥》，北原白秋作詞、山田耕筰作曲之大正新童謠藝術名作",
        "note": "本曲原出大正 8 年（1919）童謠雜誌《赤い鳥》，北原白秋作詞、山田耕筰作曲。每句疊唱滑稽活潑的「エッサッサ」，小兔子穿過玉蜀黍田送急件電報，為白秋文字遊戲的代表作。",
    },
    "4_12_saru_no_sarumane": {
        "source": "大正時期童謠，野口雨情作詞、室崎琴月作曲之大正幽默童謠",
        "note": "本曲為大正時期幽默童謠，野口雨情作詞、室崎琴月作曲。生動描寫猴子模仿人類舉止的滑稽模樣。",
    },
    "4_14_ano_machi_kono_machi": {
        "source": "大正13年（1924）童謠繪本《コドモノクニ》，野口雨情作詞、中山晉平作曲之大正新童謠黃金代表作",
        "note": "本曲原出大正 13 年（1924）婦人之友社《コドモノクニ》，野口雨情作詞、中山晉平作曲。描寫黃昏降臨時小鎮點燈、歸家雀鳥與溫馨童年，為日本童謠黃金期傳世代表作。",
    },
    "4_25_tonbi": {
        "source": "大正時期童謠，葛原しげる作詞、梁田貞作曲之大正新童謠名作",
        "note": "本曲為著名大正新童謠，葛原しげる作詞、梁田貞作曲。描繪鳶鳥（とんび）在蒼穹悠然盤旋的開闊景象（「飛べ飛べとんび 空高く」）。",
    },
    "4_32_futatsu_no_cho": {
        "source": "大正時期童謠，室崎琴月作曲之大正新童謠",
        "note": "本曲為大正時期童謠，室崎琴月作曲。描繪兩隻蝴蝶在花叢間翩翩起舞之自然意境。",
    },
    "4_37_hotaru": {
        "source": "大正時期童謠，池野道治作詞、山内冷晃作曲之大正新童謠",
        "note": "本曲為大正時期自然童謠，池野道治作詞、山内冷晃作曲。描寫夏夜幽微螢火之空靈意境。",
    },
    "7_09_satogokoro": {
        "source": "大正時期藝術歌曲/童謠，北原白秋作詞、山田耕筰作曲之思鄉藝術歌曲",
        "note": "本曲為北原白秋作詞、山田耕筰作曲之思鄉藝術歌曲/童謠。全曲以 C 小調寫成，充滿深沉哀愁美感，收錄於女子青年部作為修養歌曲。",
    },
    "7_13_no_no_sachi": {
        "source": "大正時期童謠/歌曲，葛原しげる作詞、小松耕輔作曲（青年歌謠集）",
        "note": "本曲為大正時期葛原しげる作詞、小松耕輔作曲之田園讚美歌，收錄於女子青年部，描繪田野自然收穫之豐美與感恩情懷。",
    },

    # --- 11 首童謠名家受邀創作之臺灣地景與青年團曲目 ---
    "4_13_taiwan_shonen_koshinkyoku": {
        "source": "昭和時期臺灣少年團歌曲，北原白秋作詞、山田耕筰作曲之行進曲",
        "note": "本曲為北原白秋作詞、山田耕筰作曲專為臺灣少年團量身創作之現代行進曲，將大正童謠的明亮口語轉化為動員號召：「雲よとべとべ 木瓜よみのれ／水牛はこえる…少年だ 少年だ 臺灣少年だ」。",
    },
    "5_11_nihon_kokuminka": {
        "source": "葛原しげる作詞、梁田貞作曲之國民修養歌曲",
        "note": "本曲為葛原しげる作詞、梁田貞作曲之國民歌曲，收錄於男女青年部。",
    },
    "5_14_hinomaru_no_uta": {
        "source": "葛原しげる作詞、弘田龍太郎作曲之儀式國旗歌",
        "note": "本曲為童謠名家葛原しげる作詞、弘田龍太郎作曲之儀式國旗歌。",
    },
    "5_19_hinomaru_ondo": {
        "source": "葛原しげる作詞、弘田龍太郎作曲之音頭舞曲",
        "note": "本曲為葛原しげる作詞、弘田龍太郎作曲之團體盆踊音頭舞曲。",
    },
    "5_20_rinto_bushi": {
        "source": "北原白秋作詞、藤井清水作曲之臺灣地景新民謠",
        "note": "本曲由北原白秋作詞、擅長民謠採譜的藤井清水作曲，在「ヤッサハイノ リントサット」「サンサー」的眾人和聲中詠唱常夏島嶼與林投海風。",
    },
    "6_01_seinen_no_uta": {
        "source": "東京音樂學校作曲之帝國青年團修養歌",
        "note": "本曲為東京音樂學校作曲之青年團修養歌，收錄於男子青年部。",
    },
    "6_03_taiwan_seinen_ka": {
        "source": "昭和時期臺灣青年團歌，北原白秋作詞、山田耕筰作曲之行進歌",
        "note": "本曲為北原白秋作詞、山田耕筰作曲專為臺灣青年團創作之行進歌，從椰子葉、黑潮、鵝鑾鼻唱向「臺灣 臺灣 ここぞわが島 いざ守れ」。",
    },
    "6_04_sora_wa_aogumo": {
        "source": "昭和時期青年行進歌，北原白秋作詞、山田耕筰作曲（青年歌謠集）",
        "note": "本曲為北原白秋作詞、山田耕筰作曲之青年修養行進歌，充滿雄渾進行曲色彩。",
    },
    "6_18_hoko_wo_osamete": {
        "source": "時雨音羽作詞、中山晉平作曲之勞動與捕鯨生活歌",
        "note": "本曲由著名民謠童謠作詞家時雨音羽作詞、中山晉平作曲，描繪捕鯨船凱旋返港的壯闊生活情境。",
    },
    "7_05_shinko_nihon_shojo_no_uta": {
        "source": "葛原しげる作詞、小松耕輔作曲之女子青年團歌曲",
        "note": "本曲為葛原しげる作詞、小松耕輔作曲專為女子青年團創作之修養歌曲。",
    },
    "7_14_taue_uta": {
        "source": "梁田貞作曲之日本農村田植勞動歌",
        "note": "本曲由名作曲家梁田貞譜曲，描繪農村插秧勞動情調，收錄於女子青年部。",
    },

    # --- 6 首 1929《臺灣の歌》（臺灣教育會御大典記念事業徵選） ---
    "2_11_suigyu": {
        "source": "昭和4年（1929）臺灣教育會《臺灣の歌》第3首，御船武作詞、郭明峯作曲（並編入總督府《公學校唱歌》第二學年）",
        "note": "本曲初出昭和 4 年（1929）臺灣教育會御大典記念事業募集之《臺灣の歌》第 3 首，御船武作詞、臺籍教師郭明峯作曲。原書譜面保留郭明峯署名，後亦編入總督府《公學校唱歌》第二學年第 6 課。",
    },
    "3_20_omatsuribi": {
        "source": "昭和4年（1929）臺灣教育會《臺灣の歌》第2首，田村富士雄作詞、陳華堤作曲（並編入總督府《公學校唱歌》第三學年）",
        "note": "本曲初出昭和 4 年（1929）臺灣教育會御大典記念事業募集之《臺灣の歌》第 2 首，田村富士雄作詞、臺籍教師陳華堤作曲。描寫臺灣神社大祭供奉蓬萊米、文旦、香蕉與臺語音譯鳳梨（おんらい），後編入《公學校唱歌》第三學年第 8 課。",
    },
    "5_15_korezo_taiwan": {
        "source": "昭和4年（1929）臺灣教育會《臺灣の歌》第4首，佐佐木規矩雄作詞、一條慎三郎作曲",
        "note": "本曲初出昭和 4 年（1929）臺灣教育會御大典記念事業募集之《臺灣の歌》第 4 首，佐佐木規矩雄作詞、一條慎三郎作曲，收錄於男女青年部。",
    },
    "6_12_tokonatsu_no_shima": {
        "source": "昭和4年（1929）臺灣教育會《臺灣の歌》第5首，高木良成作詞、一條慎三郎作曲",
        "note": "本曲初出昭和 4 年（1929）臺灣教育會御大典記念事業募集之《臺灣の歌》第 5 首，高木良成作詞、一條慎三郎作曲，收錄於男子青年部。",
    },
    "6_14_taiwan_koshinka": {
        "source": "昭和4年（1929）臺灣教育會《臺灣の歌》第6首，久保天隨作詞、澤崎定之作曲",
        "note": "本曲初出昭和 4 年（1929）臺灣教育會御大典記念事業募集之《臺灣の歌》第 6 首，著名漢學家久保天隨作詞、澤崎定之作曲，收錄於男子青年部。",
    },
    "7_22_shima_no_uta": {
        "source": "昭和4年（1929）臺灣教育會《臺灣の歌》第10首，田村富士雄作詞、小野正雄作曲",
        "note": "本曲初出昭和 4 年（1929）臺灣教育會御大典記念事業募集之《臺灣の歌》第 10 首，田村富士雄作詞、小野正雄作曲，收錄於女子青年部壓軸。",
    },

    # --- 8 首 1933 公學校唱歌懸賞入選與新版《公學校唱歌》 ---
    "1_13_yudachi_yanda": {
        "source": "昭和8年（1933）臺灣總督府〈懸賞募集 公學校唱歌教材入選歌詞〉，昭和9年（1934）《公學校唱歌 卷一》第8首",
        "note": "本曲歌詞源自昭和 8 年（1933）臺灣總督府〈懸賞募集 公學校唱歌教材入選歌詞〉，增本光春作詞，經總督府文教局審定後編入昭和 9 年《公學校唱歌》第一學年第 4 課〈ユフダチ ヤンダ〉。描寫芒果樹與檳榔葉落雨滴之南國午後景致。",
    },
    "1_27_mejiro_no_ko": {
        "source": "昭和8年（1933）臺灣總督府〈懸賞募集 公學校唱歌教材入選歌詞〉，昭和9年（1934）《公學校唱歌 卷一》第11首",
        "note": "本曲歌詞源自昭和 8 年（1933）臺灣總督府〈懸賞募集 公學校唱歌教材入選歌詞〉，林春芳作詞，編入昭和 9 年《公學校唱歌》第一學年第 3 課〈メジロ ノ コ〉。",
    },
    "2_07_janken": {
        "source": "昭和8年（1933）臺灣總督府〈懸賞募集 公學校唱歌教材入選歌詞〉原題〈じやんけんぽん〉，昭和9年（1934）《公學校唱歌 卷二》〈ジャンケン〉",
        "note": "本曲歌詞源自昭和 8 年（1933）臺灣總督府〈懸賞募集 公學校唱歌教材入選歌詞〉入選原題〈じやんけんぽん〉（佐野洋子作詞），原書保留入選原題，公學校課本改題為〈ジャンケン〉。描寫香蕉與鳳梨猜拳之南國童趣遊戲歌。",
    },
    "2_23_kosuzume": {
        "source": "昭和8年（1933）臺灣總督府〈懸賞募集 公學校唱歌教材入選歌詞〉，昭和9年（1934）《公學校唱歌 卷二》第10首",
        "note": "本曲歌詞源自昭和 8 年（1933）臺灣總督府〈懸賞募集 公學校唱歌教材入選歌詞〉，佐野洋子作詞，編入昭和 9 年《公學校唱歌》第二學年第 13 課〈コスズメ〉。描繪榕樹枝頭小麻雀啼鳴之鄉土情懷。",
    },
    "4_03_daisha": {
        "source": "昭和8年（1933）臺灣總督府〈懸賞募集 公學校唱歌教材入選歌詞〉，昭和10年（1935）《公學校唱歌 卷四》",
        "note": "本曲歌詞源自昭和 8 年（1933）臺灣總督府〈懸賞募集 公學校唱歌教材入選歌詞〉，佐野洋子作詞，編入昭和 10 年新版《公學校唱歌》第四學年。描寫乘輕便臺車穿行於臺灣鄉野的歡快景致。",
    },
    "4_22_ikadakazura": {
        "source": "昭和10年（1935）臺灣總督府《公學校唱歌 卷四》第5首",
        "note": "本曲出處為昭和 10 年（1935）新版《公學校唱歌》第四學年第 5 課〈いかだかづら〉。描寫臺灣校園與庭院常見之九重葛（いかだかづら）繁花盛開之南國景致。",
    },
    "4_23_shirasagi": {
        "source": "昭和8年（1933）臺灣總督府〈懸賞募集 公學校唱歌教材入選歌詞〉，昭和10年（1935）《公學校唱歌 卷四》第14首",
        "note": "本曲歌詞源自昭和 8 年（1933）臺灣總督府〈懸賞募集 公學校唱歌教材入選歌詞〉，佐野洋子作詞，編入昭和 10 年新版《公學校唱歌》第四學年第 14 課〈白さぎ〉。描繪白鷺群在綠色水田中起落之詩意鄉土圖景。",
    },
    "5_16_minami_no_kaze": {
        "source": "臺灣總督府《公學校唱歌 高等科 第一學年》第11首",
        "note": "本曲出處為臺灣總督府《公學校唱歌 高等科 第一學年》第 11 課〈南の風〉。以優美旋律描繪南風吹拂、文旦花香溢滿山野的臺灣南國意象。",
    },
}


def update_tmd_file(filepath: str, folder_key: str, data: dict):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    source_text = f'~ "出處：{data["source"]}"'
    note_text = f"   出處考證：{data['note']}"

    # Special handling for 2_08_shabondama (replace whole wrong comment block)
    if folder_key == "2_08_shabondama":
        clean_comment = """/* =========================================================================
   【曲目說明與出處考證】
   ・出處：臺灣總督府警務局《教育所用 唱歌教材集》（昭和十年／1935，國臺圖 0725 148）第二學年第 8 首，原書第 51 頁（P079.jpg）。
   ・出處考證：本曲原出大正 11 年（1922）童謠雜誌《金の星》，野口雨情作詞、中山晉平作曲，為日本童謠史上最著名名作之一（後入選日本歌百選）。雨情以悼念夭折長女之深情，寫下純真而帶哀婉的口語童謠。
   ・調性與拍號：ニ長調（D 大調），2/4 拍，速度 != 108。

   【歌詞全文】
   （第一遍）
   シャボンタマ　トンダ
   ヤネマデ　トンダ
   ヤネマデ　トンデ
   コハレテ　キエタ

   （第二遍）
   シャボンタマ　キエタ
   トバズニ　キエタ
   ウマレテ　スグニ
   コハレテ　キエタ

   （結句）
   カゼ　カゼ　フクナ
   シャボンダマ　トバソ
   ========================================================================= */"""
        # Replace comment block
        content = re.sub(r'/\*.*?\*/', clean_comment, content, flags=re.DOTALL)

    # 1. Update or Insert Header Source
    lines = content.splitlines()
    new_lines = []
    has_source = False

    # Check if ~ "出處：..." exists
    for i, line in enumerate(lines):
        if line.strip().startswith('~ "出處：'):
            has_source = True
            break

    if has_source:
        for line in lines:
            if line.strip().startswith('~ "出處：'):
                new_lines.append(source_text)
            else:
                new_lines.append(line)
    else:
        inserted = False
        for line in lines:
            new_lines.append(line)
            if not inserted and (
                "警務局《教育所用 唱歌教材集》" in line
                or line.strip().startswith('~ "source: 臺灣總督府警務局')
                or line.strip().startswith('~ "source: school_textbook"')
            ):
                new_lines.append(source_text)
                inserted = True
        if not inserted:
            # Fallback: insert before the first comment block or after the last ~ line
            last_meta_idx = -1
            for idx, l in enumerate(new_lines):
                if l.strip().startswith('~ "'):
                    last_meta_idx = idx
            if last_meta_idx != -1:
                new_lines.insert(last_meta_idx + 1, source_text)
            else:
                new_lines.insert(0, source_text)

    content = "\n".join(new_lines) + ("\n" if content.endswith("\n") else "")

    # 2. Update Comment Block (for files other than shabondama)
    if folder_key != "2_08_shabondama":
        if "/*" in content and "*/" in content:
            # Check if note already in comment
            comment_match = re.search(r'(/\*.*?\*/)', content, re.DOTALL)
            if comment_match:
                comment_body = comment_match.group(1)
                if "出處考證：" not in comment_body and data["note"] not in comment_body:
                    if "=========================================================================" in comment_body:
                        # Insert right before the closing delimiter line
                        new_comment = comment_body.replace(
                            "   =========================================================================",
                            f"{note_text}\n   ========================================================================="
                        )
                    else:
                        # Insert right before */
                        new_comment = comment_body[:-2].rstrip() + f"\n\n{note_text}\n*/"
                    content = content[:comment_match.start()] + new_comment + content[comment_match.end():]
        else:
            # No comment block, add one after header
            comment_block = f"""
/* =========================================================================
   【曲目說明與出處考證】
{note_text}
   ========================================================================= */
"""
            # Insert after the last ~ line
            parts = content.split("{", 1)
            if len(parts) == 2:
                content = parts[0].rstrip() + "\n" + comment_block + "\n{" + parts[1]

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    base_dir = "docs/kyoyusho_shoka_1935"
    updated_files = []
    for folder, data in PROVENANCE_DATA.items():
        folder_path = os.path.join(base_dir, folder)
        if not os.path.isdir(folder_path):
            print(f"Directory not found: {folder_path}", file=sys.stderr)
            continue
        for fname in os.listdir(folder_path):
            if fname.endswith(".tmd"):
                fpath = os.path.join(folder_path, fname)
                update_tmd_file(fpath, folder, data)
                updated_files.append(fpath)

    print(f"Successfully updated {len(updated_files)} TMD files across {len(PROVENANCE_DATA)} folders.")

    # Run tmd check on all updated files
    print("Running tmd check...")
    failed = []
    for fpath in updated_files:
        res = subprocess.run(["tmd", "check", fpath], capture_output=True, text=True)
        if res.returncode != 0:
            print(f"FAILED tmd check: {fpath}\n{res.stderr}")
            failed.append(fpath)

    if failed:
        print(f"Errors encountered in {len(failed)} files!", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"All {len(updated_files)} TMD files passed tmd check successfully!")


if __name__ == "__main__":
    main()
