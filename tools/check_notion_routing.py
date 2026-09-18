"""保护真实配置中的 Notion 入口、业务测速与工作白名单边界。"""
from pathlib import Path
import re

import check_private_dns_precedence as parser

BASE = "https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/"
RULE = BASE + "surge/rules/region/hk/notion_hk.list"
URL = "https://app.notion.com/"


def target(lines: list[str]) -> str:
    hits = [p[2] for _, p in parser._parse_mihomo_rules(lines)
            if len(p) == 3 and p[:2] == ["RULE-SET", "hk_notion"]]
    return hits[0] if len(hits) == 1 else ""


def group_fields(lines: list[str], name: str) -> dict[str, str]:
    fields = {}
    active = section = False
    for line in lines:
        if re.match(r"^[\w-]+:", line):
            section = line == "proxy-groups:"
            active = False
        match = re.match(r"^  - name:\s*(.+)$", line)
        if section and match:
            active = parser._scalar(match[1]) == name
        field = re.match(r"^    ([\w-]+):\s*(.+)$", line)
        if active and field:
            fields[field[1]] = parser._scalar(field[2])
    return fields


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
    if surge:
        if destination != auto or auto not in groups or groups[auto].group_type != "smart":
            errors.append("Notion 在 Surge 必须使用全地区 smart。")
        return errors
    providers = parser._parse_mihomo_providers(lines)
    if identifier not in providers or providers[identifier][1] != BASE + "mihomo/classical/region/hk/notion_hk.yaml":
        errors.append("Notion provider 必须引用规范公开产物。")
    if destination not in groups or destination == auto:
        return errors + ["Notion 必须绑定独立业务测速组。"]
    group = groups[destination]
    fields = group_fields(lines, destination)
    expected = {"type": "url-test", "url": URL, "expected-status": "200",
                "interval": "600" if "flclash-android" in path.name else "300",
                "tolerance": "150", "timeout": "5000", "lazy": "false", "max-failed-times": "2"}
    if any(fields.get(k) != v for k, v in expected.items()):
        errors.append("Notion 专用测速字段偏离已验证的主动检测与稳定选点配置。")
    if (group.filter_text or group.members or not group.source_references
            or set(group.source_references) != set(groups[auto].source_references)
            or set(group.source_references) != set(parser._parse_mihomo_proxy_provider_names(lines))
            or fields.get("exclude-filter") != group_fields(lines, auto).get("exclude-filter")):
        errors.append("Notion 必须复用全部机场 provider 与占位过滤，不能缩限地区或嵌套通用测速组。")
    return errors
