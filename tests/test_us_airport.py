"""美国机场出口回归：按来源分组，禁止链式资产复活。"""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import check_us_airport as airport
from check_private_subscriptions import yaml
from check_performance_baseline import region_filters


def document():
    providers = {'724': {}, 'diidao': {}}
    pattern = next(iter(region_filters('us', False))).replace('\\\\', '\\')
    children = [airport.child_name(n) for n in providers]
    return {'proxy-providers': providers, 'proxy-groups': [
        {'name': 'AI', 'type': 'select', 'proxies': children},
        {'name': 'Microsoft', 'type': 'select', 'proxies': [*children, 'DIRECT']},
        {'name': airport.US_GROUP, 'type': 'url-test', 'use': list(providers), 'filter': pattern, 'lazy': False},
        *[{'name': airport.child_name(n), 'type': 'url-test', 'use': [n], 'filter': pattern,
           'interval': 300, 'tolerance': 100, 'lazy': False, 'exclude-filter': '套餐'} for n in providers]]}


def lines(data):
    return (airport.MARKER + '\n' + yaml.safe_dump(data, allow_unicode=True, sort_keys=False)).splitlines()


class UsAirportTests(unittest.TestCase):
    path = Path('rulemesh-flclash-desktop.yaml')

    def test_airport_children_and_human_alias(self):
        self.assertEqual(airport.validate(self.path, lines(document())), [])
        self.assertEqual(airport.child_name('diidao'), '美国-didiao')

    def test_chain_restoration_and_parent_bypasses_are_rejected(self):
        cases = []
        for key, value in [('proxies', [{'name': 'RM-US-Exit', 'type': 'socks5', 'password': 'fixture-secret'}]),
                           ('x-rulemesh-us-chain', {'version': 6})]:
            bad = document(); bad[key] = value; cases.append(bad)
        for name in ('RM-US-Exit', '美国线路入口', '经香港接入'):
            bad = document(); bad['proxy-groups'].append({'name': name, 'type': 'select'}); cases.append(bad)
        for members in (['DIRECT'], ['美国-724'], ['美国-724', '美国-724']):
            bad = document(); bad['proxy-groups'][0]['proxies'] = members; cases.append(bad)
        for bad in cases:
            errors = airport.validate(self.path, lines(bad))
            self.assertTrue(errors)
            self.assertNotIn('fixture-secret', str(errors))

    def test_wrong_source_region_and_cycle_are_rejected(self):
        for field, value in [('use', ['724', 'diidao']), ('filter', '.*'), ('proxies', ['AI']),
                             ('interval', 600), ('tolerance', 50), ('lazy', True),
                             ('dialer-proxy', 'fixture')]:
            bad = copy.deepcopy(document()); bad['proxy-groups'][-1][field] = value
            self.assertTrue(airport.validate(self.path, lines(bad)))
        bad = document(); bad['proxy-groups'][2]['lazy'] = True
        self.assertTrue(airport.validate(self.path, lines(bad)))
        self.assertTrue(airport.validate(self.path, lines(document())[1:]))

    def test_device_uses_real_provider_nodes_and_wifi(self):
        from collect_android_acceptance import airport_runtime, wifi_vpn_observed
        expected = {'us_children': {'美国-724': '724'}, 'us_filter': r'(?i)美国|US'}
        proxies = {'AI': {'type': 'Selector', 'all': ['美国-724'], 'now': '美国-724'},
                   '美国-724': {'type': 'URLTest', 'all': ['fixture US'], 'now': 'fixture US'}}
        providers = {'724': {'proxies': [{'name': 'fixture US'}]}}
        self.assertTrue(all(airport_runtime(proxies, providers, expected).values()))
        for leaf in ('unregistered US', '美国-724', 'DIRECT', 'fixture HK'):
            bad = copy.deepcopy(proxies); bad['美国-724']['all'] = [leaf]; bad['美国-724']['now'] = leaf
            self.assertFalse(all(airport_runtime(bad, providers, expected).values()))
        line = 'NetworkAgentInfo{ ni{CONNECTED} Transports: WIFI|VPN OwnerUid: 123 }'
        self.assertTrue(wifi_vpn_observed(line, 123))
        self.assertFalse(wifi_vpn_observed(line.replace('WIFI', 'CELLULAR'), 123))
        self.assertFalse(wifi_vpn_observed(line, 456))

    def test_latest_timestamp_not_array_order_decides_provider_health(self):
        from collect_android_acceptance import provider_health
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        latest = {'time': (now - timedelta(seconds=20)).isoformat(), 'delay': 0}
        older = {'time': (now - timedelta(seconds=30)).isoformat(), 'delay': 10}
        provider = {'724': {'proxies': [{'alive': True, 'history': [latest, older]}]}}
        self.assertEqual(provider_health(provider, {'724': 600}, now)[0]['recent_alive'], 0)
        latest['delay'] = 10
        self.assertEqual(provider_health(provider, {'724': 600}, now)[0]['recent_alive'], 1)
