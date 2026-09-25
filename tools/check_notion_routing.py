"""保护真实配置中的 Notion 香港入口与工作白名单边界。"""
from pathlib import Path
import re

import check_private_dns_precedence as parser

BASE = "https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/"
RULE = BASE + "surge/rules/region/hk/notion_hk.list"
HK_GROUP = "🇭🇰 香港-自动选择"
LEGACY_GROUP = "📝 Notion-自动选择"


def target(lines: list[str]) -> str:
    hits = [p[2] for _, p in parser._parse_mihomo_rules(lines)
            if len(p) == 3 and p[:2] == ["RULE-SET", "hk_notion"]]
    return hits[0] if len(hits) == 1 else ""


def check(path: Path, lines: list[str], auto: str) -> list[str]:
    errors = []
    surge = path.suffix == ".conf"
    work = "work-whitelist" in path.name
    if surge:
        rules = [(i, [parser._scalar(p.strip()) for p in s.split(",")])
                 for i, s in parser._active_surge_section(lines, "Rule")]
        identifier, google = RULE, BASE + "surge/rules/region/hk/google_hk.list"
        groups = parser._parse_surge_groups(lines)
    else:
        rules = parser._parse_mihomo_rules(lines)
        identifier, google = "hk_notion", "hk_google"
        groups = parser._parse_mihomo_groups(lines)
    hits = [(i, p) for i, p in rules if p[:2] == ["RULE-SET", identifier]]
    if work:
        if hits:
            errors.append("Notion Personal 入口不得扩入工作白名单。")
        return errors
    if len(hits) != 1:
        return ["Notion 必须有且只有一个显式入口，不能回落 DIRECT。"]
    position, rule = hits[0]
    before = [i for i, p in rules if p[:2] == ["RULE-SET", google]]
    if not before or position >= min(before):
        errors.append("Notion 必须早于 Google 广谱入口。")
    destination = rule[2] if len(rule) == 3 else ""
    if destination != HK_GROUP:
        errors.append("Notion 必须绑定香港自动选择组。")
    if LEGACY_GROUP in groups:
        errors.append("不得保留 Notion 专用策略组。")
    hk = groups.get(HK_GROUP)
    if hk is None or not re.search(r"香港|hong kong|(?:^|[^a-z])hk(?:$|[^a-z])", hk.filter_text, re.IGNORECASE):
        errors.append("Notion 目标组必须具有香港节点过滤条件。")
    if surge:
        if hk is None or hk.group_type != "smart":
            errors.append("Notion 的香港目标组必须是 Surge smart。")
        return errors
    providers = parser._parse_mihomo_providers(lines)
    if identifier not in providers or providers[identifier][1] != BASE + "mihomo/classical/region/hk/notion_hk.yaml":
        errors.append("Notion provider 必须引用规范公开产物。")
    if hk is None or hk.group_type != "url-test":
        errors.append("Notion 的香港目标组必须是 Mihomo url-test。")
    return errors
