#!/usr/bin/env python3
"""将选定的上游规则快照同步到 rules/upstream/。"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_ROOT = ROOT / "rules" / "upstream"
USER_AGENT = "rulemesh-upstream-sync/1.0"
AWS_IP_RANGES_URL = "https://ip-ranges.amazonaws.com/ip-ranges.json"
ALICLOUD_PUBLIC_IP_DOC_URL = (
    "https://help.aliyun.com/zh/eip/developer-reference/"
    "api-vpc-2016-04-28-describepublicipaddress-eips"
)
ALICLOUD_VPC_ENDPOINT_DOC_URL = (
    "https://www.alibabacloud.com/help/en/vpc/developer-reference/"
    "api-vpc-2016-04-28-endpoint"
)
ALICLOUD_API_VERSION = "2016-04-28"
ALICLOUD_ACTION = "DescribePublicIpAddress"
LOCAL_CONFIG_PATH = ROOT / ".rulemesh.local.json"
MAX_FAILURES_IN_WEBHOOK = 8
ONEPASSWORD_PORTS_DOMAINS_URL = "https://support.1password.com/ports-domains/"
ONEPASSWORD_CORE_PATH = Path("onepassword/core_domains.list")
ONEPASSWORD_CORE_TITLE = "1Password 核心连接域名"
DOMAIN_HOST_PATTERN = re.compile(
    r"(?i)(?:\*\.)?(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}"
)
ONEPASSWORD_DOMAIN_PATTERN = DOMAIN_HOST_PATTERN
CHAINLIST_RPCS_URL = "https://chainlist.org/rpcs.json"
CHAINLIST_REPO_URL = "https://github.com/DefiLlama/chainlist"
CHAINLIST_RESOURCE_PATH = Path("chainlist/rpcs.json")
ONEPASSWORD_RULE_ORDER = (
    ("DOMAIN-SUFFIX", "1password.com"),
    ("DOMAIN-SUFFIX", "1password.ca"),
    ("DOMAIN-SUFFIX", "1password.eu"),
    ("DOMAIN-SUFFIX", "1passwordservices.com"),
    ("DOMAIN-SUFFIX", "1passwordusercontent.com"),
    ("DOMAIN-SUFFIX", "1passwordusercontent.ca"),
    ("DOMAIN-SUFFIX", "1passwordusercontent.eu"),
    ("DOMAIN", "app-updates.agilebits.com"),
    ("DOMAIN-SUFFIX", "1infra.net"),
    ("DOMAIN", "cache.agilebits.com"),
)
ONEPASSWORD_REQUIRED_RULES = frozenset(
    {
        "DOMAIN-SUFFIX,1password.com",
        "DOMAIN-SUFFIX,1passwordservices.com",
        "DOMAIN-SUFFIX,1passwordusercontent.com",
        "DOMAIN,app-updates.agilebits.com",
        "DOMAIN-SUFFIX,1infra.net",
        "DOMAIN,cache.agilebits.com",
    }
)
SYNC_HELPER_FUNCTIONS = frozenset({"sync_one"})


@dataclass(frozen=True)
class UpstreamFile:
    path: Path
    url: str


@dataclass(frozen=True)
class AwsRegionSnapshot:
    path: Path
    regions: tuple[str, ...]
    title: str


@dataclass(frozen=True)
class AlicloudCredentials:
    access_key_id: str
    access_key_secret: str
    security_token: str | None = None


@dataclass(frozen=True)
class AlicloudRegionSnapshot:
    path: Path
    ssh_path: Path
    metadata_path: Path
    region_id: str
    endpoint: str
    title: str


@dataclass(frozen=True)
class ChainlistRpcSnapshot:
    path: Path
    chain_id: int
    title: str
    preserve_hosts: tuple[str, ...] = ()


@dataclass(frozen=True)
class FeishuWebhookConfig:
    url: str
    secret: str | None = None


@dataclass(frozen=True)
class UpstreamFailure:
    source: str
    resource: str
    url: str
    category: str
    detail: str


@dataclass(frozen=True)
class SyncTask:
    name: str
    runner: Callable[[list["UpstreamFailure"]], tuple[int, int]]


UPSTREAM_FILES = (
    UpstreamFile(
        Path("loyalsoldier/direct.txt"),
        "https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/direct.txt",
    ),
    UpstreamFile(
        Path("loyalsoldier/cncidr.txt"),
        "https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/cncidr.txt",
    ),
    UpstreamFile(
        Path("loyalsoldier/gfw.txt"),
        "https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/gfw.txt",
    ),
    UpstreamFile(
        Path("loyalsoldier/tld-not-cn.txt"),
        "https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/tld-not-cn.txt",
    ),
    UpstreamFile(
        Path("loyalsoldier/telegramcidr.txt"),
        "https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/telegramcidr.txt",
    ),
    UpstreamFile(
        Path("blackmatrix7/bilibili.list"),
        "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/BiliBili/BiliBili.list",
    ),
    UpstreamFile(
        Path("blackmatrix7/bytedance.list"),
        "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/ByteDance/ByteDance.list",
    ),
    UpstreamFile(
        Path("blackmatrix7/cryptocurrency.list"),
        "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Cryptocurrency/Cryptocurrency.list",
    ),
    UpstreamFile(
        Path("blackmatrix7/douyin.list"),
        "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/DouYin/DouYin.list",
    ),
    UpstreamFile(
        Path("blackmatrix7/google_fcm.list"),
        "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/GoogleFCM/GoogleFCM.list",
    ),
    UpstreamFile(
        Path("blackmatrix7/global_media.list"),
        "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/GlobalMedia/GlobalMedia.list",
    ),
    UpstreamFile(
        Path("blackmatrix7/microsoft.list"),
        "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Microsoft/Microsoft.list",
    ),
    UpstreamFile(
        Path("blackmatrix7/netease_music.list"),
        "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/NetEaseMusic/NetEaseMusic.list",
    ),
    UpstreamFile(
        Path("blackmatrix7/onedrive.list"),
        "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/OneDrive/OneDrive.list",
    ),
    UpstreamFile(
        Path("blackmatrix7/openai.list"),
        "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/OpenAI/OpenAI.list",
    ),
    UpstreamFile(
        Path("blackmatrix7/youtube.list"),
        "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/YouTube/YouTube.list",
    ),
)

AWS_JSON_PATH = Path("aws/ip-ranges.json")
AWS_REGION_SNAPSHOTS = (
    AwsRegionSnapshot(
        path=Path("aws/hk_ipv4.txt"),
        regions=("ap-east-1",),
        title="AWS 香港 IPv4（ap-east-1）",
    ),
    AwsRegionSnapshot(
        path=Path("aws/tokyo_ipv4.txt"),
        regions=("ap-northeast-1",),
        title="AWS 东京 IPv4（ap-northeast-1）",
    ),
    AwsRegionSnapshot(
        path=Path("aws/osaka_ipv4.txt"),
        regions=("ap-northeast-3",),
        title="AWS 大阪 IPv4（ap-northeast-3）",
    ),
    AwsRegionSnapshot(
        path=Path("aws/seoul_ipv4.txt"),
        regions=("ap-northeast-2",),
        title="AWS 首尔 IPv4（ap-northeast-2）",
    ),
    AwsRegionSnapshot(
        path=Path("aws/taipei_ipv4.txt"),
        regions=("ap-east-2",),
        title="AWS 台北 IPv4（ap-east-2）",
    ),
)

ALICLOUD_REGION_SNAPSHOTS = (
    AlicloudRegionSnapshot(
        path=Path("alicloud/hk_ipv4.txt"),
        ssh_path=Path("alicloud/hk_ssh22.txt"),
        metadata_path=Path("alicloud/hk_ipv4.json"),
        region_id="cn-hongkong",
        endpoint="vpc.cn-hongkong.aliyuncs.com",
        title="阿里云香港 IPv4（cn-hongkong）",
    ),
)

CHAINLIST_RPC_SNAPSHOTS = (
    ChainlistRpcSnapshot(
        path=Path("chainlist/polygon_rpc_domains.list"),
        chain_id=137,
        title="Polygon 主网 RPC 域名累计快照",
        preserve_hosts=(
            "polygon.llamarpc.com",
            "lb.drpc.live",
        ),
    ),
    ChainlistRpcSnapshot(
        path=Path("chainlist/bsc_rpc_domains.list"),
        chain_id=56,
        title="BSC 主网 RPC 域名累计快照",
    ),
)


def decode_text(payload: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "latin-1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", errors="replace")


def normalize_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.endswith("\n"):
        normalized += "\n"
    return normalized


def ordered_unique(items: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not item or item in seen:
            continue
        unique.append(item)
        seen.add(item)
    return unique


def fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def fetch_text(url: str) -> str:
    return normalize_text(decode_text(fetch_bytes(url)))


def read_existing(path: Path) -> str | None:
    if not path.exists():
        return None
    return normalize_text(decode_text(path.read_bytes()))


def write_if_changed(path: Path, text: str) -> bool:
    normalized = normalize_text(text)
    path.parent.mkdir(parents=True, exist_ok=True)

    existing = read_existing(path)
    if existing == normalized:
        return False

    path.write_text(normalized, encoding="utf-8")
    return True


def collapse_whitespace(text: str) -> str:
    return " ".join(text.replace("\r", "\n").split())


def trim_text(text: str, limit: int = 240) -> str:
    collapsed = collapse_whitespace(text)
    if len(collapsed) <= limit:
        return collapsed
    if limit <= 3:
        return collapsed[:limit]
    return collapsed[: limit - 3] + "..."


def format_exception_message(exc: BaseException) -> str:
    message = trim_text(str(exc))
    if message:
        return message
    return exc.__class__.__name__


def classify_fetch_failure(exc: BaseException) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code in (401, 403):
            return "鉴权失败"
        if exc.code == 404:
            return "上游资源不存在"
        if exc.code >= 500:
            return "上游服务异常"
        return f"HTTP {exc.code} 错误"

    lowered = format_exception_message(exc).lower()
    if "timed out" in lowered or "timeout" in lowered:
        return "请求超时"
    if any(
        keyword in lowered
        for keyword in (
            "name or service not known",
            "temporary failure in name resolution",
            "nodename nor servname",
            "getaddrinfo failed",
            "connection refused",
            "connection reset",
            "network is unreachable",
            "no route to host",
            "remote end closed connection",
        )
    ):
        return "上游不可达"
    return "抓取失败"


def classify_alicloud_failure(exc: BaseException) -> str:
    if isinstance(exc, (urllib.error.URLError, TimeoutError, OSError)):
        return classify_fetch_failure(exc)

    lowered = format_exception_message(exc).lower()
    if any(
        keyword in lowered
        for keyword in (
            "signature",
            "security token",
            "invalidaccesskeyid",
            "forbidden",
            "unauthorized",
            "accesskey",
            "authentication",
        )
    ) or "http 401" in lowered or "http 403" in lowered:
        return "鉴权失败"
    if "http 404" in lowered or "not found" in lowered:
        return "上游资源不存在"
    if any(keyword in lowered for keyword in ("json", "payload", "missing")):
        return "返回内容异常"
    return "API 返回异常"


def record_failure(
    failures: list[UpstreamFailure],
    *,
    source: str,
    resource: str,
    url: str,
    category: str,
    detail: str,
) -> None:
    failures.append(
        UpstreamFailure(
            source=source,
            resource=resource,
            url=url,
            category=category,
            detail=trim_text(detail, limit=280),
        )
    )


def load_local_config() -> dict[str, Any]:
    if not LOCAL_CONFIG_PATH.exists():
        return {}

    try:
        raw = decode_text(LOCAL_CONFIG_PATH.read_bytes())
    except OSError as exc:
        print(f"[WARN] {LOCAL_CONFIG_PATH.name} read failed: {exc}", file=sys.stderr)
        return {}

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"[WARN] {LOCAL_CONFIG_PATH.name} parse failed: {exc}", file=sys.stderr)
        return {}

    if not isinstance(payload, dict):
        print(f"[WARN] {LOCAL_CONFIG_PATH.name} must contain a JSON object.", file=sys.stderr)
        return {}
    return payload


def sync_one(item: UpstreamFile, failures: list[UpstreamFailure]) -> tuple[bool, bool]:
    destination = UPSTREAM_ROOT / item.path

    try:
        latest = fetch_text(item.url)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"[WARN] {item.path.as_posix()} fetch failed: {exc}")
        record_failure(
            failures,
            source="通用上游规则",
            resource=item.path.as_posix(),
            url=item.url,
            category=classify_fetch_failure(exc),
            detail=format_exception_message(exc),
        )
        return False, True

    if not latest.strip():
        detail = "上游返回空内容"
        print(f"[WARN] {item.path.as_posix()} fetch failed: {detail}")
        record_failure(
            failures,
            source="通用上游规则",
            resource=item.path.as_posix(),
            url=item.url,
            category="上游内容为空",
            detail=detail,
        )
        return False, True

    if not write_if_changed(destination, latest):
        print(f"[SKIP] {item.path.as_posix()}")
        return False, False

    print(f"[UPDATE] {item.path.as_posix()}")
    return True, False


def sync_generic_upstreams(failures: list[UpstreamFailure]) -> tuple[int, int]:
    changed = 0
    failed = 0
    for item in UPSTREAM_FILES:
        updated, fetch_failed = sync_one(item, failures)
        changed += int(updated)
        failed += int(fetch_failed)
    return changed, failed


def extract_domain_candidates(text: str) -> list[str]:
    return ordered_unique(
        [
            match.group(0).lower().lstrip("*.").rstrip(".")
            for match in ONEPASSWORD_DOMAIN_PATTERN.finditer(text)
        ]
    )


def has_domain_or_subdomain(candidates: set[str], domain: str) -> bool:
    return domain in candidates or any(candidate.endswith(f".{domain}") for candidate in candidates)


def build_onepassword_core_rules(raw_text: str) -> list[str]:
    candidates = set(extract_domain_candidates(raw_text))
    rules: list[str] = []

    for token, value in ONEPASSWORD_RULE_ORDER:
        if token == "DOMAIN-SUFFIX":
            if has_domain_or_subdomain(candidates, value):
                rules.append(f"{token},{value}")
            continue

        if value in candidates:
            rules.append(f"{token},{value}")

    missing = sorted(rule for rule in ONEPASSWORD_REQUIRED_RULES if rule not in rules)
    if missing:
        raise ValueError("1Password 官方页面缺少核心域名: " + ", ".join(missing))

    return rules


def build_onepassword_snapshot_text(rules: list[str]) -> str:
    synced_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    lines = [
        f"# 来源: {ONEPASSWORD_PORTS_DOMAINS_URL}",
        f"# 标题: {ONEPASSWORD_CORE_TITLE}",
        f"# 同步时间: {synced_at}",
        "# 维护边界: 仅自动保留 1Password 官方自有核心域名与更新/基础设施端点。",
        "# 排除项: 不自动并入 Watchtower、Fastmail、Brex、Privacy Cards 等第三方依赖域名。",
        f"# 规则数量: {len(rules)}",
        "",
    ]
    lines.extend(rules)
    lines.append("")
    return "\n".join(lines)


def parse_domain_hosts_from_rule_text(text: str) -> list[str]:
    hosts: list[str] = []
    for raw in normalize_text(text).splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("DOMAIN,"):
            candidate = stripped.split(",", 1)[1].strip().lower().rstrip(".")
        elif stripped.startswith("DOMAIN-WILDCARD,*."):
            candidate = stripped.split(",", 1)[1].strip().lower()
            candidate = candidate[2:].rstrip(".")
        else:
            continue
        if DOMAIN_HOST_PATTERN.fullmatch(candidate):
            hosts.append(candidate)
    return ordered_unique(hosts)


def normalize_chainlist_rpc_host(url: str) -> str | None:
    raw_url = url.strip()
    if not raw_url:
        return None
    try:
        parsed = urllib.parse.urlsplit(raw_url)
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"http", "https", "ws", "wss"}:
        return None
    if not parsed.hostname:
        return None
    host = parsed.hostname.lower().rstrip(".")
    if not DOMAIN_HOST_PATTERN.fullmatch(host):
        return None
    return host


def extract_chainlist_rpc_hosts(payload: object, chain_id: int) -> list[str]:
    if not isinstance(payload, list):
        raise ValueError("Chainlist payload 不是数组")

    chain_entry = next(
        (
            entry
            for entry in payload
            if isinstance(entry, dict) and entry.get("chainId") == chain_id
        ),
        None,
    )
    if chain_entry is None:
        raise ValueError(f"Chainlist 缺少 chainId={chain_id} 的链定义")

    rpc_entries = chain_entry.get("rpc")
    if not isinstance(rpc_entries, list):
        raise ValueError(f"chainId={chain_id} 的 rpc 字段不是数组")

    hosts: list[str] = []
    for item in rpc_entries:
        if isinstance(item, str):
            url = item
        elif isinstance(item, dict) and isinstance(item.get("url"), str):
            url = item["url"]
        else:
            continue
        host = normalize_chainlist_rpc_host(url)
        if host:
            hosts.append(host)
    return ordered_unique(hosts)


def merge_chainlist_rpc_hosts(
    current_hosts: list[str],
    existing_hosts: list[str],
    preserve_hosts: tuple[str, ...] = (),
) -> list[str]:
    merged = {
        host.lower()
        for host in (*current_hosts, *existing_hosts, *preserve_hosts)
        if DOMAIN_HOST_PATTERN.fullmatch(host.lower())
    }
    return sorted(merged)


def build_chainlist_rpc_rules(hosts: list[str]) -> list[str]:
    rules: list[str] = []
    for host in hosts:
        rules.append(f"DOMAIN,{host}")
        rules.append(f"DOMAIN-WILDCARD,*.{host}")
    return rules


def build_chainlist_rpc_snapshot_text(
    snapshot: ChainlistRpcSnapshot,
    current_hosts: list[str],
    cumulative_hosts: list[str],
) -> str:
    synced_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    lines = [
        f"# 来源: {CHAINLIST_RPCS_URL}",
        f"# 上游项目: {CHAINLIST_REPO_URL}",
        f"# 标题: {snapshot.title}",
        f"# chainId: {snapshot.chain_id}",
        "# 维护策略: 只增不减；保留历史已收录主机名，避免上游日常波动导致覆盖面回撤。",
        "# 规则展开: 每个主机名同时生成 DOMAIN 与 DOMAIN-WILDCARD，统一收敛为节点选择入口。",
        f"# 本次抓取主机数: {len(current_hosts)}",
        f"# 累计主机数: {len(cumulative_hosts)}",
        f"# 同步时间: {synced_at}",
        "",
    ]
    lines.extend(build_chainlist_rpc_rules(cumulative_hosts))
    lines.append("")
    return "\n".join(lines)


def sync_chainlist_rpc_snapshots(failures: list[UpstreamFailure]) -> tuple[int, int]:
    try:
        raw_text = fetch_text(CHAINLIST_RPCS_URL)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"[WARN] {CHAINLIST_RESOURCE_PATH.as_posix()} fetch failed: {exc}")
        record_failure(
            failures,
            source="Chainlist RPC 快照",
            resource=CHAINLIST_RESOURCE_PATH.as_posix(),
            url=CHAINLIST_RPCS_URL,
            category=classify_fetch_failure(exc),
            detail=format_exception_message(exc),
        )
        return 0, 1

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        print(f"[WARN] {CHAINLIST_RESOURCE_PATH.as_posix()} parse failed: {exc}")
        record_failure(
            failures,
            source="Chainlist RPC 快照",
            resource=CHAINLIST_RESOURCE_PATH.as_posix(),
            url=CHAINLIST_RPCS_URL,
            category="返回内容异常",
            detail=format_exception_message(exc),
        )
        return 0, 1

    changed = 0
    failed = 0

    for snapshot in CHAINLIST_RPC_SNAPSHOTS:
        try:
            current_hosts = extract_chainlist_rpc_hosts(payload, snapshot.chain_id)
        except ValueError as exc:
            detail = format_exception_message(exc)
            print(f"[WARN] {snapshot.path.as_posix()} parse failed: {detail}")
            record_failure(
                failures,
                source="Chainlist RPC 快照",
                resource=snapshot.path.as_posix(),
                url=CHAINLIST_RPCS_URL,
                category="返回内容异常",
                detail=detail,
            )
            failed += 1
            continue

        if not current_hosts:
            detail = f"chainId={snapshot.chain_id} 的 RPC 主机名为空"
            print(f"[WARN] {snapshot.path.as_posix()} sync failed: {detail}")
            record_failure(
                failures,
                source="Chainlist RPC 快照",
                resource=snapshot.path.as_posix(),
                url=CHAINLIST_RPCS_URL,
                category="链 RPC 主机名为空",
                detail=detail,
            )
            failed += 1
            continue

        destination = UPSTREAM_ROOT / snapshot.path
        existing_text = read_existing(destination) or ""
        existing_hosts = parse_domain_hosts_from_rule_text(existing_text)
        cumulative_hosts = merge_chainlist_rpc_hosts(
            current_hosts,
            existing_hosts,
            snapshot.preserve_hosts,
        )
        rendered = build_chainlist_rpc_snapshot_text(
            snapshot,
            current_hosts,
            cumulative_hosts,
        )
        if write_if_changed(destination, rendered):
            print(f"[UPDATE] {snapshot.path.as_posix()}")
            changed += 1
        else:
            print(f"[SKIP] {snapshot.path.as_posix()}")

    return changed, failed


def sync_onepassword_snapshot(failures: list[UpstreamFailure]) -> tuple[int, int]:
    try:
        raw_text = fetch_text(ONEPASSWORD_PORTS_DOMAINS_URL)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"[WARN] {ONEPASSWORD_CORE_PATH.as_posix()} fetch failed: {exc}")
        record_failure(
            failures,
            source="1Password 官方支持页",
            resource=ONEPASSWORD_CORE_PATH.as_posix(),
            url=ONEPASSWORD_PORTS_DOMAINS_URL,
            category=classify_fetch_failure(exc),
            detail=format_exception_message(exc),
        )
        return 0, 1

    try:
        rules = build_onepassword_core_rules(raw_text)
    except ValueError as exc:
        detail = format_exception_message(exc)
        print(f"[WARN] {ONEPASSWORD_CORE_PATH.as_posix()} parse failed: {detail}")
        record_failure(
            failures,
            source="1Password 官方支持页",
            resource=ONEPASSWORD_CORE_PATH.as_posix(),
            url=ONEPASSWORD_PORTS_DOMAINS_URL,
            category="核心域名缺失" if "核心域名" in detail else "返回内容异常",
            detail=detail,
        )
        return 0, 1

    rendered = build_onepassword_snapshot_text(rules)
    if write_if_changed(UPSTREAM_ROOT / ONEPASSWORD_CORE_PATH, rendered):
        print(f"[UPDATE] {ONEPASSWORD_CORE_PATH.as_posix()}")
        return 1, 0

    print(f"[SKIP] {ONEPASSWORD_CORE_PATH.as_posix()}")
    return 0, 0


def validate_aws_payload(data: object) -> dict[str, object]:
    if not isinstance(data, dict):
        raise ValueError("AWS payload is not a JSON object")
    prefixes = data.get("prefixes")
    if not isinstance(prefixes, list):
        raise ValueError("AWS payload is missing the prefixes array")
    return data


def collect_aws_ipv4_prefixes(
    payload: dict[str, object],
    regions: tuple[str, ...],
) -> tuple[list[str], list[tuple[str, list[str]]]]:
    entries = payload["prefixes"]
    assert isinstance(entries, list)

    per_region: list[tuple[str, list[str]]] = []
    combined: list[str] = []

    for region in regions:
        region_prefixes = ordered_unique(
            [
                ip_prefix.strip()
                for entry in entries
                if isinstance(entry, dict)
                and entry.get("region") == region
                and isinstance(entry.get("ip_prefix"), str)
                and (ip_prefix := entry["ip_prefix"]).strip()
            ]
        )
        per_region.append((region, region_prefixes))
        combined.extend(region_prefixes)

    return ordered_unique(combined), per_region


def build_aws_snapshot_text(payload: dict[str, object], snapshot: AwsRegionSnapshot) -> str:
    prefixes, per_region = collect_aws_ipv4_prefixes(payload, snapshot.regions)
    sync_token = str(payload.get("syncToken", "unknown"))
    create_date = str(payload.get("createDate", "unknown"))

    lines = [
        f"# 来源: {AWS_IP_RANGES_URL}",
        f"# 标题: {snapshot.title}",
        f"# 同步令牌: {sync_token}",
        f"# 上游创建时间: {create_date}",
        f"# 区域: {', '.join(snapshot.regions)}",
        "# 范围: 所选 AWS 区域公开发布的全部 IPv4 前缀。",
        f"# IPv4 前缀数量: {len(prefixes)}",
    ]
    lines.extend(
        f"# {region}: {len(region_prefixes)} 条前缀"
        for region, region_prefixes in per_region
    )
    lines.append("")
    lines.extend(prefixes)
    lines.append("")
    return "\n".join(lines)


def sync_aws_snapshots(failures: list[UpstreamFailure]) -> tuple[int, int]:
    try:
        raw_text = fetch_text(AWS_IP_RANGES_URL)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"[WARN] aws/ip-ranges.json fetch failed: {exc}")
        record_failure(
            failures,
            source="AWS 官方地址池",
            resource=AWS_JSON_PATH.as_posix(),
            url=AWS_IP_RANGES_URL,
            category=classify_fetch_failure(exc),
            detail=format_exception_message(exc),
        )
        return 0, 1

    try:
        payload = validate_aws_payload(json.loads(raw_text))
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"[WARN] aws/ip-ranges.json parse failed: {exc}")
        record_failure(
            failures,
            source="AWS 官方地址池",
            resource=AWS_JSON_PATH.as_posix(),
            url=AWS_IP_RANGES_URL,
            category="返回内容异常",
            detail=format_exception_message(exc),
        )
        return 0, 1

    prefixes = payload.get("prefixes")
    assert isinstance(prefixes, list)
    if not prefixes:
        detail = "AWS payload prefixes 数组为空"
        print(f"[WARN] aws/ip-ranges.json parse failed: {detail}")
        record_failure(
            failures,
            source="AWS 官方地址池",
            resource=AWS_JSON_PATH.as_posix(),
            url=AWS_IP_RANGES_URL,
            category="上游内容为空",
            detail=detail,
        )
        return 0, 1

    changed = 0
    failed = 0

    if write_if_changed(
        UPSTREAM_ROOT / AWS_JSON_PATH,
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
    ):
        print(f"[UPDATE] {AWS_JSON_PATH.as_posix()}")
        changed += 1
    else:
        print(f"[SKIP] {AWS_JSON_PATH.as_posix()}")

    for snapshot in AWS_REGION_SNAPSHOTS:
        snapshot_prefixes, _ = collect_aws_ipv4_prefixes(payload, snapshot.regions)
        if not snapshot_prefixes:
            detail = f"{', '.join(snapshot.regions)} 在 AWS payload 中没有任何 IPv4 前缀"
            print(f"[WARN] {snapshot.path.as_posix()} sync failed: {detail}")
            record_failure(
                failures,
                source="AWS 区域快照",
                resource=snapshot.path.as_posix(),
                url=AWS_IP_RANGES_URL,
                category="区域前缀为空",
                detail=detail,
            )
            failed += 1
            continue

        rendered = build_aws_snapshot_text(payload, snapshot)
        if write_if_changed(UPSTREAM_ROOT / snapshot.path, rendered):
            print(f"[UPDATE] {snapshot.path.as_posix()}")
            changed += 1
        else:
            print(f"[SKIP] {snapshot.path.as_posix()}")

    return changed, failed


def env_value(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value and value.strip():
            return value.strip()
    return None


def resolve_feishu_webhook_config() -> FeishuWebhookConfig | None:
    local_payload = load_local_config()
    local_alert = local_payload.get("upstream_alert")
    local_url = None
    local_secret = None
    if isinstance(local_alert, dict):
        raw_url = local_alert.get("feishu_webhook_url")
        raw_secret = local_alert.get("feishu_secret")
        if isinstance(raw_url, str) and raw_url.strip():
            local_url = raw_url.strip()
        if isinstance(raw_secret, str) and raw_secret.strip():
            local_secret = raw_secret.strip()

    webhook_url = env_value(
        "RULEMESH_UPSTREAM_ALERT_FEISHU_WEBHOOK_URL",
        "RULEMESH_FEISHU_WEBHOOK_URL",
    ) or local_url
    if not webhook_url:
        return None

    webhook_secret = env_value(
        "RULEMESH_UPSTREAM_ALERT_FEISHU_SECRET",
        "RULEMESH_FEISHU_WEBHOOK_SECRET",
    ) or local_secret
    return FeishuWebhookConfig(url=webhook_url, secret=webhook_secret)


def build_feishu_sign(timestamp: str, secret: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def build_feishu_webhook_payload(
    message: str,
    config: FeishuWebhookConfig,
    *,
    timestamp: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "msg_type": "text",
        "content": {"text": message},
    }
    if config.secret:
        effective_timestamp = timestamp or str(int(dt.datetime.now(dt.timezone.utc).timestamp()))
        payload["timestamp"] = effective_timestamp
        payload["sign"] = build_feishu_sign(effective_timestamp, config.secret)
    return payload


def validate_feishu_webhook_response(body: str) -> None:
    stripped = body.strip()
    if not stripped:
        return

    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return

    if not isinstance(payload, dict):
        return

    code = payload.get("code")
    status_code = payload.get("StatusCode")
    if code in (None, 0) and status_code in (None, 0):
        return

    message = payload.get("msg") or payload.get("StatusMessage") or stripped
    raise ValueError(f"Feishu webhook returned an error: {message}")


def send_feishu_webhook_message(
    config: FeishuWebhookConfig,
    message: str,
    *,
    timestamp: str | None = None,
) -> None:
    payload = build_feishu_webhook_payload(message, config, timestamp=timestamp)
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        config.url,
        data=body,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        response_body = decode_text(response.read())
    validate_feishu_webhook_response(response_body)


def build_upstream_failure_message(failures: list[UpstreamFailure]) -> str:
    now_text = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    host = os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "unknown"

    lines = [
        "RuleMesh upstream 告警",
        f"时间: {now_text}",
        f"主机: {host}",
        f"失败数: {len(failures)}",
        "说明: 本次已保留旧快照，没有用异常上游结果覆盖现有文件。",
        "",
    ]

    for index, failure in enumerate(failures[:MAX_FAILURES_IN_WEBHOOK], start=1):
        lines.append(f"{index}. [{failure.category}] {failure.resource}")
        lines.append(f"来源: {failure.source}")
        lines.append(f"详情: {failure.detail}")
        lines.append(f"URL: {failure.url}")
        lines.append("")

    remaining = len(failures) - MAX_FAILURES_IN_WEBHOOK
    if remaining > 0:
        lines.append(f"其余 {remaining} 项失败已省略，请查看同步日志。")

    return "\n".join(lines).rstrip() + "\n"


def send_upstream_failure_alerts(failures: list[UpstreamFailure]) -> None:
    if not failures:
        return

    config = resolve_feishu_webhook_config()
    if config is None:
        print("[WARN] upstream failures detected but Feishu webhook is not configured.", file=sys.stderr)
        return

    try:
        send_feishu_webhook_message(config, build_upstream_failure_message(failures))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        print(f"[WARN] upstream failure webhook send failed: {exc}", file=sys.stderr)
        return

    print(f"[INFO] upstream failure webhook sent ({len(failures)} item(s)).")


def upstream_webhook_required() -> bool:
    value = env_value(
        "RULEMESH_UPSTREAM_ALERT_REQUIRED",
        "RULEMESH_REQUIRE_UPSTREAM_WEBHOOK",
    )
    if value is None:
        return False
    return value.lower() in {"1", "true", "yes", "on"}


def ensure_upstream_failure_alerts_sent(failures: list[UpstreamFailure]) -> None:
    if not failures:
        return

    config = resolve_feishu_webhook_config()
    if config is None:
        message = "upstream failures detected but Feishu webhook is not configured."
        print(f"[WARN] {message}", file=sys.stderr)
        if upstream_webhook_required():
            raise RuntimeError(message)
        return

    try:
        send_feishu_webhook_message(config, build_upstream_failure_message(failures))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        print(f"[WARN] upstream failure webhook send failed: {exc}", file=sys.stderr)
        if upstream_webhook_required():
            raise RuntimeError(f"upstream failure webhook send failed: {exc}") from exc
        return

    print(f"[INFO] upstream failure webhook sent ({len(failures)} item(s)).")


def resolve_alicloud_credentials() -> AlicloudCredentials | None:
    access_key_id = env_value(
        "RULEMESH_ALICLOUD_ACCESS_KEY_ID",
        "ALIBABA_CLOUD_ACCESS_KEY_ID",
        "ALICLOUD_ACCESS_KEY_ID",
    )
    access_key_secret = env_value(
        "RULEMESH_ALICLOUD_ACCESS_KEY_SECRET",
        "ALIBABA_CLOUD_ACCESS_KEY_SECRET",
        "ALICLOUD_ACCESS_KEY_SECRET",
    )
    if not access_key_id or not access_key_secret:
        return None

    security_token = env_value(
        "RULEMESH_ALICLOUD_SECURITY_TOKEN",
        "ALIBABA_CLOUD_SECURITY_TOKEN",
        "ALICLOUD_SECURITY_TOKEN",
    )
    return AlicloudCredentials(
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
        security_token=security_token,
    )


def has_alicloud_credentials() -> bool:
    return resolve_alicloud_credentials() is not None


def percent_encode(value: Any) -> str:
    return urllib.parse.quote(str(value), safe="~")


def build_canonical_query(params: dict[str, Any]) -> str:
    return "&".join(
        f"{percent_encode(key)}={percent_encode(value)}"
        for key, value in sorted(params.items())
    )


def sign_alicloud_request(params: dict[str, Any], access_key_secret: str) -> str:
    canonical_query = build_canonical_query(params)
    string_to_sign = f"GET&%2F&{percent_encode(canonical_query)}"
    digest = hmac.new(
        f"{access_key_secret}&".encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


def rpc_timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def api_synced_at() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def parse_alicloud_http_error(exc: urllib.error.HTTPError) -> str:
    try:
        payload = decode_text(exc.read()).strip()
    except OSError:
        payload = ""
    if not payload:
        return f"HTTP {exc.code} {exc.reason}"
    return f"HTTP {exc.code} {exc.reason}: {payload}"


def alicloud_rpc_get(
    snapshot: AlicloudRegionSnapshot,
    credentials: AlicloudCredentials,
    *,
    page_number: int,
    page_size: int,
    ip_version: str,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "Action": ALICLOUD_ACTION,
        "Format": "JSON",
        "Version": ALICLOUD_API_VERSION,
        "AccessKeyId": credentials.access_key_id,
        "SignatureMethod": "HMAC-SHA1",
        "Timestamp": rpc_timestamp(),
        "SignatureVersion": "1.0",
        "SignatureNonce": uuid.uuid4().hex,
        "RegionId": snapshot.region_id,
        "PageNumber": page_number,
        "PageSize": page_size,
        "IpVersion": ip_version,
    }
    if credentials.security_token:
        params["SecurityToken"] = credentials.security_token

    params["Signature"] = sign_alicloud_request(params, credentials.access_key_secret)
    query = build_canonical_query(params)
    url = f"https://{snapshot.endpoint}/?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = decode_text(response.read())
    except urllib.error.HTTPError as exc:
        raise ValueError(parse_alicloud_http_error(exc)) from exc

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Alibaba Cloud API returned invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Alibaba Cloud API payload is not a JSON object")
    return payload


def extract_alicloud_public_ip_prefixes(payload: dict[str, Any]) -> list[str]:
    return ordered_unique(
        [
            item.strip()
            for item in payload.get("publicIpAddress", [])
            if isinstance(item, str) and item.strip()
        ]
    )


def validate_alicloud_page(
    payload: dict[str, Any],
    snapshot: AlicloudRegionSnapshot,
) -> tuple[list[str], int | None, str | None]:
    success = payload.get("Success")
    if success is False:
        message = payload.get("Message") or payload.get("Code") or "unknown error"
        raise ValueError(f"{snapshot.region_id} returned an error: {message}")

    raw_prefixes = payload.get("PublicIpAddress")
    if not isinstance(raw_prefixes, list):
        raise ValueError(f"{snapshot.region_id} payload is missing PublicIpAddress[]")

    prefixes = ordered_unique(
        [item.strip() for item in raw_prefixes if isinstance(item, str) and item.strip()]
    )

    raw_total_count = payload.get("TotalCount")
    total_count: int | None
    if isinstance(raw_total_count, int):
        total_count = raw_total_count
    elif isinstance(raw_total_count, str) and raw_total_count.isdigit():
        total_count = int(raw_total_count)
    else:
        total_count = None

    request_id = payload.get("RequestId")
    if request_id is not None and not isinstance(request_id, str):
        request_id = str(request_id)

    return prefixes, total_count, request_id


def fetch_alicloud_region_snapshot(
    snapshot: AlicloudRegionSnapshot,
    credentials: AlicloudCredentials,
) -> dict[str, Any]:
    page_number = 1
    page_size = 100
    all_prefixes: list[str] = []
    request_ids: list[str] = []
    reported_total_count: int | None = None

    while True:
        page_payload = alicloud_rpc_get(
            snapshot,
            credentials,
            page_number=page_number,
            page_size=page_size,
            ip_version="ipv4",
        )
        page_prefixes, page_total_count, request_id = validate_alicloud_page(
            page_payload,
            snapshot,
        )
        all_prefixes.extend(page_prefixes)
        if request_id:
            request_ids.append(request_id)
        if reported_total_count is None and page_total_count is not None:
            reported_total_count = page_total_count

        if not page_prefixes:
            break
        if reported_total_count is not None and len(ordered_unique(all_prefixes)) >= reported_total_count:
            break
        if len(page_prefixes) < page_size:
            break
        page_number += 1

    prefixes = ordered_unique(all_prefixes)
    return {
        "syncToken": api_synced_at(),
        "source": {
            "api": ALICLOUD_ACTION,
            "apiVersion": ALICLOUD_API_VERSION,
            "docUrl": ALICLOUD_PUBLIC_IP_DOC_URL,
            "endpointDocUrl": ALICLOUD_VPC_ENDPOINT_DOC_URL,
        },
        "endpoint": snapshot.endpoint,
        "regionId": snapshot.region_id,
        "ipVersion": "ipv4",
        "pageSize": page_size,
        "pageCount": page_number,
        "reportedTotalCount": reported_total_count if reported_total_count is not None else len(prefixes),
        "requestIds": request_ids,
        "syncedAt": api_synced_at(),
        "publicIpAddress": prefixes,
    }


def build_alicloud_snapshot_text(
    payload: dict[str, Any],
    snapshot: AlicloudRegionSnapshot,
) -> str:
    prefixes = extract_alicloud_public_ip_prefixes(payload)
    synced_at = str(payload.get("syncedAt", "unknown"))
    reported_total_count = payload.get("reportedTotalCount", len(prefixes))
    page_count = payload.get("pageCount", "unknown")

    lines = [
        f"# 来源文档: {ALICLOUD_PUBLIC_IP_DOC_URL}",
        f"# 终端节点文档: {ALICLOUD_VPC_ENDPOINT_DOC_URL}",
        f"# API: {ALICLOUD_ACTION}",
        f"# 标题: {snapshot.title}",
        f"# 终端节点: {snapshot.endpoint}",
        f"# 区域: {snapshot.region_id}",
        "# 范围: 官方阿里云 API 返回的全部 VPC 公网 IPv4 CIDR 前缀。",
        f"# 同步时间: {synced_at}",
        f"# 抓取页数: {page_count}",
        f"# 上游总数: {reported_total_count}",
        f"# IPv4 前缀数量: {len(prefixes)}",
        "",
    ]
    lines.extend(prefixes)
    lines.append("")
    return "\n".join(lines)


def build_alicloud_ssh_snapshot_text(
    payload: dict[str, Any],
    snapshot: AlicloudRegionSnapshot,
) -> str:
    prefixes = extract_alicloud_public_ip_prefixes(payload)
    synced_at = str(payload.get("syncedAt", "unknown"))
    reported_total_count = payload.get("reportedTotalCount", len(prefixes))
    page_count = payload.get("pageCount", "unknown")

    lines = [
        f"# 来源文档: {ALICLOUD_PUBLIC_IP_DOC_URL}",
        f"# 终端节点文档: {ALICLOUD_VPC_ENDPOINT_DOC_URL}",
        f"# API: {ALICLOUD_ACTION}",
        f"# 标题: {snapshot.title} SSH TCP/22 直连规则",
        f"# 终端节点: {snapshot.endpoint}",
        f"# 区域: {snapshot.region_id}",
        "# 范围: 将官方阿里云香港公网 IPv4 前缀转换为 SSH TCP/22 直连规则。",
        "# 派生自: alicloud/hk_ipv4.txt",
        f"# 同步时间: {synced_at}",
        f"# 抓取页数: {page_count}",
        f"# 上游总数: {reported_total_count}",
        f"# SSH 规则数量: {len(prefixes)}",
        "",
    ]
    lines.extend(f"AND,((IP-CIDR,{prefix}),(DST-PORT,22))" for prefix in prefixes)
    lines.append("")
    return "\n".join(lines)


def sync_alicloud_snapshots(failures: list[UpstreamFailure]) -> tuple[int, int]:
    credentials = resolve_alicloud_credentials()
    if credentials is None:
        detail = (
            "缺少阿里云凭据。请设置 RULEMESH_ALICLOUD_ACCESS_KEY_ID 和 "
            "RULEMESH_ALICLOUD_ACCESS_KEY_SECRET（或标准阿里云环境变量）。"
        )
        print(f"[WARN] alicloud sync failed: {detail}")
        for snapshot in ALICLOUD_REGION_SNAPSHOTS:
            record_failure(
                failures,
                source="阿里云官方 API",
                resource=snapshot.path.as_posix(),
                url=f"https://{snapshot.endpoint}/",
                category="缺少凭据",
                detail=detail,
            )
        return 0, len(ALICLOUD_REGION_SNAPSHOTS)

    changed = 0
    failed = 0

    for snapshot in ALICLOUD_REGION_SNAPSHOTS:
        try:
            payload = fetch_alicloud_region_snapshot(snapshot, credentials)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            print(f"[WARN] {snapshot.path.as_posix()} sync failed: {exc}")
            record_failure(
                failures,
                source="阿里云官方 API",
                resource=snapshot.path.as_posix(),
                url=f"https://{snapshot.endpoint}/",
                category=classify_alicloud_failure(exc),
                detail=format_exception_message(exc),
            )
            failed += 1
            continue

        prefixes = extract_alicloud_public_ip_prefixes(payload)
        if not prefixes:
            detail = f"{snapshot.region_id} 返回的 publicIpAddress 为空"
            print(f"[WARN] {snapshot.path.as_posix()} sync failed: {detail}")
            record_failure(
                failures,
                source="阿里云官方 API",
                resource=snapshot.path.as_posix(),
                url=f"https://{snapshot.endpoint}/",
                category="上游内容为空",
                detail=detail,
            )
            failed += 1
            continue

        metadata_text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        if write_if_changed(UPSTREAM_ROOT / snapshot.metadata_path, metadata_text):
            print(f"[UPDATE] {snapshot.metadata_path.as_posix()}")
            changed += 1
        else:
            print(f"[SKIP] {snapshot.metadata_path.as_posix()}")

        snapshot_text = build_alicloud_snapshot_text(payload, snapshot)
        if write_if_changed(UPSTREAM_ROOT / snapshot.path, snapshot_text):
            print(f"[UPDATE] {snapshot.path.as_posix()}")
            changed += 1
        else:
            print(f"[SKIP] {snapshot.path.as_posix()}")

        ssh_snapshot_text = build_alicloud_ssh_snapshot_text(payload, snapshot)
        if write_if_changed(UPSTREAM_ROOT / snapshot.ssh_path, ssh_snapshot_text):
            print(f"[UPDATE] {snapshot.ssh_path.as_posix()}")
            changed += 1
        else:
            print(f"[SKIP] {snapshot.ssh_path.as_posix()}")

    return changed, failed


SYNC_TASKS = (
    SyncTask(name="generic_upstreams", runner=sync_generic_upstreams),
    SyncTask(name="onepassword", runner=sync_onepassword_snapshot),
    SyncTask(name="chainlist", runner=sync_chainlist_rpc_snapshots),
    SyncTask(name="aws", runner=sync_aws_snapshots),
    SyncTask(name="alicloud", runner=sync_alicloud_snapshots),
)


def main() -> int:
    changed = 0
    failed = 0
    failures: list[UpstreamFailure] = []

    for task in SYNC_TASKS:
        task_changed, task_failed = task.runner(failures)
        changed += task_changed
        failed += task_failed

    if failures:
        ensure_upstream_failure_alerts_sent(failures)

    print(f"[DONE] Updated {changed} file(s); fetch failures: {failed}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
