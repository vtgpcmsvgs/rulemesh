from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path


DOMESTIC_DNS_NEEDLES = (
    "223.5.5.5",
    "223.6.6.6",
    "119.29.29.29",
    "119.28.28.28",
    "114.114.114.114",
    "dns.alidns.com",
    "doh.pub",
)
ALLOWED_DOMESTIC_NAMESERVER_POLICY_KEYS = {
    "rule-set:cn-dns-domains",
}

SURGE_CONFIG_NAMES = (
    "surge-public.conf",
    "rulemesh-substore-surge-personal.conf",
    "rulemesh-substore-surge-work-whitelist.conf",
)
MIHOMO_CONFIG_NAMES = (
    "mihomo-public.yaml",
    "rulemesh-substore-mihomo-clash-verge.yaml",
    "rulemesh-substore-mihomo-clash-meta.yaml",
)
MIHOMO_SINGLE_DNS_TRUTH_CONFIG_NAMES = (
    "rulemesh-substore-mihomo-clash-verge.yaml",
    "rulemesh-substore-mihomo-clash-meta.yaml",
)
MIHOMO_SINGLE_DNS_TRUTH_FORBIDDEN_KEYS = {
    "nameserver-policy",
    "proxy-server-nameserver",
    "proxy-server-nameserver-policy",
    "direct-nameserver",
    "fallback",
}
MIHOMO_SINGLE_DNS_TRUTH_HTTP_TEST_URLS = (
    "http://www.google.com/generate_204",
    "http://www.gstatic.com/generate_204",
)


@dataclass(frozen=True)
class DnsSafetyFinding:
    level: str
    path: Path
    line: int
    message: str
    remediation: str


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def is_comment_or_blank(line: str) -> bool:
    stripped = line.strip()
    return not stripped or stripped.startswith("#") or stripped.startswith(";")


def domestic_needles_in(value: str) -> list[str]:
    lowered = value.lower()
    return [needle for needle in DOMESTIC_DNS_NEEDLES if needle in lowered]


def is_mihomo_single_dns_truth_config(path: Path) -> bool:
    return path.name in MIHOMO_SINGLE_DNS_TRUTH_CONFIG_NAMES


def classify_config(path: Path, lines: list[str]) -> str | None:
    name = path.name
    if name in SURGE_CONFIG_NAMES:
        return "surge"
    if name in MIHOMO_CONFIG_NAMES:
        return "mihomo"
    if any(line.strip() == "[General]" for line in lines) and any(
        line.lstrip().startswith("dns-server") for line in lines
    ):
        return "surge"
    if any(line.startswith("dns:") for line in lines) and any(
        line.startswith("proxy-providers:") for line in lines
    ):
        return "mihomo"
    return None


def find_surge_setting(lines: list[str], key: str) -> tuple[int, str] | None:
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=\s*(.+?)\s*$", re.IGNORECASE)
    for index, line in enumerate(lines, start=1):
        if is_comment_or_blank(line):
            continue
        match = pattern.match(line)
        if match:
            return index, match.group(1)
    return None


def get_surge_host_section(lines: list[str]) -> list[tuple[int, str]]:
    in_host = False
    section: list[tuple[int, str]] = []
    for index, line in enumerate(lines, start=1):
        stripped = line.strip()
        if re.fullmatch(r"\[[^\]]+\]", stripped):
            in_host = stripped.lower() == "[host]"
            continue
        if in_host:
            section.append((index, line))
    return section


def validate_surge(path: Path, lines: list[str]) -> list[DnsSafetyFinding]:
    findings: list[DnsSafetyFinding] = []
    dns_server = find_surge_setting(lines, "dns-server")
    encrypted_dns = find_surge_setting(lines, "encrypted-dns-server")
    use_local_host = find_surge_setting(lines, "use-local-host-item-for-proxy")

    if dns_server and encrypted_dns:
        dns_value = dns_server[1].lower()
        encrypted_value = encrypted_dns[1].lower()
        if (
            "system" in dns_value
            and "223.5.5.5" in dns_value
            and "119.29.29.29" in dns_value
            and "dns.alidns.com" in encrypted_value
            and "doh.pub" in encrypted_value
        ):
            findings.append(
                DnsSafetyFinding(
                    "error",
                    path,
                    dns_server[0],
                    "Surge 全局 DNS 命中 system + 国内 DNS 的高风险组合，普通目标网站域名可能泄漏给国内解析方。",
                    "把全局 dns-server / encrypted-dns-server 改为海外 DNS，并把节点 server 域名单独放到 [Host] DOMAIN-SET。",
                )
            )

    for setting_name, setting in (
        ("dns-server", dns_server),
        ("encrypted-dns-server", encrypted_dns),
    ):
        if not setting:
            continue
        needles = domestic_needles_in(setting[1])
        if needles:
            findings.append(
                DnsSafetyFinding(
                    "error",
                    path,
                    setting[0],
                    f"Surge 全局 {setting_name} 包含国内 DNS ({', '.join(needles)})，会让普通目标网站 DNS 指纹偏离代理出口。",
                    "全局 DNS 使用 1.1.1.1 / 8.8.8.8 / 9.9.9.9 与 Cloudflare / Google DoH；国内 DNS 只放在 [Host] 的 proxy-node-domains 例外里。",
                )
            )

    if not use_local_host or use_local_host[1].strip().lower() != "false":
        findings.append(
            DnsSafetyFinding(
                "error",
                path,
                use_local_host[0] if use_local_host else 1,
                "Surge 缺少 use-local-host-item-for-proxy = false，命中代理策略的目标域名可能复用 [Host] 本地解析结果。",
                "在 [General] 中保留 use-local-host-item-for-proxy = false；代理节点 server 域名仍由 [Host] 的 proxy-node-domains 单独 bootstrap。",
            )
        )

    host_section = get_surge_host_section(lines)
    for index, line in host_section:
        lowered = line.lower()
        if (
            not is_comment_or_blank(line)
            and "domain-set:" in lowered
            and "proxy-node-domains" in lowered
            and "/api/file/" in lowered
        ):
            findings.append(
                DnsSafetyFinding(
                    "error",
                    path,
                    index,
                    "Surge [Host] 的 proxy-node-domains 使用 /api/file/ 链接，生产外部资源加载容易超时或返回非纯文本。",
                    "改用 Surge 设备可直接访问的 Sub-Store 分享文件链接，例如 https://<你的 Sub-Store 后端>/share/file/proxy-node-domains。",
                )
            )

    has_proxy_node_domains = any(
        not is_comment_or_blank(line)
        and "domain-set:" in line.lower()
        and "proxy-node-domains" in line.lower()
        for _, line in host_section
    )
    if not has_proxy_node_domains:
        findings.append(
            DnsSafetyFinding(
                "error",
                path,
                host_section[0][0] if host_section else 1,
                "Surge [Host] 没有引用 proxy-node-domains，节点 server 域名无法与普通目标网站 DNS 隔离。",
                "在 [Host] 中加入 DOMAIN-SET:<Sub-Store share/file/proxy-node-domains URL> = server:https://dns.alidns.com/dns-query。",
            )
        )

    dns_mode_pattern = re.compile(r"^\s*dns-mode\s*=", re.IGNORECASE)
    for index, line in enumerate(lines, start=1):
        if not is_comment_or_blank(line) and dns_mode_pattern.search(line):
            findings.append(
                DnsSafetyFinding(
                    "error",
                    path,
                    index,
                    "Surge profile 中出现 dns-mode 字段；这是 Mihomo / Stash 语义，不是 Surge profile 字段。",
                    "移除 dns-mode；Surge 的 Fake IP 由客户端 Enhanced Mode / VIF 运行时提供，profile 只保留 [Host] 节点域名解析隔离。",
                )
            )
        if not is_comment_or_blank(line) and "proxy-server-nameserver" in line:
            findings.append(
                DnsSafetyFinding(
                    "error",
                    path,
                    index,
                    "Surge 配置中出现 Mihomo 的 proxy-server-nameserver 字段，说明 DNS 方案被混用。",
                    "Surge 只能使用 [Host] + DOMAIN-SET 隔离节点 server 域名；不要引入 Mihomo 字段。",
                )
            )

    return findings


def find_dns_block(lines: list[str]) -> list[tuple[int, str]]:
    start = None
    for index, line in enumerate(lines):
        if line.startswith("dns:"):
            start = index
            break
    if start is None:
        return []

    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line and not line.startswith((" ", "\t", "#")) and re.match(r"^[A-Za-z0-9_-]+:", line):
            end = index
            break
    return [(index + 1, lines[index]) for index in range(start, end)]


def validate_mihomo(path: Path, lines: list[str]) -> list[DnsSafetyFinding]:
    findings: list[DnsSafetyFinding] = []
    single_dns_truth = is_mihomo_single_dns_truth_config(path)

    for index, line in enumerate(lines, start=1):
        if is_comment_or_blank(line):
            continue
        stripped = line.strip()
        lowered = stripped.lower()
        if stripped == "[Host]":
            findings.append(
                DnsSafetyFinding(
                    "error",
                    path,
                    index,
                    "Mihomo 配置中出现了 Surge 的 [Host] 段，说明 DNS 方案被混用。",
                    "Mihomo 只能使用自身的 dns: 机制，不要把 Surge 的 [Host] 语法抄进来。",
                )
            )
        if "use-local-host-item-for-proxy" in line:
            findings.append(
                DnsSafetyFinding(
                    "error",
                    path,
                    index,
                    "Mihomo 配置中出现了 Surge 的 use-local-host-item-for-proxy，说明 DNS 方案被混用。",
                    "删除该字段；它只属于 Surge，不属于 Mihomo。",
                )
            )
        if single_dns_truth and re.fullmatch(r"ipv6:\s*true(?:\s+#.*)?", stripped, re.IGNORECASE):
            findings.append(
                DnsSafetyFinding(
                    "error",
                    path,
                    index,
                    "两份 Mihomo 私有 provider 配置的顶层 ipv6 不得恢复为 true，否则会重新引入已知的运行时分流与测速不一致风险。",
                    "把顶层 ipv6 保持为 false；如需重新启用，必须先获得用户明确确认并完成真实运行时复测。",
                )
            )
        if single_dns_truth and any(url in lowered for url in MIHOMO_SINGLE_DNS_TRUTH_HTTP_TEST_URLS):
            findings.append(
                DnsSafetyFinding(
                    "error",
                    path,
                    index,
                    "两份 Mihomo 私有 provider 配置的 provider health-check.url / url-test.url 必须保持 HTTPS generate_204，不能改回 HTTP。",
                    "把测速 URL 统一改回 https://www.google.com/generate_204，并在客户端重载后复测 provider 路径。",
                )
            )

    dns_block = find_dns_block(lines)
    if not dns_block:
        findings.append(
            DnsSafetyFinding(
                "error",
                path,
                1,
                "Mihomo 配置缺少 dns: 段，无法确认普通目标网站 DNS 的解析边界。",
                "显式配置 dns.default-nameserver 与 dns.nameserver；私有 provider 配置还要保持单一 DNS 真相基线。",
            )
        )
        return findings

    current_key = None
    current_nameserver_policy_key = None
    seen_default_nameserver = False
    seen_proxy_server_nameserver = False
    seen_business_nameserver = False
    business_nameserver_has_domestic = False

    for index, line in dns_block:
        if is_comment_or_blank(line):
            continue

        key_match = re.match(r"^  ([A-Za-z0-9_-]+):\s*(.*)$", line)
        if key_match:
            current_key = key_match.group(1)
            current_value = key_match.group(2).split("#", 1)[0].strip().lower()
            current_nameserver_policy_key = None

            if current_key == "default-nameserver":
                seen_default_nameserver = True
            if current_key == "proxy-server-nameserver":
                seen_proxy_server_nameserver = True
            if current_key == "nameserver":
                seen_business_nameserver = True

            if single_dns_truth:
                if current_key in MIHOMO_SINGLE_DNS_TRUTH_FORBIDDEN_KEYS:
                    findings.append(
                        DnsSafetyFinding(
                            "error",
                            path,
                            index,
                            f"两份 Mihomo 私有 provider 配置必须保持“单一 DNS 真相”，不得恢复 dns.{current_key} 这类多层 DNS 字段。",
                            "删除该字段，收敛回 default-nameserver + nameserver + fake-ip-filter 的稳定基线；如确需恢复，必须先获得用户明确确认并完成运行时复测。",
                        )
                    )
                if current_key == "respect-rules" and current_value and current_value != "false":
                    findings.append(
                        DnsSafetyFinding(
                            "error",
                            path,
                            index,
                            "两份 Mihomo 私有 provider 配置的 dns.respect-rules 不得改回 true，否则 DoH / provider 路径会重新分叉。",
                            "把 dns.respect-rules 保持为 false，并在 Mihomo API / 日志里确认运行时配置已经生效。",
                        )
                    )
                if current_key == "ipv6" and current_value == "true":
                    findings.append(
                        DnsSafetyFinding(
                            "error",
                            path,
                            index,
                            "两份 Mihomo 私有 provider 配置的 dns.ipv6 不得恢复为 true，否则会重新引入已知的运行时不一致风险。",
                            "把 dns.ipv6 保持为 false；如需重新启用，必须先获得用户明确确认并完成真实运行时复测。",
                        )
                    )
                if current_key in {"use-hosts", "use-system-hosts"} and current_value == "true":
                    findings.append(
                        DnsSafetyFinding(
                            "error",
                            path,
                            index,
                            f"两份 Mihomo 私有 provider 配置的 dns.{current_key} 不得恢复为 true，避免本地 hosts 再次混入 provider 测速链路。",
                            f"把 dns.{current_key} 保持为 false，优先使用 default-nameserver + nameserver 的单一路径。",
                        )
                    )
            continue

        if current_key == "nameserver-policy":
            policy_key_match = re.match(r"^    [\"']?([^\"']+?)[\"']?:\s*(?:#.*)?$", line)
            if policy_key_match:
                current_nameserver_policy_key = policy_key_match.group(1).strip()
                continue

        needles = domestic_needles_in(line)
        if not needles:
            continue
        if (
            current_key == "nameserver-policy"
            and current_nameserver_policy_key in ALLOWED_DOMESTIC_NAMESERVER_POLICY_KEYS
        ):
            continue
        if current_key in {
            "default-nameserver",
            "proxy-server-nameserver",
            "proxy-server-nameserver-policy",
        }:
            continue

        if current_key == "nameserver":
            business_nameserver_has_domestic = True
        findings.append(
            DnsSafetyFinding(
                "error",
                path,
                index,
                f"Mihomo dns.{current_key or '未知字段'} 包含国内 DNS ({', '.join(needles)})，普通目标网站域名可能被泄漏给国内解析方。",
                "国内 DNS 只能用于 default-nameserver bootstrap、proxy-server-nameserver 节点 bootstrap，或 rule-set:cn-dns-domains 白名单；其他业务 nameserver / nameserver-policy / direct-nameserver 应使用海外 DNS 或移除。",
            )
        )

    if not seen_business_nameserver:
        findings.append(
            DnsSafetyFinding(
                "error",
                path,
                dns_block[0][0],
                "Mihomo dns: 缺少业务 nameserver，无法保证普通目标网站默认走海外 DNS。",
                "配置 dns.nameserver，例如 Cloudflare / Google 等海外 DoH。",
            )
        )

    if single_dns_truth and not seen_default_nameserver:
        findings.append(
            DnsSafetyFinding(
                "error",
                path,
                dns_block[0][0],
                "两份 Mihomo 私有 provider 配置缺少 default-nameserver，无法为 nameserver 自身域名提供稳定 bootstrap。",
                "补回 dns.default-nameserver，并仅在这里保留国内可直连 DNS 作为 bootstrap 例外。",
            )
        )

    if not single_dns_truth and not seen_proxy_server_nameserver:
        findings.append(
            DnsSafetyFinding(
                "error",
                path,
                dns_block[0][0],
                "Mihomo dns: 缺少 proxy-server-nameserver，节点 server 域名解析与普通目标网站 DNS 没有明确隔离。",
                "配置 dns.proxy-server-nameserver 为节点 server 域名专用 DNS，例如阿里云 / 腾讯云 DoH。",
            )
        )

    if not single_dns_truth and business_nameserver_has_domestic and not seen_proxy_server_nameserver:
        findings.append(
            DnsSafetyFinding(
                "error",
                path,
                dns_block[0][0],
                "Mihomo 全局 nameserver 使用国内 DNS 且缺少 proxy-server-nameserver，节点连通性和普通目标解析被混在了一起。",
                "把业务 nameserver 改为海外 DNS，并新增 proxy-server-nameserver 处理节点 server 域名。",
            )
        )

    return findings
def validate_path(path: Path) -> list[DnsSafetyFinding]:
    lines = read_lines(path)
    config_type = classify_config(path, lines)
    if config_type == "surge":
        return validate_surge(path, lines)
    if config_type == "mihomo":
        return validate_mihomo(path, lines)
    return []


def default_paths(repo_root: Path) -> list[Path]:
    paths = [
        repo_root / "docs" / "examples" / "surge-public.conf",
        repo_root / "docs" / "examples" / "mihomo-public.yaml",
    ]

    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        current = Path(user_profile) / "Desktop" / "rulemesh-local" / "current"
        paths.extend(
            [
                current / "rulemesh-substore-surge-personal.conf",
                current / "rulemesh-substore-surge-work-whitelist.conf",
                current / "rulemesh-substore-mihomo-clash-verge.yaml",
                current / "rulemesh-substore-mihomo-clash-meta.yaml",
            ]
        )

    return [path for path in paths if path.exists()]


def format_finding(finding: DnsSafetyFinding, repo_root: Path) -> str:
    try:
        rel_path = finding.path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        rel_path = str(finding.path)
    return (
        f"[{finding.level}] {rel_path}:{finding.line}\n"
        f"  问题: {finding.message}\n"
        f"  修复: {finding.remediation}"
    )


def run(paths: list[Path], repo_root: Path) -> int:
    findings: list[DnsSafetyFinding] = []
    for path in paths:
        findings.extend(validate_path(path))

    if findings:
        for finding in findings:
            print(format_finding(finding, repo_root))
        error_count = sum(1 for finding in findings if finding.level == "error")
        warning_count = sum(1 for finding in findings if finding.level == "warning")
        print(f"DNS safety check failed: {error_count} error(s), {warning_count} warning(s).")
        return 1 if error_count else 0

    print(f"DNS safety check passed: {len(paths)} config file(s) checked.")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检查 Surge / Mihomo DNS 防泄漏边界。")
    parser.add_argument("paths", nargs="*", type=Path, help="可选：指定要检查的配置文件。")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="仓库根目录，用于默认路径和相对路径输出。",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    repo_root = args.repo_root.resolve()
    paths = [path.resolve() for path in args.paths] if args.paths else default_paths(repo_root)
    missing = [path for path in paths if not path.exists()]
    if missing:
        for path in missing:
            print(f"[error] missing config file: {path}")
        return 1
    return run(paths, repo_root)


if __name__ == "__main__":
    raise SystemExit(main())
