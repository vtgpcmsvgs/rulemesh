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
              'port': 10001 + i, 'username': 'fixture-user', 'password': 'fixture-secret',
              'udp': False, 'dialer-proxy': chain.FRONT} for i, name in enumerate(chain.EXITS)]
    health = {'type': 'url-test', 'url': 'https://www.google.com/generate_204', 'interval': 600, 'lazy': False}
    return {'proxies': nodes, 'proxy-providers': {'fixture': {}},
            chain.KEY: {'version': 1, 'front': chain.FRONT, 'region': chain.REGION, 'exits': list(chain.EXITS)},
            'proxy-groups': [
                {'name': chain.FRONT, 'type': 'select', 'hidden': False, 'use': ['fixture'], 'exclude-filter': '套餐'},
                {'name': chain.REGION, **health, 'hidden': False, 'tolerance': 100, 'proxies': list(chain.EXITS)},
                {'name': 'AI', 'type': 'select', 'proxies': [chain.REGION]},
                {'name': 'Microsoft', 'type': 'select', 'proxies': [chain.REGION, 'DIRECT']},
                {'name': 'Google', 'type': 'select', 'proxies': ['🇭🇰 香港-自动选择', chain.REGION]}]}


def lines(data):
    # 保持生产解析器所支持的两空格列表格式，避免夹具用不同 YAML 布局假通过。
    class Indented(yaml.SafeDumper):
        def increase_indent(self, flow=False, indentless=False):
            return super().increase_indent(flow, False)
    return [chain.BUSINESS_MARKER, *yaml.dump(data, Dumper=Indented, allow_unicode=True, sort_keys=False).splitlines()]


class AndroidUsChainTests(unittest.TestCase):
    def test_authorized_five_exit_structure_and_only_us_semantics(self):
        data = document(); text = lines(data)
        self.assertEqual(chain.check(Path(chain.PROFILE), text), [])
        groups = dns._parse_mihomo_groups(text)
        self.assertTrue(dns._group_has_us_semantics('AI', groups, dns.APPROVED_MIHOMO_US_FILTERS))
        self.assertFalse(dns._group_has_us_semantics('AI', groups, baseline.region_filters('hk', False)))
        self.assertTrue(chain.check(Path('desktop.yaml'), text))

    def test_final_exit_group_must_be_explicitly_visible(self):
        for hidden in (True, None, 'false'):
            data = document()
            region = data['proxy-groups'][1]
            if hidden is None:
                region.pop('hidden')
            else:
                region['hidden'] = hidden
            with self.subTest(hidden=hidden):
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
        for index, key, value in [(0, 'proxies', [chain.REGION]), (0, 'use', []),
                                  (1, 'use', ['fixture']), (1, 'proxies', list(chain.EXITS) + ['DIRECT']),
                                  (2, 'proxies', ['airport-us']), (4, 'proxies', [chain.REGION])]:
            data = document(); data['proxy-groups'][index][key] = value
            self.assertTrue(chain.validate(lines(data)))
        data = document(); data['proxy-groups'][0]['dialer-proxy'] = chain.REGION
        self.assertTrue(chain.validate(lines(data)))

    def test_duplicate_yaml_keys_and_forged_marker_do_not_authorize_chain(self):
        text = lines(document()); text += ['proxies: []']
        self.assertTrue(chain.validate(text))
        groups = dns._parse_mihomo_groups(text)
        self.assertFalse(any(g.approved_us_chain_exit for g in groups.values()))
        self.assertTrue(chain.validate([chain.KEY + ': {}']))
        self.assertTrue(chain.validate([s for s in lines(document()) if s != chain.BUSINESS_MARKER]))
