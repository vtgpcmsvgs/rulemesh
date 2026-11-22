"""当前私人美国出口使用机场节点；拒绝恢复已撤销的链式资产。"""
from pathlib import Path
import re

MARKER = '# RuleMesh 美国机场节点：2026-11-07'
PROFILES = frozenset({'rulemesh-flclash-desktop.yaml', 'rulemesh-flclash-android.yaml',
                      'rulemesh-clashmi-ios.yaml', 'rulemesh-surge-home.conf',
                      'rulemesh-surge-company.conf', 'rulemesh-surge-work.conf'})
US_GROUP = '🇺🇸 美国-自动选择'
ALIASES = {'diidao': 'didiao'}


def child_name(provider):
    return '美国-' + ALIASES.get(provider, provider)


def forbidden_name(name):
    return (name in {'美国线路入口', 'RM-US-Front', 'RM-HK-Front'}
            or name.startswith(('RM-US-', 'RM-HK-', '前置-'))
            or name.startswith('经') and name.endswith('接入'))


def validate(path: Path, lines):
    from check_private_subscriptions import load_yaml
    from check_performance_baseline import region_filters
    from check_android_us_chain import surge_definitions, validate_quarantine, QUARANTINE
    try:
        assert lines.count(MARKER) == 1
        assert not any('x-rulemesh-us-chain' in s or 'x-rulemesh-android-us-chain' in s for s in lines)
        assert not any(re.search(r'\b(?:dialer-proxy\s*:|underlying-proxy\s*=)', s)
                       for s in lines if not s.lstrip().startswith('#'))
        if path.suffix == '.conf':
            groups = surge_definitions(lines, 'Proxy Group')
            assert not surge_definitions(lines, 'Proxy')
            airports = {name.removeprefix('✈️ '): parts for name, parts in groups.items()
                        if name.startswith('✈️ ')}
            assert airports
            children = ['美国-' + name for name in airports]
            ai = groups['AI']
            assert ai[0] == 'url-test' and [p for p in ai[1:] if '=' not in p] == children
            assert groups['Microsoft'] == ['select', *children, 'DIRECT', 'hidden=0']
            assert groups[US_GROUP][0] == 'url-test'
            for label, airport in airports.items():
                leaf = groups['美国-' + label]
                options = dict(p.split('=', 1) for p in leaf[1:] if '=' in p)
                original = dict(p.split('=', 1) for p in airport[1:] if '=' in p)
                assert leaf[0] == 'url-test' and len(options) == len(leaf) - 1
                assert options['policy-path'] == original['policy-path']
                assert options['policy-regex-filter'] in region_filters('us', True)
                assert options['include-all-proxies'] == '0' and 'include-other-group' not in options
                assert options['interval'] == '300'
            assert not any('udp-policy-not-supported-behaviour' in s for s in lines)
        else:
            data = load_yaml('\n'.join(lines))
            assert not data.get('proxies')
            providers = data['proxy-providers']
            groups = {g['name']: g for g in data['proxy-groups']}
            assert len(groups) == len(data['proxy-groups'])
            children = [child_name(name) for name in providers]
            assert groups['AI']['type'] == 'select' and groups['AI']['proxies'] == children
            assert groups['Microsoft']['type'] == 'select'
            assert groups['Microsoft']['proxies'] == [*children, 'DIRECT']
            assert groups[US_GROUP]['type'] == 'url-test'
            assert groups[US_GROUP]['lazy'] is False
            assert set(groups[US_GROUP]['use']) == set(providers)
            expected_filter = {s.replace('\\\\', '\\') for s in region_filters('us', False)}
            assert groups[US_GROUP]['filter'] in expected_filter
            cycle = 300 if 'desktop' in path.name else 600
            for provider in providers:
                leaf = groups[child_name(provider)]
                assert leaf['type'] == 'url-test' and leaf['use'] == [provider]
                assert not leaf.get('proxies') and leaf['filter'] in expected_filter
                assert leaf['interval'] == cycle and leaf['tolerance'] == 100
                assert leaf['lazy'] is False and leaf.get('exclude-filter')
                assert not any(leaf.get(k) for k in ('include-all', 'include-all-proxies', 'include-all-providers'))
            if path.name == 'rulemesh-flclash-android.yaml':
                assert QUARANTINE in data
                validate_quarantine(data)
        assert not any(forbidden_name(name) for name in groups)
        assert {name for name in groups if name.startswith('美国-')} == set(children)
    except Exception:
        return ['美国机场节点结构不完整或仍有已撤销的链式资产；私人字段已隐藏。']
    return []


def check(path, lines):
    return validate(path, lines) if path.name in PROFILES and MARKER in lines else []
