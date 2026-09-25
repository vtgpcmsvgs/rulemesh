"""安卓 Google 下载与日常直连保护；兼容历史组件夹具，不输出私人值。"""
from pathlib import Path
import re

MARKER = "# RuleMesh 安卓下载保护：2026-09-14"
PROFILE = "rulemesh-substore-mihomo-flclash-android.yaml"
ALIPAY_MARKER = "# RuleMesh 安卓支付宝组件保护：2026-09-16"
ALIPAY_PACKAGE = "com.eg.android.AlipayGphone"
ALIPAY_COMPONENT_HOSTS = (
    "gw.alipayobjects.com",
    "mdn.alipayobjects.com",
    "mdn-js.alipayobjects.com",
)
PACKAGES = (
    "com.android.vending",
    "com.google.android.gms",
    "com.google.android.gsf",
    "com.android.providers.downloads",
    "com.android.providers.downloads.ui",
)


def active(path: Path, lines: list[str]) -> bool:
    return path.name == PROFILE or MARKER in lines or any(line.strip() == ALIPAY_MARKER for line in lines)


def alipay_component_rules() -> list[str]:
    return [f"AND,((PROCESS-NAME,{ALIPAY_PACKAGE}),(DOMAIN,{host})),DIRECT"
            for host in ALIPAY_COMPONENT_HOSTS]


def retired_quic_rules() -> list[str]:
    # 实机 Cronet 未可靠回退，旧定向拒绝会引发网络错误；仅用于检测回归。
    matchers = ["RULE-SET,hk_google", *(f"PROCESS-NAME,{p}" for p in PACKAGES)]
    return [f"AND,((NETWORK,udp),(DST-PORT,443),({m})),REJECT" for m in matchers]


def stable_target(lines: list[str]) -> str:
    import check_private_dns_precedence as parser
    import check_service_groups as service
    targets = [parts[2] for _, parts in parser._parse_mihomo_rules(lines)
               if len(parts) == 3 and parts[:2] == ["RULE-SET", "hk_google"]]
    target = targets[0] if len(targets) == 1 else ""
    return service.default_target(target, parser._parse_mihomo_groups(lines)) if service.MARKER in lines else target


def allowed_stable_rule(parts: list[str]) -> bool:
    return (parts[:2] == ["RULE-SET", "hk_google"] or
            len(parts) == 3 and parts[0] == "PROCESS-NAME" and parts[1] in PACKAGES)


def check(path: Path, lines: list[str]) -> list[str]:
    import check_private_dns_precedence as parser
    import check_private_performance as performance
    import check_common_routes as common
    import check_service_groups as service
    business = service.MARKER in lines
    daily = common.MARKER in lines
    errors = []

    def require(ok, message):
        if not ok:
            errors.append(message)

    require(path.name == PROFILE, "安卓下载保护不得自动扩散到桌面或 Surge。")
    require(lines.count(MARKER) == 1, "安卓下载保护标记必须唯一保留。")
    require(not any("不得恢复 nameserver-policy" in line or "只保留 default-nameserver、nameserver、fake-ip-filter" in line for line in lines),
            "安卓不得保留会诱发删除已批准 DNS policy 或节点 bootstrap 的旧说明。")
    target = stable_target(lines)
    groups = parser._parse_mihomo_groups(lines)
    _, health_groups, _ = performance.parse_mihomo(lines)
    stable = groups.get(target)
    if business:
        require(stable is not None and stable.group_type == "select", "安卓 Google 必须使用香港节点选择组。")
        if stable:
            require(stable.filter_text and "香港" in stable.filter_text and not stable.members, "安卓 Google 只能展示香港机场节点，不能混入其他地区或 DIRECT。")
            require(stable.has_external_source and not stable.has_invalid_external_source and set(stable.source_references) == set(parser._parse_mihomo_proxy_provider_names(lines)), "安卓 Google 必须保留全部机场来源的香港节点。")
            start = stable.line
            end = next((i for i in range(start, len(lines)) if lines[i].startswith("  - name:") or re.match(r"^[\w-]+:", lines[i])), len(lines))
            block = lines[start:end]
            require(not any(re.match(r"    disable-udp:\s*true", s) for s in block), "Google 香港节点组必须保留 UDP 能力，不能强制 Cronet 回退。")
    else:
        require(stable is not None and stable.group_type == "fallback", "安卓 Google 必须使用稳定优先的 fallback 组。")
        if stable:
            require(not stable.filter_text and not stable.members, "Google 稳定组应直接使用机场节点，不嵌套测速组或加入 DIRECT。")
            require(stable.has_external_source and not stable.has_invalid_external_source and set(stable.source_references) == set(parser._parse_mihomo_proxy_provider_names(lines)), "Google 稳定组必须保留全部当前机场来源。")
            start = stable.line
            end = next((i for i in range(start, len(lines)) if lines[i].startswith("  - name:") or re.match(r"^[\w-]+:", lines[i])), len(lines))
            block = lines[start:end]
            require(any(re.fullmatch(r'    url:\s*[\"\']?https://www\.google\.com/generate_204[\"\']?', s) for s in block), "Google 稳定组必须使用 HTTPS 连通性检查。")
            require(not any(re.match(r"    disable-udp:\s*true", s) for s in block), "Google 稳定组必须保留 UDP 能力，不能强制 Cronet 回退或跳过代理规则。")
        health = health_groups.get(target)
        require(health is not None and health.interval == "600" and health.lazy == "false", "Google 稳定组必须每 600 秒主动检查。")
    rules = [parts for _, parts in parser._parse_mihomo_rules(lines)]
    codes = [",".join(parts) for parts in rules]
    google = next((i for i, p in enumerate(rules) if p[:2] == ["RULE-SET", "hk_google"]), -1)
    reject = next((i for i, p in enumerate(rules) if p[:2] == ["RULE-SET", "reject_adblock"]), len(rules))
    ai = next((i for i, p in enumerate(rules) if p[:2] == ["RULE-SET", "us_ai"]), -1)
    alibaba = next((i for i, p in enumerate(rules) if p[:2] == ["RULE-SET", "hk_alibaba"]), len(rules))
    component_rules = alipay_component_rules()
    if daily:
        errors.extend(common.profile_contract(path, lines))
        require(not any(line.strip() == ALIPAY_MARKER for line in lines), "日常直连已替代支付宝组件补丁，旧标记必须移除。")
    else:
        require(sum(line.strip() == ALIPAY_MARKER for line in lines) == 1,
                "历史安卓支付宝组件保护标记必须唯一保留。")
        for code in component_rules:
            require(codes.count(code) == 1 and ai < codes.index(code) < min(google, reject, alibaba) if code in codes else False,
                    "历史支付宝三个组件域名必须各有一条应用限定的精确 DIRECT，位于 AI 后、Google 广谱与阿里系代理前。")
    for code in codes:
        compact = re.sub(r"\s+", "", code)
        if "alipay" in compact.lower() and compact.endswith(",DIRECT"):
            require(compact in component_rules,
                    "支付宝组件修复不得扩大为整个应用、域名后缀或其他应用的直连。")
        if ALIPAY_PACKAGE in compact:
            require(compact in component_rules,
                    "支付宝组件必须保留 TCP/UDP，不能用协议拒绝或整个应用规则替代精确例外。")
    for code in codes:
        compact = re.sub(r"\s+", "", code).lower()
        rejects_udp = "network,udp" in compact and compact.rsplit(",", 1)[-1].startswith("reject")
        google_scope = "rule-set,hk_google" in compact or any(f"process-name,{p}" in compact for p in PACKAGES)
        global_quic = compact.startswith("and,((network,udp),(dst-port,443)),") or compact.startswith("and,((dst-port,443),(network,udp)),")
        require(not (rejects_udp and (google_scope or global_quic)),
                "不得恢复 Google/Play UDP/443 拒绝：实机 Cronet 会发生协议错误及下载重试。")
    for package in (PACKAGES[:3] if daily else PACKAGES):
        rule = f"PROCESS-NAME,{package},{'Google' if business else target}"
        require(codes.count(rule) == 1 and google < codes.index(rule) < reject if rule in codes else False,
                "Google 专属进程必须在广告拒绝前使用同一稳定组；历史配置另保留旧下载管理器保护。")
    require(not any(p[:2] == ["NETWORK", "udp"] and p[-1].startswith("REJECT") for p in rules), "不得用全局 UDP 拒绝代替 Google 定向保护。")
    _, policies = parser._parse_mihomo_dns(lines)
    expected_ids = [("us_ai",), ("proxy_youtube",), ("hk_google",)] if business else [("us_ai",), ("hk_google",)]
    require([p.providers for p in policies] == expected_ids,
            "安卓 DNS 必须先 AI、再 YouTube 独立业务、最后 Google；仅允许已登记专项 policy。")
    if [p.providers for p in policies] == expected_ids:
        pairs = [(policies[-1], "Google" if business else target)]
        if business:
            pairs.append((policies[1], "YouTube"))
        for policy, outbound in pairs:
            expected = tuple(f"{endpoint}#{outbound}" for endpoint in ("https://cloudflare-dns.com/dns-query", "https://dns.google/dns-query"))
            require(policy.nameservers == expected, "Google / YouTube 海外 DoH 必须跟随对应业务选择；默认仍是下载稳定组。")
    require(not any(re.fullmatch(r'\s*-\s*[\"\']?(android\.clients\.google\.com|clients4\.google\.com)[\"\']?\s*', s) for s in lines),
            "Play API 不能被误当作联网探测主机加入 fake-ip-filter。")
    return list(dict.fromkeys(errors))
