from __future__ import annotations

import argparse
import hashlib
import ipaddress
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from check_dns_safety import default_paths


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_PROFILE_NAMES = {
    "rulemesh-substore-surge-personal.conf",
    "rulemesh-substore-surge-personal-company.conf",
    "rulemesh-substore-surge-work-whitelist.conf",
    "rulemesh-substore-mihomo-clash-verge.yaml",
    "rulemesh-substore-mihomo-clash-meta.yaml",
}
SURGE_PERSONAL_NAMES = {
    "rulemesh-substore-surge-personal.conf",
    "rulemesh-substore-surge-personal-company.conf",
}
SURGE_WORK = "rulemesh-substore-surge-work-whitelist.conf"
MIHOMO_PROFILES = {
    "rulemesh-substore-mihomo-clash-verge.yaml",
    "rulemesh-substore-mihomo-clash-meta.yaml",
}
ROUTING_CATEGORIES = {"reject", "proxy", "region"}
AI_US_RULE_IDENTIFIER = "region/us/ai_us"
DOMAIN_RULE = re.compile(
    r"(?:^|[(,])DOMAIN(?:-SUFFIX|-KEYWORD|-WILDCARD|-REGEX)?\s*,",
    re.IGNORECASE,
)
OVERSEAS_DNS_HOSTS = {
    "cloudflare-dns.com",
    "dns.google",
    "dns.quad9.net",
}
DOMESTIC_DNS_HOSTS = {"dns.alidns.com", "doh.pub"}
PUBLIC_RULE_HOST = "raw.githubusercontent.com"
PUBLIC_RULE_PATH_PREFIX = "/vtgpcmsvgs/rulemesh/main"
US_GROUP_MAX_DEPTH = 32
FILTERING_GROUP_TYPES = {"smart", "url-test", "fallback", "load-balance"}
WRAPPER_GROUP_TYPES = {"select"}
APPROVED_SURGE_US_FILTERS = frozenset(
    {"((🇺🇸)|(美国)|(United States)|(US))"}
)
APPROVED_MIHOMO_US_FILTERS = frozenset(
    {r"(?i)🇺🇸|美国|united states|\\bus\\b"}
)
SAFE_NAMESERVER_DIGEST_HEX_LENGTH = 16


def safe_nameserver_summary(values: tuple[str, ...]) -> dict[str, object]:
    """返回可安全记录的计数与不可逆摘要，不回显私有 DNS 值。"""
    digest = hashlib.sha256()
    for value in values:
        encoded = value.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return {
        "count": len(values),
        "sha256": digest.hexdigest()[:SAFE_NAMESERVER_DIGEST_HEX_LENGTH],
    }


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
    is_rule_set: bool = True


@dataclass
class _ProxyGroup:
    line: int
    group_type: str = ""
    filter_text: str = ""
    members: list[str] = field(default_factory=list)
    has_external_source: bool = False
    has_invalid_external_source: bool = False
    source_references: list[str] = field(default_factory=list)
    declares_source_references: bool = False


def _dns_endpoint_hostname(value: str) -> str | None:
    if value.strip().startswith(("&", "*")):
        return None
    parsed = urlsplit(value.strip())
    try:
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or parsed.path != "/dns-query"
        or parsed.query
    ):
        return None
    return parsed.hostname.lower()


def _is_approved_overseas_dns(value: str) -> bool:
    return _dns_endpoint_hostname(value) in OVERSEAS_DNS_HOSTS


def _is_approved_domestic_dns(value: str) -> bool:
    return _dns_endpoint_hostname(value) in DOMESTIC_DNS_HOSTS


def _contains_yaml_reference(values: tuple[str, ...]) -> bool:
    return any(value.strip().startswith(("&", "*")) for value in values)


def _approved_public_path(value: str) -> str | None:
    raw_value = _scalar(value)
    if "?" in raw_value or "#" in raw_value:
        return None
    parsed = urlsplit(raw_value)
    try:
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.hostname.lower() != PUBLIC_RULE_HOST
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or parsed.query
        or parsed.fragment
        or not parsed.path.startswith(f"{PUBLIC_RULE_PATH_PREFIX}/")
    ):
        return None
    return parsed.path[len(PUBLIC_RULE_PATH_PREFIX) :]


def _scalar(value: str) -> str:
    return value.strip().strip('"\'')


def _is_valid_url_hostname(value: str) -> bool:
    hostname = value.rstrip(".")
    if not hostname:
        return False
    try:
        ipaddress.ip_address(hostname)
        return True
    except ValueError:
        pass
    try:
        ascii_hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError:
        return False
    if len(ascii_hostname) > 253:
        return False
    labels = ascii_hostname.split(".")
    return all(
        1 <= len(label) <= 63
        and re.fullmatch(r"[A-Za-z0-9-]+", label) is not None
        and not label.startswith("-")
        and not label.endswith("-")
        for label in labels
    )


def _is_supported_surge_policy_path(value: str) -> bool:
    try:
        parsed = urlsplit(_scalar(value))
        parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme.lower() == "https"
        and parsed.hostname is not None
        and _is_valid_url_hostname(parsed.hostname)
        and parsed.username is None
        and parsed.password is None
    )


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
    path = _approved_public_path(value)
    if path is None or "\\" in path:
        return None
    if client == "surge":
        match = re.fullmatch(
            r"/dist/surge/rules/(reject|proxy|region|direct)/(.+)\.list",
            path,
        )
        output_root = public_root / "dist/surge/rules"
        suffix = ".list"
    else:
        match = re.fullmatch(
            r"/dist/mihomo/classical/(reject|proxy|region|direct)/(.+)\.yaml",
            path,
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


def _surge_ai_route(
    lines: list[str], public_root: Path
) -> tuple[int, str] | None:
    for line_number, line in _active_surge_section(lines, "Rule"):
        parts = [part.strip() for part in line.split(",", 2)]
        if len(parts) < 3 or parts[0].upper() != "RULE-SET":
            continue
        rule = _public_rule_from_url(parts[1], public_root, "surge")
        if not rule:
            continue
        if rule.category == "direct" and rule.identifier.endswith("/cn_direct"):
            break
        if rule.identifier == AI_US_RULE_IDENTIFIER:
            return line_number, _scalar(parts[2])
    return None


def _surge_other_us_targets(lines: list[str], public_root: Path) -> list[str]:
    targets: list[str] = []
    for _, line in _active_surge_section(lines, "Rule"):
        parts = [part.strip() for part in line.split(",", 2)]
        if len(parts) < 3 or parts[0].upper() != "RULE-SET":
            continue
        rule = _public_rule_from_url(parts[1], public_root, "surge")
        if not rule:
            continue
        if rule.category == "direct" and rule.identifier.endswith("/cn_direct"):
            break
        if (
            rule.identifier != AI_US_RULE_IDENTIFIER
            and rule.identifier.startswith("region/us/")
            and rule.local_path.is_file()
        ):
            targets.append(_scalar(parts[2]))
    return targets


def _parse_surge_groups(lines: list[str]) -> dict[str, _ProxyGroup]:
    groups: dict[str, _ProxyGroup] = {}
    for line_number, line in _active_surge_section(lines, "Proxy Group"):
        if "=" not in line:
            continue
        name, definition = line.split("=", 1)
        group_name = _scalar(name)
        parts = [_scalar(part) for part in definition.split(",")]
        if not group_name or not parts:
            continue
        group = _ProxyGroup(line=line_number, group_type=parts[0].lower())
        for part in parts[1:]:
            if "=" not in part:
                group.members.append(_scalar(part))
                continue
            key, value = part.split("=", 1)
            normalized_key = key.strip().lower()
            if normalized_key == "policy-regex-filter":
                group.filter_text = _scalar(value)
            elif normalized_key == "policy-path":
                if _is_supported_surge_policy_path(value):
                    group.has_external_source = True
                else:
                    group.has_invalid_external_source = True
            elif normalized_key == "include-all-proxies":
                group.has_external_source |= _scalar(value).lower() in {
                    "1",
                    "true",
                    "yes",
                }
        groups[group_name] = group
    return groups


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


def _parse_mihomo_proxy_provider_names(lines: list[str]) -> frozenset[str]:
    section = ""
    providers: set[str] = set()
    for line in lines:
        top_level = re.match(r"^([A-Za-z0-9_-]+):\s*(?:#.*)?$", line)
        if top_level:
            section = top_level.group(1)
            continue
        if section != "proxy-providers":
            continue
        provider = re.match(r"^  ([^\s#][^:]*):(?:\s*.*?)?$", line)
        if provider:
            provider_name = _scalar(provider.group(1))
            if provider_name:
                providers.add(provider_name)
    return frozenset(providers)


def _parse_mihomo_source_references(value: str) -> tuple[list[str], bool]:
    value = value.strip()
    if not value:
        return [], False
    if value.startswith("[") and value.endswith("]"):
        raw_items = value[1:-1].split(",")
        references = [_scalar(item) for item in raw_items]
        return references, any(not item for item in references)
    reference = _scalar(value)
    return ([reference] if reference else []), not reference


def _parse_mihomo_groups(lines: list[str]) -> dict[str, _ProxyGroup]:
    section = ""
    provider_names = _parse_mihomo_proxy_provider_names(lines)
    groups: dict[str, _ProxyGroup] = {}
    group: _ProxyGroup | None = None
    list_key = ""
    for line_number, line in enumerate(lines, start=1):
        top_level = re.match(r"^([A-Za-z0-9_-]+):\s*(?:#.*)?$", line)
        if top_level:
            section = top_level.group(1)
            group = None
            list_key = ""
            continue
        if section != "proxy-groups":
            continue
        name = re.match(r"^  - name:\s*(.+?)\s*$", line)
        if name:
            group_name = _scalar(name.group(1).split(" #", 1)[0])
            group = _ProxyGroup(line=line_number)
            groups[group_name] = group
            list_key = ""
            continue
        if group is None:
            continue
        field = re.match(r"^    ([A-Za-z0-9_-]+):\s*(.*?)\s*$", line)
        if field:
            key = field.group(1)
            value = field.group(2).split(" #", 1)[0].strip()
            list_key = key if not value else ""
            if key == "type":
                group.group_type = _scalar(value).lower()
            elif key == "filter":
                group.filter_text = _scalar(value)
            elif key == "proxies":
                group.members.extend(_parse_inline_or_scalar(value))
            elif key == "use":
                group.declares_source_references = True
                references, has_empty_item = _parse_mihomo_source_references(
                    value
                )
                group.source_references.extend(references)
                group.has_invalid_external_source |= has_empty_item
            elif key == "include-all":
                group.has_external_source |= _scalar(value).lower() in {
                    "1",
                    "true",
                    "yes",
                }
            continue
        item = re.match(r"^      -(?:\s*(.*?))?\s*$", line)
        if not item:
            continue
        item_value = _scalar((item.group(1) or "").split(" #", 1)[0])
        if list_key == "proxies" and item_value:
            group.members.append(item_value)
        elif list_key == "use":
            group.declares_source_references = True
            if item_value:
                group.source_references.append(item_value)
            else:
                group.has_invalid_external_source = True
    for parsed_group in groups.values():
        if not parsed_group.declares_source_references:
            continue
        references_are_valid = (
            bool(parsed_group.source_references)
            and not parsed_group.has_invalid_external_source
            and all(
                reference in provider_names
                for reference in parsed_group.source_references
            )
        )
        parsed_group.has_external_source |= references_are_valid
        parsed_group.has_invalid_external_source |= not references_are_valid
    return groups


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
    current_policy_is_rule_set = True

    def finish_policy() -> None:
        nonlocal current_policy_line, current_policy_providers
        nonlocal current_policy_is_rule_set
        if current_policy_line:
            policies.append(
                _PolicyEntry(
                    current_policy_line,
                    current_policy_providers,
                    tuple(current_policy_nameservers),
                    current_policy_is_rule_set,
                )
            )
        current_policy_line = 0
        current_policy_providers = ()
        current_policy_nameservers.clear()
        current_policy_is_rule_set = True

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
            inline_value = key.group(2).split(" #", 1)[0].strip()
            if dns_key == "nameserver":
                nameservers.extend(_parse_inline_or_scalar(inline_value))
            elif dns_key == "nameserver-policy" and inline_value:
                policies.append(
                    _PolicyEntry(
                        line_number,
                        (),
                        _parse_inline_or_scalar(inline_value),
                        False,
                    )
                )
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
                policies.append(_PolicyEntry(line_number, (), (), False))
                continue
            policy_key = _scalar(parts[0])
            current_policy_is_rule_set = policy_key.lower().startswith("rule-set:")
            if current_policy_is_rule_set:
                provider_text = policy_key[len("rule-set:") :]
                current_policy_providers = tuple(
                    item.removeprefix("rule-set:").strip()
                    for item in provider_text.split(",")
                    if item.strip()
                )
            else:
                current_policy_providers = ()
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
    return _is_approved_overseas_dns(server.group(1))


def _group_has_us_semantics(
    name: str,
    groups: dict[str, _ProxyGroup],
    approved_filters: frozenset[str],
    *,
    seen: frozenset[str] = frozenset(),
    depth: int = 0,
) -> bool:
    if depth >= US_GROUP_MAX_DEPTH or name in seen:
        return False
    group = groups.get(name)
    if group is None:
        return False
    next_seen = seen | {name}
    members_are_us = bool(group.members) and all(
        _group_has_us_semantics(
            member,
            groups,
            approved_filters,
            seen=next_seen,
            depth=depth + 1,
        )
        for member in group.members
    )
    has_us_filtered_source = (
        group.filter_text in approved_filters
        and not group.has_invalid_external_source
        and group.has_external_source
    )
    if group.group_type in FILTERING_GROUP_TYPES:
        return (
            group.filter_text in approved_filters
            and not group.has_invalid_external_source
            and (group.has_external_source or bool(group.members))
            and (not group.members or members_are_us)
        )
    return group.group_type in WRAPPER_GROUP_TYPES and (
        members_are_us
        or (has_us_filtered_source and (not group.members or members_are_us))
    )


def _surge_host_entries(
    lines: list[str], public_root: Path
) -> tuple[list[tuple[int, str, str]], int | None]:
    exceptions: list[tuple[int, str, str]] = []
    performance_line: int | None = None
    for line_number, line in _active_surge_section(lines, "Host"):
        if "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        key_match = re.match(r"^(?:RULE-SET|DOMAIN-SET):(.+)$", key, re.IGNORECASE)
        if not key_match:
            continue
        artifact_url = key_match.group(1)
        if _approved_public_path(artifact_url) == (
            "/dist/surge/dns/cn_performance_dns_domains.list"
        ):
            performance_line = line_number
            continue
        rule = _public_rule_from_url(artifact_url, public_root, "surge")
        if rule:
            exceptions.append((line_number, rule.identifier, value))
    return exceptions, performance_line


def _validate_surge_personal(
    path: Path, lines: list[str], public_root: Path
) -> list[DnsPrecedenceFinding]:
    findings: list[DnsPrecedenceFinding] = []
    required = required_surge_exceptions(lines, public_root)
    exceptions, performance_line = _surge_host_entries(lines, public_root)
    ai_route = _surge_ai_route(lines, public_root)
    groups = _parse_surge_groups(lines)
    other_us_targets = _surge_other_us_targets(lines, public_root)
    if ai_route is None:
        findings.append(
            DnsPrecedenceFinding(
                path,
                1,
                f"Surge Personal 缺少位于中国兜底前的规范 {AI_US_RULE_IDENTIFIER} 路由。",
                "恢复规范公开 AI RULE-SET，并保持美国出口与海外 DNS 例外。",
            )
        )
    elif (
        not _group_has_us_semantics(
            ai_route[1], groups, APPROVED_SURGE_US_FILTERS
        )
        or not other_us_targets
        or any(target != ai_route[1] for target in other_us_targets)
    ):
        findings.append(
            DnsPrecedenceFinding(
                path,
                ai_route[0],
                f"规范 {AI_US_RULE_IDENTIFIER} 必须路由到美国策略组。",
                "恢复 OpenAI / ChatGPT 的固定美国出口。",
            )
        )
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


def _performance_providers(lines: list[str]) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    for name, (line_number, url) in _parse_mihomo_providers(lines).items():
        if _approved_public_path(url) == (
            "/dist/surge/dns/cn_performance_dns_domains.list"
        ):
            result.append((line_number, name))
    return result


def _mihomo_ai_route(
    lines: list[str], public_root: Path
) -> tuple[int, str] | None:
    providers = _parse_mihomo_providers(lines)
    public_rules = {
        name: _public_rule_from_url(url, public_root, "mihomo")
        for name, (_, url) in providers.items()
    }
    for line_number, parts in _parse_mihomo_rules(lines):
        if len(parts) < 2 or parts[0].upper() != "RULE-SET":
            continue
        rule = public_rules.get(parts[1])
        if not rule:
            continue
        if rule.category == "direct" and rule.identifier.endswith("/cn_direct"):
            break
        if rule.identifier == AI_US_RULE_IDENTIFIER:
            return line_number, parts[2] if len(parts) >= 3 else ""
    return None


def _mihomo_other_us_targets(
    lines: list[str], public_root: Path
) -> list[str]:
    providers = _parse_mihomo_providers(lines)
    public_rules = {
        name: _public_rule_from_url(url, public_root, "mihomo")
        for name, (_, url) in providers.items()
    }
    targets: list[str] = []
    for _, parts in _parse_mihomo_rules(lines):
        if len(parts) < 3 or parts[0].upper() != "RULE-SET":
            continue
        rule = public_rules.get(parts[1])
        if not rule:
            continue
        if rule.category == "direct" and rule.identifier.endswith("/cn_direct"):
            break
        if (
            rule.identifier != AI_US_RULE_IDENTIFIER
            and rule.identifier.startswith("region/us/")
            and rule.local_path.is_file()
        ):
            targets.append(parts[2])
    return targets


def _validate_mihomo(
    path: Path, lines: list[str], public_root: Path
) -> list[DnsPrecedenceFinding]:
    findings: list[DnsPrecedenceFinding] = []
    providers = _parse_mihomo_providers(lines)
    public_rules = {
        name: _public_rule_from_url(url, public_root, "mihomo")
        for name, (_, url) in providers.items()
    }
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
    elif not all(_is_approved_overseas_dns(value) for value in nameservers):
        findings.append(
            DnsPrecedenceFinding(
                path,
                1,
                "Mihomo dns.nameserver 必须逐项使用已批准的默认海外端点。",
                "仅使用 Cloudflare、Google 或 Quad9 的官方 HTTPS /dns-query endpoint。",
            )
        )

    if _contains_yaml_reference(nameservers) or any(
        _contains_yaml_reference(policy.nameservers) for policy in policies
    ):
        findings.append(
            DnsPrecedenceFinding(
                path,
                1,
                "Mihomo DNS 子集不接受未解析的 YAML anchor/alias。",
                "展开为显式 nameserver 与 nameserver-policy 数组后再校验。",
            )
        )

    performance_providers = _performance_providers(lines)
    performance_provider = (
        performance_providers[0] if len(performance_providers) == 1 else None
    )
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

    expected_policy_providers = Counter(required)
    if performance_provider:
        expected_policy_providers[performance_provider[1]] += 1
    actual_policy_providers = Counter(
        provider
        for policy in policies
        if policy.is_rule_set
        for provider in policy.providers
    )
    if (
        any(
            not policy.is_rule_set or not policy.providers
            for policy in policies
        )
        or actual_policy_providers != expected_policy_providers
    ):
        findings.append(
            DnsPrecedenceFinding(
                path,
                1,
                "Mihomo nameserver-policy 包含未登记、缺失或重复项。",
                "精确保留真实 required 海外 policy 与唯一性能型中国 DNS policy。",
            )
        )

    if performance_policy and (
        not performance_policy.nameservers
        or not all(
            _is_approved_domestic_dns(value)
            for value in performance_policy.nameservers
        )
    ):
        findings.append(
            DnsPrecedenceFinding(
                path,
                performance_policy.line,
                "性能型中国 DNS policy 必须逐项使用已批准的国内 DNS endpoint。",
                "使用 AliDNS 或 DNSPod 的官方 HTTPS /dns-query endpoint。",
            )
        )

    ai_route = _mihomo_ai_route(lines, public_root)
    groups = _parse_mihomo_groups(lines)
    other_us_targets = _mihomo_other_us_targets(lines, public_root)
    if ai_route is None:
        findings.append(
            DnsPrecedenceFinding(
                path,
                1,
                f"Mihomo 缺少位于中国兜底前的规范 {AI_US_RULE_IDENTIFIER} 路由。",
                "恢复规范公开 AI provider、美国出口与海外 DNS policy。",
            )
        )
    elif (
        not _group_has_us_semantics(
            ai_route[1], groups, APPROVED_MIHOMO_US_FILTERS
        )
        or not other_us_targets
        or any(
            not _group_has_us_semantics(
                target, groups, APPROVED_MIHOMO_US_FILTERS
            )
            for target in other_us_targets
        )
    ):
        findings.append(
            DnsPrecedenceFinding(
                path,
                ai_route[0],
                f"规范 {AI_US_RULE_IDENTIFIER} 必须路由到美国策略组。",
                "恢复 OpenAI / ChatGPT 的固定美国出口。",
            )
        )

    for provider_name in required:
        public_rule = public_rules.get(provider_name)
        identifier = (
            public_rule.identifier if public_rule else "公开高优先级规则集"
        )
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
                f"高优先级域名规则集 {identifier} 缺少海外 DNS policy。"
                if not matching
                else f"高优先级域名规则集 {identifier} 的 policy 必须与 dns.nameserver 完全相同。"
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
                    f"高优先级域名规则集 {identifier} 的海外 policy 位于性能型中国 DNS 之后。",
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
    if path.name in SURGE_PERSONAL_NAMES:
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
