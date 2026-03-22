#!/usr/bin/env python3
"""Sync selected upstream rule snapshots into rules/upstream/."""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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
        title="AWS Hong Kong IPv4 (ap-east-1)",
    ),
    AwsRegionSnapshot(
        path=Path("aws/tokyo_ipv4.txt"),
        regions=("ap-northeast-1",),
        title="AWS Tokyo IPv4 (ap-northeast-1)",
    ),
    AwsRegionSnapshot(
        path=Path("aws/osaka_ipv4.txt"),
        regions=("ap-northeast-3",),
        title="AWS Osaka IPv4 (ap-northeast-3)",
    ),
    AwsRegionSnapshot(
        path=Path("aws/seoul_ipv4.txt"),
        regions=("ap-northeast-2",),
        title="AWS Seoul IPv4 (ap-northeast-2)",
    ),
    AwsRegionSnapshot(
        path=Path("aws/taipei_ipv4.txt"),
        regions=("ap-east-2",),
        title="AWS Taipei IPv4 (ap-east-2)",
    ),
)

ALICLOUD_REGION_SNAPSHOTS = (
    AlicloudRegionSnapshot(
        path=Path("alicloud/hk_ipv4.txt"),
        ssh_path=Path("alicloud/hk_ssh22.txt"),
        metadata_path=Path("alicloud/hk_ipv4.json"),
        region_id="cn-hongkong",
        endpoint="vpc.cn-hongkong.aliyuncs.com",
        title="Alibaba Cloud Hong Kong IPv4 (cn-hongkong)",
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


def sync_one(item: UpstreamFile) -> tuple[bool, bool]:
    destination = UPSTREAM_ROOT / item.path

    try:
        latest = fetch_text(item.url)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"[WARN] {item.path.as_posix()} fetch failed: {exc}")
        return False, True

    if not write_if_changed(destination, latest):
        print(f"[SKIP] {item.path.as_posix()}")
        return False, False

    print(f"[UPDATE] {item.path.as_posix()}")
    return True, False


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
        f"# Source: {AWS_IP_RANGES_URL}",
        f"# Title: {snapshot.title}",
        f"# Sync token: {sync_token}",
        f"# Upstream create date: {create_date}",
        f"# Regions: {', '.join(snapshot.regions)}",
        "# Scope: all published IPv4 prefixes returned for the selected AWS region(s).",
        f"# IPv4 prefix count: {len(prefixes)}",
    ]
    lines.extend(
        f"# {region}: {len(region_prefixes)} prefix(es)"
        for region, region_prefixes in per_region
    )
    lines.append("")
    lines.extend(prefixes)
    lines.append("")
    return "\n".join(lines)


def sync_aws_snapshots() -> tuple[int, int]:
    try:
        raw_text = fetch_text(AWS_IP_RANGES_URL)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"[WARN] aws/ip-ranges.json fetch failed: {exc}")
        return 0, 1

    try:
        payload = validate_aws_payload(json.loads(raw_text))
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"[WARN] aws/ip-ranges.json parse failed: {exc}")
        return 0, 1

    changed = 0

    if write_if_changed(
        UPSTREAM_ROOT / AWS_JSON_PATH,
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
    ):
        print(f"[UPDATE] {AWS_JSON_PATH.as_posix()}")
        changed += 1
    else:
        print(f"[SKIP] {AWS_JSON_PATH.as_posix()}")

    for snapshot in AWS_REGION_SNAPSHOTS:
        rendered = build_aws_snapshot_text(payload, snapshot)
        if write_if_changed(UPSTREAM_ROOT / snapshot.path, rendered):
            print(f"[UPDATE] {snapshot.path.as_posix()}")
            changed += 1
        else:
            print(f"[SKIP] {snapshot.path.as_posix()}")

    return changed, 0


def env_value(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value and value.strip():
            return value.strip()
    return None


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
    prefixes = ordered_unique(
        [
            item.strip()
            for item in payload.get("publicIpAddress", [])
            if isinstance(item, str) and item.strip()
        ]
    )
    synced_at = str(payload.get("syncedAt", "unknown"))
    reported_total_count = payload.get("reportedTotalCount", len(prefixes))
    page_count = payload.get("pageCount", "unknown")

    lines = [
        f"# Source doc: {ALICLOUD_PUBLIC_IP_DOC_URL}",
        f"# Endpoint doc: {ALICLOUD_VPC_ENDPOINT_DOC_URL}",
        f"# API: {ALICLOUD_ACTION}",
        f"# Title: {snapshot.title}",
        f"# Endpoint: {snapshot.endpoint}",
        f"# Region: {snapshot.region_id}",
        "# Scope: all VPC public IPv4 CIDR blocks returned by the official Alibaba Cloud API.",
        f"# Synced at: {synced_at}",
        f"# Pages fetched: {page_count}",
        f"# Reported total count: {reported_total_count}",
        f"# IPv4 prefix count: {len(prefixes)}",
        "",
    ]
    lines.extend(prefixes)
    lines.append("")
    return "\n".join(lines)


def build_alicloud_ssh_snapshot_text(
    payload: dict[str, Any],
    snapshot: AlicloudRegionSnapshot,
) -> str:
    prefixes = ordered_unique(
        [
            item.strip()
            for item in payload.get("publicIpAddress", [])
            if isinstance(item, str) and item.strip()
        ]
    )
    synced_at = str(payload.get("syncedAt", "unknown"))
    reported_total_count = payload.get("reportedTotalCount", len(prefixes))
    page_count = payload.get("pageCount", "unknown")

    lines = [
        f"# Source doc: {ALICLOUD_PUBLIC_IP_DOC_URL}",
        f"# Endpoint doc: {ALICLOUD_VPC_ENDPOINT_DOC_URL}",
        f"# API: {ALICLOUD_ACTION}",
        f"# Title: {snapshot.title} SSH TCP/22 direct rules",
        f"# Endpoint: {snapshot.endpoint}",
        f"# Region: {snapshot.region_id}",
        "# Scope: all official Alibaba Cloud Hong Kong public IPv4 prefixes converted to SSH TCP/22 rules.",
        "# Derived from: alicloud/hk_ipv4.txt",
        f"# Synced at: {synced_at}",
        f"# Pages fetched: {page_count}",
        f"# Reported total count: {reported_total_count}",
        f"# SSH rule count: {len(prefixes)}",
        "",
    ]
    lines.extend(f"AND,((IP-CIDR,{prefix}),(DST-PORT,22))" for prefix in prefixes)
    lines.append("")
    return "\n".join(lines)


def sync_alicloud_snapshots() -> tuple[int, int]:
    credentials = resolve_alicloud_credentials()
    if credentials is None:
        print(
            "[WARN] alicloud/hk_ipv4.txt and alicloud/hk_ssh22.txt skipped: missing credentials. "
            "Set RULEMESH_ALICLOUD_ACCESS_KEY_ID and "
            "RULEMESH_ALICLOUD_ACCESS_KEY_SECRET (or the standard Alibaba Cloud env vars)."
        )
        return 0, 0

    changed = 0
    failed = 0

    for snapshot in ALICLOUD_REGION_SNAPSHOTS:
        try:
            payload = fetch_alicloud_region_snapshot(snapshot, credentials)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            print(f"[WARN] {snapshot.path.as_posix()} sync failed: {exc}")
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


def main() -> int:
    changed = 0
    failed = 0

    for item in UPSTREAM_FILES:
        updated, fetch_failed = sync_one(item)
        changed += int(updated)
        failed += int(fetch_failed)

    aws_changed, aws_failed = sync_aws_snapshots()
    changed += aws_changed
    failed += aws_failed

    alicloud_changed, alicloud_failed = sync_alicloud_snapshots()
    changed += alicloud_changed
    failed += alicloud_failed

    print(f"[DONE] Updated {changed} file(s); fetch failures: {failed}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
