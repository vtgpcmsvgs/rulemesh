from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

from check_dns_safety import default_paths


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_PROFILE_NAMES = {
    "rulemesh-substore-surge-personal.conf",
    "rulemesh-substore-surge-work-whitelist.conf",
    "rulemesh-substore-mihomo-clash-verge.yaml",
    "rulemesh-substore-mihomo-clash-meta.yaml",
}


@dataclass(frozen=True)
class PerformanceFinding:
    path: Path
    line: int
    message: str
    remediation: str


@dataclass
class MihomoProvider:
    line: int
    interval: str | None = None
    lazy: str | None = None


@dataclass
class MihomoGroup:
    line: int
    name: str
    group_type: str | None = None
    filter_text: str = ""
    interval: str | None = None
    lazy: str | None = None
    tolerance: str | None = None


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def scalar(value: str) -> str:
    return value.strip().strip('"\'')


def role(value: str) -> str:
    lowered = value.lower()
    if "美国" in value or re.search(r"(^|[^a-z])us([^a-z]|$)", lowered):
        return "us"
    if "全地区" in value or "节点-自动" in value or "节点自动" in value:
        return "global_auto"
    if "global" in lowered and "auto" in lowered:
        return "global_auto"
    return "other"


def section_lines(lines: list[str], section_name: str) -> list[tuple[int, str]]:
    wanted = f"[{section_name}]".lower()
    active = False
    result: list[tuple[int, str]] = []
    for index, line in enumerate(lines, start=1):
        stripped = line.strip()
        if re.fullmatch(r"\[[^]]+\]", stripped):
            active = stripped.lower() == wanted
            continue
        if active:
            result.append((index, line))
    return result


def parse_surge_groups(lines: list[str]) -> dict[str, tuple[int, str, str]]:
    groups: dict[str, tuple[int, str, str]] = {}
    for index, line in section_lines(lines, "Proxy Group"):
        if not line.strip() or line.lstrip().startswith(("#", ";")) or "=" not in line:
            continue
        name, definition = line.split("=", 1)
        group_name = name.strip()
        group_type = definition.split(",", 1)[0].strip().lower()
        groups[group_name] = (index, group_type, role(f"{group_name} {definition}"))
    return groups


def validate_surge_personal(path: Path, lines: list[str]) -> list[PerformanceFinding]:
    findings: list[PerformanceFinding] = []
    groups = parse_surge_groups(lines)
    final = next(
        (
            (index, [scalar(part) for part in line.split(",")])
            for index, line in section_lines(lines, "Rule")
            if line.strip().upper().startswith("FINAL,")
        ),
        None,
    )
    if not final or len(final[1]) < 2:
        findings.append(
            PerformanceFinding(path, 1, "Surge personal 缺少通用 FINAL。", "补回通用 FINAL 并指向全地区 smart 自动组。")
        )
        return findings

    line_number, parts = final
    target = groups.get(parts[1])
    smart_groups = [name for name, group in groups.items() if group[1] == "smart"]
    if (
        not target
        or target[1] != "smart"
        or not smart_groups
        or parts[1] != smart_groups[0]
    ):
        findings.append(
            PerformanceFinding(
                path,
                line_number,
                "Surge personal 的通用 FINAL 未指向全地区 smart 自动组。",
                "保留 OpenAI 美国专项规则，只把通用 FINAL 改为全地区 smart 自动组。",
            )
        )
    return findings


def validate_surge_work(path: Path, lines: list[str]) -> list[PerformanceFinding]:
    findings: list[PerformanceFinding] = []
    active_rules = [
        (index, line.strip())
        for index, line in section_lines(lines, "Rule")
        if line.strip() and not line.lstrip().startswith(("#", ";"))
    ]
    required = {
        "DOMAIN-SUFFIX,zsxq.com,DIRECT": "zsxq.com",
        "DOMAIN-SUFFIX,yikaiying.com,DIRECT": "yikaiying.com",
    }
    final_position = next(
        (position for position, (_, line) in enumerate(active_rules) if line.upper().startswith("FINAL,")),
        None,
    )
    for rule_line, domain in required.items():
        position = next(
            (position for position, (_, line) in enumerate(active_rules) if line == rule_line),
            None,
        )
        if position is None or final_position is None or position > final_position:
            findings.append(
                PerformanceFinding(
                    path,
                    active_rules[final_position][0] if final_position is not None else 1,
                    f"工作白名单缺少位于 FINAL 前的 {domain} 精确 DIRECT 入口。",
                    f"在 FINAL,REJECT 前加入 DOMAIN-SUFFIX,{domain},DIRECT。",
                )
            )
    if final_position is None or active_rules[final_position][1].upper() != "FINAL,REJECT":
        findings.append(
            PerformanceFinding(path, 1, "工作白名单必须保持 FINAL,REJECT。", "恢复最终拒绝，不接入通用兜底。")
        )
    return findings


def parse_mihomo(
    lines: list[str],
) -> tuple[list[MihomoProvider], dict[str, MihomoGroup], list[tuple[int, list[str]]]]:
    section = ""
    providers: list[MihomoProvider] = []
    groups: dict[str, MihomoGroup] = {}
    rules: list[tuple[int, list[str]]] = []
    provider: MihomoProvider | None = None
    group: MihomoGroup | None = None
    in_health = False

    for index, line in enumerate(lines, start=1):
        top_level = re.match(r"^([A-Za-z0-9_-]+):\s*", line)
        if top_level:
            section = top_level.group(1)
            provider = None
            group = None
            in_health = False
            continue

        if section == "proxy-providers":
            if re.match(r"^  [^\s#][^:]*:\s*$", line):
                provider = MihomoProvider(line=index)
                providers.append(provider)
                in_health = False
                continue
            if provider is None:
                continue
            if re.match(r"^    health-check:\s*$", line):
                in_health = True
                continue
            if re.match(r"^    [A-Za-z0-9_-]+:", line):
                in_health = False
            if in_health:
                field = re.match(r"^      ([A-Za-z0-9_-]+):\s*(.+?)\s*$", line)
                if field and field.group(1) == "interval":
                    provider.interval = scalar(field.group(2))
                elif field and field.group(1) == "lazy":
                    provider.lazy = scalar(field.group(2)).lower()
            continue

        if section == "proxy-groups":
            name_match = re.match(r"^  - name:\s*(.+?)\s*$", line)
            if name_match:
                name = scalar(name_match.group(1))
                group = MihomoGroup(line=index, name=name)
                groups[name] = group
                continue
            if group is None:
                continue
            field = re.match(r"^    ([A-Za-z0-9_-]+):\s*(.*?)\s*$", line)
            if not field:
                continue
            key, value = field.group(1), scalar(field.group(2))
            if key == "type":
                group.group_type = value.lower()
            elif key in {"filter", "exclude-filter"}:
                group.filter_text += f" {value}"
            elif key == "interval":
                group.interval = value
            elif key == "lazy":
                group.lazy = value.lower()
            elif key == "tolerance":
                group.tolerance = value
            continue

        if section == "rules":
            rule_match = re.match(r"^  -\s*(.+?)\s*$", line)
            if rule_match:
                value = scalar(rule_match.group(1))
                rules.append((index, [scalar(part) for part in value.split(",")]))

    return providers, groups, rules


def validate_mihomo(path: Path, lines: list[str]) -> list[PerformanceFinding]:
    findings: list[PerformanceFinding] = []
    providers, groups, rules = parse_mihomo(lines)

    for provider in providers:
        if provider.interval != "300" or provider.lazy != "false":
            findings.append(
                PerformanceFinding(
                    path,
                    provider.line,
                    "Mihomo provider 健康检查必须使用 300 秒主动检测。",
                    "设置 health-check.interval: 300 与 health-check.lazy: false。",
                )
            )

    for group in groups.values():
        if group.group_type != "url-test":
            continue
        group_role = role(f"{group.name} {group.filter_text}")
        if group.interval != "300" or group.lazy != "false":
            findings.append(
                PerformanceFinding(
                    path,
                    group.line,
                    "Mihomo url-test 组必须使用 300 秒主动检测。",
                    "设置 interval: 300 与 lazy: false。",
                )
            )
        if group_role == "us" and group.tolerance != "100":
            findings.append(
                PerformanceFinding(
                    path,
                    group.line,
                    "Mihomo 美国 url-test 组的 tolerance 必须为 100。",
                    "把美国组 tolerance 调整为 100，兼顾切换速度与出口稳定。",
                )
            )

    ai_us = next(
        (
            (line, parts)
            for line, parts in rules
            if len(parts) >= 3
            and "ai" in parts[1].lower()
            and "us" in parts[1].lower()
        ),
        None,
    )
    if not ai_us or role(ai_us[1][-1]) != "us":
        findings.append(
            PerformanceFinding(path, ai_us[0] if ai_us else 1, "Mihomo 的 ai-us 规则必须固定美国组。", "恢复 OpenAI / ChatGPT 美国出口。")
        )

    match = next(
        ((line, parts) for line, parts in rules if parts and parts[0].upper() == "MATCH"),
        None,
    )
    target = groups.get(match[1][1]) if match and len(match[1]) >= 2 else None
    url_test_groups = [
        name for name, group in groups.items() if group.group_type == "url-test"
    ]
    if (
        not match
        or target is None
        or target.group_type != "url-test"
        or not url_test_groups
        or match[1][1] != url_test_groups[0]
    ):
        findings.append(
            PerformanceFinding(
                path,
                match[0] if match else 1,
                "Mihomo 的通用 MATCH 未指向全地区 url-test 自动组。",
                "保留 ai-us 美国专项规则，只把 MATCH 改为全地区自动组。",
            )
        )
    return findings


def validate_profile(path: Path) -> list[PerformanceFinding]:
    lines = read_lines(path)
    if path.name == "rulemesh-substore-surge-personal.conf":
        return validate_surge_personal(path, lines)
    if path.name == "rulemesh-substore-surge-work-whitelist.conf":
        return validate_surge_work(path, lines)
    if path.name in {
        "rulemesh-substore-mihomo-clash-verge.yaml",
        "rulemesh-substore-mihomo-clash-meta.yaml",
    }:
        return validate_mihomo(path, lines)
    return []


def main() -> int:
    paths = [path for path in default_paths(ROOT) if path.name in PRIVATE_PROFILE_NAMES]
    if not paths:
        print("[private-performance] 未发现已登记私有配置，跳过。")
        return 0

    findings = [finding for path in paths for finding in validate_profile(path)]
    if findings:
        for finding in findings:
            print(f"[private-performance] {finding.path.name}:{finding.line}: {finding.message}")
        return 1

    print(f"[private-performance] 性能优先检查通过：{len(paths)} 个配置文件。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
