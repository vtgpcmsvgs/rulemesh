from datetime import datetime, timedelta, timezone
from pathlib import Path
import copy
import json
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import check_task_acceptance as acceptance
from collect_android_acceptance import dns_evidence, provider_health, shell_result, public_address, front_runtime, quarantine_runtime, trace_evidence, exit_evidence, regional_probes, selection_snapshot
from check_android_us_chain import FRONT, FRONT_GROUPS, REGION, HK_REGION, US_EXITS, HK_EXITS, EXITS
from android_usb_transport import UsbAdb
from android_chrome_probe import audit_page


class TaskAcceptanceTests(unittest.TestCase):
    def test_hk_identity_requires_observed_public_ip_region_and_chain(self):
        expected = {'exit_identities': dict(zip(EXITS, ('8.8.8.8', '1.1.1.1', '9.9.9.9')))}
        raw = 'ip=9.9.9.9\nloc=HK\n'
        self.assertTrue(exit_evidence(raw, 0, True, HK_EXITS[0], expected)['passed'])
        for content, code, chain_seen in (('', 0, True), (raw, 200, True), (raw, 0, False),
                                          ('ip=9.9.9.9\nloc=US\n', 0, True),
                                          ('ip=8.8.8.8\nloc=HK\n', 0, True)):
            self.assertFalse(exit_evidence(content, code, chain_seen, HK_EXITS[0], expected)['passed'])

    def test_natural_hash_observation_never_switches_load_balance(self):
        import base64
        from unittest.mock import patch
        from urllib.parse import urlsplit
        expected = {'exit_identities': dict(zip(EXITS, ('8.8.8.8', '1.1.1.1', '9.9.9.9')))}
        seen = []
        def probe(device, controller, previous, name, url, required):
            leaf = EXITS[min(len(seen), 2)]; seen.append(leaf)
            connection = {'id': str(len(seen)), 'metadata': {'host': urlsplit(url).hostname},
                          'chains': [*required, leaf], 'download': 10}
            encoded = base64.b64encode(json.dumps({'connections': [connection]}).encode()).decode()
            raw = 'RM_CONN ' + encoded + '\nRM_TRACE_CODE=0\nip=' + expected['exit_identities'][leaf] + '\nloc=' + ('US' if leaf in US_EXITS else 'HK') + '\n'
            return raw, 0, False
        with patch('collect_android_acceptance.trace_probe', probe), patch('collect_android_acceptance.change', side_effect=AssertionError('No writes')):
            rows = regional_probes(None, {}, lambda path: {'connections': []}, expected)
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row['passed'] for row in rows))
        self.assertEqual(len({r['_ip'] for r in rows}), 3)
        self.assertEqual(selection_snapshot({REGION: {'type': 'LoadBalance', 'all': list(US_EXITS)}})[REGION]['now'], None)

    def test_short_lived_connection_is_proved_during_transfer_without_accepting_old_bytes(self):
        import base64
        def sample(connections):
            return 'RM_CONN '+base64.b64encode(json.dumps({'connections':connections}).encode()).decode()+'\n'
        connection={'id':'fixture','metadata':{'host':'chatgpt.com'},'chains':['AI',EXITS[0]],'download':100}
        raw=sample([])+sample([connection])+sample([])+'RM_TRACE_CODE=0\nloc=US\n'
        self.assertEqual(trace_evidence(raw,{},EXITS[0]),(0,True))
        self.assertEqual(trace_evidence(raw,{'fixture':100},EXITS[0]),(0,False))
        self.assertEqual(trace_evidence(raw,{},EXITS[1]),(0,False))
        connection['chains']=['DIRECT']
        self.assertEqual(trace_evidence(sample([connection])+'RM_TRACE_CODE=0\n',{},EXITS[0]),(0,False))
        with self.assertRaises(RuntimeError):trace_evidence(sample([]),{},EXITS[0])

    def test_provider_exclusion_must_be_observed_and_cannot_pass_empty_data(self):
        expected = {'fixture': ['bad-node']}
        good = {'fixture': {'proxies': [{'name': 'good-node'}]}}
        self.assertTrue(quarantine_runtime(good, expected))
        for providers in ({}, {'fixture': {'proxies': []}},
                          {'fixture': {'proxies': [{'name': 'good-node'}, {'name': 'bad-node'}]}}):
            self.assertFalse(quarantine_runtime(providers, expected))
        self.assertFalse(quarantine_runtime(good, {}))

    def test_runtime_requires_six_airport_fronts_and_rejects_final_exit_cycles(self):
        proxies = {FRONT: {'type': 'Selector', 'all': list(FRONT_GROUPS), 'now': FRONT_GROUPS[0]},
                   **{name: {'type': 'URLTest', 'all': ['fixture-airport']} for name in FRONT_GROUPS}}
        self.assertTrue(all(front_runtime(proxies).values()))
        for target in (REGION, FRONT, EXITS[0], 'DIRECT'):
            bad = copy.deepcopy(proxies); bad[FRONT_GROUPS[-1]]['all'] = [target]
            self.assertFalse(all(front_runtime(bad).values()))
        bad = copy.deepcopy(proxies); bad.pop(FRONT_GROUPS[0])
        self.assertFalse(all(front_runtime(bad).values()))
        bad = copy.deepcopy(proxies); bad[FRONT]['now'] = REGION
        self.assertFalse(all(front_runtime(bad).values()))

    def test_exit_requires_a_real_public_address(self):
        for value in (None,'invalid','127.0.0.1','10.0.0.1','::1','192.0.2.1'):
            self.assertIsNone(public_address(value))
        self.assertEqual(public_address('8.8.8.8'),'8.8.8.8')
    def report(self):
        return {'baseline': {'passed': True}, 'source_unchanged': True, 'exit_identity_policy': 'user-provided-trusted',
                'android': {'passed': True, 'selection_restored': True,
                            'distinct_us_exit_count': len(US_EXITS), 'distinct_hk_exit_count': len(HK_EXITS),
                            'regional_exits': [{'exit': i, 'region': 'US' if i <= len(US_EXITS) else 'HK', 'passed': True}
                                               for i in range(1, len(EXITS) + 1)]}}

    def test_every_required_gate_and_all_regional_exits_must_pass(self):
        good = self.report()
        self.assertTrue(acceptance.overall(good))
        for key in ('baseline', 'android', 'source_unchanged'):
            bad = copy.deepcopy(good); bad.pop(key)
            self.assertFalse(acceptance.overall(bad))
        for index in range(len(EXITS)):
            bad = copy.deepcopy(good); bad['android']['regional_exits'][index]['passed'] = False
            self.assertFalse(acceptance.overall(bad))
        bad = copy.deepcopy(good); bad['android']['regional_exits'][-1]['exit'] = 1
        self.assertFalse(acceptance.overall(bad))
        good['android']['selection_restored'] = False
        self.assertFalse(acceptance.overall(good))
        bad = self.report(); bad['android']['distinct_us_exit_count'] = 1
        self.assertFalse(acceptance.overall(bad))

    def test_stale_empty_or_future_provider_health_cannot_pass(self):
        now = datetime.now(timezone.utc)
        def body(age, delay=12, alive=True):
            return {'fixture': {'proxies': [{'alive': alive, 'history': [{'time': (now - timedelta(seconds=age)).isoformat(), 'delay': delay}]}]}}
        self.assertEqual(provider_health(body(10), {'fixture': 600}, now)[0]['state'], 'passed')
        for age, delay, alive in [(601, 12, True), (-1, 12, True), (10, 0, True), (10, 12, False)]:
            self.assertEqual(provider_health(body(age, delay, alive), {'fixture': 600}, now)[0]['state'], 'unknown')
        self.assertEqual(provider_health({}, {'fixture': 600}, now)[0]['state'], 'unknown')

    def test_dns_requires_new_bytes_and_actual_business_chain(self):
        row = {'id': 'fixture', 'download': 100, 'chains': ['HK', 'Google'], 'metadata': {'host': 'dns.google'}}
        self.assertTrue(dns_evidence([], [row], 'Google', 'HK'))
        self.assertFalse(dns_evidence([row], [row], 'Google', 'HK'))
        self.assertFalse(dns_evidence([], [row], 'AI', 'US'))
        row['chains'].append('DIRECT')
        self.assertFalse(dns_evidence([], [row], 'Google', 'HK'))

    def test_device_command_requires_unique_exit_marker(self):
        class Device:
            def shell(self, command, deadline_seconds):
                return self.raw
        device = Device(); device.raw = 'body\nRM_ACCEPT_EXIT=28\n'
        self.assertEqual(shell_result(device, 'curl')[1], 28)
        for raw in ('body', 'RM_ACCEPT_EXIT=0\nRM_ACCEPT_EXIT=0\n'):
            device.raw = raw
            with self.assertRaises(RuntimeError):
                shell_result(device, 'curl')

    def test_missing_device_configuration_and_unregistered_policy_are_not_skipped(self):
        for settings in ({}, {'exit_identity_policy': 'trust-node-label'}, {'exit_identity_policy': 'user-provided-trusted'}):
            with self.assertRaises(ValueError):
                acceptance.validate_settings(settings)

    def test_closing_entrypoint_and_no_cached_evidence_bypass_are_documented(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / 'tools/check_task_acceptance.py').read_text('utf-8')
        self.assertIn('tools/check.ps1', source)
        self.assertNotIn("add_argument('--skip", source)
        self.assertNotIn("add_argument('--evidence", source)
        self.assertIn('check_task_acceptance.py', (root / 'AGENTS.md').read_text('utf-8'))

    def test_usb_wait_respects_command_deadline_beyond_ten_seconds(self):
        class Transport:
            local = 0
            maximum = 4096
            def send(self, *args):
                pass
            def receive(self, timeout):
                self.timeout = timeout
                return b'CLSE', 1, self.local, b''
        for method, args in ((UsbAdb.service, ('shell:true',)), (UsbAdb.exchange, ('tcp:9090', b''))):
            device = Transport()
            self.assertEqual(method(device, *args, deadline_seconds=20), b'')
            self.assertGreater(device.timeout, 19000)

    def test_chrome_requires_current_search_path_trusted_response_and_dom(self):
        page={'host':'www.google.com','path':'/search','ready':'complete','search':True,'error':False}
        doc={'host':'www.google.com','path':'/search','status':200,'https':True,'tls':True,'cached':False}
        self.assertTrue(audit_page(page,[doc],'/search'))
        for key,value in [('host','google.cn'),('path','/'),('search',False),('error',True)]:
            self.assertFalse(audit_page({**page,key:value},[doc],'/search'))
        for key,value in [('status',403),('tls',False),('cached',True)]:
            self.assertFalse(audit_page(page,[{**doc,key:value}],'/search'))
