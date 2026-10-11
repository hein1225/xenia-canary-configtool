#!/usr/bin/env python3
"""生成 [XConfig] 分组的取值对照表（国家 / 语言）。

xenia-canary 新版配置里 user_country / user_language 是「自由整数」，
配置文件注释只给了 ISO 二字码（101=TW），界面若不翻译，用户只能看到数字。
这里把 ISO 码补成中英双语标签，让下拉框直接选「中国 / China」。

数据来源：xenia-canary.config.toml 的 [XConfig] 段注释（权威），
名称由本文件人工撰写。仅覆盖配置文件实际列出的取值，不臆造其它码。
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "src" / "data" / "schema.json"
OUT = ROOT / "src" / "data" / "xconfig_choices.json"

# ISO 3166-1 alpha-2 → 中文名 / 英文名
# 仅包含 xenia 注释里真实出现的 107 个国家码。
COUNTRY: dict[str, tuple[str, str]] = {
    "AE": ("阿联酋", "United Arab Emirates"),
    "AL": ("阿尔巴尼亚", "Albania"),
    "AM": ("亚美尼亚", "Armenia"),
    "AR": ("阿根廷", "Argentina"),
    "AT": ("奥地利", "Austria"),
    "AU": ("澳大利亚", "Australia"),
    "AZ": ("阿塞拜疆", "Azerbaijan"),
    "BE": ("比利时", "Belgium"),
    "BG": ("保加利亚", "Bulgaria"),
    "BH": ("巴林", "Bahrain"),
    "BN": ("文莱", "Brunei"),
    "BO": ("玻利维亚", "Bolivia"),
    "BR": ("巴西", "Brazil"),
    "BY": ("白俄罗斯", "Belarus"),
    "BZ": ("伯利兹", "Belize"),
    "CA": ("加拿大", "Canada"),
    "CH": ("瑞士", "Switzerland"),
    "CL": ("智利", "Chile"),
    "CN": ("中国大陆", "China"),
    "CO": ("哥伦比亚", "Colombia"),
    "CR": ("哥斯达黎加", "Costa Rica"),
    "CZ": ("捷克", "Czechia"),
    "DE": ("德国", "Germany"),
    "DK": ("丹麦", "Denmark"),
    "DO": ("多米尼加", "Dominican Republic"),
    "DZ": ("阿尔及利亚", "Algeria"),
    "EC": ("厄瓜多尔", "Ecuador"),
    "EE": ("爱沙尼亚", "Estonia"),
    "EG": ("埃及", "Egypt"),
    "ES": ("西班牙", "Spain"),
    "FI": ("芬兰", "Finland"),
    "FO": ("法罗群岛", "Faroe Islands"),
    "FR": ("法国", "France"),
    "GB": ("英国", "United Kingdom"),
    "GE": ("格鲁吉亚", "Georgia"),
    "GR": ("希腊", "Greece"),
    "GT": ("危地马拉", "Guatemala"),
    "HK": ("中国香港", "Hong Kong"),
    "HN": ("洪都拉斯", "Honduras"),
    "HR": ("克罗地亚", "Croatia"),
    "HU": ("匈牙利", "Hungary"),
    "ID": ("印度尼西亚", "Indonesia"),
    "IE": ("爱尔兰", "Ireland"),
    "IL": ("以色列", "Israel"),
    "IN": ("印度", "India"),
    "IQ": ("伊拉克", "Iraq"),
    "IR": ("伊朗", "Iran"),
    "IS": ("冰岛", "Iceland"),
    "IT": ("意大利", "Italy"),
    "JM": ("牙买加", "Jamaica"),
    "JO": ("约旦", "Jordan"),
    "JP": ("日本", "Japan"),
    "KE": ("肯尼亚", "Kenya"),
    "KG": ("吉尔吉斯斯坦", "Kyrgyzstan"),
    "KR": ("韩国", "South Korea"),
    "KW": ("科威特", "Kuwait"),
    "KZ": ("哈萨克斯坦", "Kazakhstan"),
    "LB": ("黎巴嫩", "Lebanon"),
    "LI": ("列支敦士登", "Liechtenstein"),
    "LT": ("立陶宛", "Lithuania"),
    "LU": ("卢森堡", "Luxembourg"),
    "LV": ("拉脱维亚", "Latvia"),
    "LY": ("利比亚", "Libya"),
    "MA": ("摩洛哥", "Morocco"),
    "MC": ("摩纳哥", "Monaco"),
    "MK": ("北马其顿", "North Macedonia"),
    "MN": ("蒙古", "Mongolia"),
    "MO": ("中国澳门", "Macao"),
    "MV": ("马尔代夫", "Maldives"),
    "MX": ("墨西哥", "Mexico"),
    "MY": ("马来西亚", "Malaysia"),
    "NI": ("尼加拉瓜", "Nicaragua"),
    "NL": ("荷兰", "Netherlands"),
    "NO": ("挪威", "Norway"),
    "NZ": ("新西兰", "New Zealand"),
    "OM": ("阿曼", "Oman"),
    "PA": ("巴拿马", "Panama"),
    "PE": ("秘鲁", "Peru"),
    "PH": ("菲律宾", "Philippines"),
    "PK": ("巴基斯坦", "Pakistan"),
    "PL": ("波兰", "Poland"),
    "PR": ("波多黎各", "Puerto Rico"),
    "PT": ("葡萄牙", "Portugal"),
    "PY": ("巴拉圭", "Paraguay"),
    "QA": ("卡塔尔", "Qatar"),
    "RO": ("罗马尼亚", "Romania"),
    "RU": ("俄罗斯", "Russia"),
    "SA": ("沙特阿拉伯", "Saudi Arabia"),
    "SE": ("瑞典", "Sweden"),
    "SG": ("新加坡", "Singapore"),
    "SI": ("斯洛文尼亚", "Slovenia"),
    "SK": ("斯洛伐克", "Slovakia"),
    "SV": ("萨尔瓦多", "El Salvador"),
    "SY": ("叙利亚", "Syria"),
    "TH": ("泰国", "Thailand"),
    "TN": ("突尼斯", "Tunisia"),
    "TR": ("土耳其", "Türkiye"),
    "TT": ("特立尼达和多巴哥", "Trinidad and Tobago"),
    "TW": ("中国台湾", "Taiwan"),
    "UA": ("乌克兰", "Ukraine"),
    "US": ("美国", "United States"),
    "UY": ("乌拉圭", "Uruguay"),
    "UZ": ("乌兹别克斯坦", "Uzbekistan"),
    "VE": ("委内瑞拉", "Venezuela"),
    "VN": ("越南", "Vietnam"),
    "YE": ("也门", "Yemen"),
    "ZA": ("南非", "South Africa"),
}

# 语言码 → 中文名 / 英文名
LANGUAGE: dict[str, tuple[str, str]] = {
    "en": ("英语", "English"),
    "ja": ("日语", "Japanese"),
    "de": ("德语", "German"),
    "fr": ("法语", "French"),
    "es": ("西班牙语", "Spanish"),
    "it": ("意大利语", "Italian"),
    "ko": ("韩语", "Korean"),
    "zh": ("中文", "Chinese"),
    "pt": ("葡萄牙语", "Portuguese"),
    "pl": ("波兰语", "Polish"),
    "ru": ("俄语", "Russian"),
    "sv": ("瑞典语", "Swedish"),
    "tr": ("土耳其语", "Turkish"),
    "nb": ("书面挪威语", "Norwegian Bokmål"),
    "nl": ("荷兰语", "Dutch"),
}


def parse_pairs(comment: str) -> list[tuple[str, str]]:
    """从配置注释里抽出 (数字码, 二字码) 列表，保持文件中的原始顺序。"""
    return re.findall(r"\b(\d{1,3})=([A-Za-z]{2})\b", comment)


def build(comment: str, table: dict[str, tuple[str, str]], what: str) -> list[dict]:
    pairs = parse_pairs(comment)
    if not pairs:
        raise SystemExit(f"错误：{what} 的注释里没解析到任何取值对")
    unknown = sorted({c for _, c in pairs if c not in table})
    if unknown:
        raise SystemExit(f"错误：{what} 缺少 {len(unknown)} 个名称: {unknown}")
    unused = sorted(set(table) - {c for _, c in pairs})
    if unused:
        print(f"  提示：{what} 有 {len(unused)} 个未被使用的名称 {unused}（配置未列出，已忽略）")
    out = []
    for num, code in pairs:
        zh, en = table[code]
        out.append({"value": int(num), "code": code, "zh": zh, "en": en})
    # 按数字码排序，下拉列表顺序与配置文件一致
    out.sort(key=lambda r: r["value"])
    return out


def main() -> int:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    entries = {e["key"]: e for e in schema["entries"]}
    countries = build(entries["user_country"]["comment"], COUNTRY, "user_country")
    languages = build(entries["user_language"]["comment"], LANGUAGE, "user_language")

    data = {"user_country": countries, "user_language": languages}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已写出 {OUT.relative_to(ROOT)}")
    print(f"  user_country : {len(countries)} 项（{countries[0]['code']} … {countries[-1]['code']}）")
    print(f"  user_language: {len(languages)} 项（{languages[0]['code']} … {languages[-1]['code']}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
