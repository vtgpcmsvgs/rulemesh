from pathlib import Path
import copy
import json
import sys
import unittest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import check_android_us_chain as chain
import check_private_dns_precedence as dns
import check_performance_baseline as baseline


def document():
    nodes = [{'name': name, 'type': 'socks5', 'server': '8.8.8.8',
              'port': 1080, 'username': 'fixture-user', 'password': 'fixture-secret',
              'udp': False, 'dialer-proxy': chain.FRONT} for i, name in enumerate(chain.EXITS)]
    health = {'type': 'url-test', 'url': 'https://www.google.com/generate_204', 'interval': 600, 'lazy': False}
    blocked = ['fixture-bad[1]']
    from check_android_stability import google_hk_exclusion
    front_groups = [{'name': name, **health, 'hidden': True, 'lazy': True,
                     'tolerance': 100 if code == 'us' else 50,
                     'filter': chain.front_region_filter(code), 'use': ['fixture'],
                     'exclude-filter': '套餐' + (google_hk_exclusion(blocked) if code == 'hk' else '')}
                    for code, name in chain.FRONT_REGIONS.items()]
    return {'proxies': nodes, 'proxy-providers': {'fixture': {'exclude-filter': chain.quarantine_pattern(blocked)}},
            'x-rulemesh-android-google-hk-blocked-nodes': blocked,
            chain.QUARANTINE: {'version': 1, 'nodes': [{'provider': 'fixture', 'name': blocked[0],
                'reason': 'google_cn_redirect', 'evidence': {'http_status': 302, 'final_host_role': 'google_cn',
                    'tls_handshake_completed': True, 'certificate_verify_result': 0}}]},
            chain.KEY: {'version': 6, 'front': chain.FRONT, 'front-mode': 'regional-airport-select', 'front-regions': list(chain.FRONT_GROUPS),
                        'region': chain.REGION, 'exits': list(chain.EXITS), 'exit-identities': [
                            {'name': chain.EXITS[0], 'region': 'US', 'ip': '8.8.8.8', 'port': 1080},
                        ]},
            'proxy-groups': [
                {'name': chain.FRONT, 'type': 'select', 'hidden': False, 'proxies': list(chain.FRONT_GROUPS)},
                {'name': chain.REGION, 'type': 'load-balance', 'strategy': 'consistent-hashing', **{k: v for k, v in health.items() if k != 'type'}, 'hidden': True, 'proxies': list(chain.US_EXITS)},
                {'name': chain.HK_REGION, 'type': 'select', 'hidden': False, 'use': ['fixture'], 'filter': chain.front_region_filter('hk'), 'exclude-filter': '套餐'+google_hk_exclusion(blocked)},
                {'name': 'AI', 'type': 'select', 'proxies': [chain.REGION]},
                {'name': 'Microsoft', 'type': 'select', 'proxies': [chain.REGION, 'DIRECT']},
                {'name': '香港券商', 'type': 'select', 'proxies': ['香港-fixture']},
                {'name': 'Google', 'type': 'select', 'proxies': [chain.HK_REGION, chain.REGION]}, *front_groups]}


def lines(data):
    # 保持生产解析器所支持的两空格列表格式，避免夹具用不同 YAML 布局假通过。
    class Indented(yaml.SafeDumper):
        def increase_indent(self, flow=False, indentless=False):
            return super().increase_indent(flow, False)
    return [chain.BUSINESS_MARKER, *yaml.dump(data, Dumper=Indented, allow_unicode=True, sort_keys=False).splitlines()]


class AndroidUsChainTests(unittest.TestCase):
    def test_each_mihomo_client_uses_its_interval_and_hk_has_no_chain(self):
        for profile in ('rulemesh-flclash-desktop.yaml', 'rulemesh-clashmi-ios.yaml', chain.PROFILE):
            data = document()
            interval = 300 if 'desktop' in profile else 600
            for group in data['proxy-groups']:
                if 'interval' in group:
                    group['interval'] = interval
            self.assertFalse(chain.check(Path(profile), lines(data)))
            data['proxies'][0]['dialer-proxy'] = chain.HK_REGION
            self.assertTrue(chain.check(Path(profile), lines(data)))

    def test_surge_single_exit_semantics_and_no_front_cycles(self):
        data = document()
        definition = ['[General]', 'udp-policy-not-supported-behaviour = REJECT', '[Proxy]',
                      'RM-US-Exit = socks5, 8.8.8.8, 1080, username=fixture, password=fixture, underlying-proxy='+chain.FRONT+', udp-relay=false',
                      '[Proxy Group]', '✈️ fixture = select, policy-path=https://fixture.invalid/sub, include-all-proxies=0',
                      chain.FRONT + ' = select, ' + ', '.join(chain.FRONT_GROUPS) + ', hidden=0',
                      chain.REGION + ' = select, RM-US-Exit, hidden=1',
                      'AI = url-test, ' + chain.REGION + ', interval=300, hidden=0',
                      'Microsoft = select, ' + chain.REGION + ', DIRECT, hidden=0']
        for code, name in chain.FRONT_REGIONS.items():
            definition.append(name + ' = url-test, include-all-proxies=0, include-other-group="✈️ fixture", policy-regex-filter=' + chain.surge_front_filter(code) + ', interval=300, hidden=1')
        definition += ['[Rule]', 'FINAL,REJECT', chain.SURGE_MARKER + json.dumps(data[chain.KEY])]
        for profile in sorted(chain.PROFILES):
            if profile.endswith('.conf'):
                self.assertFalse(chain.check(Path(profile), definition))
        groups = dns._parse_surge_groups(definition)
        self.assertTrue(dns._group_has_us_semantics('AI', groups, dns.APPROVED_SURGE_US_FILTERS))
        self.assertFalse(dns._group_has_us_semantics('AI', groups, baseline.region_filters('hk', True)))
        for old, new in [('underlying-proxy='+chain.FRONT, 'underlying-proxy=' + chain.REGION),
                         ('underlying-proxy='+chain.FRONT, 'underlying-proxy=' + chain.LEGACY_FRONT),
                         ('udp-relay=false', 'udp-relay=true'),
                         ('behaviour = REJECT', 'behaviour = DIRECT'),
                         ('RM-US-Exit, hidden=1', 'RM-US-Exit, hidden=0'),
                         (chain.surge_front_filter('us'), baseline.METADATA_FILTER),
                         ('interval=300, hidden=1', 'interval=300, hidden=0'),
                         ('include-all-proxies=0', 'include-all-proxies=1'),
                         ('include-other-group="✈️ fixture"', 'include-other-group="' + chain.REGION + '"')]:
            mutated = [line.replace(old, new) for line in definition]
            self.assertNotEqual(mutated, definition)
            self.assertTrue(chain.validate_surge(mutated))
        self.assertTrue(chain.validate_surge([line for line in definition if line != '[Proxy]']))

    def test_hk_brokers_and_all_final_groups_cannot_bypass_registered_exits(self):
        for name, key, value in ((chain.HK_REGION, 'include-all', True),
                                 (chain.HK_REGION, 'type', 'load-balance'),
                                 (chain.HK_REGION, 'filter', 'missing'),
                                 (chain.REGION, 'exclude-filter', '.*'),
                                 ('香港券商', 'proxies', ['airport-hk'])):
            data = document()
            next(g for g in data['proxy-groups'] if g['name'] == name)[key] = value
            self.assertTrue(chain.validate(lines(data)))
        data = document(); data[chain.KEY]['exit-identities'].append(copy.deepcopy(data[chain.KEY]['exit-identities'][0]))
        self.assertTrue(chain.validate(lines(data)))
        data = document(); data['rules'] = ['DOMAIN,fixture.invalid,' + chain.US_EXITS[0]]
        self.assertTrue(chain.validate(lines(data)))

    def test_authorized_single_us_structure_and_only_us_semantics(self):
        data = document(); text = lines(data)
        self.assertEqual(chain.check(Path(chain.PROFILE), text), [])
        groups = dns._parse_mihomo_groups(text)
        self.assertTrue(dns._group_has_us_semantics('AI', groups, dns.APPROVED_MIHOMO_US_FILTERS))
        self.assertFalse(dns._group_has_us_semantics('AI', groups, baseline.region_filters('hk', False)))
        self.assertTrue(chain.check(Path('desktop.yaml'), text))

    def test_final_exit_group_is_hidden_but_front_remains_visible(self):
        for index in (1,):
            for hidden in (False, None, 'true'):
                data = document()
                region = data['proxy-groups'][index]
                if hidden is None:
                    region.pop('hidden')
                else:
                    region['hidden'] = hidden
                with self.subTest(index=index, hidden=hidden):
                    self.assertTrue(chain.validate(lines(data)))
        data = document(); data['proxy-groups'][0]['hidden'] = True
        self.assertTrue(chain.validate(lines(data)))

    def test_wrong_cardinality_ports_missing_auth_and_direct_dialing_fail(self):
        changes = []
        for key, value in [('port', 80), ('password', ''), ('dialer-proxy', 'DIRECT'), ('udp', True), ('server', 'different.invalid')]:
            data = document(); data['proxies'][0][key] = value; changes.append(data)
        data = document(); data['proxies'].pop(); changes.append(data)
        data = document(); data['proxies'].append(copy.deepcopy(data['proxies'][0])); changes.append(data)
        for data in changes:
            with self.subTest(index=changes.index(data)):
                self.assertTrue(chain.validate(lines(data)))
                self.assertNotIn('fixture-secret', json.dumps(chain.validate(lines(data))))

    def test_provider_leak_recursive_front_and_airport_fallback_fail(self):
        for index, key, value in [(0, 'proxies', [chain.REGION]), (0, 'use', ['unknown']),
                                  (1, 'use', ['fixture']), (1, 'proxies', list(chain.EXITS) + ['DIRECT']),
                                  (2, 'proxies', ['airport-hk']), (4, 'proxies', [chain.REGION])]:
            data = document(); data['proxy-groups'][index][key] = value
            self.assertTrue(chain.validate(lines(data)))
        data = document(); data['proxy-groups'][0]['dialer-proxy'] = chain.REGION
        self.assertTrue(chain.validate(lines(data)))

    def test_single_front_rejects_group_cycles_and_keeps_all_airport_sources(self):
        self.assertFalse(chain.validate(lines(document())))
        for key, value in [('proxies', [chain.REGION]), ('proxies', [chain.FRONT]),
                           ('proxies', list(chain.EXITS)), ('proxies', ['DIRECT']),
                           ('use', []), ('use', ['fixture', 'fixture']), ('filter', '.*'),
                           ('type', 'url-test'), ('include-all', True), ('include-all-proxies', True),
                           ('interval', 300), ('hidden', True), ('exclude-filter', '')]:
            data = document(); data['proxy-groups'][0][key] = value
            with self.subTest(field=key, value=value):
                self.assertTrue(chain.validate(lines(data)))
        data = document(); data['proxy-groups'].append({'name': '前置-香港-自动选择', 'type': 'url-test', 'use': ['fixture']})
        self.assertTrue(chain.validate(lines(data)))
        data = document(); data['proxy-groups'][0]['proxies'].reverse()
        self.assertTrue(chain.validate(lines(data)))
        data = document(); data['proxy-groups'].append({'name': chain.LEGACY_FRONT, 'type': 'select', 'proxies': list(chain.FRONT_GROUPS)})
        self.assertTrue(chain.validate(lines(data)))

    def test_regional_helpers_are_hidden_airport_only_and_correctly_filtered(self):
        for code, name in chain.FRONT_REGIONS.items():
            for key, value in [('hidden', False), ('hidden', 'true'), ('use', []), ('type', 'select'),
                               ('filter', '.*'), ('filter', chain.front_region_filter('us' if code != 'us' else 'hk')),
                               ('proxies', [chain.REGION]), ('proxies', [chain.FRONT]),
                               ('proxies', list(chain.US_EXITS)), ('proxies', ['DIRECT']),
                               ('include-all', True), ('include-all-proxies', True), ('lazy', False), ('interval', 300)]:
                data = document(); next(g for g in data['proxy-groups'] if g['name'] == name)[key] = value
                with self.subTest(region=code, field=key):
                    self.assertTrue(chain.validate(lines(data)))
        data = document(); data['proxy-groups'].pop()
        self.assertTrue(chain.validate(lines(data)))

    def test_business_hk_filter_still_matches_bare_country_code(self):
        import re
        parsed = yaml.safe_load('\n'.join(lines(document())))
        groups = {g['name']: g for g in parsed['proxy-groups']}
        pattern = groups[chain.HK_REGION]['filter']
        self.assertIsNotNone(re.search(pattern, 'Airport HK 01'))
        self.assertIsNone(re.search(pattern, 'prefixhksuffix'))

    def test_front_us_filters_match_country_labels_without_wide_substrings(self):
        import re
        data = yaml.safe_load('\n'.join(lines(document())))
        pattern = next(g for g in data['proxy-groups'] if g['name'] == chain.FRONT_REGIONS['us'])['filter']
        for expression in (pattern, chain.surge_front_filter('us')):
            for name in ('fixture | 🇺🇸 01', 'fixture | 美国 02', 'fixture | United States 03', 'fixture | US 04', 'fixture | us-05'):
                self.assertIsNotNone(re.search(expression, name))
            for name in ('fixture | HK 01', 'fixture | 香港 01', 'fixture | JP 01', 'fixture | RUSSIA', 'fixture | AUS', 'fixture | BUS'):
                self.assertIsNone(re.search(expression, name))
        for name in ('直接连接', '剩余流量 US 88GB', '套餐到期 美国', 'Traffic Reset US in 3 days'):
            self.assertIsNone(re.search(chain.surge_front_filter('us'), name))
        for bad_filter in (None, '.*', chain.front_region_filter('hk')):
            bad = document()
            group = next(g for g in bad['proxy-groups'] if g['name'] == chain.FRONT_REGIONS['us'])
            if bad_filter is None:
                group.pop('filter')
            else:
                group['filter'] = bad_filter
            self.assertTrue(chain.validate(lines(bad)))
        bad = document(); bad['proxy-providers']['fixture']['override'] = {'additional-prefix': 'US | '}
        self.assertTrue(chain.validate(lines(bad)))

    def test_timeout_is_not_redirect_and_provider_quarantine_is_exact(self):
        data = document(); evidence = data[chain.QUARANTINE]['nodes'][0]['evidence']
        self.assertTrue(chain.confirmed_redirect(evidence))
        for key, value in [('http_status', 0), ('final_host_role', 'google_com'),
                           ('tls_handshake_completed', False), ('certificate_verify_result', 1)]:
            bad = document(); bad[chain.QUARANTINE]['nodes'][0]['evidence'][key] = value
            self.assertFalse(chain.confirmed_redirect(bad[chain.QUARANTINE]['nodes'][0]['evidence']))
            self.assertTrue(chain.validate(lines(bad)))
        for value in (None, '.*', 'fixture-bad'):
            bad = document(); bad['proxy-providers']['fixture']['exclude-filter'] = value
            self.assertTrue(chain.validate(lines(bad)))
        import re
        pattern = data['proxy-providers']['fixture']['exclude-filter']
        self.assertIsNotNone(re.search(pattern, 'fixture-bad[1]'))
        self.assertIsNone(re.search(pattern, 'fixture-bad1'))
        self.assertIsNone(re.search(pattern, 'prefix-fixture-bad[1]'))

    def test_provider_filter_uses_original_name_before_display_prefix_and_suffix(self):
        data = document(); record = data[chain.QUARANTINE]['nodes'][0]
        original = record['name']; displayed = 'fixture | '+original+' [suffix]'
        provider = data['proxy-providers']['fixture']
        provider['override'] = {'additional-prefix': 'fixture | ', 'additional-suffix': ' [suffix]'}
        record['name'] = displayed
        data['x-rulemesh-android-google-hk-blocked-nodes'] = [displayed]
        from check_android_stability import google_hk_exclusion
        hk_front = next(group for group in data['proxy-groups'] if group['name'] == chain.FRONT_REGIONS['hk'])
        hk_front['exclude-filter'] = '套餐'+google_hk_exclusion([displayed])
        next(group for group in data['proxy-groups'] if group['name'] == chain.HK_REGION)['exclude-filter'] = '套餐'+google_hk_exclusion([displayed])
        self.assertEqual(chain.provider_match_name(provider, displayed), original)
        self.assertFalse(chain.validate(lines(data)))
        provider['exclude-filter'] = chain.quarantine_pattern([displayed])
        self.assertTrue(chain.validate(lines(data)))

    def test_duplicate_yaml_keys_and_forged_marker_do_not_authorize_chain(self):
        text = lines(document()); text += ['proxies: []']
        self.assertTrue(chain.validate(text))
        groups = dns._parse_mihomo_groups(text)
        self.assertFalse(any(g.approved_us_chain_exit for g in groups.values()))
        self.assertTrue(chain.validate([chain.KEY + ': {}']))
        self.assertTrue(chain.validate([s for s in lines(document()) if s != chain.BUSINESS_MARKER]))
