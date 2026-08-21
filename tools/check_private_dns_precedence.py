from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from check_dns_safety import default_paths


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_PROFILE_NAMES = {
    "rulemesh-substore-surge-personal.conf",
    "rulemesh-substore-surge-work-whitelist.conf",
    "rulemesh-substore-mihomo-clash-verge.yaml",
    "rulemesh-substore-mihomo-clash-meta.yaml",
}
SURGE_PERSONAL = "rulemesh-substore-surge-personal.conf"
SURGE_WORK = "rulemesh-substore-surge-work-whitelist.conf"
MIHOMO_PROFILES = {
    "rulemesh-substore-mihomo-clash-verge.yaml",
    "rulemesh-substore-mihomo-clash-meta.yaml",
}
ROUTING_CATEGORIES = {"reject", "proxy", "region"}
DOMAIN_RULE = re.compile(
    r"(?:^|[(,])DOMAIN(?:-SUFFIX|-KEYWORD|-WILDCARD)?\s*,",
    re.IGNORECASE,
)
OVERSEAS_DNS_HOSTS = {
    "cloudflare-dns.com",
    "dns.google",
    "dns.quad9.net",
}


def safe_nameserver_summary(values: tuple[str, ...]) -> dict[str, object]:
    """返回可安全记录的计数与不可逆摘要，不回显私有 DNS 值。"""
    digest = hashlib.sha256()
    for value in values:
        encoded = value.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return {"count": len(values), "sha256": digest.hexdigest()}


@dataclass(frozen=True)
class DnsPrecedenceFinding:
    path: Path
    line: int
    message: str
    remediation: str


@dataclass(frozen=True)
class _PublicRule:
    identifier: str
    local_path: Path
    category: str


@dataclass(frozen=True)
class _PolicyEntry:
    line: int
    providers: tuple[str, ...]
    nameservers: tuple[str, ...]


def _scalar(value: str) -> str:
    return value.strip().strip('"\'')


def _active_surge_section(
    lines: list[str], section_name: str
) -> list[tuple[int, str]]:
    wanted = f"[{section_name}]".lower()
    active = False
    result: list[tuple[int, str]] = []
    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if re.fullmatch(r"\[[^]]+\]", stripped):
            active = stripped.lower() == wanted
            continue
        if active and stripped and not stripped.startswith(("#", ";")):
            result.append((line_number, stripped))
    return result


def _public_rule_from_url(
    value: str, public_root: Path, client: str
) -> _PublicRule | None:
    path = urlsplit(_scalar(value)).path.replace("\\", "/")
    if client == "surge":
        match = re.search(
            r"(?:^|/)dist/surge/rules/(reject|proxy|region|direct)/(.+)\.list$",
            path,
            re.IGNORECASE,
        )
        output_root = public_root / "dist/surge/rules"
        suffix = ".list"
    else:
        match = re.search(
            r"(?:^|/)dist/mihomo/classical/(reject|proxy|region|direct)/(.+)\.ya?ml$",
            path,
            re.IGNORECASE,
        )
        output_root = public_root / "dist/mihomo/classical"
        suffix = ".yaml"
    if not match:
        return None

    category = match.group(1).lower()
    tail = match.group(2).strip("/")
    if not tail or any(part in {"", ".", ".."} for part in tail.split("/")):
        return None
    identifier = f"{category}/{tail}"
    return _PublicRule(
        identifier=identifier,
        local_path=output_root / f"{identifier}{suffix}",
        category=category,
    )


def _artifact_has_domain_rule(path: Path) -> bool:
    if not path.is_file():
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip().lstrip("- ").strip('"\'')
        if stripped.startswith(("#", ";")):
            continue
        if DOMAIN_RULE.search(stripped):
            return True
    return False


def required_surge_exceptions(
    lines: list[str], public_root: Path = ROOT
) -> list[str]:
    required: list[str] = []
    for _, line in _active_surge_section(lines, "Rule"):
        parts = [part.strip() for part in line.split(",", 2)]
        if len(parts) < 2 or parts[0].upper() != "RULE-SET":
            continue
        rule = _public_rule_from_url(parts[1], public_root, "surge")
        if not rule:
            continue
        if rule.category == "direct" and rule.identifier.endswith("/cn_direct"):
            break
        if (
            rule.category in ROUTING_CATEGORIES
            and _artifact_has_domain_rule(rule.local_path)
            and rule.identifier not in required
        ):
            required.append(rule.identifier)
    return required


def _parse_mihomo_providers(lines: list[str]) -> dict[str, tuple[int, str]]:
    section = ""
    current_provider: str | None = None
    providers: dict[str, tuple[int, str]] = {}
    provider_lines: dict[str, int] = {}
    for line_number, line in enumerate(lines, start=1):
        top_level = re.match(r"^([A-Za-z0-9_-]+):\s*(?:#.*)?$", line)
        if top_level:
            section = top_level.group(1)
            current_provider = None
            continue
        if section != "rule-providers":
            continue
        provider = re.match(r"^  ([^\s#][^:]*):\s*(?:#.*)?$", line)
        if provider:
            current_provider = _scalar(provider.group(1))
            provider_lines[current_provider] = line_number
            continue
        if current_provider is None:
            continue
        url = re.match(r"^    url:\s*(.+?)\s*$", line)
        if url:
            providers[current_provider] = (
                provider_lines[current_provider],
                _scalar(url.group(1).split(" #", 1)[0]),
            )
    return providers


def _parse_mihomo_rules(lines: list[str]) -> list[tuple[int, list[str]]]:
    section = ""
    rules: list[tuple[int, list[str]]] = []
    for line_number, line in enumerate(lines, start=1):
        top_level = re.match(r"^([A-Za-z0-9_-]+):\s*(?:#.*)?$", line)
        if top_level:
            section = top_level.group(1)
            continue
        if section != "rules":
            continue
        match = re.match(r"^  -\s*(.+?)\s*$", line)
        if match:
            value = _scalar(match.group(1).split(" #", 1)[0])
            rules.append(
                (line_number, [_scalar(part) for part in value.split(",")])
            )
    return rules


def required_mihomo_exceptions(
    lines: list[str], public_root: Path = ROOT
) -> list[str]:
    providers = _parse_mihomo_providers(lines)
    public_rules = {
        name: _public_rule_from_url(url, public_root, "mihomo")
        for name, (_, url) in providers.items()
    }
    required: list[str] = []
    for _, parts in _parse_mihomo_rules(lines):
        if len(parts) < 2 or parts[0].upper() != "RULE-SET":
            continue
        provider_name = parts[1]
        rule = public_rules.get(provider_name)
        if not rule:
            continue
        if rule.category == "direct" and rule.identifier.endswith("/cn_direct"):
            break
        if (
            rule.category in ROUTING_CATEGORIES
            and _artifact_has_domain_rule(rule.local_path)
            and provider_name not in required
        ):
            required.append(provider_name)
    return required


def _parse_inline_or_scalar(value: str) -> tuple[str, ...]:
    value = value.strip()
    if not value:
        return ()
    if value.startswith("[") and value.endswith("]"):
        return tuple(
            _scalar(item) for item in value[1:-1].split(",") if item.strip()
        )
    return (_scalar(value),)


def _parse_mihomo_dns(
    lines: list[str],
) -> tuple[tuple[str, ...], list[_PolicyEntry]]:
    section = ""
    dns_key = ""
    nameservers: list[str] = []
    policies: list[_PolicyEntry] = []
    current_policy_line = 0
    current_policy_providers: tuple[str, ...] = ()
    current_policy_nameservers: list[str] = []

    def finish_policy() -> None:
        nonlocal current_policy_line, current_policy_providers
        if current_policy_line:
            policies.append(
                _PolicyEntry(
                    current_policy_line,
                    current_policy_providers,
                    tuple(current_policy_nameservers),
                )
            )
        current_policy_line = 0
        current_policy_providers = ()
        current_policy_nameservers.clear()

    for line_number, line in enumerate(lines, start=1):
        top_level = re.match(r"^([A-Za-z0-9_-]+):\s*(?:#.*)?$", line)
        if top_level:
            if section == "dns":
                finish_policy()
            section = top_level.group(1)
            dns_key = ""
            continue
        if section != "dns" or not line.strip() or line.lstrip().startswith("#"):
            continue

        key = re.match(r"^  ([A-Za-z0-9_-]+):\s*(.*?)\s*$", line)
        if key:
            finish_policy()
            dns_key = key.group(1)
            if dns_key == "nameserver":
                nameservers.extend(_parse_inline_or_scalar(key.group(2)))
            continue

        if dns_key == "nameserver":
            item = re.match(r"^    -\s*(.+?)\s*$", line)
            if item:
                nameservers.append(_scalar(item.group(1).split(" #", 1)[0]))
            continue

        if dns_key != "nameserver-policy":
            continue

        if re.match(r"^    \S", line):
            finish_policy()
            parts = re.split(r":(?=\s|$)", line.strip(), maxsplit=1)
            if len(parts) != 2:
                continue
            policy_key = _scalar(parts[0])
            if not policy_key.lower().startswith("rule-set:"):
                continue
            provider_text = policy_key[len("rule-set:") :]
            current_policy_providers = tuple(
                item.removeprefix("rule-set:").strip()
                for item in provider_text.split(",")
                if item.strip()
            )
            current_policy_line = line_number
            current_policy_nameservers.extend(_parse_inline_or_scalar(parts[1]))
            continue

        item = re.match(r"^      -\s*(.+?)\s*$", line)
        if item and current_policy_line:
            current_policy_nameservers.append(
                _scalar(item.group(1).split(" #", 1)[0])
            )

    if section == "dns":
        finish_policy()
    return tuple(nameservers), policies


def _is_overseas_surge_dns(value: str) -> bool:
    server = re.fullmatch(r"server:\s*(\S+)", value.strip(), re.IGNORECASE)
    if not server:
        return False
    hostname = urlsplit(server.group(1)).hostname
    return bool(hostname and hostname.lower() in OVERSEAS_DNS_HOSTS)


def _surge_host_entries(
    lines: list[str], public_root: Path
) -> tuple[list[tuple[int, str, str]], int | None]:
    exceptions: list[tuple[int, str, str]] = []
    performance_line: int | None = None
    for line_number, line in _active_surge_section(lines, "Host"):
        if "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        if "cn_performance_dns_domains.list" in key.lower():
            performance_line = line_number
            continue
        key_match = re.match(r"^(?:RULE-SET|DOMAIN-SET):(.+)$", key, re.IGNORECASE)
        if not key_match:
            continue
        rule = _public_rule_from_url(key_match.group(1), public_root, "surge")
        if rule:
            exceptions.append((line_number, rule.identifier, value))
    return exceptions, performance_line


def _validate_surge_personal(
    path: Path, lines: list[str], public_root: Path
) -> list[DnsPrecedenceFinding]:
    findings: list[DnsPrecedenceFinding] = []
    required = required_surge_exceptions(lines, public_root)
    exceptions, performance_line = _surge_host_entries(lines, public_root)
    if performance_line is None:
        findings.append(
            DnsPrecedenceFinding(
                path,
                1,
                "Surge Personal 缺少性能型中国 DNS DOMAIN-SET。",
                "在 [Host] 中加入性能型中国 DNS 产物，并放在全部海外规则例外之后。",
            )
        )

    for identifier in required:
        matching = [entry for entry in exceptions if entry[1] == identifier]
        overseas = [entry for entry in matching if _is_overseas_surge_dns(entry[2])]
        if not overseas:
            findings.append(
                DnsPrecedenceFinding(
                    path,
                    matching[0][0] if matching else 1,
                    f"高优先级域名规则集 {identifier} 缺少海外 DNS 例外。",
                    "在性能型中国 DNS 条目前加入该公开规则集的海外 DoH 映射。",
                )
            )
            continue
        if performance_line is not None and not any(
            entry[0] < performance_line for entry in overseas
        ):
            findings.append(
                DnsPrecedenceFinding(
                    path,
                    overseas[0][0],
                    f"高优先级域名规则集 {identifier} 的海外例外位于性能型中国 DNS 之后。",
                    "把该海外 DoH 映射移动到性能型中国 DNS 条目之前。",
                )
            )
    return findings


def _performance_provider_name(lines: list[str]) -> tuple[int, str] | None:
    for name, (line_number, url) in _parse_mihomo_providers(lines).items():
        if "cn_performance_dns_domains.list" in url.lower():
            return line_number, name
    return None


def _is_ai_us_provider(name: str) -> bool:
    return name.strip().lower() in {"ai-us", "us_ai"}


def _validate_mihomo(
    path: Path, lines: list[str], public_root: Path
) -> list[DnsPrecedenceFinding]:
    findings: list[DnsPrecedenceFinding] = []
    required = required_mihomo_exceptions(lines, public_root)
    nameservers, policies = _parse_mihomo_dns(lines)
    if not nameservers:
        findings.append(
            DnsPrecedenceFinding(
                path,
                1,
                "Mihomo dns.nameserver 不能为空，海外 policy 无法据此建立完整镜像。",
                "恢复默认海外 dns.nameserver 数组，再让高优先级 policy 与其完全相同。",
            )
        )
    performance_provider = _performance_provider_name(lines)
    performance_policy: _PolicyEntry | None = None
    if performance_provider:
        performance_policy = next(
            (
                policy
                for policy in policies
                if performance_provider[1] in policy.providers
            ),
            None,
        )
    if not performance_provider or not performance_policy:
        findings.append(
            DnsPrecedenceFinding(
                path,
                performance_provider[0] if performance_provider else 1,
                "Mihomo 缺少性能型中国 DNS provider 或 nameserver-policy。",
                "注册性能型域名 provider，并为其配置国内 DoH policy。",
            )
        )

    if not any(_is_ai_us_provider(name) for name in required):
        findings.append(
            DnsPrecedenceFinding(
                path,
                1,
                "Mihomo 缺少位于中国兜底前的 ai-us/us_ai 高优先级域名规则。",
                "保留 OpenAI / ChatGPT 的美国路由，并把该 rule-set 加入海外 DNS 例外。",
            )
        )

    for provider_name in required:
        matching = [
            policy for policy in policies if provider_name in policy.providers
        ]
        overseas = [
            policy
            for policy in matching
            if nameservers and policy.nameservers == nameservers
        ]
        if not overseas:
            message = (
                f"高优先级域名规则集 {provider_name} 缺少海外 DNS policy。"
                if not matching
                else f"高优先级域名规则集 {provider_name} 的 policy 必须与 dns.nameserver 完全相同。"
            )
            findings.append(
                DnsPrecedenceFinding(
                    path,
                    matching[0].line if matching else 1,
                    message,
                    "使用与 dns.nameserver 顺序和值完全相同的数组配置该 rule-set。",
                )
            )
            continue
        if performance_policy and not any(
            policy.line < performance_policy.line for policy in overseas
        ):
            findings.append(
                DnsPrecedenceFinding(
                    path,
                    overseas[0].line,
                    f"高优先级域名规则集 {provider_name} 的海外 policy 位于性能型中国 DNS 之后。",
                    "把该 rule-set 的海外 policy 移到性能型中国 DNS policy 之前。",
                )
            )
    return findings


def validate_profile(
    path: Path, public_root: Path = ROOT
) -> list[DnsPrecedenceFinding]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if path.name == SURGE_WORK:
        relevant_lines = _active_surge_section(lines, "Host")
        relevant_lines.extend(_active_surge_section(lines, "Rule"))
        for line_number, line in relevant_lines:
            if "cn_performance_dns_domains" in line.lower():
                return [
                    DnsPrecedenceFinding(
                        path,
                        line_number,
                        "工作白名单不得引用性能型中国 DNS 产物。",
                        "继续使用小型 cn_dns_domains 白名单，不改变工作白名单行为。",
                    )
                ]
        return []
    if path.name == SURGE_PERSONAL:
        return _validate_surge_personal(path, lines, public_root)
    if path.name in MIHOMO_PROFILES:
        return _validate_mihomo(path, lines, public_root)
    return []


def _format_finding(finding: DnsPrecedenceFinding) -> str:
    return (
        f"[private-dns-precedence] {finding.path.name}:{finding.line}: "
        f"{finding.message} 修复：{finding.remediation}"
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检查私有配置的 DNS 规则优先级。")
    parser.add_argument("paths", nargs="*", type=Path, help="可选：指定私有配置文件。")
    parser.add_argument(
        "--public-root",
        type=Path,
        default=ROOT,
        help="公开 rulemesh 仓库根目录。",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    paths = (
        [path.resolve() for path in args.paths]
        if args.paths
        else [
            path
            for path in default_paths(ROOT)
            if path.name in PRIVATE_PROFILE_NAMES
        ]
    )
    if not paths:
        print("[private-dns-precedence] 未发现已登记私有配置，跳过。")
        return 0
    findings = [
        finding
        for path in paths
        for finding in validate_profile(path, args.public_root)
    ]
    if findings:
        for finding in findings:
            print(_format_finding(finding))
        print(
            "[private-dns-precedence] DNS 优先级检查失败："
            f"{len(findings)} 个问题，涉及 {len({item.path for item in findings})} 个配置。"
        )
        return 1
    print(f"[private-dns-precedence] DNS 优先级检查通过：{len(paths)} 个配置文件。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
