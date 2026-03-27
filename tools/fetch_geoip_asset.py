#!/usr/bin/env python3
"""根据 geodata 快照下载当前选定的 GeoIP 资产。"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path

import sync_upstream_rules


def parse_snapshot_mapping(text: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        mapping[key.strip()] = value.strip()
    return mapping


def read_snapshot_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def resolve_snapshot_path(raw_path: str | None) -> Path:
    if raw_path:
        return Path(raw_path).resolve()
    return (
        sync_upstream_rules.UPSTREAM_ROOT
        / sync_upstream_rules.META_RULES_DAT_GEODATA_SNAPSHOT_PATH
    ).resolve()


def resolve_download_url(snapshot: dict[str, str], key: str) -> str:
    url = snapshot.get(key, "").strip()
    if not url:
        raise ValueError(f"GeoIP 快照缺少下载字段: {key}")
    return url


def download_binary(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": sync_upstream_rules.USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def write_output(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="下载 RuleMesh 当前选定的 GeoIP mmdb 资产。"
    )
    parser.add_argument("--output", required=True, help="输出文件路径")
    parser.add_argument(
        "--snapshot",
        default="",
        help=(
            "可选，指定 geodata 快照文件路径；"
            "默认使用 rules/upstream/geodata/metacubex_country_mmdb.yaml"
        ),
    )
    parser.add_argument(
        "--url-key",
        default="github_release",
        help="从快照读取哪个下载字段，默认 github_release",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    snapshot_path = resolve_snapshot_path(args.snapshot)
    output_path = Path(args.output).resolve()

    try:
        snapshot_text = read_snapshot_text(snapshot_path)
        snapshot = parse_snapshot_mapping(snapshot_text)
        download_url = resolve_download_url(snapshot, args.url_key)
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"[ERROR] GeoIP 快照读取失败: {exc}", file=sys.stderr)
        return 1

    try:
        payload = download_binary(download_url)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"[ERROR] GeoIP 下载失败: {exc}", file=sys.stderr)
        return 1

    if not payload:
        print("[ERROR] GeoIP 下载结果为空。", file=sys.stderr)
        return 1

    write_output(output_path, payload)
    print(f"[DONE] GeoIP 已下载到 {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
