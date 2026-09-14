"""安卓 Google 下载保护；诊断只包含公开字段，不输出私人策略或订阅值。"""
from pathlib import Path
import re

MARKER = "# RuleMesh 安卓下载保护：2026-09-14"
PROFILE = "rulemesh-substore-mihomo-flclash-android.yaml"
PACKAGES = (
    "com.android.vending",
    "com.google.android.gms",
    "com.google.android.gsf",
    "com.android.providers.downloads",
    "com.android.providers.downloads.ui",
)


def active(path: Path, lines: list[str]) -> bool:
    return path.name == PROFILE or MARKER in lines


def quic_rules() -> list[str]:
    # 使用明确 REJECT，不能用静默 DROP 等待超时，也不能关闭全部 UDP。
    matchers = ["RULE-SET,hk_google", *(f"PROCESS-NAME,{p}" for p in PACKAGES)]
    return [f"AND,((NETWORK,udp),(DST-PORT,443),({m})),REJECT" for m in matchers]


def stable_target(lines: list[str]) -> str:
    import check_private_dns_precedence as parser
    targets = [parts[2] for _, parts in parser._parse_mihomo_rules(lines)
               if len(parts) == 3 and parts[:2] == ["RULE-SET", "hk_google"]]
    return targets[0] if len(targets) == 1 else ""


def allowed_stable_rule(parts: list[str]) -> bool:
    return (parts[:2] == ["RULE-SET", "hk_google"] or
            len(parts) == 3 and parts[0] == "PROCESS-NAME" and parts[1] in PACKAGES)


def check(path: Path, lines: list[str]) -> list[str]:
    import check_private_dns_precedence as parser
    import check_private_performance as performance
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
    require(stable is not None and stable.group_type == "fallback", "安卓 Google 必须使用稳定优先的 fallback 组。")
    if stable:
        require(not stable.filter_text and not stable.members, "Google 稳定组应直接使用机场节点，不嵌套测速组或加入 DIRECT。")
        require(stable.has_external_source and not stable.has_invalid_external_source and set(stable.source_references) == set(parser._parse_mihomo_proxy_provider_names(lines)), "Google 稳定组必须保留全部当前机场来源。")
        start = stable.line
        end = next((i for i in range(start, len(lines)) if lines[i].startswith("  - name:") or re.match(r"^[\w-]+:", lines[i])), len(lines))
        block = lines[start:end]
        require(any(re.fullmatch(r'    url:\s*[\"\']?https://www\.google\.com/generate_204[\"\']?', s) for s in block), "Google 稳定组必须使用 HTTPS 连通性检查。")
        require(not any(re.match(r"    disable-udp:\s*true", s) for s in block), "Google 不能用 disable-udp 替代前置拒绝，否则可能跳过代理规则。")
    health = health_groups.get(target)
    require(health is not None and health.interval == "600" and health.lazy == "false", "Google 稳定组必须每 600 秒主动检查。")
    rules = [parts for _, parts in parser._parse_mihomo_rules(lines)]
    codes = [",".join(parts) for parts in rules]
    google = next((i for i, p in enumerate(rules) if p[:2] == ["RULE-SET", "hk_google"]), -1)
    reject = next((i for i, p in enumerate(rules) if p[:2] == ["RULE-SET", "reject_adblock"]), len(rules))
    required = quic_rules()
    for rule in required:
        require(codes.count(rule) == 1 and 0 < codes.index(rule) < google if rule in codes else False,
                "Google 域名与下载进程的 UDP/443 必须在 Google 放行前明确 REJECT。")
    for package in PACKAGES:
        rule = f"PROCESS-NAME,{package},{target}"
        require(codes.count(rule) == 1 and google < codes.index(rule) < reject if rule in codes else False,
                "Google Play、服务框架与系统下载管理器必须在广告拒绝前使用同一稳定组。")
    require(not any(p[:2] == ["NETWORK", "udp"] and p[-1].startswith("REJECT") for p in rules), "不得用全局 UDP 拒绝代替 Google 定向保护。")
    _, policies = parser._parse_mihomo_dns(lines)
    require(len(policies) == 2 and policies[0].providers == ("us_ai",) and policies[1].providers == ("hk_google",),
            "安卓 DNS 必须先 AI、后 Google，仅允许这两个专项 policy。")
    if len(policies) == 2:
        expected = tuple(f"{endpoint}#{target}" for endpoint in ("https://cloudflare-dns.com/dns-query", "https://dns.google/dns-query"))
        require(policies[1].nameservers == expected, "Google 海外 DoH 必须与 Google 下载使用同一稳定组。")
    require(not any(re.fullmatch(r'\s*-\s*[\"\']?(android\.clients\.google\.com|clients4\.google\.com)[\"\']?\s*', s) for s in lines),
            "Play API 不能被误当作联网探测主机加入 fake-ip-filter。")
    return list(dict.fromkeys(errors))
