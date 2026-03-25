#!/usr/bin/env python3
"""从 AdsPower 主清单派生 reject/direct/proxy 源规则。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


RULES_APP_RELATIVE_PATH = Path("rules/app/adspower.txt")
SECTION_OUTPUTS = {
    "reject": Path("reject/adspower_reject.list"),
    "direct": Path("direct/adspower_direct.list"),
    "proxy": Path("proxy/adspower_proxy.list"),
}
SECTION_LABELS = {
    "reject": "拒绝",
    "direct": "直连",
    "proxy": "代理",
}
COMMENT_PREFIXES = ("#", ";", "//")
ACTION_FIELDS = {
    "REJECT",
    "DIRECT",
    "🚀 节点选择",
    "\"🚀 节点选择\"",
}


class AdspowerSyncError(Exception):
    """当 AdsPower 主清单不符合维护约定时抛出。"""


@dataclass
class SyncResult:
    manifest_path: Path | None = None
    rule_counts: dict[str, int] = field(default_factory=dict)
    generated_paths: dict[str, Path] = field(default_factory=dict)


def is_blank_or_comment(raw: str) -> bool:
    stripped = raw.strip()
    return not stripped or stripped.startswith(COMMENT_PREFIXES)


def parse_manifest(path: Path) -> dict[str, list[tuple[int, str]]]:
    sections = {name: [] for name in SECTION_OUTPUTS}
    current_section: str | None = None

    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = raw.strip()
        if stripped in {f"[{name}]" for name in SECTION_OUTPUTS}:
            current_section = stripped[1:-1]
            continue

        if current_section is None:
            if stripped and not stripped.startswith(COMMENT_PREFIXES):
                raise AdspowerSyncError(
                    f"{path.as_posix()}:{line_no} 节标题前只能出现注释或空行"
                )
            continue

        sections[current_section].append((line_no, raw))

    missing_sections = [name for name, items in sections.items() if not items]
    if missing_sections:
        joined = "、".join(missing_sections)
        raise AdspowerSyncError(f"{path.as_posix()} 缺少必要分组：{joined}")

    return sections


def active_rule_lines(entries: list[tuple[int, str]]) -> list[tuple[int, str]]:
    return [(line_no, raw.strip()) for line_no, raw in entries if not is_blank_or_comment(raw)]


def count_active_rules(entries: list[tuple[int, str]]) -> int:
    return len(active_rule_lines(entries))


def counterpart_rule(rule: str) -> str | None:
    if "adspower.com" in rule and "adspower.net" not in rule:
        return rule.replace("adspower.com", "adspower.net")
    if "adspower.net" in rule and "adspower.com" not in rule:
        return rule.replace("adspower.net", "adspower.com")
    return None


def validate_rule_actions(path: Path, sections: dict[str, list[tuple[int, str]]]) -> None:
    for section, entries in sections.items():
        for line_no, rule in active_rule_lines(entries):
            fields = [field.strip() for field in rule.split(",")]
            if len(fields) >= 3 and fields[-1] in ACTION_FIELDS:
                raise AdspowerSyncError(
                    f"{path.as_posix()}:{line_no} [{section}] 不要在主清单里写动作字段：{rule}"
                )


def validate_counterparts(path: Path, sections: dict[str, list[tuple[int, str]]]) -> None:
    for section, entries in sections.items():
        rules = {rule for _, rule in active_rule_lines(entries)}
        for line_no, rule in active_rule_lines(entries):
            counterpart = counterpart_rule(rule)
            if counterpart is None:
                continue
            if counterpart not in rules:
                raise AdspowerSyncError(
                    f"{path.as_posix()}:{line_no} [{section}] 缺少镜像规则：{counterpart}"
                )


def normalize_output_lines(entries: list[tuple[int, str]]) -> list[str]:
    lines: list[str] = []
    for _, raw in entries:
        line = raw.rstrip()
        if not line:
            if lines and lines[-1] != "":
                lines.append("")
            continue
        lines.append(line)

    while lines and lines[0] == "":
        lines.pop(0)
    while lines and lines[-1] == "":
        lines.pop()
    return lines


def write_output(path: Path, section: str, entries: list[tuple[int, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = normalize_output_lines(entries)
    header = [
        f"# AdsPower 专项{SECTION_LABELS[section]}规则。",
        f"# 生成来源：{RULES_APP_RELATIVE_PATH.as_posix()}",
        "# 请修改主清单，不要直接编辑本文件。",
        "",
    ]
    payload = body if body else ["# 暂无规则"]
    path.write_text("\n".join(header + payload + [""]), encoding="utf-8")


def sync_adspower_rules(root: Path, rules_root: Path) -> SyncResult:
    manifest_path = root / RULES_APP_RELATIVE_PATH
    if not manifest_path.exists():
        return SyncResult()

    sections = parse_manifest(manifest_path)
    validate_rule_actions(manifest_path, sections)
    validate_counterparts(manifest_path, sections)

    result = SyncResult(manifest_path=manifest_path)
    for section, relative_path in SECTION_OUTPUTS.items():
        output_path = rules_root / relative_path
        write_output(output_path, section, sections[section])
        result.rule_counts[section] = count_active_rules(sections[section])
        result.generated_paths[section] = output_path
    return result


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    rules_root = root / "rules"
    result = sync_adspower_rules(root, rules_root)
    if result.manifest_path is None:
        print("[SYNC] 未找到 AdsPower 主清单，跳过。")
        return 0

    print(
        "[SYNC] AdsPower 主清单 -> "
        f"reject={result.rule_counts.get('reject', 0)}, "
        f"direct={result.rule_counts.get('direct', 0)}, "
        f"proxy={result.rule_counts.get('proxy', 0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
