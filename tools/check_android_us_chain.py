"""2026-10-24 明确授权的安卓美国五出口链路；不放开其他客户端的旧链式资产。"""
from pathlib import Path

KEY = 'x-rulemesh-android-us-chain'
PROFILE = 'rulemesh-flclash-android-20261023.yaml'
FRONT = 'RM-US-Front'
REGION = '🇺🇸 美国-自动选择'
EXITS = tuple(f'美国原生-{i:02d}' for i in range(1, 6))
BUSINESS_MARKER = '# RuleMesh 业务策略组：2026-09-25'


def present(lines):
    return any(line.startswith(KEY + ':') for line in lines)


def validate(lines):
    """返回固定诊断；所有敏感 YAML 与解析异常仅在内存中处理。"""
    from check_private_subscriptions import load_yaml
    if not present(lines):
        return ['安卓美国链式授权登记缺失。']
    try:
        assert lines.count(BUSINESS_MARKER) == 1
        data = load_yaml('\n'.join(lines))
        assert data[KEY] == {'version': 1, 'front': FRONT, 'region': REGION, 'exits': list(EXITS)}
        nodes = data['proxies']
        assert isinstance(nodes, list) and len(nodes) == 5
        assert [n['name'] for n in nodes] == list(EXITS)
        assert {n['port'] for n in nodes} == set(range(10001, 10006))
        for i, node in enumerate(nodes):
            assert node['type'] == 'socks5' and node['port'] == 10001 + i
            assert type(node['port']) is int and node.get('udp') is False
            assert node.get('dialer-proxy') == FRONT
            assert set(node) == {'name', 'type', 'server', 'port', 'username', 'password', 'udp', 'dialer-proxy'}
            assert all(isinstance(node[k], str) and node[k] and '\r' not in node[k] and '\n' not in node[k] for k in ('server', 'username', 'password'))
        assert all(len({n[k] for n in nodes}) == 1 for k in ('server', 'username', 'password'))
        rows = data['proxy-groups']; groups = {g['name']: g for g in rows}
        assert len(groups) == len(rows) and not (set(EXITS) & groups.keys())
        front = groups[FRONT]
        assert front['type'] == 'select' and not front.get('proxies')
        assert set(front['use']) == set(data['proxy-providers']) and len(front['use']) == len(data['proxy-providers'])
        assert not front.get('filter') and front.get('exclude-filter')
        assert front.get('hidden') is False
        assert not any(k in front for k in ('url', 'interval', 'tolerance', 'timeout', 'lazy'))
        region = groups[REGION]
        assert region['type'] == 'url-test' and region['proxies'] == list(EXITS)
        assert region.get('hidden') is False
        assert not region.get('use') and not any(region.get(k) for k in ('include-all', 'include-all-providers', 'include-all-proxies'))
        assert region.get('lazy') is False and region.get('interval') == 600 and region.get('tolerance') == 100
        assert region.get('url') == 'https://www.google.com/generate_204'
        assert groups['AI']['proxies'] == [REGION]
        assert groups['Microsoft']['proxies'] == [REGION, 'DIRECT']
        assert groups['Google']['proxies'][0] == '🇭🇰 香港-自动选择'
        assert not any(g.get('dialer-proxy') for g in rows)
        assert not any(g['name'].startswith('美国-') for g in rows)
        # 只有五个落地节点可以拥有 dialer-proxy；防止 provider 或 DNS 额外挂拨号链。
        assert sum('dialer-proxy:' in line for line in lines if not line.lstrip().startswith('#')) == 5
    except Exception:
        return ['安卓美国五出口链式结构不完整或越界；私人字段与异常原文已隐藏。']
    return []


def check(path: Path, lines):
    if not present(lines):
        return []
    if path.name != PROFILE:
        return ['美国五出口链式例外仅限已授权的安卓私人配置。']
    return validate(lines)
