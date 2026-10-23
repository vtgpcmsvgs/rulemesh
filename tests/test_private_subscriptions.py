"""订阅必检使用脱敏夹具；单元测试不访问真实订阅。"""
import json
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import check_private_subscriptions as checker

CONFIG = '''proxy-providers:
  example:
    type: http
    url: https://subscription.example/api?token=private-fixture-token
    proxy: DIRECT
    header:
      User-Agent:
        - clash.meta
    health-check:
      url: https://health.example/generate_204
'''
NODES = '''proxies:
  - name: "节点一"
    type: ss
    server: example.com
    port: 443
    password: fixture
    plugin-opts:
      mode: tls
      host: example.com
  - {name: '节点二', type: vmess, server: example.net, port: 443,
     ws-opts: {headers: {Host: example.net}}}
proxy-groups:
  - name: 不是节点
    type: select
    proxies: [节点一, 节点二]
'''


class PrivateSubscriptionsTests(unittest.TestCase):
    def row(self, **changes):
        result = {'name': 'example', 'status': 200, 'body': NODES, 'userinfo': '', 'error': False}
        result.update(changes)
        return result

    def test_parse_complete_yaml_counts_only_top_proxies(self):
        result = checker.evaluate(self.row(), 100)
        self.assertTrue(result['passed'])
        self.assertEqual(result['nodes'], 2)
        self.assertNotIn('example.com', json.dumps(result))

    def test_json_and_indentless_yaml_are_supported(self):
        for body in ('proxies:\n- {name: a, type: ss}\n', '{"proxies":[{"name":"a","type":"ss"}]}'):
            with self.subTest(format=body[:1]):
                self.assertEqual(checker.evaluate(self.row(body=body), 100)['nodes'], 1)

    def test_html_base64_empty_and_invalid_yaml_cannot_pass_http_200(self):
        for body in ('<html>private-fixture-token</html>', 'dm1lc3M6Ly9maXh0dXJl', 'proxies: []',
                     'proxies: [broken', 'proxies: [{name: a}]',
                     'proxies: []\nproxies: [{name: a, type: ss}]',
                     'proxies: !!python/object/apply:os.system [echo fixture]'):
            result = checker.evaluate(self.row(body=body), 100)
            self.assertFalse(result['passed'])
            self.assertNotIn('private-fixture-token', json.dumps(result))

    def test_expiration_and_exhaustion_block_even_with_nodes(self):
        for metadata in ('expire=100', 'expire=99', 'upload=4;download=6;total=10',
                         'upload=11;download=0;total=10', 'expire=200;expire=300'):
            with self.subTest(metadata=metadata):
                self.assertFalse(checker.evaluate(self.row(userinfo=metadata), 100)['passed'])

    def test_missing_or_zero_metadata_is_unprovided_not_permanent(self):
        for metadata in ('', 'expire=0;total=0', 'total=10;download=3'):
            result = checker.evaluate(self.row(userinfo=metadata), 100)
            self.assertTrue(result['passed'])
            self.assertEqual(result['calendar'], '未提供')
            self.assertEqual(result['quota'], '未提供')

    def test_valid_metadata_and_transport_failures(self):
        result = checker.evaluate(self.row(userinfo='upload=1;download=2;total=10;expire=200'), 100)
        self.assertTrue(result['passed'])
        self.assertEqual(result['remaining_percent'], 70)
        self.assertEqual(result['calendar'], '未过期')
        for changes in ({'status': 403}, {'status': 302}, {'status': None, 'error': True}):
            self.assertFalse(checker.evaluate(self.row(**changes), 100)['passed'])

    def test_manifest_uses_direct_url_and_exact_user_agent(self):
        provider = checker.manifest(CONFIG)['example']
        self.assertIn('subscription.example', provider.url)
        self.assertNotIn('health.example', provider.url)
        self.assertEqual(provider.agent, ('clash.meta',))
        self.assertNotIn('private-fixture-token', repr(provider))
        for config in (CONFIG.replace('proxy: DIRECT', 'proxy: other'),
                       CONFIG.replace('proxy: DIRECT\n', ''),
                       CONFIG.replace('https://subscription.example', 'http://subscription.example'),
                       CONFIG + CONFIG):
            with self.assertRaises(checker.CheckError) as caught:
                checker.manifest(config)
            self.assertNotIn('private-fixture-token', str(caught.exception))

    def test_drift_missing_profiles_and_empty_manifest_send_no_requests(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for content in (CONFIG.replace('clash.meta', 'different'), CONFIG.replace('token=', 'changed='),
                            CONFIG.replace('example:', 'other:')):
                for name, value in zip(checker.PROFILE_NAMES, (CONFIG, content)):
                    (directory / name).write_text(value, encoding='utf-8')
                with patch.object(checker, 'transport') as fetch:
                    with self.assertRaises(checker.CheckError):
                        checker.run(directory, fetch=fetch)
                    fetch.assert_not_called()
            (directory / checker.PROFILE_NAMES[1]).unlink()
            with self.assertRaises(checker.CheckError):
                checker.aligned_manifest(directory)
        with self.assertRaises(checker.CheckError):
            checker.manifest('proxy-providers: {}')

    def test_timeout_and_bad_child_output_never_echo_private_values(self):
        provider = checker.Provider('example', 'https://secret.example/token', ('private-agent',))
        outcomes = (subprocess.TimeoutExpired('fixture', 1),
                    subprocess.CompletedProcess([], 1, 'private-fixture-token', 'private-fixture-token'),
                    subprocess.CompletedProcess([], 0, 'private-fixture-token', ''),
                    subprocess.CompletedProcess([], 0, '[]', ''))
        for outcome in outcomes:
            with patch.object(checker.shutil, 'which', return_value='pwsh'), patch.object(checker.subprocess, 'run') as call:
                if isinstance(outcome, Exception):
                    call.side_effect = outcome
                else:
                    call.return_value = outcome
                with self.assertRaises(checker.CheckError) as caught:
                    checker.transport([provider], checker.time.monotonic() + 1)
                self.assertNotIn('private-fixture-token', str(caught.exception))

    def test_global_deadline_and_unexpected_errors_are_private(self):
        provider = checker.Provider('example', 'https://secret.example/token', ())
        with patch.object(checker, 'aligned_manifest', return_value=[provider]), patch.object(checker, 'transport') as fetch:
            with self.assertRaises(checker.CheckError):
                checker.run(Path('.'), fetch=fetch, clock=iter((0, 61)).__next__)
            fetch.assert_not_called()
        output = io.StringIO()
        with patch.object(checker, 'run', side_effect=ValueError('private-fixture-token')), contextlib.redirect_stdout(output):
            self.assertEqual(checker.worker(Path('.')), 1)
        self.assertNotIn('private-fixture-token', output.getvalue())
        output = io.StringIO()
        with patch.object(sys, 'argv', ['check']), patch.object(checker.subprocess, 'run', side_effect=subprocess.TimeoutExpired('private-fixture-token', 60)), contextlib.redirect_stdout(output):
            self.assertEqual(checker.main(), 1)
        self.assertNotIn('private-fixture-token', output.getvalue())

    def test_check_entrypoint_requires_live_gate_and_transport_is_bounded(self):
        wrapper = (ROOT / 'tools/check.ps1').read_text('utf-8')
        self.assertIn('Invoke-PrivateSubscriptionValidation', wrapper)
        self.assertIn('Private subscription validation failed.', wrapper)
        transport = (ROOT / 'tools/fetch_private_subscriptions.ps1').read_text('utf-8')
        for required in ('UseProxy = $false', 'AllowAutoRedirect = $false', 'CancelAfter(10000)',
                         'Min(60000', 'ResponseContentRead', 'MaxResponseContentBufferSize'):
            self.assertIn(required, transport)


if __name__ == '__main__':
    unittest.main()
