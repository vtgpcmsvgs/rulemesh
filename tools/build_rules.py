#!/usr/bin/env python3
"""从 rules/ 源规则层构建 Surge 与 Mihomo 显式产物。"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import shutil
import sys
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import sync_upstream_rules


ROOT = Path(__file__).resolve().parents[1]
RULES_ROOT = ROOT / "rules"
DIST_ROOT = ROOT / "dist"
SOURCE_GROUPS = ("reject", "direct", "proxy", "region")
AWS_UPSTREAM_BOOTSTRAP_PATH = RULES_ROOT / "upstream" / "aws" / "ip-ranges.json"
ALICLOUD_UPSTREAM_BOOTSTRAP_PATH = RULES_ROOT / "upstream" / "alicloud" / "hk_ipv4.json"
DOMAIN_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._")
DOMAIN_WILDCARD_CHARS = DOMAIN_CHARS | set("*?+")
SUPPORTED_CLASSICAL_TOKENS = {
    "AND",
    "OR",
    "NOT",
    "DOMAIN",
    "DOMAIN-SUFFIX",
    "DOMAIN-KEYWORD",
    "DOMAIN-WILDCARD",
    "DOMAIN-REGEX",
    "IP-CIDR",
    "IP-CIDR6",
    "GEOIP",
    "IP-ASN",
    "SRC-IP",
    "SRC-IP-CIDR",
    "SRC-IP-SUFFIX",
    "DEST-PORT",
    "DST-PORT",
    "SRC-PORT",
    "IN-PORT",
    "PROCESS-NAME",
    "PROCESS-PATH",
    "NETWORK",
    "PROTOCOL",
    "RULE-SET",
    "USER-AGENT",
    "URL-REGEX",
    "MATCH",
}
COMMENT_MARKERS = ("//", "#", ";")
COMMENTED_RULE_PREFIXES = tuple(sorted((*SUPPORTED_CLASSICAL_TOKENS, "INCLUDE")))
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
ASCII_WORD_RE = re.compile(r"[A-Za-z]+")
COMMENTED_RULE_RE = re.compile(
    r"^(?:" + "|".join(re.escape(token) for token in COMMENTED_RULE_PREFIXES) + r"),"
)


@dataclass
class ParsedLine:
    source_type: str | None = None
    surge_rule: str | None = None
    mihomo_classical: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class SourceLine:
    path: Path
    line_no: int
    raw: str


@dataclass
class SourceBuildResult:
    relative_path: Path
    category: str
    classification: str
    outputs: dict[str, list[str]]
    warnings: list[str]


class BuildError(Exception):
    """当规则源文件布局不符合仓库约定时抛出。"""


def read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="latin-1")


def iter_source_files() -> list[Path]:
    files: list[Path] = []
    for group in SOURCE_GROUPS:
        root = RULES_ROOT / group
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file():
                files.append(path)
    return sorted(files, key=lambda item: item.relative_to(RULES_ROOT).as_posix())


def validate_source_files(files: Iterable[Path]) -> None:
    invalid = [
        path.relative_to(RULES_ROOT).as_posix()
        for path in files
        if path.suffix.lower() != ".list"
    ]
    if invalid:
        joined = ", ".join(f"rules/{item}" for item in invalid)
        raise BuildError(
            "rules/{reject,direct,proxy,region} 下的源文件"
            f"都必须使用 .list 扩展名：{joined}"
        )


def ordered_unique(items: Iterable[str]) -> list[str]:
    return list(OrderedDict((item, None) for item in items if item).keys())


def strip_inline_comment(raw: str) -> str:
    line = raw.rstrip()
    for marker in (" #", "\t#", " //", "\t//"):
        index = line.find(marker)
        if index != -1:
            return line[:index].rstrip()
    return line


def repo_relative_path(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def parse_include_directive(raw: str) -> str | None:
    if is_comment_or_blank(raw):
        return None

    line = strip_inline_comment(raw).strip()
    if not line or "," not in line:
        return None

    token, _, rest = line.partition(",")
    if token.strip().upper() != "INCLUDE":
        return None
    return rest.strip()


def resolve_include_path(source_path: Path, line_no: int, target: str) -> Path:
    if not target:
        raise BuildError(f"{repo_relative_path(source_path)}:{line_no} INCLUDE 缺少路径参数")

    candidate = Path(target.replace("\\", "/"))
    if candidate.is_absolute():
        raise BuildError(
            f"{repo_relative_path(source_path)}:{line_no} INCLUDE 必须使用 rules/ 下的相对路径：{target}"
        )

    if candidate.parts and candidate.parts[0] == "rules":
        candidate = Path(*candidate.parts[1:])

    if candidate.parts and candidate.parts[0] in {".", ".."}:
        resolved = (source_path.parent / candidate).resolve()
    else:
        resolved = (RULES_ROOT / candidate).resolve()

    try:
        resolved.relative_to(RULES_ROOT.resolve())
    except ValueError as exc:
        raise BuildError(
            f"{repo_relative_path(source_path)}:{line_no} INCLUDE 必须位于 rules/ 目录内：{target}"
        ) from exc

    if not resolved.exists() or not resolved.is_file():
        raise BuildError(f"{repo_relative_path(source_path)}:{line_no} INCLUDE 目标不存在：{target}")
    return resolved


def expand_source_lines(path: Path, stack: tuple[Path, ...] = ()) -> list[SourceLine]:
    resolved_path = path.resolve()
    if resolved_path in stack:
        chain = " -> ".join(repo_relative_path(item) for item in (*stack, resolved_path))
        raise BuildError(f"检测到 INCLUDE 循环引用：{chain}")

    lines: list[SourceLine] = []
    for line_no, raw in enumerate(read_text(path).splitlines(), start=1):
        include_target = parse_include_directive(raw)
        if include_target is None:
            lines.append(SourceLine(path=path, line_no=line_no, raw=raw))
            continue

        include_path = resolve_include_path(path, line_no, include_target)
        lines.extend(expand_source_lines(include_path, (*stack, resolved_path)))
    return lines


def is_comment_or_blank(raw: str) -> bool:
    stripped = raw.strip()
    return not stripped or stripped.startswith("#") or stripped.startswith(";") or stripped.startswith("//")


def extract_comment_body(raw: str) -> str | None:
    stripped = raw.strip()
    for marker in COMMENT_MARKERS:
        if stripped.startswith(marker):
            return stripped[len(marker) :].strip()
    return None


def detect_non_chinese_comment(raw: str) -> str | None:
    body = extract_comment_body(raw)
    if not body:
        return None

    if CJK_RE.search(body):
        return None

    normalized = body.lstrip("-* ").strip()
    if not normalized:
        return None
    if normalized.startswith(("http://", "https://", "===", "---")):
        return None
    if COMMENTED_RULE_RE.match(normalized):
        return None
    if not ASCII_WORD_RE.search(normalized):
        return None
    return body


def find_non_chinese_comment_lines(path: Path) -> list[tuple[int, str]]:
    violations: list[tuple[int, str]] = []
    for line_no, raw in enumerate(read_text(path).splitlines(), start=1):
        comment_body = detect_non_chinese_comment(raw)
        if comment_body is not None:
            violations.append((line_no, comment_body))
    return violations


def validate_source_comment_language(files: Iterable[Path]) -> None:
    violations: list[str] = []
    for path in files:
        for line_no, comment_body in find_non_chinese_comment_lines(path):
            violations.append(
                f"{repo_relative_path(path)}:{line_no} 注释必须使用中文：{comment_body}"
            )

    if not violations:
        return

    preview = "\n".join(f"- {item}" for item in violations[:20])
    remainder = len(violations) - 20
    suffix = ""
    if remainder > 0:
        suffix = f"\n- 其余 {remainder} 处请在仓库中继续修正"
    raise BuildError(
        "rules/ 源规则中的自写注释必须使用中文。\n"
        "请将英文说明改为中文后再重新构建：\n"
        f"{preview}{suffix}"
    )


def is_domain_literal(value: str) -> bool:
    if not value:
        return False
    if value.startswith("+."):
        value = value[1:]
    if value.startswith("."):
        value = value[1:]
    if not value or value.endswith("."):
        return False
    if any(char not in DOMAIN_CHARS for char in value):
        return False
    return True


def is_domain_wildcard(value: str) -> bool:
    if not value or "." not in value:
        return False
    return all(char in DOMAIN_WILDCARD_CHARS for char in value)


def normalize_domain_exact(value: str) -> str:
    return value.strip().lstrip("+")


def normalize_domain_suffix(value: str) -> str:
    base = value.strip()
    if base.startswith("+."):
        base = base[1:]
    if not base.startswith("."):
        base = "." + base.lstrip(".")
    return base


def normalize_ip_network(value: str) -> tuple[str, str]:
    text = value.strip()
    if "/" in text:
        network = ipaddress.ip_network(text, strict=False)
    else:
        address = ipaddress.ip_address(text)
        suffix = 32 if address.version == 4 else 128
        network = ipaddress.ip_network(f"{address}/{suffix}", strict=False)
    token = "IP-CIDR6" if network.version == 6 else "IP-CIDR"
    return str(network), token


def normalize_source_ip(value: str) -> str:
    network, _ = normalize_ip_network(value)
    return network


def parse_plain_value(text: str) -> ParsedLine:
    parsed = ParsedLine()
    try:
        network, token = normalize_ip_network(text)
    except ValueError:
        if text.startswith("+.") or text.startswith("."):
            if not is_domain_literal(text):
                parsed.warnings.append(f"invalid domain literal: {text}")
                return parsed
            payload = normalize_domain_suffix(text)
            parsed.source_type = "domain"
            parsed.surge_rule = f"DOMAIN-SUFFIX,{payload[1:]}"
            parsed.mihomo_classical = f"DOMAIN-SUFFIX,{payload[1:]}"
            return parsed
        if not is_domain_literal(text):
            parsed.warnings.append(f"unrecognized plain rule: {text}")
            return parsed
        payload = normalize_domain_exact(text)
        parsed.source_type = "domain"
        parsed.surge_rule = f"DOMAIN,{payload}"
        parsed.mihomo_classical = f"DOMAIN,{payload}"
        return parsed

    parsed.source_type = "ipcidr"
    parsed.surge_rule = f"{token},{network}"
    parsed.mihomo_classical = f"{token},{network}"
    return parsed


def parse_simple_rule(token: str, rest: str) -> ParsedLine:
    parsed = ParsedLine()
    fields = [field.strip() for field in rest.split(",")]
    value = fields[0] if fields else ""
    extras = [field for field in fields[1:] if field]

    if not value:
        parsed.warnings.append(f"{token} is missing a value")
        return parsed

    normalized = ",".join([token, value, *extras])

    if token == "DOMAIN":
        if not is_domain_literal(value):
            parsed.warnings.append(f"invalid DOMAIN value: {value}")
            return parsed
        payload = normalize_domain_exact(value)
        parsed.source_type = "domain"
        parsed.surge_rule = normalized
        parsed.mihomo_classical = f"DOMAIN,{payload}"
        return parsed

    if token == "DOMAIN-SUFFIX":
        if not is_domain_literal(value):
            parsed.warnings.append(f"invalid DOMAIN-SUFFIX value: {value}")
            return parsed
        payload = normalize_domain_suffix(value)
        parsed.source_type = "domain"
        parsed.surge_rule = normalized
        parsed.mihomo_classical = f"DOMAIN-SUFFIX,{payload[1:]}"
        return parsed

    if token == "DOMAIN-WILDCARD":
        if not is_domain_wildcard(value):
            parsed.warnings.append(f"invalid DOMAIN-WILDCARD value: {value}")
            return parsed
        parsed.source_type = "classical"
        parsed.surge_rule = normalized
        parsed.mihomo_classical = f"DOMAIN-WILDCARD,{value}"
        return parsed

    if token == "DOMAIN-KEYWORD":
        parsed.source_type = "classical"
        parsed.surge_rule = normalized
        parsed.mihomo_classical = f"DOMAIN-KEYWORD,{value}"
        return parsed

    if token == "DOMAIN-REGEX":
        parsed.source_type = "classical"
        parsed.surge_rule = normalized
        parsed.mihomo_classical = f"DOMAIN-REGEX,{value}"
        return parsed

    if token in {"IP-CIDR", "IP-CIDR6"}:
        try:
            network, network_token = normalize_ip_network(value)
        except ValueError:
            parsed.warnings.append(f"invalid {token} value: {value}")
            return parsed
        option_fields = []
        for extra in extras:
            if extra.lower() == "no-resolve":
                option_fields.append("no-resolve")
            else:
                parsed.warnings.append(
                    f"{token} has an unsupported extra field kept only in Surge output: {extra}"
                )
        parsed.source_type = "ipcidr"
        parsed.surge_rule = ",".join([network_token, network, *option_fields])
        parsed.mihomo_classical = ",".join([network_token, network, *option_fields])
        return parsed

    if token == "SRC-IP":
        try:
            network = normalize_source_ip(value)
        except ValueError:
            parsed.warnings.append(f"invalid SRC-IP value: {value}")
            return parsed
        option_fields = [extra for extra in extras if extra.lower() == "no-resolve"]
        ignored = [extra for extra in extras if extra.lower() != "no-resolve"]
        for extra in ignored:
            parsed.warnings.append(f"SRC-IP has an unsupported extra field kept only in Surge output: {extra}")
        parsed.source_type = "classical"
        parsed.surge_rule = ",".join(["SRC-IP", network, *option_fields])
        parsed.mihomo_classical = ",".join(["SRC-IP-CIDR", network, *option_fields])
        return parsed

    if token == "SRC-IP-CIDR":
        try:
            network = normalize_source_ip(value)
        except ValueError:
            parsed.warnings.append(f"invalid SRC-IP-CIDR value: {value}")
            return parsed
        option_fields = [extra for extra in extras if extra.lower() == "no-resolve"]
        parsed.source_type = "classical"
        parsed.surge_rule = ",".join(["SRC-IP", network, *option_fields])
        parsed.mihomo_classical = ",".join(["SRC-IP-CIDR", network, *option_fields])
        return parsed

    if token == "DEST-PORT":
        parsed.source_type = "classical"
        parsed.surge_rule = f"DEST-PORT,{value}"
        parsed.mihomo_classical = f"DST-PORT,{value}"
        return parsed

    if token == "PROTOCOL":
        upper_value = value.upper()
        parsed.source_type = "classical"
        parsed.surge_rule = f"PROTOCOL,{upper_value}"
        if upper_value in {"TCP", "UDP"}:
            parsed.mihomo_classical = f"NETWORK,{upper_value.lower()}"
        else:
            parsed.warnings.append(f"mihomo does not support PROTOCOL,{upper_value}; kept only in Surge rules")
        return parsed

    if token == "RULE-SET":
        parsed.source_type = "classical"
        parsed.surge_rule = normalized
        parsed.warnings.append("RULE-SET should be expanded into rules/ source files; skipped for mihomo classical")
        return parsed

    if token in SUPPORTED_CLASSICAL_TOKENS:
        parsed.source_type = "classical"
        parsed.surge_rule = normalized
        parsed.mihomo_classical = normalized
        return parsed

    parsed.warnings.append(f"unknown rule type: {token}")
    return parsed


def parse_line(raw: str) -> ParsedLine:
    if is_comment_or_blank(raw):
        return ParsedLine()

    line = strip_inline_comment(raw).strip()
    if not line:
        return ParsedLine()

    if "," not in line:
        return parse_plain_value(line)

    token, _, rest = line.partition(",")
    token = token.strip().upper()
    rest = rest.strip()

    if token in {"AND", "OR", "NOT"}:
        return ParsedLine(
            source_type="classical",
            surge_rule=f"{token},{rest}",
            mihomo_classical=f"{token},{rest}",
        )

    return parse_simple_rule(token, rest)


TARGET_RULE_REPLACEMENTS = {
    "surge": (
        ("DST-PORT,", "DEST-PORT,"),
        ("SRC-IP-CIDR,", "SRC-IP,"),
    ),
    "mihomo_classical": (
        ("DEST-PORT,", "DST-PORT,"),
        ("SRC-IP,", "SRC-IP-CIDR,"),
    ),
}


def normalize_rule_for_target(rule: str, target: str) -> str:
    normalized = rule
    for source, replacement in TARGET_RULE_REPLACEMENTS.get(target, ()):
        normalized = normalized.replace(source, replacement)
    return normalized


def reset_output_roots() -> None:
    DIST_ROOT.mkdir(parents=True, exist_ok=True)
    for child_name in ("surge", "mihomo"):
        path = DIST_ROOT / child_name
        if path.is_file():
            path.unlink()
        elif path.exists():
            shutil.rmtree(path)
    report_path = DIST_ROOT / "build-report.json"
    if report_path.exists():
        report_path.unlink()


def write_surge_file(path: Path, source_path: Path, payload: list[str], kind: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = [
        f"# 生成来源：{source_path.as_posix()}",
        f"# 类型：{kind}",
        "# 请勿直接编辑 dist。",
        "",
    ]
    if payload:
        content = header + payload + [""]
    else:
        content = header + ["# 空文件", ""]
    path.write_text("\n".join(content), encoding="utf-8")


def write_mihomo_file(path: Path, source_path: Path, payload: list[str], kind: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if payload:
        body = [f"  - {json.dumps(item, ensure_ascii=False)}" for item in payload]
        content = [
            f"# 生成来源：{source_path.as_posix()}",
            f"# 行为：{kind}",
            "payload:",
            *body,
            "",
        ]
    else:
        content = [
            f"# 生成来源：{source_path.as_posix()}",
            f"# 行为：{kind}",
            "payload: []",
            "",
        ]
    path.write_text("\n".join(content), encoding="utf-8")


def classify_file(source_types: list[str]) -> str:
    unique = set(source_types)
    if not unique:
        return "empty"
    if unique == {"domain"}:
        return "domain-only"
    if unique == {"ipcidr"}:
        return "ipcidr-only"
    return "classical/mixed"


def build_source(path: Path) -> SourceBuildResult:
    relative = path.relative_to(RULES_ROOT)
    category = relative.parts[0]
    source_types: list[str] = []
    warnings: list[str] = []

    surge_rules: list[str] = []
    mihomo_classical: list[str] = []

    for source_line in expand_source_lines(path):
        parsed = parse_line(source_line.raw)
        if parsed.source_type:
            source_types.append(parsed.source_type)
        if parsed.surge_rule:
            surge_rules.append(normalize_rule_for_target(parsed.surge_rule, "surge"))
        if parsed.mihomo_classical:
            mihomo_classical.append(
                normalize_rule_for_target(parsed.mihomo_classical, "mihomo_classical")
            )
        for message in parsed.warnings:
            warnings.append(f"{repo_relative_path(source_line.path)}:{source_line.line_no} {message}")

    outputs = {
        "surge_rules": ordered_unique(surge_rules),
        "mihomo_classical": ordered_unique(mihomo_classical),
    }

    return SourceBuildResult(
        relative_path=relative,
        category=category,
        classification=classify_file(source_types),
        outputs=outputs,
        warnings=warnings,
    )


def write_outputs(result: SourceBuildResult) -> dict[str, str]:
    source_label = Path("rules") / result.relative_path
    surge_rel = result.relative_path.with_suffix(".list")
    mihomo_rel = result.relative_path.with_suffix(".yaml")

    output_paths = {
        "surge_rules": DIST_ROOT / "surge" / "rules" / surge_rel,
        "mihomo_classical": DIST_ROOT / "mihomo" / "classical" / mihomo_rel,
    }

    write_surge_file(output_paths["surge_rules"], source_label, result.outputs["surge_rules"], "rules")
    write_mihomo_file(output_paths["mihomo_classical"], source_label, result.outputs["mihomo_classical"], "classical")

    labels: dict[str, str] = {}
    for key, output_path in output_paths.items():
        if output_path.exists():
            labels[key] = output_path.relative_to(ROOT).as_posix()
    return labels


def build_report(results: list[SourceBuildResult], path_map: dict[str, dict[str, str]]) -> dict[str, object]:
    all_warnings = [warning for result in results for warning in result.warnings]
    summary = {
        "domain-only": sum(result.classification == "domain-only" for result in results),
        "ipcidr-only": sum(result.classification == "ipcidr-only" for result in results),
        "classical/mixed": sum(result.classification == "classical/mixed" for result in results),
        "empty": sum(result.classification == "empty" for result in results),
        "total_sources": len(results),
        "total_warnings": len(all_warnings),
    }

    sources = []
    for result in results:
        item = {
            "source": f"rules/{result.relative_path.as_posix()}",
            "category": result.category,
            "classification": result.classification,
            "counts": {name: len(payload) for name, payload in result.outputs.items()},
            "dist": path_map[result.relative_path.as_posix()],
        }
        if result.warnings:
            item["warnings"] = result.warnings
        sources.append(item)

    return {
        "summary": summary,
        "sources": sources,
        "warnings": all_warnings,
    }


def run_build() -> int:
    source_files = iter_source_files()
    validate_source_files(source_files)
    validate_source_comment_language(source_files)

    reset_output_roots()
    results: list[SourceBuildResult] = []
    path_map: dict[str, dict[str, str]] = {}

    for source_file in source_files:
        result = build_source(source_file)
        relative_key = result.relative_path.as_posix()
        path_map[relative_key] = write_outputs(result)
        results.append(result)
        counts = result.outputs
        print(
            "[BUILD] "
            f"rules/{relative_key} -> {result.classification} "
            f"(surge rules={len(counts['surge_rules'])}, "
            f"mihomo classical={len(counts['mihomo_classical'])})"
        )
        for message in result.warnings:
            print(f"[WARN] {message}")

    report = build_report(results, path_map)
    (DIST_ROOT / "build-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        "[DONE] "
        f"共处理 {report['summary']['total_sources']} 个源文件，"
        f"{report['summary']['total_warnings']} 条 warning。"
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="构建 Surge 与 Mihomo 规则产物。")
    parser.add_argument(
        "--sync-upstream",
        action="store_true",
        help="在重建 dist 前先刷新 rules/upstream 快照",
    )
    return parser.parse_args()


def configure_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None or not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except ValueError:
            continue


def aws_snapshots_need_sync() -> bool:
    if not AWS_UPSTREAM_BOOTSTRAP_PATH.exists():
        return True
    expected_snapshot_paths = [
        RULES_ROOT / "upstream" / snapshot.path
        for snapshot in sync_upstream_rules.AWS_REGION_SNAPSHOTS
    ]
    for path in expected_snapshot_paths:
        if not path.exists():
            return True
        if "Placeholder file kept in repo" in read_text(path):
            return True
    try:
        payload = json.loads(read_text(AWS_UPSTREAM_BOOTSTRAP_PATH))
    except json.JSONDecodeError:
        return True
    return isinstance(payload, dict) and payload.get("syncToken") == "bootstrap"


def alicloud_snapshots_need_sync() -> bool:
    if not sync_upstream_rules.has_alicloud_credentials():
        return False

    expected_snapshot_paths: list[Path] = []
    for snapshot in sync_upstream_rules.ALICLOUD_REGION_SNAPSHOTS:
        expected_snapshot_paths.append(RULES_ROOT / "upstream" / snapshot.path)
        expected_snapshot_paths.append(RULES_ROOT / "upstream" / snapshot.ssh_path)
    for path in expected_snapshot_paths:
        if not path.exists():
            return True
        if "Placeholder file kept in repo" in read_text(path):
            return True

    if not ALICLOUD_UPSTREAM_BOOTSTRAP_PATH.exists():
        return True
    try:
        payload = json.loads(read_text(ALICLOUD_UPSTREAM_BOOTSTRAP_PATH))
    except json.JSONDecodeError:
        return True
    return isinstance(payload, dict) and payload.get("syncToken") == "bootstrap"


def main() -> int:
    configure_stdio()
    args = parse_args()
    try:
        should_sync_upstream = (
            args.sync_upstream
            or os.environ.get("RULEMESH_SYNC_UPSTREAM") == "1"
            or os.environ.get("SURGE_CONFIG_SYNC_UPSTREAM") == "1"
            or aws_snapshots_need_sync()
            or alicloud_snapshots_need_sync()
        )
        if should_sync_upstream:
            sync_status = sync_upstream_rules.main()
            if sync_status != 0:
                return sync_status
        return run_build()
    except BuildError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
