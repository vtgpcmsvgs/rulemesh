#!/usr/bin/env python3
"""Sync selected third-party rule snapshots into rules/upstream/."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_ROOT = ROOT / "rules" / "upstream"
USER_AGENT = "surge-config-upstream-sync/1.0"
AWS_IP_RANGES_URL = "https://ip-ranges.amazonaws.com/ip-ranges.json"


@dataclass(frozen=True)
class UpstreamFile:
    path: Path
    url: str


@dataclass(frozen=True)
class AwsRegionSnapshot:
    path: Path
    regions: tuple[str, ...]
    title: str


UPSTREAM_FILES = (
    UpstreamFile(Path("loyalsoldier/direct.txt"), "https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/direct.txt"),
    UpstreamFile(Path("loyalsoldier/cncidr.txt"), "https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/cncidr.txt"),
    UpstreamFile(Path("loyalsoldier/gfw.txt"), "https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/gfw.txt"),
    UpstreamFile(Path("loyalsoldier/tld-not-cn.txt"), "https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/tld-not-cn.txt"),
    UpstreamFile(Path("loyalsoldier/telegramcidr.txt"), "https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/telegramcidr.txt"),
    UpstreamFile(Path("blackmatrix7/bilibili.list"), "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/BiliBili/BiliBili.list"),
    UpstreamFile(Path("blackmatrix7/google_fcm.list"), "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/GoogleFCM/GoogleFCM.list"),
    UpstreamFile(Path("blackmatrix7/global_media.list"), "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/GlobalMedia/GlobalMedia.list"),
    UpstreamFile(Path("blackmatrix7/microsoft.list"), "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/Microsoft/Microsoft.list"),
    UpstreamFile(Path("blackmatrix7/netease_music.list"), "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/NetEaseMusic/NetEaseMusic.list"),
    UpstreamFile(Path("blackmatrix7/onedrive.list"), "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/OneDrive/OneDrive.list"),
    UpstreamFile(Path("blackmatrix7/openai.list"), "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/OpenAI/OpenAI.list"),
    UpstreamFile(Path("blackmatrix7/youtube.list"), "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Clash/YouTube/YouTube.list"),
)
AWS_JSON_PATH = Path("aws/ip-ranges.json")
AWS_REGION_SNAPSHOTS = (
    AwsRegionSnapshot(
        path=Path("aws/hk_ipv4.txt"),
        regions=("ap-east-1",),
        title="AWS Hong Kong IPv4 (ap-east-1)",
    ),
    AwsRegionSnapshot(
        path=Path("aws/jp_ipv4.txt"),
        regions=("ap-northeast-1", "ap-northeast-3"),
        title="AWS Japan IPv4 (ap-northeast-1 Tokyo + ap-northeast-3 Osaka)",
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
        f"# Generated from {AWS_IP_RANGES_URL}",
        f"# title: {snapshot.title}",
        f"# syncToken: {sync_token}",
        f"# createDate: {create_date}",
        f"# regions: {', '.join(snapshot.regions)}",
        "# services: all published IPv4 prefixes for the listed AWS regions",
        f"# total IPv4 prefixes: {len(prefixes)}",
    ]
    lines.extend(f"# {region}: {len(region_prefixes)} prefixes" for region, region_prefixes in per_region)
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

    if write_if_changed(UPSTREAM_ROOT / AWS_JSON_PATH, json.dumps(payload, indent=2, ensure_ascii=False) + "\n"):
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

    print(f"[DONE] {changed} files updated, {failed} fetch failures.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
