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
    nodes = [{'name': name, 'type': 'socks5', 'server': 'fixture.invalid',
              'port': chain.EXIT_PORTS[name], 'username': 'fixture-user', 'password': 'fixture-secret',
              'udp': False, 'dialer-proxy': chain.FRONT} for i, name in enumerate(chain.EXITS)]
    health = {'type': 'url-test', 'url': 'https://www.google.com/generate_204', 'interval': 600, 'lazy': False}
    blocked = ['fixture-bad[1]']
    front_groups = [{'name': name, **health, 'hidden': False, 'lazy': True,
                     'tolerance': 100 if code == 'us' else 50,
                     'filter': chain.front_region_filter(code), 'use': ['fixture'],
                     'exclude-filter': '套餐'}
                    for code, name in zip(chain.FRONT_REGIONS, chain.FRONT_GROUPS)]
    from check_android_stability import google_hk_exclusion
    front_groups[0]['exclude-filter'] = '套餐' + google_hk_exclusion(blocked)
    return {'proxies': nodes, 'proxy-providers': {'fixture': {'exclude-filter': chain.quarantine_pattern(blocked)}},
            'x-rulemesh-android-google-hk-blocked-nodes': blocked,
            chain.QUARANTINE: {'version': 1, 'nodes': [{'provider': 'fixture', 'name': blocked[0],
                'reason': 'google_cn_redirect', 'evidence': {'http_status': 302, 'final_host_role': 'google_cn',
                    'tls_handshake_completed': True, 'certificate_verify_result': 0}}]},
            chain.KEY: {'version': 3, 'front': chain.FRONT, 'front-regions': list(chain.FRONT_GROUPS),
                        'regions': {'us': chain.REGION, 'hk': chain.HK_REGION},
                        'us-exits': list(chain.US_EXITS), 'hk-exits': list(chain.HK_EXITS),
                        'exits': list(chain.EXITS), 'exit-identities': [
                            {'name': '美国-Comcast-01', 'region': 'US', 'city': 'Boston', 'asn': 7015, 'ip': '8.8.8.8', 'port': 10002},
                            {'name': '美国-Comcast-02', 'region': 'US', 'city': 'Boston', 'asn': 7015, 'ip': '1.1.1.1', 'port': 10003},
                            {'name': '香港-Lumen-01', 'region': 'HK', 'city': 'Hong Kong', 'asn': 10753, 'ip': '9.9.9.9', 'port': 10001},
                        ]},
            'proxy-groups': [
                {'name': chain.FRONT, 'type': 'select', 'hidden': False, 'proxies': list(chain.FRONT_GROUPS)},
                {'name': chain.REGION, 'type': 'load-balance', 'strategy': 'consistent-hashing', **{k: v for k, v in health.items() if k != 'type'}, 'hidden': False, 'proxies': list(chain.US_EXITS)},
                {'name': chain.HK_REGION, **health, 'type': 'load-balance', 'strategy': 'consistent-hashing', 'hidden': False, 'proxies': list(chain.HK_EXITS)},
                {'name': 'AI', 'type': 'select', 'proxies': [chain.REGION]},
                {'name': 'Microsoft', 'type': 'select', 'proxies': [chain.REGION, 'DIRECT']},
                {'name': '香港券商', 'type': 'select', 'proxies': [chain.HK_REGION]},
                {'name': 'Google', 'type': 'select', 'proxies': [chain.HK_REGION, chain.REGION]}, *front_groups]}


def lines(data):
    # 保持生产解析器所支持的两空格列表格式，避免夹具用不同 YAML 布局假通过。
    class Indented(yaml.SafeDumper):
        def increase_indent(self, flow=False, indentless=False):
            return super().increase_indent(flow, False)
    return [chain.BUSINESS_MARKER, *yaml.dump(data, Dumper=Indented, allow_unicode=True, sort_keys=False).splitlines()]


class AndroidUsChainTests(unittest.TestCase):
    def test_hk_brokers_and_all_final_groups_cannot_bypass_registered_exits(self):
        for name, key, value in ((chain.HK_REGION, 'include-all', True),
                                 (chain.HK_REGION, 'type', 'select'),
                                 (chain.HK_REGION, 'filter', 'missing'),
                                 (chain.REGION, 'exclude-filter', '.*'),
                                 ('香港券商', 'proxies', ['airport-hk'])):
            data = document()
            next(g for g in data['proxy-groups'] if g['name'] == name)[key] = value
            self.assertTrue(chain.validate(lines(data)))
        data = document(); data[chain.KEY]['exit-identities'][1]['ip'] = data[chain.KEY]['exit-identities'][0]['ip']
        self.assertTrue(chain.validate(lines(data)))
        data = document(); data['rules'] = ['DOMAIN,fixture.invalid,' + chain.US_EXITS[0]]
        self.assertTrue(chain.validate(lines(data)))

    def test_authorized_two_us_and_one_hk_structure_and_only_us_semantics(self):
        data = document(); text = lines(data)
        self.assertEqual(chain.check(Path(chain.PROFILE), text), [])
        groups = dns._parse_mihomo_groups(text)
        self.assertTrue(dns._group_has_us_semantics('AI', groups, dns.APPROVED_MIHOMO_US_FILTERS))
        self.assertFalse(dns._group_has_us_semantics('AI', groups, baseline.region_filters('hk', False)))
        self.assertTrue(chain.check(Path('desktop.yaml'), text))

    def test_final_exit_group_must_be_explicitly_visible(self):
        for index in (1, 2):
            for hidden in (True, None, 'false'):
                data = document()
                region = data['proxy-groups'][index]
                if hidden is None:
                    region.pop('hidden')
                else:
                    region['hidden'] = hidden
                with self.subTest(index=index, hidden=hidden):
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
        for index, key, value in [(0, 'proxies', [chain.REGION]), (0, 'use', ['fixture']),
                                  (1, 'use', ['fixture']), (1, 'proxies', list(chain.EXITS) + ['DIRECT']),
                                  (2, 'proxies', ['airport-hk']), (4, 'proxies', [chain.REGION])]:
            data = document(); data['proxy-groups'][index][key] = value
            self.assertTrue(chain.validate(lines(data)))
        data = document(); data['proxy-groups'][0]['dialer-proxy'] = chain.REGION
        self.assertTrue(chain.validate(lines(data)))

    def test_all_front_regions_are_independent_airport_only_auto_groups(self):
        self.assertFalse(chain.validate(lines(document())))
        for name in chain.FRONT_GROUPS:
            for key, value in [('proxies', [chain.REGION]), ('proxies', [chain.FRONT]),
                               ('proxies', list(chain.EXITS)), ('use', []), ('filter', '.*'),
                               ('lazy', False), ('type', 'select'), ('include-all', True),
                               ('interval', 300), ('hidden', True), ('tolerance', 999)]:
                data = document(); next(g for g in data['proxy-groups'] if g['name'] == name)[key] = value
                with self.subTest(region=name, field=key, value=value):
                    self.assertTrue(chain.validate(lines(data)))
        data = document(); data['proxy-groups'][0]['proxies'][-1] = chain.REGION
        self.assertTrue(chain.validate(lines(data)))
        data = document(); data['proxy-groups'].pop()
        self.assertTrue(chain.validate(lines(data)))

    def test_front_region_regex_matches_bare_country_codes_after_yaml_round_trip(self):
        import re
        parsed = yaml.safe_load('\n'.join(lines(document())))
        groups = {g['name']: g for g in parsed['proxy-groups']}
        for code, name in zip(chain.FRONT_REGIONS, chain.FRONT_GROUPS):
            pattern = groups[name]['filter']
            self.assertIsNotNone(re.search(pattern, 'Airport '+code.upper()+' 01'))
            self.assertIsNone(re.search(pattern, 'prefix'+code+'suffix'))

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
        hk_front = next(group for group in data['proxy-groups'] if group['name'] == chain.FRONT_GROUPS[0])
        hk_front['exclude-filter'] = '套餐'+google_hk_exclusion([displayed])
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
