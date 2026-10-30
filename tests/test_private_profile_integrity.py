import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from check_private_profile_integrity import check, check_chain_consistency


class PrivateProfileIntegrityTests(unittest.TestCase):
    def test_client_credentials_cannot_drift_and_absent_clients_fail(self):
        from unittest.mock import patch
        from test_android_us_chain import document, lines
        import check_android_us_chain as chain
        data = document()
        profiles = {chain.PROFILE: lines(data), 'rulemesh-clashmi-ios.yaml': lines(data)}
        self.assertTrue(check_chain_consistency(profiles))  # missing four clients
        with patch.object(chain, 'PROFILES', set(profiles)):
            self.assertEqual(check_chain_consistency(profiles), [])
            data['proxies'][0]['password'] = 'different-fixture-secret'
            profiles['rulemesh-clashmi-ios.yaml'] = lines(data)
            self.assertFalse(chain.validate(lines(data)))  # each file alone is valid
            result = check_chain_consistency(profiles)
            self.assertTrue(result)
            self.assertNotIn('different-fixture-secret', str(result))

    def test_complete_headers_and_existing_line_endings(self):
        for name, text in [('profile.yaml', 'dns:\nproxy-providers:\nproxy-groups:\nrule-providers:\nrules:\n'),
                           ('profile.conf', '[General]\n[Proxy Group]\n[Rule]\n')]:
            for newline in ('\n', '\r\n'):
                self.assertEqual(check(Path(name), text.replace('\n', newline).encode()), [])
                self.assertTrue(check(Path(name), text.splitlines()[0].encode()))
                self.assertTrue(check(Path(name), (text + text).encode()))

    def test_upload_literal_encoded_payload_and_bom_are_rejected(self):
        for raw in (b'([Convert]::ToBase64String([IO.File]::ReadAllBytes($profile)))',
                    b'ZG5zOgo=', b'\xef\xbb\xbfdns:\n', b'\xff', b''):
            for suffix in ('.yaml', '.conf'):
                findings = check(Path('profile' + suffix), raw)
                self.assertTrue(findings)
                if raw:
                    self.assertNotIn(raw.decode('utf-8', 'replace'), '\n'.join(findings))
