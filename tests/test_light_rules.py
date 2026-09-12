from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_rules
from sync_performance_rules import protective_rules


def matcher(rules):
    exact = {r.split(',')[1] for r in rules if r.startswith('DOMAIN,')}
    suffix = {r.split(',')[1] for r in rules if r.startswith('DOMAIN-SUFFIX,')}
    return lambda d: d in exact or any('.'.join(d.split('.')[i:]) in suffix for i in range(len(d.split('.'))))


class LightRulesTests(unittest.TestCase):
    def test_overlap_in_both_directions_and_boundary(self):
        direct = ['DOMAIN-SUFFIX,cn', 'DOMAIN-SUFFIX,cdn.example.org', 'DOMAIN,exact.example.net', 'DOMAIN-SUFFIX,notexample.org', 'GEOIP,CN,no-resolve']
        proxy = ['DOMAIN-SUFFIX,example.cn', 'DOMAIN-SUFFIX,example.org', 'DOMAIN,exact.example.net']
        self.assertEqual(protective_rules(direct, proxy), [direct[i] for i in (0, 1, 2, 4)])

    def test_unknown_proxy_semantics_fail_closed(self):
        for rule in ['DOMAIN-KEYWORD,example', 'IP-CIDR,1.1.1.1/32', 'DOMAIN-WILDCARD,*.example.com']:
            with self.assertRaises(ValueError):
                protective_rules(['DOMAIN-SUFFIX,cn'], [rule])

    def test_real_domain_tail_equivalence_and_ip_preservation(self):
        direct = build_rules.build_source(ROOT / 'rules/direct/cn_direct.list').outputs['surge_rules']
        proxy = build_rules.build_source(ROOT / 'rules/proxy/gfw_precise.list').outputs['surge_rules']
        light = protective_rules(direct, proxy)
        self.assertEqual([r for r in direct if not r.startswith('DOMAIN')], [r for r in light if not r.startswith('DOMAIN')])
        self.assertLess(len(light), len(direct) / 5)
        full_match, light_match, proxy_match = matcher(direct), matcher(light), matcher(proxy)
        for row in direct + proxy:
            if not row.startswith(('DOMAIN,', 'DOMAIN-SUFFIX,')):
                continue
            domain = row.split(',')[1]
            for sample in (domain, 'test.' + domain):
                old = 'DIRECT' if full_match(sample) or not proxy_match(sample) else 'PROXY'
                new = 'DIRECT' if light_match(sample) or not proxy_match(sample) else 'PROXY'
                self.assertEqual(old, new)

    def test_precise_proxy_does_not_restore_tld_catchalls(self):
        proxy = build_rules.build_source(ROOT / 'rules/proxy/gfw_precise.list').outputs['surge_rules']
        self.assertTrue(all('.' in r.split(',')[1] for r in proxy))
        self.assertIn('DOMAIN-SUFFIX,decodo.com', proxy)
