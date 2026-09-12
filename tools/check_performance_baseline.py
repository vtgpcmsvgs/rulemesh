"""校验用户于 2026-09-09 批准的性能基线；所有诊断只输出字段和公开规则名。"""
from __future__ import annotations

import re
from pathlib import Path

MARKER = "# RuleMesh 性能基线：2026-09-09"
BASE = "https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/"
DOMESTIC = ("https://dns.alidns.com/dns-query", "https://doh.pub/dns-query")
OVERSEAS = ("https://cloudflare-dns.com/dns-query", "https://dns.google/dns-query")
METADATA_FILTER = r"^(?!剩余流量)(?!(直接连接)$)(?!套餐到期)(?!距离下次重置)(?!.*联系我们)(?!过滤掉)(?!Expire Date)(?!Traffic Reset)(?!.*\d+(?:\.\d+)?\s*(?:[KMGT]B?|B)\s*\|\s*\d+(?:\.\d+)?\s*(?:[KMGT]B?|B)).*$"
PUBLIC_US_FILTER = METADATA_FILTER[:-3] + r".*((🇺🇸)|(美国)|(United States)|(US)).*$"
GEOIP_URL = "https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/country.mmdb"
AI_DNS_RULE = BASE + "surge/rules/region/us/ai_dns_us.list"
AIRPORT_START = "# AIRPORT_MANUAL_GROUPS_START"
AIRPORT_END = "# AIRPORT_MANUAL_GROUPS_END"


def check_airport_groups(lines: list[str]) -> list[str]:
    """当前私人 Surge 的七个机场手动入口属于用户功能，不能按规则引用数清理。"""
    import check_private_dns_precedence as dns

    if lines.count(AIRPORT_START) != 1 or lines.count(AIRPORT_END) != 1:
        return ["机场手动组保护块必须完整且唯一。"]
    start, end = lines.index(AIRPORT_START), lines.index(AIRPORT_END)
    section = dict(dns._active_surge_section(lines, "Proxy Group"))
    active = [line for number, line in section.items() if start < number - 1 < end]
    groups = dns._parse_surge_groups(["[Proxy Group]", *active])
    all_groups = dns._parse_surge_groups(lines)
    owners = [g for g in all_groups.values() if g.group_type == "select" and set(groups).issubset(g.members)]
    if start >= end or len(active) != 7 or len(groups) != 7 or not owners:
        return ["必须保留七个独立机场手动组并接入手动选择入口。"]
    if not all(g.group_type == "select" and g.has_external_source and g.filter_text for g in groups.values()):
        return ["机场手动组必须保留订阅来源与过滤条件。"]
    if not all(re.search(r"(?:^|,)\s*hidden=0(?:,|$)", line) for line in active):
        return ["机场手动组必须在界面中可见。"]
    return []
REGIONAL = {
    "region/tw/crypto_tw": "tw", "region/jp/domains_to_jp": "jp",
    "region/hk/hk_brokers": "hk", "region/hk/hk_securities_aggressive": "hk",
    "proxy/polygon_rpc_proxy": "tw", "proxy/bsc_rpc_proxy": "tw",
}
PROVIDER_IDS = {
    "tw_crypto": "region/tw/crypto_tw", "jp_domains": "region/jp/domains_to_jp",
    "hk_brokers": "region/hk/hk_brokers", "hk_securities_aggressive": "region/hk/hk_securities_aggressive",
    "proxy_polygon_rpc": "proxy/polygon_rpc_proxy", "proxy_bsc_rpc": "proxy/bsc_rpc_proxy",
}


def region_filters(region: str, surge: bool) -> frozenset[str]:
    tags = {"tw": ("🇨🇳", "台湾", "Taiwan", "TW"), "jp": ("🇯🇵", "日本", "Japan", "JP"), "hk": ("🇭🇰", "香港", "Hong Kong", "HK")}[region]
    if surge:
        simple = "(" + "|".join(f"({tag})" for tag in tags) + ")"
        return frozenset({simple, METADATA_FILTER[:-3] + ".*" + simple + ".*$"})
    return frozenset({"(?i)" + "|".join(tags[:2] + (tags[2].lower(), r"\\b" + tags[3].lower() + r"\\b"))})


def applies(lines: list[str]) -> bool:
    return MARKER in lines[:3]


def check(path: Path, lines: list[str]) -> list[str]:
    # 延迟导入避免旧版入口与新版基线互相导入时形成循环。
    import check_private_dns_precedence as dns
    import check_private_performance as performance

    errors: list[str] = []

    def require(ok: bool, message: str) -> None:
        if not ok:
            errors.append(message)

    work = "work-whitelist" in path.name
    surge = path.suffix == ".conf"
    if path.name.startswith("rulemesh-substore-"):
        for marker in ("PRIVATE_SUBSCRIPTION_DIRECT_START", "PRIVATE_SUBSCRIPTION_DIRECT_END"):
            require(sum(marker in line for line in lines) == 1, "私有订阅同步块的起止标记必须完整保留。")
    if surge:
        if path.name.startswith("rulemesh-substore-"):
            errors.extend(check_airport_groups(lines))
        for name in ("General", "Host", "Proxy Group", "Rule"):
            require(sum(line.strip() == f"[{name}]" for line in lines) == 1, f"Surge {name} 节必须唯一。")
        groups = dns._parse_surge_groups(lines)
        auto_groups = [name for name, group in groups.items() if group.group_type == "smart"]
        rules = []
        for index, line in dns._active_surge_section(lines, "Rule"):
            code = line.partition(" //")[0]
            parts = [part.strip().strip('"') for part in code.split(",")]
            rules.append((index, parts))
        identifiers = {
            BASE + "surge/rules/region/us/ai_us.list": "ai",
            BASE + "surge/rules/direct/ips5_direct.list": "ips5",
            BASE + "surge/rules/direct/bytedance_direct.list": "douyin",
            BASE + "surge/rules/direct/cn_social_direct.list": "social",
            BASE + "surge/rules/region/hk/google_hk.list": "google",
        }
    else:
        for name in ("dns", "rules", "proxy-groups", "rule-providers", "proxy-providers"):
            require(sum(line == f"{name}:" for line in lines) == 1, f"Mihomo {name} 节必须唯一。")
        groups = dns._parse_mihomo_groups(lines)
        auto_groups = [name for name, group in groups.items() if group.group_type == "url-test"]
        rules = dns._parse_mihomo_rules(lines)
        identifiers = {"us_ai": "ai", "direct_ips5": "ips5", "direct_bytedance": "douyin", "direct_cn_social": "social", "hk_google": "google"}
        providers = dns._parse_mihomo_providers(lines)
        for name, identifier in {
            "us_ai": "region/us/ai_us", "direct_bytedance": "direct/bytedance_direct",
            "direct_cn_social": "direct/cn_social_direct", "hk_google": "region/hk/google_hk",
            "direct_ips5": "direct/ips5_direct",
        }.items():
            require(name in providers and providers[name][1] == BASE + f"mihomo/classical/{identifier}.yaml", f"Mihomo {name} 必须引用规范公开产物。")

    require(bool(auto_groups), "缺少全地区自动组。")
    if not auto_groups:
        return errors
    auto = auto_groups[0]
    # 多个组可能复用美国过滤器；从实际 AI 路由解析目标，不能假定美国组唯一。
    selected: dict[str, list[tuple[int, list[str]]]] = {}
    for position, (_, parts) in enumerate(rules):
        if len(parts) >= 3 and parts[0] == "RULE-SET" and parts[1] in identifiers:
            selected.setdefault(identifiers[parts[1]], []).append((position, parts))
    for identifier in ("ai", "douyin", "social", "ips5", "google"):
        require(len(selected.get(identifier, [])) == 1, f"{identifier} 必须有且只有一个显式入口。")
    if not all(len(selected.get(key, [])) == 1 for key in ("ai", "douyin", "social", "ips5", "google")):
        return errors
    ai_position, ai_rule = selected["ai"][0]
    us = ai_rule[2]
    allowed = dns.APPROVED_SURGE_US_FILTERS | {PUBLIC_US_FILTER} if surge else dns.APPROVED_MIHOMO_US_FILTERS
    require(dns._group_has_us_semantics(us, groups, frozenset(allowed)), "AI 必须绑定实际具有美国节点过滤条件的组。")
    require(ai_position == 0, "AI 美国入口必须是第一条有效规则，防止 Google IP 或设备广谱规则抢先覆盖。")
    fixed_positions = {}
    for position, (_, parts) in enumerate(rules):
        if len(parts) < 3 or parts[0] != "RULE-SET":
            continue
        identifier = parts[1].removeprefix(BASE + "surge/rules/").removesuffix(".list") if surge else PROVIDER_IDS.get(parts[1], "")
        if identifier not in REGIONAL:
            continue
        fixed_positions[identifier] = position
        require(dns._group_has_us_semantics(parts[2], groups, region_filters(REGIONAL[identifier], surge)), f"{identifier} 必须保留已登记地区出口。")
        if identifier.startswith("region/"):
            require(position < selected["google"][0][0], "地区必需入口必须早于 Google 完整 IP 地址空间。")
    require(all(key in fixed_positions for key in ("region/tw/crypto_tw", "region/jp/domains_to_jp", "region/hk/hk_brokers")), "缺少 Crypto 台湾、日本明确入口或香港券商专项规则。")
    for key in ("douyin", "social", "ips5"):
        position, parts = selected[key][0]
        require(parts[2] == "DIRECT", f"{key} 必须直连。")
        require(ai_position < position < selected["google"][0][0], f"{key} 必须在 AI 之后、Google 广谱规则之前。")
    # 停用只撤销配置调用和专用注册；保留源规则与产物，以便明确授权后恢复。
    require(not any("adspower" in line.lower() for line in lines if line.strip() and not line.lstrip().startswith(("#", ";", "//"))), "AdsPower 已停用，配置不得保留调用、观察兜底或专用 provider / DNS 入口。")
    for position, (_, parts) in enumerate(rules):
        if not parts:
            continue
        policy_index = -2 if parts[-1] in {"no-resolve", "dns-failed"} else -1
        target = parts[policy_index]
        is_ai = position == ai_position
        is_ai_dns = surge and parts[:2] == ["RULE-SET", AI_DNS_RULE]
        if target in groups:
            if position not in fixed_positions.values():
                require(target == (us if is_ai or is_ai_dns else auto), "无明确地区要求的代理规则仍绑定地区或手动组。")
        else:
            require(target in {"DIRECT", "REJECT", "REJECT-DROP", "REJECT-TINYGIF"}, "规则引用未知策略。")
        if "REJECT" in target:
            require(position > selected["social"][0][0], "国内精选直连必须早于拒绝规则。")
            require(position > selected["ips5"][0][0], "ips5 直连必须早于拒绝规则。")
    finals = [parts for _, parts in rules if parts[0] in {"FINAL", "MATCH"}]
    require(len(finals) == 1 and finals[0][1] == ("REJECT" if work else "DIRECT"), "最终兜底必须为 DIRECT，工作白名单必须保持 REJECT。")
    if work:
        require(not any(any(token in str(parts) for token in ('cn_direct', 'gfw', 'direct_cn', 'proxy_gfw')) for _, parts in rules), "工作白名单不得增加中国通用或广谱代理入口。")
    else:
        tail = [parts for _, parts in rules][-3:]
        expected = [BASE + 'surge/rules/direct/cn_direct_light.list', BASE + 'surge/rules/proxy/gfw_precise.list'] if surge else ['direct_cn', 'proxy_gfw']
        require(len(tail) == 3 and all(tail[i][:2] == ['RULE-SET', expected[i]] for i in range(2)) and tail[0][2] == 'DIRECT' and tail[1][2] == auto, '精简直连表、精确代理表、DIRECT 兜底必须相邻且位于末尾。')
        if not surge:
            for key, file in zip(expected, ('direct/cn_direct_light', 'proxy/gfw_precise')):
                require(key in providers and providers[key][1] == BASE + 'mihomo/classical/' + file + '.yaml', '精简兜底 provider 必须引用配套产物。')
    require(not any("aws_ipv4" in line or "chain_socks5_ipcidr" in line for line in lines if not line.lstrip().startswith("#")), "配置应停用 AWS IP 与链式代理入口，源规则仍保留。")
    require(any(GEOIP_URL in line for line in lines if not line.lstrip().startswith("#")), "GeoIP 必须直接使用 MetaCubeX 持续更新的上游。")
    require(not any("vtgpcmsvgs/rulemesh/releases/download/" in line for line in lines if not line.lstrip().startswith("#")), "配置不得重新依赖本仓库 Release 镜像。")

    if surge:
        global_group = groups[auto]
        require(global_group.filter_text == METADATA_FILTER, "全地区 smart 组只过滤套餐占位项，不再限定地区标签。")
        settings = {}
        for _, line in dns._active_surge_section(lines, "General"):
            if "=" in line:
                key, value = line.split("=", 1)
                settings[key.strip()] = value.strip()
        require(settings.get("dns-server") == "223.5.5.5, 119.29.29.29", "Surge 普通 DNS 应使用国内双端点。")
        require(settings.get("encrypted-dns-server") == ", ".join(DOMESTIC), "Surge 默认 DoH 应使用国内双端点。")
        require(settings.get("use-local-host-item-for-proxy") == "false", "Surge 应保留代理侧域名解析。")
        require(settings.get("encrypted-dns-follow-outbound-mode") == "true", "Surge AI DoH 必须遵守出站规则。")
        require(settings.get("hijack-dns") == "*:53", "Surge 必须接管传统 DNS。")
        require("dns-mode" not in settings and "proxy-server-nameserver" not in settings, "Surge 不得混入 Mihomo DNS 字段。")
        host = [line for _, line in dns._active_surge_section(lines, "Host")]
        ai_host = f"RULE-SET:{BASE}surge/rules/region/us/ai_us.list = server:{OVERSEAS[0]}"
        require(bool(host) and host[0] == ai_host, "Surge Host 第一项必须为 AI 专用海外 DoH。")
        ai_dns_positions = [pos for pos, (_, parts) in enumerate(rules) if parts[:3] == ["RULE-SET", AI_DNS_RULE, us]]
        require(len(ai_dns_positions) == 1, "Surge AI DoH 缺少唯一规则集美国出站。")
        if len(ai_dns_positions) == 1:
            require(all(ai_dns_positions[0] < pos for pos, (_, parts) in enumerate(rules) if parts[0] in {"SRC-IP", "PROTOCOL", "FINAL"}), "AI DNS 美国出口必须早于设备、协议和最终兜底。")
        for endpoint in ("dns.alidns.com", "doh.pub"):
            require(any(parts[:3] == ["DOMAIN", endpoint, "DIRECT"] for _, parts in rules), "国内 DoH 端点必须显式直连。")
        node_entries = [line for line in host if "proxy-node-domains" in line]
        require(len(node_entries) == 1 and "DOMAIN-SET:" in node_entries[0] and "/api/file/" not in node_entries[0], "节点 bootstrap 必须使用唯一可分享的 DOMAIN-SET 入口。")
        require(not any("cn_performance_dns_domains" in line for line in host), "默认国内 DNS 后不应重复加载性能型 DNS 清单。")
    else:
        require(not groups[auto].filter_text, "全地区 url-test 组不得限定地区标签。")
        require("tcp-concurrent: true" in lines and "ipv6: false" in lines, "Mihomo 必须开启 TCP 并发并保留 IPv4 基线。")
        require("find-process-mode: strict" in lines, "FlClash 必须按需识别进程，避免 always 开销或 off 使进程规则失效。")
        values, policies = dns._parse_mihomo_dns(lines)
        require(values == DOMESTIC, "Mihomo 默认业务 DNS 应为国内双 DoH。")
        require(len(policies) == 1 and policies[0].providers == ("us_ai",), "Mihomo 仅保留 AI 专用 DNS policy。")
        expected = tuple(f"{endpoint}#{us}" for endpoint in OVERSEAS)
        require(len(policies) == 1 and policies[0].nameservers == expected, "AI 的两个海外 DoH 必须显式指定实际美国组。")
        block = []
        active = False
        for line in lines:
            if re.match(r"^[\w-]+:", line):
                active = line == "dns:"
            if active:
                block.append(line)
        for key in ("ipv6", "use-hosts", "use-system-hosts", "respect-rules"):
            require(f"  {key}: false" in block, f"Mihomo dns.{key} 必须为 false。")
        require("  cache-algorithm: arc" in block and "  enhanced-mode: fake-ip" in block, "Mihomo 必须保留 ARC 缓存和 fake-ip。")
        require(not any(re.match(r"^  (fallback|direct-nameserver|proxy-server-nameserver-policy):", line) for line in block), "Mihomo 不得重新叠加 fallback 或二级 DNS policy。")
        node_dns = []
        active = False
        for line in block:
            if re.match(r"^  [\w-]+:", line):
                active = line == "  proxy-server-nameserver:"
            elif active and line.startswith("    - "):
                node_dns.append(line[6:].strip().strip('"'))
        require(tuple(node_dns) == DOMESTIC, "指定代理的 AI DoH 必须配套独立国内节点 bootstrap，避免解析循环。")
        require(not any(name in {"cn-dns-domains", "cn-performance-dns-domains"} for name in providers), "Mihomo 不应重复加载 DNS 专用域名清单。")
        health, parsed_groups, _ = performance.parse_mihomo(lines)
        health_interval = '600' if 'flclash-android' in path.name else '300'
        require(bool(health) and all(item.interval == health_interval and item.lazy == "false" for item in health), "机场健康检查应为桌面 300 秒、安卓 600 秒主动检测。")
        for name, group in parsed_groups.items():
            if group.group_type == "url-test":
                used = any(name in parts[2:3] for _, parts in rules)
                require(group.interval == health_interval and group.lazy == ('false' if used else 'true'), "自动组须采用客户端检测周期，实际业务组主动检测，备用地区组按需检测。")
                require(group.tolerance == ("100" if name == us else "50") if name in {us, auto} else True, "全地区/美国组切换容差应为 50/100。")
        # 只检查字段和值，不在错误中输出机场标识、订阅地址或 header。
        active = False
        provider_count = direct_count = 0
        for line in lines:
            if re.match(r"^[\w-]+:", line):
                active = line == "proxy-providers:"
            if active:
                provider_count += bool(re.match(r"^  [^\s#][^:]*:\s*$", line))
                direct_count += bool(re.fullmatch(r"    proxy:\s*[\"']?DIRECT[\"']?", line))
        require(provider_count > 0 and provider_count == direct_count, "所有机场 provider 的下载出站必须为 DIRECT。")
        require(not any("http://www.google.com/generate_204" in line for line in lines if not line.lstrip().startswith("#")), "Mihomo 测速必须使用 HTTPS。")
    return list(dict.fromkeys(errors))
