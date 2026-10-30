"""六份私人配置的单美国落地链路；保留模块名兼容验收入口。"""
from pathlib import Path
import ipaddress

KEY = 'x-rulemesh-us-chain'
PROFILE = 'rulemesh-flclash-android.yaml'
PROFILES = {PROFILE, 'rulemesh-flclash-desktop.yaml',
            'rulemesh-clashmi-ios.yaml', 'rulemesh-surge-home.conf',
            'rulemesh-surge-company.conf', 'rulemesh-surge-work.conf'}
SURGE_MARKER = '# ' + KEY + ': '
FRONT = 'RM-US-Front'
FRONT_REGIONS = {'hk': '香港', 'tw': '台湾', 'jp': '日本', 'kr': '韩国', 'sg': '新加坡', 'us': '美国'}
FRONT_GROUPS = tuple(f'前置-{label}-自动选择' for label in FRONT_REGIONS.values())
QUARANTINE = 'x-rulemesh-android-provider-quarantine'
REGION = '🇺🇸 美国-自动选择'
HK_REGION = '🇭🇰 香港-自动选择'
US_EXITS = ('RM-US-Exit',)
HK_EXITS = ()
EXITS = US_EXITS + HK_EXITS
EXIT_REGIONS = {name: 'us' for name in US_EXITS} | {name: 'hk' for name in HK_EXITS}
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
    return any(line.startswith((KEY + ':', SURGE_MARKER)) for line in lines)


def registration_valid(registration):
    assert set(registration) == {'version', 'front', 'front-regions', 'region', 'exits', 'exit-identities'}
    assert registration['version'] == 4
    assert registration['front'] == FRONT and registration['front-regions'] == list(FRONT_GROUPS)
    assert registration['region'] == REGION and registration['exits'] == list(EXITS)
    identities = registration['exit-identities']
    assert len(identities) == 1
    identity = identities[0]
    assert set(identity) == {'name', 'region', 'ip', 'port'}
    assert identity['name'] == EXITS[0] and identity['region'] == 'US'
    assert isinstance(identity['ip'], str) and ipaddress.ip_address(identity['ip']).is_global
    assert type(identity['port']) is int and 1 <= identity['port'] <= 65535
    return identity


def validate(lines, interval=None):
    """完整候选图必须无环；解析错误只输出固定诊断，不回显凭据。"""
    from check_private_subscriptions import load_yaml
    if not present(lines):
        return ['私人美国链式授权登记缺失。']
    if any(line.startswith(SURGE_MARKER) for line in lines):
        return validate_surge(lines)
    try:
        assert lines.count(BUSINESS_MARKER) == 1
        data = load_yaml('\n'.join(lines))
        identity = registration_valid(data[KEY])
        assert 'x-rulemesh-android-us-chain' not in data
        nodes = data['proxies']
        assert isinstance(nodes, list) and len(nodes) == 1
        node = nodes[0]
        assert node['name'] == EXITS[0] and node['type'] == 'socks5'
        assert node['server'] == identity['ip'] and node['port'] == identity['port']
        assert node.get('udp') is False and node.get('dialer-proxy') == FRONT
        assert set(node) == {'name', 'type', 'server', 'port', 'username', 'password', 'udp', 'dialer-proxy'}
        assert all(isinstance(node[k], str) and node[k] and '\r' not in node[k] and '\n' not in node[k] for k in ('server', 'username', 'password'))
        rows = data['proxy-groups']; groups = {g['name']: g for g in rows}
        assert len(groups) == len(rows) and not (set(EXITS) & groups.keys())
        assert 'RM-HK-Front' not in groups
        front = groups[FRONT]
        assert front == {'name': FRONT, 'type': 'select', 'hidden': False, 'proxies': list(FRONT_GROUPS)}
        assert {n for n in groups if n.startswith('前置-')} == set(FRONT_GROUPS)
        region = groups[REGION]
        cycle = region.get('interval')
        assert cycle in (300, 600) and (interval is None or cycle == interval)
        for code, name in zip(FRONT_REGIONS, FRONT_GROUPS):
            child = groups[name]
            assert child['type'] == 'url-test' and child.get('hidden') is False
            assert child['filter'] == front_region_filter(code) and child.get('exclude-filter')
            assert set(child) <= {'name', 'type', 'hidden', 'filter', 'exclude-filter', 'use', 'url', 'interval', 'lazy', 'tolerance', 'timeout'}
            assert set(child['use']) == set(data['proxy-providers']) and len(child['use']) == len(data['proxy-providers'])
            assert child['url'] == 'https://www.google.com/generate_204'
            assert child['interval'] == cycle and child['lazy'] is True
            assert child['tolerance'] == (100 if code == 'us' else 50)
        # Singleton LB prevents TCP-only Selector causing UDP to skip to MATCH,DIRECT.
        assert region['type'] == 'load-balance' and region['proxies'] == list(US_EXITS)
        assert region.get('hidden') is False and region.get('strategy') == 'consistent-hashing'
        assert region.get('lazy') is False and region.get('url') == 'https://www.google.com/generate_204'
        assert set(region) <= {'name', 'type', 'proxies', 'strategy', 'hidden', 'url', 'interval', 'lazy', 'timeout'}
        assert groups['AI']['proxies'] == [REGION]
        assert groups['Microsoft']['proxies'] == [REGION, 'DIRECT']
        # Hong Kong is an ordinary airport path again, never a purchased chain exit.
        hk = groups[HK_REGION]
        assert hk['type'] in ('select', 'url-test') and not hk.get('proxies')
        assert hk['filter'] == front_region_filter('hk')
        assert set(hk['use']) == set(data['proxy-providers'])
        assert not any(hk.get(k) for k in ('include-all', 'include-all-proxies', 'include-all-providers', 'dialer-proxy'))
        assert groups['香港券商']['proxies'] == ['香港-' + name for name in data['proxy-providers']]
        assert groups['Google']['proxies'][0] == HK_REGION
        assert not any(g.get('dialer-proxy') for g in rows)
        assert not any(g['name'].startswith('美国-') for g in rows)
        assert not any(rule.split(',')[-1] in EXITS for rule in data.get('rules', []))
        assert sum('dialer-proxy:' in line for line in lines if not line.lstrip().startswith('#')) == 1
        if QUARANTINE in data:
            validate_quarantine(data)
            from check_android_stability import GOOGLE_HK_QUARANTINE, google_hk_exclusion
            suffix = google_hk_exclusion(data[GOOGLE_HK_QUARANTINE])
            for group in (groups[FRONT_GROUPS[0]], hk):
                assert group['exclude-filter'].endswith(suffix) and group['exclude-filter'].count(suffix) == 1
    except Exception:
        return ['私人美国单落地链式结构不完整或越界；私人字段与异常原文已隐藏。']
    return []


def surge_definitions(lines, section):
    from check_private_dns_precedence import _active_surge_section, _split_surge_definition, _scalar
    result = {}
    for _, line in _active_surge_section(lines, section):
        name, value = line.split('=', 1)
        name = _scalar(name)
        assert name not in result
        result[name] = [_scalar(p) for p in _split_surge_definition(value)]
    return result


def validate_surge(lines):
    import json
    try:
        for section in ('Proxy', 'Proxy Group', 'General', 'Rule'):
            assert lines.count('[' + section + ']') == 1
        metadata = [s[len(SURGE_MARKER):] for s in lines if s.startswith(SURGE_MARKER)]
        assert len(metadata) == 1
        identity = registration_valid(json.loads(metadata[0]))
        nodes = surge_definitions(lines, 'Proxy')
        assert set(nodes) == set(EXITS)
        node = nodes[EXITS[0]]
        assert node[:3] == ['socks5', identity['ip'], str(identity['port'])]
        options = dict(p.split('=', 1) for p in node[3:])
        assert len(options) == len(node[3:])
        assert set(options) == {'username', 'password', 'underlying-proxy', 'udp-relay'}
        assert options['username'] and options['password']
        assert options['underlying-proxy'] == FRONT and options['udp-relay'] == 'false'
        groups = surge_definitions(lines, 'Proxy Group')
        assert 'RM-HK-Front' not in groups
        assert groups[FRONT] == ['select', *FRONT_GROUPS, 'hidden=0']
        assert groups[REGION] == ['select', EXITS[0], 'hidden=0']
        assert groups['Microsoft'] == ['select', REGION, 'DIRECT', 'hidden=0']
        assert groups['AI'][0] == 'url-test' and groups['AI'][1] == REGION
        assert not any('=' not in p for p in groups['AI'][2:])
        airports = {n for n in groups if n.startswith('✈️ ')}
        assert airports and not any(n.startswith('美国-') for n in groups)
        for name in airports:
            assert groups[name][0] == 'select'
            opts = dict(p.split('=', 1) for p in groups[name][1:])
            assert opts.get('policy-path') and opts.get('include-all-proxies') == '0'
            assert 'include-other-group' not in opts and 'underlying-proxy' not in opts
        assert {n for n in groups if n.startswith('前置-')} == set(FRONT_GROUPS)
        from check_performance_baseline import region_filters
        for code, name in zip(FRONT_REGIONS, FRONT_GROUPS):
            child = groups[name]
            assert child[0] == 'url-test'
            opts = dict(p.split('=', 1) for p in child[1:])
            assert opts['include-all-proxies'] == '0'
            assert set(opts['include-other-group'].strip('"').split(',')) == airports
            assert opts['policy-regex-filter'] in region_filters(code, True)
            assert opts['hidden'] == '0' and opts['interval'] == '300'
            assert 'underlying-proxy' not in opts
        for name, parts in groups.items():
            assert not any(p.startswith('underlying-proxy=') for p in parts)
        assert sum('underlying-proxy=' in s for s in lines if not s.lstrip().startswith('#')) == 1
        assert 'udp-policy-not-supported-behaviour = REJECT' in lines
    except Exception:
        return ['Surge 美国单落地链式结构不完整或越界；私人字段与异常原文已隐藏。']
    return []


def check(path: Path, lines):
    if not present(lines):
        return []
    if path.name not in PROFILES:
        return ['美国链式例外仅限明确登记的六份私人配置。']
    if path.suffix == '.conf':
        return validate_surge(lines)
    errors = validate(lines, 300 if 'desktop' in path.name else 600)
    if path.name == PROFILE and not any(s.startswith(QUARANTINE + ':') for s in lines):
        errors.append('安卓历史隔离证据必须保留。')
    return errors
