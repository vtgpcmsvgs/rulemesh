"""校验业务选择层、默认引擎和前置专项；只输出公共业务名与字段。"""
from pathlib import Path
import re

MARKER = "# RuleMesh 业务策略组：2026-09-25"
SERVICES = ("Google", "YouTube", "AI", "Telegram", "Crypto", "Microsoft", "Apple", "香港券商")
FIXED = {"AI": "us", "Crypto": "tw", "Microsoft": "us", "香港券商": "hk"}
REGIONS = {"🇭🇰 香港-自动选择": "hk", "🇨🇳 台湾-自动选择": "tw",
           "🇯🇵 日本-自动选择": "jp", "🇰🇷 韩国-自动选择": "kr",
           "🇸🇬 新加坡-自动选择": "sg", "🇺🇸 美国-自动选择": "us"}
ROUTES = {
    "region/hk/hk_securities": "香港券商",
    "region/us/ai_us": "AI", "region/us/ai_dns_us": "AI",
    "region/hk/google_hk": "Google", "proxy/youtube": "YouTube",
    "region/hk/telegram": "Telegram", "region/tw/crypto_tw": "Crypto",
    "proxy/polygon_rpc_proxy": "Crypto", "proxy/bsc_rpc_proxy": "Crypto",
    "region/us/microsoft_us": "Microsoft", "direct/apple_direct": "Apple",
    "region/us/macos_update_us": "Apple",
}
IDS = {
    "hk_securities": "region/hk/hk_securities",
    "us_ai": "region/us/ai_us", "hk_google": "region/hk/google_hk", "proxy_youtube": "proxy/youtube",
    "hk_telegram": "region/hk/telegram", "tw_crypto": "region/tw/crypto_tw",
    "proxy_polygon_rpc": "proxy/polygon_rpc_proxy", "proxy_bsc_rpc": "proxy/bsc_rpc_proxy",
    "us_microsoft": "region/us/microsoft_us", "direct_apple": "direct/apple_direct",
    "us_macos_update": "region/us/macos_update_us",
}


def default_chain(name, groups):
    """只遍历 select 的首项默认值；自动组是终点，环和空组不能当作有效默认值。"""
    chain = []
    while name in groups and groups[name].group_type == "select":
        if groups[name].has_external_source and not groups[name].members:
            return tuple(chain + [name])
        if name in chain or not groups[name].members:
            return ()
        chain.append(name)
        name = groups[name].members[0]
    return tuple(chain + [name])


def default_target(name, groups):
    chain = default_chain(name, groups)
    return chain[-1] if chain else ""


def identifier(parts, surge):
    from check_performance_baseline import BASE
    if len(parts) < 3 or parts[0] != "RULE-SET":
        return ""
    return parts[1].removeprefix(BASE + "surge/rules/").removesuffix(".list") if surge else IDS.get(parts[1], "")


def expected_service(parts, surge):
    return ROUTES.get(identifier(parts, surge))


def check(path: Path, lines, groups, rules, auto):
    import check_private_dns_precedence as parser
    import check_performance_baseline as baseline
    surge = path.suffix == ".conf"
    work = "work-whitelist" in path.name
    errors = []

    def require(ok, message):
        if not ok:
            errors.append(message)

    def source(group):
        match = re.search(r'(?:^|,)\s*policy-path=([^,]+)', lines[group.line-1])
        return parser._scalar(match.group(1)) if match else ""

    def group_block(group):
        end = next((i for i in range(group.line, len(lines)) if lines[i].startswith("  - name:") or re.match(r'^[\w-]+:', lines[i])), len(lines))
        return lines[group.line:end]

    def hidden(name):
        group = groups[name]
        if surge:
            return bool(re.search(r'(?:^|,)\s*hidden=1(?:,|$)', lines[group.line-1]))
        return "    hidden: true" in group_block(group)

    expected_sources = ({source(g) for n, g in groups.items() if g.group_type == "select" and g.has_external_source and (n.startswith("✈️ ") or n.startswith("机场 "))}
                        if surge else set(parser._parse_mihomo_proxy_provider_names(lines)))
    require(bool(expected_sources), "缺少已登记的机场订阅来源。")
    definitions = ([parser._scalar(line.split("=", 1)[0]) for _, line in parser._active_surge_section(lines, "Proxy Group") if "=" in line]
                   if surge else [parser._scalar(line.split(":", 1)[1]) for line in lines if line.startswith("  - name:")])
    require(len(definitions) == len(set(definitions)), "策略组定义必须唯一，不能覆盖同名 provider 子组。")
    require(lines.count(MARKER) == 1, "业务策略组标记必须唯一。")
    for name in SERVICES:
        group = groups.get(name)
        require(group is not None and group.group_type == "select", f"{name} 必须是可见的业务 select 组。")
        if group is None:
            continue
        pattern = r'^' + re.escape(name) + r'\s*=' if surge else r'^  - name:\s*[\"\']?' + name + r'[\"\']?\s*$'
        require(sum(bool(re.match(pattern, line)) for line in lines) == 1, f"{name} 组定义必须唯一。")
        if surge:
            require(bool(re.search(r'(?:^|,)\s*hidden=0(?:,|$)', lines[group.line-1])), f"{name} 必须显式可见。")
        else:
            end = next((i for i in range(group.line, len(lines)) if lines[i].startswith("  - name:") or re.match(r'^[\w-]+:', lines[i])), len(lines))
            block = lines[group.line:end]
            require("    hidden: false" in block, f"{name} 必须显式可见。")
            require(not any(re.match(r'^    (url|interval|lazy|tolerance):', s) for s in block), f"{name} 选择层不得重复建立测速任务。")
        require((bool(group.members) or group.has_external_source) and all(m in groups or m == "DIRECT" for m in group.members), f"{name} 存在空候选或未知组引用。")
        require(bool(default_chain(name, groups)), f"{name} 默认选择链存在环或空组。")
        require(not group.has_external_source and not group.filter_text, f"{name} 选择层应复用子组，不得直接混入节点。")
        if name in FIXED:
            approved = baseline.region_filters(FIXED[name], surge)
            require(parser._group_has_us_semantics(name, groups, approved), f"{name} 所有候选必须满足地区约束。")
            sources = []
            for child in group.members:
                leaf = groups.get(child)
                require(leaf is not None and leaf.group_type == ("smart" if surge else "url-test"), f"{name} 必须按 provider 自动测速选择。")
                if leaf is None:
                    continue
                require(not leaf.members and leaf.has_external_source and not leaf.has_invalid_external_source, f"{name} 子组必须只使用一个有效订阅来源。")
                require(leaf.filter_text in approved, f"{name} 子组必须保留限定地区过滤器。")
                require(hidden(child), f"{name} 子组必须隐藏，避免重复展示。")
                if surge:
                    sources.append(source(leaf))
                    require('include-all-proxies=0' in lines[leaf.line-1], f"{name} 子组不得混入其他订阅节点。")
                    require('include-other-group=' not in lines[leaf.line-1], f"{name} 子组不得混入其他订阅节点。")
                else:
                    require(len(leaf.source_references) == 1, f"{name} 子组只能绑定一个 provider。")
                    require(not any(re.fullmatch(r'      -\s+\d+\s*', line) for line in group_block(leaf)), f"{name} 数字 provider 引用必须加引号，避免 YAML 解码为数字。")
                    require(not any(re.match(r'^    include-all(?:-providers|-proxies)?:', line) for line in group_block(leaf)), f"{name} 子组不得聚合全部机场。")
                    require(any(line.startswith('    exclude-filter:') for line in group_block(leaf)), f"{name} 子组必须排除套餐占位项。")
                    sources.extend(leaf.source_references)
            require(len(sources) == len(expected_sources) and set(sources) == expected_sources, f"{name} 必须逐一覆盖全部 provider，不能重复或遗漏。")
        else:
            candidates = list(REGIONS) + (["DIRECT"] if name == "Apple" else [])
            require(len(group.members) == len(candidates) and set(group.members) == set(candidates), f"{name} 必须完整展示六个地区自动组。")

    for name, region in REGIONS.items():
        group = groups.get(name)
        require(group is not None and group.group_type == ("smart" if surge else "url-test"), "缺少地区自动测速组。")
        if group:
            require(hidden(name), "地区自动组必须隐藏。")
            require(not group.members and group.has_external_source and not group.has_invalid_external_source and group.filter_text in baseline.region_filters(region, surge), "地区自动组必须保留正确地区过滤器和订阅来源。")
            if not surge:
                require(set(group.source_references) == expected_sources, "地区自动组必须覆盖全部 provider。")
    require(not any("Google" in name and "稳定" in name for name in groups), "不得恢复独立 Google 下载稳定组。")

    # 检查全部候选边，不能只检查首项，避免手动切换后出现环。
    def acyclic(name, seen):
        if name in seen:
            return False
        group = groups.get(name)
        return group is None or all(acyclic(m, seen | {name}) for m in group.members if m in groups)

    require(all(acyclic(s, set()) for s in SERVICES), "业务策略组的候选引用存在循环。")
    for name in ("Google", "YouTube", "Telegram"):
        require(default_target(name, groups) == next(iter(REGIONS)), f"{name} 默认必须使用香港自动组。")
    require(default_target("Apple", groups) == "DIRECT", "Apple 默认直连，保留六地区手动选项。")
    positions = {}
    for pos, (_, parts) in enumerate(rules):
        ident = identifier(parts, surge)
        expected = ROUTES.get(ident)
        if expected:
            positions.setdefault(ident, []).append(pos)
            require(parts[2] == expected, f"{expected} 规则必须接入对应可见业务组。")
    for ident in ROUTES:
        if (not surge and ident == "region/us/ai_dns_us") or (work and ident == "direct/apple_direct"):
            continue
        require(len(positions.get(ident, [])) == 1, f"业务入口 {ident} 必须唯一存在。")
    if positions.get("proxy/youtube") and positions.get("region/hk/google_hk"):
        require(positions["proxy/youtube"][0] < positions["region/hk/google_hk"][0], "YouTube 必须早于 Google 广谱入口。")
    if work:
        require("direct/apple_direct" not in positions, "工作白名单不得引入 Personal 的 Apple 全域放行。")
    elif not surge:
        # 两份 FlClash 的既有更新拒绝不能被新增 Apple 入口绕过；公开模板沿用已有前置 Apple。
        if path.name.startswith("rulemesh-substore-"):
            reject = [i for i, (_, p) in enumerate(rules) if p[:2] == ["RULE-SET", "reject_os_update"]]
            require(bool(reject) and bool(positions.get("direct/apple_direct")) and reject[0] < positions["direct/apple_direct"][0], "FlClash 的更新拒绝必须早于 Apple 业务入口。")
    if not surge:
        require(not any(re.match(r"^\s+-\s+(['\"])(['\"]).+\2\1\s*$", line) for line in lines), "Mihomo provider 引用不得嵌套两层 YAML 引号。")
        providers = parser._parse_mihomo_providers(lines)
        require(not ({"hk_brokers", "hk_securities_aggressive", "android_brokers_aggressive"} & providers.keys()), "券商统一入口不得残留旧 provider 注册。")
        for name, ident in (("proxy_youtube", "proxy/youtube"), ("direct_apple", "direct/apple_direct"), ("hk_securities", "region/hk/hk_securities")):
            require(name in providers and providers[name][1] == baseline.BASE + "mihomo/classical/" + ident + ".yaml", f"{name} 必须引用配套公开产物。")
    retired = ("region/hk/hk_brokers", "region/hk/hk_securities_aggressive", "region/hk/android_brokers_aggressive")
    require(not any(p[0] == "RULE-SET" and (p[1].removeprefix(baseline.BASE + "surge/rules/").removesuffix(".list") in retired if surge else p[1] in {"hk_brokers", "hk_securities_aggressive", "android_brokers_aggressive"}) for _, p in rules if len(p) >= 3), "券商统一入口不得重复调用旧规则集。")
    return errors
