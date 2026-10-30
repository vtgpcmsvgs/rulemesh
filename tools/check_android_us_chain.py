"""安卓私人链式出口：两个美国负载均衡、一个香港固定出口。"""
from pathlib import Path
import ipaddress

KEY = 'x-rulemesh-android-us-chain'
PROFILE = 'rulemesh-flclash-android.yaml'
FRONT = 'RM-US-Front'
FRONT_REGIONS = {'hk': '香港', 'tw': '台湾', 'jp': '日本', 'kr': '韩国', 'sg': '新加坡', 'us': '美国'}
FRONT_GROUPS = tuple(f'前置-{label}-自动选择' for label in FRONT_REGIONS.values())
QUARANTINE = 'x-rulemesh-android-provider-quarantine'
REGION = '🇺🇸 美国-自动选择'
HK_REGION = '🇭🇰 香港-自动选择'
US_EXITS = ('美国-Comcast-01', '美国-Comcast-02')
HK_EXITS = ('香港-Lumen-01',)
EXITS = US_EXITS + HK_EXITS
EXIT_REGIONS = {name: 'us' for name in US_EXITS} | {name: 'hk' for name in HK_EXITS}
EXIT_PORTS = {
    '美国-Comcast-01': 10002,
    '美国-Comcast-02': 10003,
    '香港-Lumen-01': 10001,
}
EXIT_IDENTITY_FIELDS = {
    '美国-Comcast-01': {'region': 'US', 'city': 'Boston', 'asn': 7015},
    '美国-Comcast-02': {'region': 'US', 'city': 'Boston', 'asn': 7015},
    '香港-Lumen-01': {'region': 'HK', 'city': 'Hong Kong', 'asn': 10753},
}
BUSINESS_MARKER = '# RuleMesh 业务策略组：2026-09-25'


def front_region_filter(code):
    """基线集合用于 YAML 文本检查；正式解析后的正则需还原一层反斜杠。"""
    from check_performance_baseline import region_filters
    return next(iter(region_filters(code, False))).replace('\\\\', '\\')


def confirmed_redirect(evidence):
    """超时、未完成 TLS 和无归属的失败不能冒充已证实的 Google 跳转。"""
    return (isinstance(evidence, dict) and evidence.get('http_status') in (301, 302, 303, 307, 308)
            and evidence.get('final_host_role') == 'google_cn'
            and evidence.get('tls_handshake_completed') is True
            and evidence.get('certificate_verify_result') == 0)


def quarantine_pattern(names):
    """只按完整名称排除；真实名称和表达式留在私人配置。"""
    import re
    return '^(?:' + '|'.join(re.escape(name) for name in names) + ')$'


def provider_match_name(provider, displayed_name):
    """provider 过滤先于 override 名称前后缀，须按订阅原始名称精确匹配。"""
    override = provider.get('override', {})
    prefix = override.get('additional-prefix', '')
    suffix = override.get('additional-suffix', '')
    assert isinstance(prefix, str) and isinstance(suffix, str)
    assert displayed_name.startswith(prefix) and displayed_name.endswith(suffix)
    end = len(displayed_name) - len(suffix) if suffix else len(displayed_name)
    raw = displayed_name[len(prefix):end]
    assert raw
    return raw


def validate_quarantine(data):
    quarantine = data[QUARANTINE]
    assert set(quarantine) == {'version', 'nodes'} and quarantine['version'] == 1
    entries = quarantine['nodes']
    assert isinstance(entries, list) and entries
    providers = data['proxy-providers']; blocked = data['x-rulemesh-android-google-hk-blocked-nodes']
    by_provider = {}
    for entry in entries:
        assert set(entry) == {'provider', 'name', 'reason', 'evidence'}
        assert entry['provider'] in providers and entry['name'] in blocked
        assert entry['reason'] == 'google_cn_redirect' and confirmed_redirect(entry['evidence'])
        names = by_provider.setdefault(entry['provider'], [])
        original_name = provider_match_name(providers[entry['provider']], entry['name'])
        assert original_name not in names
        names.append(original_name)
    for name, provider in providers.items():
        expected = quarantine_pattern(by_provider[name]) if name in by_provider else None
        assert provider.get('exclude-filter') == expected


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
        registration = data[KEY]
        assert registration['version'] == 3
        assert registration['front'] == FRONT and registration['front-regions'] == list(FRONT_GROUPS)
        assert registration['regions'] == {'us': REGION, 'hk': HK_REGION}
        assert registration['us-exits'] == list(US_EXITS)
        assert registration['hk-exits'] == list(HK_EXITS)
        assert registration['exits'] == list(EXITS)
        identities = registration['exit-identities']
        assert isinstance(identities, list) and len(identities) == len(EXITS)
        assert {item.get('name') for item in identities} == set(EXITS)
        assert len({item.get('ip') for item in identities}) == len(EXITS)
        for item in identities:
            expected = EXIT_IDENTITY_FIELDS[item['name']]
            assert item['name'] in EXIT_REGIONS
            assert item.get('region') == expected['region'] and item.get('city') == expected['city']
            assert item.get('asn') == expected['asn'] and item.get('port') == EXIT_PORTS[item['name']]
            assert isinstance(item.get('ip'), str) and ipaddress.ip_address(item['ip']).is_global
        validate_quarantine(data)
        nodes = data['proxies']
        assert isinstance(nodes, list) and len(nodes) == len(EXITS)
        assert [n['name'] for n in nodes] == list(EXITS)
        assert {n['port'] for n in nodes} == set(EXIT_PORTS.values())
        for i, node in enumerate(nodes):
            assert node['type'] == 'socks5' and node['port'] == EXIT_PORTS[node['name']]
            assert type(node['port']) is int and node.get('udp') is False
            assert node.get('dialer-proxy') == FRONT
            assert set(node) == {'name', 'type', 'server', 'port', 'username', 'password', 'udp', 'dialer-proxy'}
            assert all(isinstance(node[k], str) and node[k] and '\r' not in node[k] and '\n' not in node[k] for k in ('server', 'username', 'password'))
        assert all(len({n[k] for n in nodes}) == 1 for k in ('server', 'username', 'password'))
        rows = data['proxy-groups']; groups = {g['name']: g for g in rows}
        assert len(groups) == len(rows) and not (set(EXITS) & groups.keys())
        front = groups[FRONT]
        assert front['type'] == 'select' and front['proxies'] == list(FRONT_GROUPS)
        assert not front.get('use') and not front.get('filter') and not front.get('exclude-filter')
        assert front.get('hidden') is False
        assert not any(k in front for k in ('url', 'interval', 'tolerance', 'timeout', 'lazy'))
        assert not any(front.get(k) for k in ('include-all', 'include-all-providers', 'include-all-proxies'))
        from check_android_stability import GOOGLE_HK_QUARANTINE, google_hk_exclusion
        assert {name for name in groups if name.startswith('前置-')} == set(FRONT_GROUPS)
        for (code, _), name in zip(FRONT_REGIONS.items(), FRONT_GROUPS):
            child = groups[name]
            assert child['type'] == 'url-test' and child.get('hidden') is False
            assert child['filter'] == front_region_filter(code) and child.get('exclude-filter')
            assert not child.get('proxies') and not any(child.get(k) for k in ('include-all', 'include-all-providers', 'include-all-proxies'))
            assert set(child['use']) == set(data['proxy-providers']) and len(child['use']) == len(data['proxy-providers'])
            assert child['url'] == 'https://www.google.com/generate_204'
            assert child['interval'] == 600 and child['lazy'] is True
            assert child['tolerance'] == (100 if code == 'us' else 50)
            if code == 'hk':
                assert child['exclude-filter'].endswith(google_hk_exclusion(data[GOOGLE_HK_QUARANTINE]))
                assert child['exclude-filter'].count(google_hk_exclusion(data[GOOGLE_HK_QUARANTINE])) == 1
        region = groups[REGION]
        assert region['type'] == 'load-balance' and region['proxies'] == list(US_EXITS)
        assert region.get('hidden') is False and region.get('strategy') == 'consistent-hashing'
        assert not region.get('use') and not any(region.get(k) for k in ('include-all', 'include-all-providers', 'include-all-proxies'))
        assert region.get('lazy') is False and region.get('interval') == 600 and 'tolerance' not in region
        assert region.get('url') == 'https://www.google.com/generate_204'
        assert set(region) <= {'name', 'type', 'proxies', 'strategy', 'hidden', 'url', 'interval', 'lazy', 'timeout'}
        hk_region = groups[HK_REGION]
        # Selector forwards a TCP-only leaf's SupportUDP=false, allowing Mihomo to skip
        # the matching rule and eventually use DIRECT. A singleton LoadBalance keeps
        # routing on the fixed exit and lets unsupported UDP fail at that exit.
        assert hk_region['type'] == 'load-balance' and hk_region['proxies'] == list(HK_EXITS)
        assert hk_region.get('hidden') is False
        assert set(hk_region) == {'name', 'type', 'proxies', 'hidden', 'strategy', 'url', 'interval', 'lazy'}
        assert hk_region.get('strategy') == 'consistent-hashing'
        assert hk_region.get('url') == 'https://www.google.com/generate_204'
        assert hk_region.get('interval') == 600 and hk_region.get('lazy') is False
        assert groups['AI']['proxies'] == [REGION]
        assert groups['Microsoft']['proxies'] == [REGION, 'DIRECT']
        assert groups['香港券商']['proxies'] == [HK_REGION]
        assert groups['Google']['proxies'][0] == '🇭🇰 香港-自动选择'
        assert not any(g.get('dialer-proxy') for g in rows)
        assert not any(g['name'].startswith(('美国-', '香港-')) for g in rows)
        assert not any(rule.split(',')[-1] in EXITS for rule in data.get('rules', []))
        # 只有登记的三个落地节点可以拥有 dialer-proxy；防止 provider 或 DNS 额外挂拨号链。
        assert sum('dialer-proxy:' in line for line in lines if not line.lstrip().startswith('#')) == len(EXITS)
    except Exception:
        return ['安卓链式出口结构不完整或越界；私人字段与异常原文已隐藏。']
    return []


def check(path: Path, lines):
    if not present(lines):
        return []
    if path.name != PROFILE:
        return ['安卓链式出口例外仅限已授权的安卓私人配置。']
    return validate(lines)
