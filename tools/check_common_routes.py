"""检查常用业务的域名首条命中；不替代真实 IP、DNS 出口或手机业务验收。"""
from __future__ import annotations

import argparse
import fnmatch
import json
from functools import lru_cache
from pathlib import Path

import check_private_dns_precedence as parser

ROOT = Path(__file__).resolve().parents[1]
CASES = Path(__file__).with_name("common_route_cases.json")
MARKER = "# RuleMesh 日常连通性基线：2026-09-16"
PRIVATE_NAMES = {f"rulemesh-substore-mihomo-flclash-{client}.yaml" for client in ("android", "desktop")}


def split_rule(text: str) -> list[str]:
    parts, start, depth = [], 0, 0
    for i, char in enumerate(text):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(text[start:i].strip())
            start = i + 1
        if depth < 0:
            raise ValueError("规则括号不平衡")
    if depth:
        raise ValueError("规则括号不平衡")
    parts.append(text[start:].strip())
    return parts


def matches(rule: str, domain: str, process: str, network: str = "tcp", port: int = 443) -> bool:
    parts = split_rule(rule)
    kind, value = parts[0], parts[1] if len(parts) > 1 else ""
    if kind in {"AND", "OR", "NOT"}:
        if not (value.startswith("(") and value.endswith(")")):
            raise ValueError("逻辑规则缺少条件列表")
        children = split_rule(value[1:-1])
        if not children or any(not (s.startswith("(") and s.endswith(")")) for s in children):
            raise ValueError("逻辑规则条件格式错误")
        outcomes = [matches(s[1:-1], domain, process, network, port) for s in children]
        if kind == "NOT":
            if len(outcomes) != 1:
                raise ValueError("NOT 必须只有一个条件")
            return not outcomes[0]
        return all(outcomes) if kind == "AND" else any(outcomes)
    if kind in {"MATCH", "FINAL"}:
        return True
    if kind == "DOMAIN":
        return domain == value.lower()
    if kind == "DOMAIN-SUFFIX":
        return domain == value.lower() or domain.endswith("." + value.lower())
    if kind == "DOMAIN-KEYWORD":
        return value.lower() in domain
    if kind == "DOMAIN-WILDCARD":
        return fnmatch.fnmatchcase(domain, value.lower())
    if kind == "PROCESS-NAME":
        return process == value
    if kind == "NETWORK":
        return network.lower() == value.lower()
    if kind == "DST-PORT":
        return str(port) == value
    if kind in {"IP-CIDR", "IP-CIDR6", "GEOIP", "IP-ASN"}:
        # 用例只覆盖域名阶段，没有伪造真实解析地址；仅允许明确不触发解析的 IP 条件。
        if "no-resolve" not in parts:
            raise ValueError("域名审计无法判定会触发解析的 IP 规则")
        return False
    raise ValueError("域名审计遇到不支持的规则类型")


@lru_cache(maxsize=128)
def provider_rules(path: Path) -> tuple[str, ...]:
    if not path.is_file():
        raise ValueError("规则产物缺失；先完成构建再执行检查")
    return tuple(parser._scalar(s[4:]) for s in path.read_text("utf-8").splitlines() if s.startswith("  - "))


def route(lines: list[str], domain: str, process: str, network: str = "tcp") -> tuple[str, str]:
    providers = parser._parse_mihomo_providers(lines)
    for _, fields in parser._parse_mihomo_rules(lines):
        text = ",".join(fields)
        parts = split_rule(text)
        target = parts[-2] if parts[-1] == "no-resolve" else parts[-1]
        if parts[0] == "RULE-SET":
            identifier = parts[1]
            if identifier not in providers:
                raise ValueError("规则集未注册")
            relative = parser._approved_public_path(providers[identifier][1])
            if not relative or not relative.startswith("/dist/mihomo/classical/"):
                raise ValueError("规则集不是可核对的本仓库 classical 产物")
            candidates = provider_rules(ROOT / relative.lstrip("/"))
            hit = any(matches(r, domain, process, network) for r in candidates)
            reason = identifier
        else:
            hit = matches(",".join(parts[:-1]) if parts[-1] != "no-resolve" else ",".join(parts[:-2] + ["no-resolve"]), domain, process, network)
            reason = parts[0]
        if hit:
            return target, reason
    raise ValueError("配置没有匹配到最终规则")


def audit(path: Path, lines: list[str], cases: list[dict]) -> list[dict]:
    if not cases:
        raise ValueError("常用业务用例不能为空")
    targets = {p[1]: p[2] for _, p in parser._parse_mihomo_rules(lines) if p[0] == "RULE-SET" and len(p) >= 3}
    results = []
    for case in cases:
        expected = case["expected"]
        target = "DIRECT" if expected == "DIRECT" else targets.get(expected)
        for network in ("tcp", "udp"):
            actual, reason = route(lines, case["domain"].lower().rstrip("."), case.get("process", "com.android.chrome"), network)
            # 不输出实际策略名、内联端点或配置正文。
            results.append({"service": case["service"], "domain": case["domain"], "network": network,
                            "expected_role": expected, "passed": target is not None and actual == target,
                            "first_match": reason, "actual_direct": actual == "DIRECT"})
    return results


def profile_contract(path: Path, lines: list[str]) -> list[str]:
    if path.name not in PRIVATE_NAMES:
        return []
    errors = []
    if lines.count(MARKER) != 1:
        errors.append("日常连通性基线标记必须唯一保留")
    active = [s for s in lines if s.strip() and not s.lstrip().startswith("#")]
    if any("hk_alibaba" in s or "region/hk/alibaba_hk" in s for s in active):
        errors.append("已停用的阿里系强制代理不得恢复调用、注册或解析依赖")
    for _, parts in parser._parse_mihomo_rules(lines):
        if parts[:1] == ["PROCESS-NAME"] and parts[1] in {"com.android.providers.downloads", "com.android.providers.downloads.ui"}:
            errors.append("系统下载管理器必须按目的地分流，不能整体强制代理或直连")
        if "com.eg.android.AlipayGphone" in ",".join(parts):
            errors.append("已恢复正常直连后，不得保留支付宝进程补丁")
    return list(dict.fromkeys(errors))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("profiles", type=Path, nargs="*")
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()
    cases = json.loads(CASES.read_text("utf-8"))
    reports = []
    paths = args.profiles or [p for p in parser.default_paths(ROOT) if p.name in PRIVATE_NAMES | {"mihomo-public.yaml"}]
    for path in paths:
        lines = path.read_text("utf-8").splitlines()
        rows = audit(path, lines, cases)
        reports.append({"profile": path.name, "checks": len(rows), "passed": sum(r["passed"] for r in rows),
                        "failures": [r for r in rows if not r["passed"]], "contract_errors": profile_contract(path, lines)})
    if args.report:
        args.report.write_text(json.dumps(reports, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(reports, ensure_ascii=False))
    return int(any(r["failures"] or r["contract_errors"] for r in reports))


if __name__ == "__main__":
    raise SystemExit(main())
