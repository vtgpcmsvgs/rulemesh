#!/usr/bin/env python3
"""将选定的上游规则快照同步到 rules/upstream/。"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import ipaddress
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
RULEMESH_REPO = "vtgpcmsvgs/rulemesh"
RULEMESH_REPO_URL = f"https://github.com/{RULEMESH_REPO}"
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
ALICLOUD_STABILITY_FETCH_ATTEMPTS = 3
ALICLOUD_FALLBACK_ASNS = (45102, 134963, 24429)
ALICLOUD_LEGACY_IPV4_SEED = (
    "11.51.225.0/24",
    "11.51.226.0/24",
    "45.158.183.0/25",
    "45.158.183.128/25",
    "103.142.8.0/24",
    "103.142.9.0/24",
    "103.142.100.0/24",
    "103.142.101.0/24",
    "103.145.72.0/25",
    "103.145.72.128/25",
    "103.151.206.0/24",
    "103.151.207.0/24",
    "103.183.154.0/24",
    "103.183.155.0/24",
    "122.254.76.0/24",
    "122.254.77.0/24",
    "156.224.138.0/25",
    "156.224.138.128/25",
    "156.226.24.0/22",
    "156.226.28.0/22",
    "185.78.106.0/24",
    "185.78.107.0/24",
    "198.44.244.0/23",
    "198.44.246.0/23",
    "202.61.84.0/24",
    "202.61.85.0/24",
    "202.61.86.0/24",
    "202.61.87.0/24",
)
RIPESTAT_ANNOUNCED_PREFIXES_DOC_URL = (
    "https://stat.ripe.net/docs/data-api/api-endpoints/announced-prefixes"
)
RIPESTAT_ANNOUNCED_PREFIXES_API_URL = (
    "https://stat.ripe.net/data/announced-prefixes/data.json"
)
RIPESTAT_ALICLOUD_IPV4_URL_TEMPLATE = (
    f"{RIPESTAT_ANNOUNCED_PREFIXES_API_URL}?"
    "resource=AS{asn}&min_peers_seeing=1&sourceapp=rulemesh"
)
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
META_RULES_DAT_REPO = "MetaCubeX/meta-rules-dat"
META_RULES_DAT_REPO_URL = f"https://github.com/{META_RULES_DAT_REPO}"
META_RULES_DAT_README_URL = (
    "https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/master/README.md"
)
META_RULES_DAT_GEODATA_SNAPSHOT_PATH = Path("geodata/metacubex_country_mmdb.yaml")
META_RULES_DAT_COUNTRY_MMDB_GITHUB_RELEASE_URL = (
    "https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/country.mmdb"
)
META_RULES_DAT_COUNTRY_MMDB_JSDELIVR_URL = (
    "https://cdn.jsdelivr.net/gh/MetaCubeX/meta-rules-dat@release/country.mmdb"
)
META_RULES_DAT_COUNTRY_MMDB_JSDELIVR_CF_URL = (
    "https://testingcf.jsdelivr.net/gh/MetaCubeX/meta-rules-dat@release/country.mmdb"
)
RULEMESH_GEOIP_RELEASE_TAG = "geoip-country-mmdb"
RULEMESH_GEOIP_ASSET_NAME = "country.mmdb"
RULEMESH_GEOIP_MIRROR_URL = (
    f"{RULEMESH_REPO_URL}/releases/download/"
    f"{RULEMESH_GEOIP_RELEASE_TAG}/{RULEMESH_GEOIP_ASSET_NAME}"
)
META_RULES_DAT_REQUIRED_MARKERS = (
    META_RULES_DAT_COUNTRY_MMDB_GITHUB_RELEASE_URL,
    META_RULES_DAT_COUNTRY_MMDB_JSDELIVR_URL,
    "同 [Loyalsoldier/v2ray-rules-dat]",
)
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
    source_repo: str | None = None
    format_hint: str = "raw"


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
    bgp_path: Path
    bgp_metadata_path: Path
    history_path: Path
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
        Path("blackmatrix7/claude.list"),
        "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Claude/Claude.list",
    ),
    UpstreamFile(
        Path("blackmatrix7/copilot.list"),
        "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Copilot/Copilot.list",
    ),
    UpstreamFile(
        Path("blackmatrix7/gemini.list"),
        "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Gemini/Gemini.list",
    ),
    UpstreamFile(
        Path("blackmatrix7/youtube.list"),
        "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/YouTube/YouTube.list",
    ),
    UpstreamFile(
        Path("skywalkerji/cursor.list"),
        "https://raw.githubusercontent.com/SkywalkerJi/Clash-Rules/master/AI/Cursor.yaml",
        source_repo="SkywalkerJi/Clash-Rules",
        format_hint="clash_yaml_payload",
    ),
    UpstreamFile(
        Path("skywalkerji/trae.list"),
        "https://raw.githubusercontent.com/SkywalkerJi/Clash-Rules/master/AI/Trae.yaml",
        source_repo="SkywalkerJi/Clash-Rules",
        format_hint="clash_yaml_payload",
    ),
    UpstreamFile(
        Path("skywalkerji/windsurf.list"),
        "https://raw.githubusercontent.com/SkywalkerJi/Clash-Rules/master/AI/Windsurf.yaml",
        source_repo="SkywalkerJi/Clash-Rules",
        format_hint="clash_yaml_payload",
    ),
    UpstreamFile(
        Path("skywalkerji/augmentcode.list"),
        "https://raw.githubusercontent.com/SkywalkerJi/Clash-Rules/master/AI/AugmentCode.yaml",
        source_repo="SkywalkerJi/Clash-Rules",
        format_hint="clash_yaml_payload",
    ),
    UpstreamFile(
        Path("accademia/grok.list"),
        "https://raw.githubusercontent.com/Accademia/Additional_Rule_For_Clash/main/Grok/Grok.yaml",
        source_repo="Accademia/Additional_Rule_For_Clash",
        format_hint="clash_yaml_payload",
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
        bgp_path=Path("alicloud/fallback_asns_ipv4.txt"),
        bgp_metadata_path=Path("alicloud/fallback_asns_ipv4.json"),
        history_path=Path("alicloud/ssh22_ipv4_history.txt"),
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


def local_config_value(payload: dict[str, Any], *path: str) -> str | None:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)

    if isinstance(current, str) and current.strip():
        return current.strip()
    return None


def normalize_rule_csv(text: str) -> str:
    stripped = text.strip()
    if not stripped or "," not in stripped:
        return stripped
    return ",".join(part.strip() for part in stripped.split(","))


def normalize_clash_yaml_payload(item: UpstreamFile, text: str) -> str:
    rules: list[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped == "payload:":
            continue
        if stripped.startswith("#"):
            rules.append(stripped)
            continue
        if stripped.startswith("- "):
            rule = normalize_rule_csv(stripped[2:])
            if rule:
                rules.append(rule)
            continue
        raise ValueError(f"{item.path.as_posix()} 存在无法识别的 YAML payload 行：{stripped}")

    if not rules:
        raise ValueError(f"{item.path.as_posix()} 规范化后为空")

    header = [
        f"# 上游来源：{item.url}",
        f"# 上游仓库：{item.source_repo or '未声明'}",
        "# 说明：原始文件为 Clash YAML payload，已自动规范化为普通规则列表。",
        "# 请勿直接编辑，更新请重新执行上游同步。",
        "",
    ]
    return "\n".join([*header, *rules, ""])


def normalize_upstream_text(item: UpstreamFile, text: str) -> str:
    if item.format_hint == "raw":
        return text
    if item.format_hint == "clash_yaml_payload":
        return normalize_clash_yaml_payload(item, text)
    raise ValueError(f"不支持的上游格式：{item.format_hint}")


def sync_one(item: UpstreamFile, failures: list[UpstreamFailure]) -> tuple[bool, bool]:
    destination = UPSTREAM_ROOT / item.path

    try:
        latest = fetch_text(item.url)
        latest = normalize_upstream_text(item, latest)
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
    except ValueError as exc:
        detail = str(exc)
        print(f"[WARN] {item.path.as_posix()} fetch failed: {detail}")
        record_failure(
            failures,
            source="通用上游规则",
            resource=item.path.as_posix(),
            url=item.url,
            category="上游格式异常",
            detail=detail,
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


def validate_meta_rules_dat_readme(readme_text: str) -> None:
    missing = [marker for marker in META_RULES_DAT_REQUIRED_MARKERS if marker not in readme_text]
    if not missing:
        return
    raise ValueError("MetaCubeX README 缺少关键下载入口或同源说明: " + ", ".join(missing))


def build_geodata_snapshot_text() -> str:
    synced_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    lines = [
        f"# 来源仓库: {META_RULES_DAT_REPO_URL}",
        f"# 来源 README: {META_RULES_DAT_README_URL}",
        "# 作用: 统一登记 Surge geoip-maxmind-url 与 Mihomo geox-url.mmdb 的共享 GeoIP 上游。",
        "# 选择原因: Mihomo 官方文档的 geox-url 默认示例指向 MetaCubeX/meta-rules-dat；同时提供 mmdb/dat/db/lite 多格式。",
        "# 交叉验证: 上游 README 明确标注 country.mmdb / geoip.dat / geoip.db 内容同 Loyalsoldier/v2ray-rules-dat。",
        "# 维护边界: 这里只登记上游选择与下载入口，不把大体积 mmdb 二进制直接提交进仓库。",
        f"# 同步时间: {synced_at}",
        "",
        f"provider: {META_RULES_DAT_REPO}",
        "selected_asset: country.mmdb",
        f"github_release: {META_RULES_DAT_COUNTRY_MMDB_GITHUB_RELEASE_URL}",
        f"jsdelivr: {META_RULES_DAT_COUNTRY_MMDB_JSDELIVR_URL}",
        f"jsdelivr_cf: {META_RULES_DAT_COUNTRY_MMDB_JSDELIVR_CF_URL}",
        "recommended_endpoint: github_release",
        "recommended_for: surge, mihomo-mmdb",
        "content_reference: Loyalsoldier/v2ray-rules-dat",
        f"rulemesh_repo: {RULEMESH_REPO}",
        f"rulemesh_release_tag: {RULEMESH_GEOIP_RELEASE_TAG}",
        f"rulemesh_asset_name: {RULEMESH_GEOIP_ASSET_NAME}",
        f"rulemesh_release_mirror: {RULEMESH_GEOIP_MIRROR_URL}",
        "",
    ]
    return "\n".join(lines)


def sync_geodata_snapshot(failures: list[UpstreamFailure]) -> tuple[int, int]:
    try:
        readme_text = fetch_text(META_RULES_DAT_README_URL)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"[WARN] {META_RULES_DAT_GEODATA_SNAPSHOT_PATH.as_posix()} fetch failed: {exc}")
        record_failure(
            failures,
            source="MetaCubeX 官方 GEO 数据说明",
            resource=META_RULES_DAT_GEODATA_SNAPSHOT_PATH.as_posix(),
            url=META_RULES_DAT_README_URL,
            category=classify_fetch_failure(exc),
            detail=format_exception_message(exc),
        )
        return 0, 1

    try:
        validate_meta_rules_dat_readme(readme_text)
    except ValueError as exc:
        print(f"[WARN] {META_RULES_DAT_GEODATA_SNAPSHOT_PATH.as_posix()} sync failed: {exc}")
        record_failure(
            failures,
            source="MetaCubeX 官方 GEO 数据说明",
            resource=META_RULES_DAT_GEODATA_SNAPSHOT_PATH.as_posix(),
            url=META_RULES_DAT_README_URL,
            category="返回内容异常",
            detail=format_exception_message(exc),
        )
        return 0, 1

    snapshot_text = build_geodata_snapshot_text()
    if write_if_changed(UPSTREAM_ROOT / META_RULES_DAT_GEODATA_SNAPSHOT_PATH, snapshot_text):
        print(f"[UPDATE] {META_RULES_DAT_GEODATA_SNAPSHOT_PATH.as_posix()}")
        return 1, 0

    print(f"[SKIP] {META_RULES_DAT_GEODATA_SNAPSHOT_PATH.as_posix()}")
    return 0, 0


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


def running_in_github_actions() -> bool:
    value = env_value("GITHUB_ACTIONS")
    return value is not None and value.lower() == "true"


def has_available_alicloud_snapshots() -> bool:
    expected_paths: list[Path] = []
    for snapshot in ALICLOUD_REGION_SNAPSHOTS:
        expected_paths.extend(
            [
                snapshot.path,
                snapshot.ssh_path,
                snapshot.metadata_path,
                snapshot.bgp_path,
                snapshot.bgp_metadata_path,
                snapshot.history_path,
            ]
        )

    for relative_path in expected_paths:
        path = UPSTREAM_ROOT / relative_path
        if not path.exists():
            return False
        existing = read_existing(path)
        if not existing or "Placeholder file kept in repo" in existing:
            return False

    for snapshot in ALICLOUD_REGION_SNAPSHOTS:
        try:
            validate_alicloud_snapshot_files(snapshot)
        except (OSError, ValueError):
            return False
    return True


def can_skip_alicloud_sync_without_credentials() -> bool:
    return not running_in_github_actions() and has_available_alicloud_snapshots()


def resolve_alicloud_credentials() -> AlicloudCredentials | None:
    local_payload = load_local_config()
    local_access_key_id = local_config_value(local_payload, "alicloud", "access_key_id")
    local_access_key_secret = local_config_value(local_payload, "alicloud", "access_key_secret")
    local_security_token = local_config_value(local_payload, "alicloud", "security_token")

    access_key_id = env_value(
        "RULEMESH_ALICLOUD_ACCESS_KEY_ID",
        "ALIBABA_CLOUD_ACCESS_KEY_ID",
        "ALICLOUD_ACCESS_KEY_ID",
    ) or local_access_key_id
    access_key_secret = env_value(
        "RULEMESH_ALICLOUD_ACCESS_KEY_SECRET",
        "ALIBABA_CLOUD_ACCESS_KEY_SECRET",
        "ALICLOUD_ACCESS_KEY_SECRET",
    ) or local_access_key_secret
    if not access_key_id or not access_key_secret:
        return None

    security_token = env_value(
        "RULEMESH_ALICLOUD_SECURITY_TOKEN",
        "ALIBABA_CLOUD_SECURITY_TOKEN",
        "ALICLOUD_SECURITY_TOKEN",
    ) or local_security_token
    return AlicloudCredentials(
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
        security_token=security_token,
    )


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
        body = decode_text(exc.read()).strip()
    except OSError:
        body = ""
    finally:
        exc.close()

    details: list[str] = []
    if body:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            api_code = payload.get("Code")
            request_id = payload.get("RequestId")
            if isinstance(api_code, str) and api_code.strip():
                details.append(f"Code={api_code.strip()}")
            if isinstance(request_id, str) and request_id.strip():
                details.append(f"RequestId={request_id.strip()}")

    suffix = f" ({', '.join(details)})" if details else ""
    return f"HTTP {exc.code} {exc.reason}{suffix}"


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
        raise ValueError(parse_alicloud_http_error(exc)) from None

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


def collapse_ipv4_networks(prefixes: list[str]) -> list[ipaddress.IPv4Network]:
    networks: list[ipaddress.IPv4Network] = []
    for prefix in prefixes:
        network = ipaddress.ip_network(prefix, strict=True)
        if not isinstance(network, ipaddress.IPv4Network):
            raise ValueError(f"non-IPv4 CIDR in IPv4 coverage calculation: {prefix}")
        networks.append(network)
    return list(ipaddress.collapse_addresses(networks))


def calculate_ipv4_coverage(prefixes: list[str]) -> int:
    return sum(network.num_addresses for network in collapse_ipv4_networks(prefixes))


def calculate_ipv4_intersection_coverage(
    left_prefixes: list[str],
    right_prefixes: list[str],
) -> int:
    left = collapse_ipv4_networks(left_prefixes)
    right = collapse_ipv4_networks(right_prefixes)
    left_index = 0
    right_index = 0
    intersection_count = 0

    while left_index < len(left) and right_index < len(right):
        left_network = left[left_index]
        right_network = right[right_index]
        left_start = int(left_network.network_address)
        left_end = int(left_network.broadcast_address)
        right_start = int(right_network.network_address)
        right_end = int(right_network.broadcast_address)

        overlap_start = max(left_start, right_start)
        overlap_end = min(left_end, right_end)
        if overlap_start <= overlap_end:
            intersection_count += overlap_end - overlap_start + 1

        if left_end <= right_end:
            left_index += 1
        if right_end <= left_end:
            right_index += 1

    return intersection_count


def canonicalize_ipv4_prefixes(prefixes: list[str]) -> list[str]:
    return [str(network) for network in collapse_ipv4_networks(prefixes)]


def parse_ipv4_snapshot_prefixes(text: str, resource: str) -> list[str]:
    prefixes = [
        line.strip()
        for line in normalize_text(text).splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not prefixes:
        raise ValueError(f"{resource} 不包含 IPv4 前缀")
    try:
        canonical = canonicalize_ipv4_prefixes(prefixes)
    except ValueError as exc:
        raise ValueError(f"{resource} 包含无效 IPv4 前缀: {exc}") from exc
    if prefixes != canonical:
        raise ValueError(f"{resource} 必须按地址排序、去重并折叠为规范 IPv4 前缀")
    return prefixes


def ipv4_coverage_contains(container: list[str], members: list[str]) -> bool:
    return calculate_ipv4_intersection_coverage(container, members) == calculate_ipv4_coverage(
        members
    )


def build_ripestat_alicloud_url(asn: int) -> str:
    return RIPESTAT_ALICLOUD_IPV4_URL_TEMPLATE.format(asn=asn)


def fetch_alicloud_bgp_snapshot() -> dict[str, Any]:
    all_prefixes: list[str] = []
    per_asn: list[dict[str, Any]] = []

    for asn in ALICLOUD_FALLBACK_ASNS:
        url = build_ripestat_alicloud_url(asn)
        try:
            payload = json.loads(fetch_text(url))
        except json.JSONDecodeError as exc:
            raise ValueError(f"RIPEstat AS{asn} 返回无效 JSON: {exc}") from exc
        if not isinstance(payload, dict) or payload.get("status") != "ok":
            message = payload.get("message") if isinstance(payload, dict) else None
            raise ValueError(f"RIPEstat AS{asn} 返回异常状态: {message or 'unknown'}")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ValueError(f"RIPEstat AS{asn} 缺少 data 对象")
        if str(data.get("resource")) not in {str(asn), f"AS{asn}"}:
            raise ValueError(
                f"RIPEstat AS{asn} 返回了错误资源: {data.get('resource')}"
            )
        raw_entries = data.get("prefixes")
        if not isinstance(raw_entries, list):
            raise ValueError(f"RIPEstat AS{asn} 缺少 prefixes[]")

        ipv4_prefixes: list[str] = []
        for entry in raw_entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("prefix"), str):
                raise ValueError(f"RIPEstat AS{asn} prefixes[] 包含无效条目")
            raw_prefix = entry["prefix"].strip()
            try:
                network = ipaddress.ip_network(raw_prefix, strict=True)
            except ValueError as exc:
                raise ValueError(
                    f"RIPEstat AS{asn} 包含无效 CIDR: {raw_prefix}"
                ) from exc
            if isinstance(network, ipaddress.IPv4Network):
                ipv4_prefixes.append(str(network))

        unique_ipv4_prefixes = sorted(set(ipv4_prefixes))
        if not unique_ipv4_prefixes:
            raise ValueError(f"RIPEstat AS{asn} 没有任何 IPv4 公告")
        collapsed_ipv4_prefixes = canonicalize_ipv4_prefixes(unique_ipv4_prefixes)
        all_prefixes.extend(collapsed_ipv4_prefixes)
        per_asn.append(
            {
                "asn": asn,
                "queryStartTime": data.get("query_starttime"),
                "queryEndTime": data.get("query_endtime"),
                "reportedPrefixCount": len(raw_entries),
                "reportedIpv4PrefixCount": len(ipv4_prefixes),
                "uniqueIpv4PrefixCount": len(unique_ipv4_prefixes),
                "collapsedIpv4PrefixCount": len(collapsed_ipv4_prefixes),
            }
        )

    collapsed = canonicalize_ipv4_prefixes(all_prefixes)
    return {
        "syncToken": api_synced_at(),
        "source": {
            "api": "RIPEstat announced-prefixes",
            "docUrl": RIPESTAT_ANNOUNCED_PREFIXES_DOC_URL,
            "minPeersSeeing": 1,
        },
        "asns": list(ALICLOUD_FALLBACK_ASNS),
        "perAsn": per_asn,
        "collapsedIpv4PrefixCount": len(collapsed),
        "uniqueIpv4AddressCount": calculate_ipv4_coverage(collapsed),
        "syncedAt": api_synced_at(),
        "ipv4Prefix": collapsed,
    }


def validate_alicloud_bgp_snapshot_payload(payload: dict[str, Any]) -> list[str]:
    if payload.get("asns") != list(ALICLOUD_FALLBACK_ASNS):
        raise ValueError("阿里云 BGP 快照 ASN 列表不匹配")
    source = payload.get("source")
    if not isinstance(source, dict) or source.get("minPeersSeeing") != 1:
        raise ValueError("阿里云 BGP 快照必须使用 min_peers_seeing=1")
    per_asn = payload.get("perAsn")
    if not isinstance(per_asn, list) or len(per_asn) != len(ALICLOUD_FALLBACK_ASNS):
        raise ValueError("阿里云 BGP 快照缺少逐 ASN 统计")
    for expected_asn, item in zip(ALICLOUD_FALLBACK_ASNS, per_asn, strict=True):
        if not isinstance(item, dict) or item.get("asn") != expected_asn:
            raise ValueError("阿里云 BGP 快照逐 ASN 统计顺序或编号错误")
        for name in (
            "reportedPrefixCount",
            "reportedIpv4PrefixCount",
            "uniqueIpv4PrefixCount",
            "collapsedIpv4PrefixCount",
        ):
            value = item.get(name)
            if not isinstance(value, int) or value <= 0:
                raise ValueError(f"阿里云 BGP 快照缺少有效的 {name}")

    raw_prefixes = payload.get("ipv4Prefix")
    if not isinstance(raw_prefixes, list) or not all(
        isinstance(prefix, str) and prefix.strip() for prefix in raw_prefixes
    ):
        raise ValueError("阿里云 BGP 快照缺少 ipv4Prefix[]")
    prefixes = canonicalize_ipv4_prefixes(raw_prefixes)
    if raw_prefixes != prefixes:
        raise ValueError("阿里云 BGP 快照 IPv4 前缀没有规范折叠")
    if payload.get("collapsedIpv4PrefixCount") != len(prefixes):
        raise ValueError("阿里云 BGP 快照前缀数量不一致")
    coverage = calculate_ipv4_coverage(prefixes)
    if payload.get("uniqueIpv4AddressCount") != coverage:
        raise ValueError("阿里云 BGP 快照地址覆盖量不一致")
    return prefixes


def alicloud_bgp_snapshot_signature(payload: dict[str, Any]) -> tuple[Any, ...]:
    return (
        tuple(payload.get("asns", [])),
        payload.get("collapsedIpv4PrefixCount"),
        payload.get("uniqueIpv4AddressCount"),
        tuple(payload.get("ipv4Prefix", [])),
    )


def fetch_stable_alicloud_bgp_snapshot() -> dict[str, Any]:
    previous_signature: tuple[Any, ...] | None = None
    for _attempt in range(1, ALICLOUD_STABILITY_FETCH_ATTEMPTS + 1):
        payload = fetch_alicloud_bgp_snapshot()
        signature = alicloud_bgp_snapshot_signature(payload)
        if previous_signature == signature:
            return payload
        previous_signature = signature
    raise ValueError(
        "阿里云兜底 ASN 的 RIPEstat 公告在连续完整抓取期间持续变化，已保留旧快照"
    )


def validate_alicloud_snapshot_payload(
    payload: dict[str, Any],
    snapshot: AlicloudRegionSnapshot,
) -> list[str]:
    raw_prefixes = payload.get("publicIpAddress")
    if not isinstance(raw_prefixes, list):
        raise ValueError(f"{snapshot.region_id} snapshot is missing publicIpAddress[]")
    prefixes = extract_alicloud_public_ip_prefixes(payload)
    if not prefixes:
        raise ValueError(f"{snapshot.region_id} snapshot contains no IPv4 prefixes")
    if len(raw_prefixes) != len(prefixes):
        raise ValueError(
            f"{snapshot.region_id} snapshot publicIpAddress[] must contain only "
            "non-empty unique strings"
        )

    for prefix in prefixes:
        try:
            network = ipaddress.ip_network(prefix, strict=True)
        except ValueError as exc:
            raise ValueError(
                f"{snapshot.region_id} snapshot contains an invalid CIDR: {prefix}"
            ) from exc
        if network.version != 4:
            raise ValueError(
                f"{snapshot.region_id} IPv4 snapshot contains a non-IPv4 CIDR: {prefix}"
            )

    reported_total_count = payload.get("reportedTotalCount")
    fetched_entry_count = payload.get("fetchedEntryCount")
    duplicate_entry_count = payload.get("duplicateEntryCount")
    unique_prefix_count = payload.get("uniquePrefixCount")
    unique_ipv4_address_count = payload.get("uniqueIpv4AddressCount")
    for name, value in (
        ("reportedTotalCount", reported_total_count),
        ("fetchedEntryCount", fetched_entry_count),
        ("duplicateEntryCount", duplicate_entry_count),
        ("uniquePrefixCount", unique_prefix_count),
        ("uniqueIpv4AddressCount", unique_ipv4_address_count),
    ):
        if not isinstance(value, int) or value < 0:
            raise ValueError(
                f"{snapshot.region_id} snapshot is missing a valid {name}"
            )

    if fetched_entry_count != reported_total_count:
        raise ValueError(
            f"{snapshot.region_id} snapshot is incomplete: fetched "
            f"{fetched_entry_count} of {reported_total_count} entries"
        )

    page_size = payload.get("pageSize")
    page_count = payload.get("pageCount")
    if not isinstance(page_size, int) or page_size <= 0:
        raise ValueError(f"{snapshot.region_id} snapshot is missing a valid pageSize")
    if not isinstance(page_count, int) or page_count <= 0:
        raise ValueError(f"{snapshot.region_id} snapshot is missing a valid pageCount")
    expected_page_count = (reported_total_count + page_size - 1) // page_size
    if page_count != expected_page_count:
        raise ValueError(
            f"{snapshot.region_id} snapshot page count mismatch: "
            f"metadata={page_count}, calculated={expected_page_count}"
        )

    if payload.get("regionId") != snapshot.region_id:
        raise ValueError(
            f"{snapshot.region_id} snapshot region mismatch: {payload.get('regionId')}"
        )
    if payload.get("ipVersion") != "ipv4":
        raise ValueError(
            f"{snapshot.region_id} snapshot IP version is not ipv4"
        )

    expected_duplicate_count = fetched_entry_count - len(prefixes)
    if duplicate_entry_count != expected_duplicate_count:
        raise ValueError(
            f"{snapshot.region_id} snapshot duplicate count mismatch: "
            f"metadata={duplicate_entry_count}, calculated={expected_duplicate_count}"
        )

    if unique_prefix_count != len(prefixes):
        raise ValueError(
            f"{snapshot.region_id} snapshot unique prefix count mismatch: "
            f"metadata={unique_prefix_count}, calculated={len(prefixes)}"
        )

    calculated_address_count = calculate_ipv4_coverage(prefixes)
    if unique_ipv4_address_count != calculated_address_count:
        raise ValueError(
            f"{snapshot.region_id} snapshot address count mismatch: "
            f"metadata={unique_ipv4_address_count}, calculated={calculated_address_count}"
        )
    return prefixes


def validate_alicloud_page(
    payload: dict[str, Any],
    snapshot: AlicloudRegionSnapshot,
    *,
    expected_page_number: int,
    expected_page_size: int,
) -> tuple[list[str], int, str | None]:
    success = payload.get("Success")
    if success is not True:
        api_code = payload.get("Code") or "unknown error"
        raise ValueError(f"{snapshot.region_id} returned an error: {api_code}")

    raw_prefixes = payload.get("PublicIpAddress")
    if not isinstance(raw_prefixes, list):
        raise ValueError(f"{snapshot.region_id} payload is missing PublicIpAddress[]")

    prefixes: list[str] = []
    for index, item in enumerate(raw_prefixes):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(
                f"{snapshot.region_id} page {expected_page_number} "
                f"contains an invalid PublicIpAddress[{index}]"
            )
        prefix = item.strip()
        try:
            network = ipaddress.ip_network(prefix, strict=True)
        except ValueError as exc:
            raise ValueError(
                f"{snapshot.region_id} page {expected_page_number} "
                f"contains an invalid IPv4 CIDR: {prefix}"
            ) from exc
        if network.version != 4:
            raise ValueError(
                f"{snapshot.region_id} page {expected_page_number} "
                f"contains a non-IPv4 CIDR: {prefix}"
            )
        prefixes.append(str(network))

    raw_total_count = payload.get("TotalCount")
    if isinstance(raw_total_count, int):
        total_count = raw_total_count
    elif isinstance(raw_total_count, str) and raw_total_count.isdigit():
        total_count = int(raw_total_count)
    else:
        raise ValueError(f"{snapshot.region_id} payload is missing a valid TotalCount")

    if total_count < 0:
        raise ValueError(f"{snapshot.region_id} returned a negative TotalCount")

    response_page_number = payload.get("PageNumber")
    if str(response_page_number) != str(expected_page_number):
        raise ValueError(
            f"{snapshot.region_id} returned PageNumber={response_page_number}, "
            f"expected {expected_page_number}"
        )

    response_page_size = payload.get("PageSize")
    if str(response_page_size) != str(expected_page_size):
        raise ValueError(
            f"{snapshot.region_id} returned PageSize={response_page_size}, "
            f"expected {expected_page_size}"
        )

    response_region_id = payload.get("RegionId")
    if response_region_id != snapshot.region_id:
        raise ValueError(
            f"{snapshot.region_id} request returned data for region {response_region_id}"
        )

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
    fetched_entry_count = 0

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
            expected_page_number=page_number,
            expected_page_size=page_size,
        )
        all_prefixes.extend(page_prefixes)
        fetched_entry_count += len(page_prefixes)
        if request_id:
            request_ids.append(request_id)
        if reported_total_count is None:
            reported_total_count = page_total_count
        elif page_total_count != reported_total_count:
            raise ValueError(
                f"{snapshot.region_id} TotalCount changed during pagination: "
                f"{reported_total_count} -> {page_total_count}"
            )

        if not page_prefixes:
            if fetched_entry_count < reported_total_count:
                raise ValueError(
                    f"{snapshot.region_id} pagination ended early on page {page_number}: "
                    f"fetched {fetched_entry_count} of {reported_total_count} entries"
                )
            break
        if fetched_entry_count >= reported_total_count:
            if fetched_entry_count != reported_total_count:
                raise ValueError(
                    f"{snapshot.region_id} pagination count mismatch: "
                    f"fetched {fetched_entry_count}, expected {reported_total_count}"
                )
            break
        page_number += 1

    if reported_total_count is None or fetched_entry_count != reported_total_count:
        raise ValueError(
            f"{snapshot.region_id} pagination is incomplete: "
            f"fetched {fetched_entry_count}, expected {reported_total_count}"
        )

    prefixes = sorted(ordered_unique(all_prefixes))
    unique_ipv4_address_count = calculate_ipv4_coverage(prefixes)
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
        "reportedTotalCount": reported_total_count,
        "fetchedEntryCount": fetched_entry_count,
        "duplicateEntryCount": fetched_entry_count - len(prefixes),
        "uniquePrefixCount": len(prefixes),
        "uniqueIpv4AddressCount": unique_ipv4_address_count,
        "requestIds": request_ids,
        "syncedAt": api_synced_at(),
        "publicIpAddress": prefixes,
    }


def alicloud_snapshot_signature(payload: dict[str, Any]) -> tuple[Any, ...]:
    return (
        payload.get("reportedTotalCount"),
        payload.get("fetchedEntryCount"),
        payload.get("duplicateEntryCount"),
        payload.get("uniquePrefixCount"),
        payload.get("uniqueIpv4AddressCount"),
        tuple(sorted(extract_alicloud_public_ip_prefixes(payload))),
    )


def fetch_stable_alicloud_region_snapshot(
    snapshot: AlicloudRegionSnapshot,
    credentials: AlicloudCredentials,
) -> dict[str, Any]:
    previous_signature: tuple[Any, ...] | None = None

    for _attempt in range(1, ALICLOUD_STABILITY_FETCH_ATTEMPTS + 1):
        payload = fetch_alicloud_region_snapshot(snapshot, credentials)
        signature = alicloud_snapshot_signature(payload)
        if previous_signature == signature:
            return payload
        previous_signature = signature

    raise ValueError(
        f"{snapshot.region_id} changed during "
        f"{ALICLOUD_STABILITY_FETCH_ATTEMPTS} consecutive full fetches; "
        "the previous snapshot was kept"
    )


def build_alicloud_snapshot_text(
    payload: dict[str, Any],
    snapshot: AlicloudRegionSnapshot,
) -> str:
    prefixes = extract_alicloud_public_ip_prefixes(payload)
    synced_at = str(payload.get("syncedAt", "unknown"))
    reported_total_count = payload.get("reportedTotalCount", len(prefixes))
    fetched_entry_count = payload.get("fetchedEntryCount", len(prefixes))
    duplicate_entry_count = payload.get("duplicateEntryCount", 0)
    unique_ipv4_address_count = payload.get(
        "uniqueIpv4AddressCount", calculate_ipv4_coverage(prefixes)
    )
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
        f"# 抓取条目数量: {fetched_entry_count}",
        f"# 重复条目数量: {duplicate_entry_count}",
        f"# IPv4 前缀数量: {len(prefixes)}",
        f"# 唯一 IPv4 地址数量: {unique_ipv4_address_count}",
        "",
    ]
    lines.extend(prefixes)
    lines.append("")
    return "\n".join(lines)


def build_alicloud_bgp_snapshot_text(payload: dict[str, Any]) -> str:
    prefixes = validate_alicloud_bgp_snapshot_payload(payload)
    asn_text = ", ".join(f"AS{asn}" for asn in ALICLOUD_FALLBACK_ASNS)
    lines = [
        f"# 来源文档: {RIPESTAT_ANNOUNCED_PREFIXES_DOC_URL}",
        f"# 来源接口: {RIPESTAT_ANNOUNCED_PREFIXES_API_URL}",
        f"# 阿里云兜底 ASN: {asn_text}",
        "# 范围: RIPE RIS 最近观察窗口内至少被一个对等体看到的 IPv4 公告，已跨 ASN 去重折叠。",
        "# 边界: 这是故意放宽的全球阿里网络兜底，不代表香港地域归属，只用于 SSH TCP/22。",
        f"# 同步时间: {payload.get('syncedAt', 'unknown')}",
        f"# 折叠后 IPv4 前缀数量: {len(prefixes)}",
        f"# 唯一 IPv4 地址数量: {payload.get('uniqueIpv4AddressCount', 0)}",
        "",
    ]
    lines.extend(prefixes)
    lines.append("")
    return "\n".join(lines)


def merge_alicloud_ssh_history(
    existing_prefixes: list[str],
    official_prefixes: list[str],
    bgp_prefixes: list[str],
) -> list[str]:
    return canonicalize_ipv4_prefixes(
        [
            *ALICLOUD_LEGACY_IPV4_SEED,
            *existing_prefixes,
            *official_prefixes,
            *bgp_prefixes,
        ]
    )


def build_alicloud_history_snapshot_text(
    payload: dict[str, Any],
    bgp_payload: dict[str, Any],
    snapshot: AlicloudRegionSnapshot,
    prefixes: list[str],
) -> str:
    lines = [
        f"# 标题: {snapshot.title} SSH TCP/22 单调历史覆盖",
        f"# 官方来源: {ALICLOUD_PUBLIC_IP_DOC_URL}",
        f"# BGP 来源: {RIPESTAT_ANNOUNCED_PREFIXES_DOC_URL}",
        "# 范围: 官方香港 VPC 当前/历史前缀与阿里兜底 ASN 当前/历史 BGP 前缀的累计并集。",
        "# 维护策略: 自动同步只增不减；上游撤回不会删除已发布覆盖，删除必须人工审计。",
        f"# 官方同步时间: {payload.get('syncedAt', 'unknown')}",
        f"# BGP 同步时间: {bgp_payload.get('syncedAt', 'unknown')}",
        f"# 累计折叠后 IPv4 前缀数量: {len(prefixes)}",
        f"# 累计唯一 IPv4 地址数量: {calculate_ipv4_coverage(prefixes)}",
        "",
    ]
    lines.extend(prefixes)
    lines.append("")
    return "\n".join(lines)


def build_alicloud_ssh_snapshot_text(
    payload: dict[str, Any],
    snapshot: AlicloudRegionSnapshot,
    *,
    history_prefixes: list[str] | None = None,
    bgp_payload: dict[str, Any] | None = None,
) -> str:
    official_prefixes = extract_alicloud_public_ip_prefixes(payload)
    prefixes = history_prefixes or official_prefixes
    synced_at = str(payload.get("syncedAt", "unknown"))
    reported_total_count = payload.get("reportedTotalCount", len(official_prefixes))
    fetched_entry_count = payload.get("fetchedEntryCount", len(official_prefixes))
    duplicate_entry_count = payload.get("duplicateEntryCount", 0)
    page_count = payload.get("pageCount", "unknown")
    asn_text = ", ".join(f"AS{asn}" for asn in ALICLOUD_FALLBACK_ASNS)

    lines = [
        f"# 来源文档: {ALICLOUD_PUBLIC_IP_DOC_URL}",
        f"# BGP 来源文档: {RIPESTAT_ANNOUNCED_PREFIXES_DOC_URL}",
        f"# 终端节点文档: {ALICLOUD_VPC_ENDPOINT_DOC_URL}",
        f"# API: {ALICLOUD_ACTION}",
        f"# 标题: {snapshot.title} SSH TCP/22 直连规则",
        f"# 终端节点: {snapshot.endpoint}",
        f"# 区域: {snapshot.region_id}",
        "# 范围: 官方香港 VPC 与阿里兜底 ASN 的单调历史 IPv4 并集，只匹配 SSH TCP/22。",
        f"# 运行时兜底 ASN: {asn_text}",
        "# 派生自: alicloud/ssh22_ipv4_history.txt",
        f"# 同步时间: {synced_at}",
        f"# BGP 同步时间: {(bgp_payload or {}).get('syncedAt', 'unknown')}",
        f"# 抓取页数: {page_count}",
        f"# 上游总数: {reported_total_count}",
        f"# 抓取条目数量: {fetched_entry_count}",
        f"# 重复条目数量: {duplicate_entry_count}",
        f"# 静态 SSH CIDR 规则数量: {len(prefixes)}",
        f"# 运行时 ASN 规则数量: {len(ALICLOUD_FALLBACK_ASNS)}",
        f"# 累计唯一 IPv4 地址数量: {calculate_ipv4_coverage(prefixes)}",
        "",
    ]
    lines.extend(
        f"AND,((IP-CIDR,{prefix},no-resolve),(PROTOCOL,TCP),(DST-PORT,22))"
        for prefix in prefixes
    )
    lines.extend(
        f"AND,((IP-ASN,{asn},no-resolve),(PROTOCOL,TCP),(DST-PORT,22))"
        for asn in ALICLOUD_FALLBACK_ASNS
    )
    lines.append("")
    return "\n".join(lines)


def validate_alicloud_snapshot_files(
    snapshot: AlicloudRegionSnapshot,
) -> dict[str, Any]:
    metadata_path = UPSTREAM_ROOT / snapshot.metadata_path
    try:
        payload = json.loads(decode_text(metadata_path.read_bytes()))
    except OSError as exc:
        raise ValueError(
            f"{snapshot.region_id} snapshot metadata cannot be read: {exc}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{snapshot.region_id} snapshot metadata is invalid JSON: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{snapshot.region_id} snapshot metadata is not an object")

    official_prefixes = validate_alicloud_snapshot_payload(payload, snapshot)

    bgp_metadata_path = UPSTREAM_ROOT / snapshot.bgp_metadata_path
    try:
        bgp_payload = json.loads(decode_text(bgp_metadata_path.read_bytes()))
    except OSError as exc:
        raise ValueError(
            f"阿里云 BGP 快照元数据无法读取: {exc}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"阿里云 BGP 快照元数据不是有效 JSON: {exc}") from exc
    if not isinstance(bgp_payload, dict):
        raise ValueError("阿里云 BGP 快照元数据不是对象")
    bgp_prefixes = validate_alicloud_bgp_snapshot_payload(bgp_payload)

    history_text = read_existing(UPSTREAM_ROOT / snapshot.history_path)
    if history_text is None:
        raise ValueError(
            f"{snapshot.region_id} 历史覆盖文件缺失: {snapshot.history_path.as_posix()}"
        )
    history_prefixes = parse_ipv4_snapshot_prefixes(
        history_text,
        snapshot.history_path.as_posix(),
    )
    if not ipv4_coverage_contains(history_prefixes, official_prefixes):
        raise ValueError(f"{snapshot.region_id} 历史覆盖没有包含当前官方前缀")
    if not ipv4_coverage_contains(history_prefixes, bgp_prefixes):
        raise ValueError(f"{snapshot.region_id} 历史覆盖没有包含当前 BGP 前缀")
    if not ipv4_coverage_contains(
        history_prefixes,
        list(ALICLOUD_LEGACY_IPV4_SEED),
    ):
        raise ValueError(f"{snapshot.region_id} 历史覆盖没有包含迁移前历史种子")

    expected_files = (
        (snapshot.path, build_alicloud_snapshot_text(payload, snapshot)),
        (snapshot.bgp_path, build_alicloud_bgp_snapshot_text(bgp_payload)),
        (
            snapshot.history_path,
            build_alicloud_history_snapshot_text(
                payload,
                bgp_payload,
                snapshot,
                history_prefixes,
            ),
        ),
        (
            snapshot.ssh_path,
            build_alicloud_ssh_snapshot_text(
                payload,
                snapshot,
                history_prefixes=history_prefixes,
                bgp_payload=bgp_payload,
            ),
        ),
    )
    for relative_path, expected_text in expected_files:
        actual_text = read_existing(UPSTREAM_ROOT / relative_path)
        if actual_text is None:
            raise ValueError(
                f"{snapshot.region_id} snapshot file is missing: {relative_path.as_posix()}"
            )
        if actual_text != normalize_text(expected_text):
            raise ValueError(
                f"{snapshot.region_id} snapshot file does not match metadata: "
                f"{relative_path.as_posix()}"
            )
    return payload


def load_existing_alicloud_official_snapshot(
    snapshot: AlicloudRegionSnapshot,
) -> dict[str, Any] | None:
    metadata_path = UPSTREAM_ROOT / snapshot.metadata_path
    try:
        payload = json.loads(decode_text(metadata_path.read_bytes()))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    try:
        validate_alicloud_snapshot_payload(payload, snapshot)
    except ValueError:
        return None
    actual_text = read_existing(UPSTREAM_ROOT / snapshot.path)
    if actual_text != normalize_text(build_alicloud_snapshot_text(payload, snapshot)):
        return None
    return payload


def sync_alicloud_snapshots(failures: list[UpstreamFailure]) -> tuple[int, int]:
    credentials = resolve_alicloud_credentials()

    changed = 0
    failed = 0

    for snapshot in ALICLOUD_REGION_SNAPSHOTS:
        existing_payload = load_existing_alicloud_official_snapshot(snapshot)
        payload: dict[str, Any] | None = None
        if credentials is not None:
            try:
                payload = fetch_stable_alicloud_region_snapshot(snapshot, credentials)
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
                if existing_payload is not None and not running_in_github_actions():
                    payload = existing_payload
                    print(
                        f"[SKIP] {snapshot.path.as_posix()} API 刷新失败，"
                        f"本地构建继续使用已校验快照: {exc}"
                    )
                else:
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
        elif existing_payload is not None and not running_in_github_actions():
            payload = existing_payload
            print(
                f"[SKIP] {snapshot.path.as_posix()} 缺少阿里云凭据，"
                "本地构建继续使用已校验官方快照并刷新公开 BGP 兜底。"
            )
        else:
            detail = (
                "缺少阿里云凭据。请设置 RULEMESH_ALICLOUD_ACCESS_KEY_ID 和 "
                "RULEMESH_ALICLOUD_ACCESS_KEY_SECRET（或标准阿里云环境变量；"
                "本地也可写入 .rulemesh.local.json 的 alicloud 节点）。"
            )
            print(f"[WARN] alicloud sync failed: {detail}")
            record_failure(
                failures,
                source="阿里云官方 API",
                resource=snapshot.path.as_posix(),
                url=f"https://{snapshot.endpoint}/",
                category="缺少凭据",
                detail=detail,
            )
            failed += 1
            continue

        assert payload is not None

        try:
            bgp_payload = fetch_stable_alicloud_bgp_snapshot()
            bgp_prefixes = validate_alicloud_bgp_snapshot_payload(bgp_payload)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            print(f"[WARN] {snapshot.bgp_path.as_posix()} sync failed: {exc}")
            record_failure(
                failures,
                source="RIPEstat 阿里云兜底 ASN 公告",
                resource=snapshot.bgp_path.as_posix(),
                url=build_ripestat_alicloud_url(ALICLOUD_FALLBACK_ASNS[0]),
                category=classify_fetch_failure(exc),
                detail=format_exception_message(exc),
            )
            failed += 1
            continue

        try:
            validate_alicloud_snapshot_payload(payload, snapshot)
        except ValueError as exc:
            detail = str(exc)
            print(f"[WARN] {snapshot.path.as_posix()} sync failed: {detail}")
            record_failure(
                failures,
                source="阿里云官方 API",
                resource=snapshot.path.as_posix(),
                url=f"https://{snapshot.endpoint}/",
                category="上游内容不完整",
                detail=detail,
            )
            failed += 1
            continue

        existing_history_text = read_existing(UPSTREAM_ROOT / snapshot.history_path)
        existing_history_prefixes: list[str] = []
        if existing_history_text:
            try:
                existing_history_prefixes = parse_ipv4_snapshot_prefixes(
                    existing_history_text,
                    snapshot.history_path.as_posix(),
                )
            except ValueError as exc:
                detail = str(exc)
                print(f"[WARN] {snapshot.history_path.as_posix()} sync failed: {detail}")
                record_failure(
                    failures,
                    source="阿里云 SSH 单调历史覆盖",
                    resource=snapshot.history_path.as_posix(),
                    url=RULEMESH_REPO_URL,
                    category="历史覆盖异常",
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

        bgp_metadata_text = json.dumps(bgp_payload, indent=2, ensure_ascii=False) + "\n"
        if write_if_changed(
            UPSTREAM_ROOT / snapshot.bgp_metadata_path,
            bgp_metadata_text,
        ):
            print(f"[UPDATE] {snapshot.bgp_metadata_path.as_posix()}")
            changed += 1
        else:
            print(f"[SKIP] {snapshot.bgp_metadata_path.as_posix()}")

        bgp_snapshot_text = build_alicloud_bgp_snapshot_text(bgp_payload)
        if write_if_changed(UPSTREAM_ROOT / snapshot.bgp_path, bgp_snapshot_text):
            print(f"[UPDATE] {snapshot.bgp_path.as_posix()}")
            changed += 1
        else:
            print(f"[SKIP] {snapshot.bgp_path.as_posix()}")

        official_prefixes = extract_alicloud_public_ip_prefixes(payload)
        history_prefixes = merge_alicloud_ssh_history(
            existing_history_prefixes,
            official_prefixes,
            bgp_prefixes,
        )
        history_snapshot_text = build_alicloud_history_snapshot_text(
            payload,
            bgp_payload,
            snapshot,
            history_prefixes,
        )
        if write_if_changed(
            UPSTREAM_ROOT / snapshot.history_path,
            history_snapshot_text,
        ):
            print(f"[UPDATE] {snapshot.history_path.as_posix()}")
            changed += 1
        else:
            print(f"[SKIP] {snapshot.history_path.as_posix()}")

        ssh_snapshot_text = build_alicloud_ssh_snapshot_text(
            payload,
            snapshot,
            history_prefixes=history_prefixes,
            bgp_payload=bgp_payload,
        )
        if write_if_changed(UPSTREAM_ROOT / snapshot.ssh_path, ssh_snapshot_text):
            print(f"[UPDATE] {snapshot.ssh_path.as_posix()}")
            changed += 1
        else:
            print(f"[SKIP] {snapshot.ssh_path.as_posix()}")

        try:
            validate_alicloud_snapshot_files(snapshot)
        except ValueError as exc:
            detail = str(exc)
            print(f"[WARN] {snapshot.path.as_posix()} sync failed: {detail}")
            record_failure(
                failures,
                source="阿里云官方 API",
                resource=snapshot.path.as_posix(),
                url=f"https://{snapshot.endpoint}/",
                category="快照文件不一致",
                detail=detail,
            )
            failed += 1

    return changed, failed


SYNC_TASKS = (
    SyncTask(name="generic_upstreams", runner=sync_generic_upstreams),
    SyncTask(name="geodata", runner=sync_geodata_snapshot),
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
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
