"""必检私人机场订阅下载、节点列表及已提供的配额/到期信息，不输出私人值。"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from urllib.parse import urlsplit

try:
    import yaml
except ImportError:
    yaml = None

ROOT = Path(__file__).resolve().parents[1]
PROFILE_NAMES = ('rulemesh-flclash-desktop-20261023.yaml', 'rulemesh-flclash-android-20261023.yaml')
MAX_BYTES = 20 * 1024 * 1024


class CheckError(ValueError):
    """仅携带固定诊断，不接收配置值或上游异常原文。"""


def load_yaml(text: str):
    if yaml is None:
        raise CheckError('缺少已登记依赖：请安装 requirements-check.txt。')
    if not isinstance(text, str):
        raise CheckError('响应文本格式无效。')

    class UniqueLoader(yaml.SafeLoader):
        pass

    def mapping(loader, node, deep=False):
        loader.flatten_mapping(node)
        result = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if not isinstance(key, (str, int, float, bool, type(None))) or key in result:
                raise CheckError('YAML 存在重复或不支持的键。')
            result[key] = loader.construct_object(value_node, deep=deep)
        return result

    UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    try:
        if len(text.encode('utf-8')) > MAX_BYTES:
            raise CheckError('响应超出大小限制。')
        return yaml.load(text, Loader=UniqueLoader)
    except CheckError:
        raise
    except (yaml.YAMLError, UnicodeError, ValueError, TypeError, RecursionError):
        raise CheckError('YAML 解析失败。') from None


@dataclass(frozen=True)
class Provider:
    name: str
    url: str = field(repr=False)
    agent: tuple[str, ...] = field(repr=False)


def manifest(text: str) -> dict[str, Provider]:
    document = load_yaml(text)
    providers = document.get('proxy-providers') if isinstance(document, dict) else None
    if not isinstance(providers, dict) or not providers:
        raise CheckError('缺少非空 proxy-providers。')
    result = {}
    for name, spec in providers.items():
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', name):
            raise CheckError('provider 名称不符合可安全输出的格式。')
        if not isinstance(spec, dict) or spec.get('type') != 'http' or spec.get('proxy') != 'DIRECT':
            raise CheckError('机场 provider 必须为 HTTP 类型并显式使用 DIRECT。')
        url = spec.get('url')
        try:
            parsed = urlsplit(url) if isinstance(url, str) else None
            if not parsed or parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
                raise ValueError
        except (ValueError, TypeError):
            raise CheckError('机场直属 URL 必须为有效 HTTPS 地址。') from None
        headers = spec.get('header', {})
        if not isinstance(headers, dict):
            raise CheckError('provider header 格式无效。')
        # 仅 User-Agent 参与内容协商；拒绝静默漏发其他凭据 header。
        if any(not isinstance(key, str) or key.lower() != 'user-agent' for key in headers):
            raise CheckError('存在未支持的 provider 请求头，需先扩展检查器。')
        if len(headers) > 1:
            raise CheckError('User-Agent 请求头重复。')
        agent = next(iter(headers.values()), ())
        if isinstance(agent, str):
            agent = (agent,)
        elif isinstance(agent, list) and all(isinstance(value, str) for value in agent):
            agent = tuple(agent)
        elif agent != ():
            raise CheckError('User-Agent 格式无效。')
        if any('\r' in value or '\n' in value for value in agent):
            raise CheckError('User-Agent 不得包含换行。')
        result[name] = Provider(name, url, agent)
    return result


def aligned_manifest(directory: Path) -> list[Provider]:
    try:
        desktop, android = (manifest((directory / name).read_text('utf-8')) for name in PROFILE_NAMES)
    except (OSError, UnicodeError):
        raise CheckError('两份私人 Mihomo 配置缺失或不可读；必检不能跳过。') from None
    if desktop != android:
        raise CheckError('两份 Mihomo 的 provider 名称、直属 URL、DIRECT 或 User-Agent 不一致；未发送请求。')
    return [desktop[name] for name in sorted(desktop)]


def default_directory() -> Path:
    registration = json.loads((ROOT / 'private-repository.json').read_text('utf-8'))
    checkout = Path(os.path.expandvars(registration['windows_checkout']))
    for candidate in registration['current_config_candidates']:
        current = checkout / candidate
        if all((current / name).is_file() for name in PROFILE_NAMES):
            return current
    raise CheckError('未找到已登记的私人配置；按 private-repository-bootstrap.md 恢复后重跑。')


def transport(providers: list[Provider], deadline: float) -> list[dict]:
    executable = shutil.which('pwsh')
    if not executable:
        raise CheckError('必检需要 PowerShell 7；不能用缺少完整 deadline 的下载方式代替。')
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise CheckError('订阅检查已超出 60 秒总预算。')
    payload = json.dumps({'budgetMs': max(1, int(remaining * 1000)), 'providers': [
        {'name': item.name, 'url': item.url, 'agent': item.agent} for item in providers
    ]}, ensure_ascii=True)
    try:
        result = subprocess.run([executable, '-NoProfile', '-File', str(ROOT / 'tools/fetch_private_subscriptions.ps1')],
                                input=payload, capture_output=True, encoding='utf-8',
                                timeout=remaining, check=False)
        if result.returncode:
            raise CheckError('直连下载进程失败；私人输出已隐藏。')
        rows = json.loads(result.stdout)
        if not isinstance(rows, list) or len(rows) != len(providers):
            raise CheckError('下载结果不完整。')
        if [row.get('name') for row in rows] != [item.name for item in providers]:
            raise CheckError('下载结果与当前 provider 清单不一致。')
        return rows
    except (subprocess.TimeoutExpired, OSError):
        raise CheckError('订阅下载超时或下载进程不可用。') from None
    except (json.JSONDecodeError, TypeError, AttributeError):
        raise CheckError('下载进程未返回完整结果；私人输出已隐藏。') from None


def evaluate(row: dict, now: int) -> dict:
    summary = {'provider': row['name'], 'http': row.get('status'), 'nodes': None,
               'remaining_percent': None, 'expire': None, 'quota': '未提供',
               'calendar': '未提供', 'errors': []}
    errors = summary['errors']
    if row.get('error'):
        errors.append('请求超时或传输失败')
    if row.get('status') != 200:
        errors.append('HTTP 非 200')
    else:
        try:
            document = load_yaml(row.get('body', ''))
            nodes = document.get('proxies') if isinstance(document, dict) else None
            if not isinstance(nodes, list) or not nodes or not all(
                isinstance(node, dict) and isinstance(node.get('name'), str) and node['name']
                and isinstance(node.get('type'), str) and node['type'] for node in nodes
            ):
                raise CheckError('缺少非空顶层 proxies 节点列表。')
            summary['nodes'] = len(nodes)
        except CheckError:
            errors.append('响应不是有效的非空 Clash YAML 节点列表')
    metadata = {}
    for key, value in re.findall(r'(?i)(upload|download|total|expire)\s*=\s*(\d+)', str(row.get('userinfo', ''))):
        key = key.lower()
        number = int(value)
        if key in metadata and metadata[key] != number:
            errors.append('订阅配额头冲突')
        metadata[key] = number
    if {'upload', 'download', 'total'} <= metadata.keys() and metadata['total'] > 0:
        used = metadata['upload'] + metadata['download']
        summary['remaining_percent'] = round(max(0, 100 * (1 - used / metadata['total'])), 2)
        summary['quota'] = '耗尽' if used >= metadata['total'] else '有剩余'
        if used >= metadata['total']:
            errors.append('订阅流量已耗尽')
    expire = metadata.get('expire', 0)
    if expire > 0:
        try:
            summary['expire'] = datetime.fromtimestamp(expire, timezone.utc).isoformat()
            summary['calendar'] = '已过期' if expire <= now else '未过期'
            if expire <= now:
                errors.append('订阅已过期')
        except (OverflowError, OSError, ValueError):
            errors.append('到期时间无效')
    summary['passed'] = not errors
    return summary


def run(directory: Path, fetch=transport, clock=time.monotonic) -> tuple[list[dict], bool]:
    deadline = clock() + 60
    providers = aligned_manifest(directory)
    if clock() >= deadline:
        raise CheckError('订阅检查已超出 60 秒总预算；未发送请求。')
    rows = fetch(providers, deadline)
    now = int(time.time())
    summaries = [evaluate(row, now) for row in rows]
    if clock() > deadline:
        raise CheckError('订阅检查已超出 60 秒总预算。')
    return summaries, all(item['passed'] for item in summaries)


def worker(directory: Path | None) -> int:
    try:
        summaries, passed = run(directory or default_directory())
        print(json.dumps({'subscription_downloads_passed': passed, 'providers': summaries,
                          'runtime': '节点存活与设备 DNS 出口未验收'}, ensure_ascii=False))
        return 0 if passed else 1
    except CheckError as error:
        print('[private-subscriptions] ' + str(error))
        return 1
    except (OSError, ValueError, TypeError, KeyError, OverflowError, AttributeError):
        print('[private-subscriptions] 检查失败；私人异常原文已隐藏。')
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-root', type=Path)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        return worker(args.private_root)
    command = [sys.executable, '-B', '-X', 'utf8', str(Path(__file__).resolve()), '--worker']
    if args.private_root:
        command.extend(['--private-root', str(args.private_root)])
    try:
        # 外层覆盖清单解析、下载和 YAML 解析，避免响应解析越过总预算。
        result = subprocess.run(command, capture_output=True, encoding='utf-8', timeout=60)
        if result.returncode not in (0, 1):
            raise CheckError('订阅检查子进程异常退出；私人输出已隐藏。')
        output = result.stdout.strip()
        if not output:
            raise CheckError('订阅检查未返回结果。')
        print(output)
        return result.returncode
    except (subprocess.TimeoutExpired, OSError):
        print('[private-subscriptions] 订阅检查超过 60 秒总预算或进程不可用。')
        return 1
    except CheckError as error:
        print('[private-subscriptions] ' + str(error))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
