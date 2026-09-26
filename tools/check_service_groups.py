"""校验业务选择层、默认引擎和前置专项；只输出公共业务名与字段。"""
from pathlib import Path
import re

MARKER = "# RuleMesh 业务策略组：2026-09-25"
SERVICES = ("Google", "YouTube", "AI", "Telegram", "Crypto", "Microsoft", "Apple")
NODE_FILTERS = {
    "Google": ("hk", "香港节点"), "YouTube": ("hk", "香港节点"),
    "Telegram": ("hk", "香港节点"), "Microsoft": ("us", "美国节点"),
}
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
    import check_android_stability as android_rules
    surge = path.suffix == ".conf"
    # 2026-09-26 业务选择层：业务组展示地区自动选择，AI/Crypto/Microsoft/香港券商按 provider 分组。
    # 保留旧解析器供历史夹具使用，但生产配置统一走以下结构检查。
    if MARKER in lines:
        errors = []
        visible = {"Google", "YouTube", "AI", "Telegram", "Crypto", "Microsoft", "Apple", "香港券商"}
        for name in visible:
            group = groups.get(name)
            if group is None or group.group_type != "select":
                errors.append(f"{name} 必须是可见的 select 组。")
        region = {"🇭🇰 香港-自动选择", "🇨🇳 台湾-自动选择", "🇯🇵 日本-自动选择", "🇰🇷 韩国-自动选择", "🇸🇬 新加坡-自动选择", "🇺🇸 美国-自动选择"}
        for name in region:
            if name not in groups:
                errors.append(f"缺少地区自动组：{name}。")
        for name in ("Google", "YouTube", "Telegram"):
            if name in groups and not set(groups[name].members).issubset(region):
                errors.append(f"{name} 必须只展示六个地区自动组。")
        if "Apple" in groups and not set(groups["Apple"].members).issubset(region | {"DIRECT"}):
            errors.append("Apple 必须只展示六个地区自动组和 DIRECT。")
        for name, prefix in (("AI", "AI-"), ("Crypto", "Crypto-"), ("Microsoft", "Microsoft-"), ("香港券商", "香港券商-")):
            if name in groups and not groups[name].members:
                errors.append(f"{name} 必须引用 provider 分组。")
            # Mihomo 兼容模板仍可保留既有地区自动组；新私有 Surge 入口使用 provider 子组。
            if name in groups and any(m == "DIRECT" and name != "Microsoft" for m in groups[name].members):
                errors.append(f"{name} 不得把 DIRECT 作为候选。")
        # 业务入口必须绑定对应策略组；香港券商统一使用 hk_securities 规则集。
        for _, parts in rules:
            if len(parts) < 3:
                continue
            ident = identifier(parts, surge)
            target = parts[2]
            expected = ROUTES.get(ident)
            if ident == "region/hk/hk_securities" or ident == "hk_securities":
                if target != "香港券商": errors.append("香港券商规则集必须绑定香港券商组。")
            elif expected and target != expected:
                errors.append(f"{expected} 规则必须绑定 {expected} 组。")
        return list(dict.fromkeys(errors))
    work = "work-whitelist" in path.name
    # 与既有检查使用同一能力标记；测试中的通用文件名只选择检测周期，不暗示下载结构。
    android = android_rules.active(path, lines)
    errors = []

    def require(ok, message):
        if not ok:
            errors.append(message)

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
        if name in NODE_FILTERS:
            region, label = NODE_FILTERS[name]
            approved = baseline.region_filters(region, surge)
            require(group.has_external_source, f"{name} 必须直接展示{label}。")
            require(group.filter_text in approved, f"{name} 必须只保留{label}过滤器。")
            if region == "hk":
                require(not group.members, f"{name} 不得混入自动组、其他地区或 DIRECT。")
            else:
                require(group.members == ["DIRECT"], f"{name} 只能额外保留 DIRECT。")
            if not surge:
                require(set(group.source_references) == set(parser._parse_mihomo_proxy_provider_names(lines)), f"{name} 必须展示全部机场 provider 的{label}节点。")
        elif name not in {"AI", "Crypto"}:
            require(not group.has_external_source, f"{name} 应复用底层引擎和手动组，不复制订阅列表。")
        else:
            approved = baseline.region_filters("tw", surge) if name == "Crypto" else (parser.APPROVED_SURGE_US_FILTERS | {baseline.PUBLIC_US_FILTER} if surge else parser.APPROVED_MIHOMO_US_FILTERS)
            require(parser._group_has_us_semantics(name, groups, frozenset(approved)), f"{name} 所有可选出口必须满足美国或台湾地区约束。")
            require(group.has_external_source, f"{name} 必须提供限定地区的手动节点选择。")
            require(group.filter_text in approved, f"{name} 手动节点必须保留审核后的地区过滤器。")
            if not surge:
                require(set(group.source_references) == set(parser._parse_mihomo_proxy_provider_names(lines)), f"{name} 手动候选缺少机场来源。")

    # 检查全部候选边，不能只检查首项，避免手动切换后出现环。
    def acyclic(name, seen):
        if name in seen:
            return False
        group = groups.get(name)
        return group is None or all(acyclic(m, seen | {name}) for m in group.members if m in groups)

    require(all(acyclic(s, set()) for s in SERVICES), "业务策略组的候选引用存在循环。")
    for name in NODE_FILTERS:
        allowed_default = {"Microsoft", "DIRECT"} if name == "Microsoft" else {name}
        require(default_target(name, groups) in allowed_default, f"{name} 默认入口必须停留在限定地区节点列表。")
    google = default_target("Google", groups)
    require(google == "Google", "Google 默认必须停留在香港节点选择层。")
    require(default_target("YouTube", groups) == "YouTube", "YouTube 默认必须停留在香港节点选择层。")
    require(default_target("Apple", groups) == (auto if work else "DIRECT"), "Apple 默认直连；工作只沿用已有更新白名单的自动出口。")
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
        for name, ident in (("proxy_youtube", "proxy/youtube"), ("direct_apple", "direct/apple_direct")):
            require(name in providers and providers[name][1] == baseline.BASE + "mihomo/classical/" + ident + ".yaml", f"{name} 必须引用配套公开产物。")
    return errors

