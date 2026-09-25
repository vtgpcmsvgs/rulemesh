"""参考配置只允许输出已审核统计，连 DNS 节和异常也不能原样回显。"""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_reference_profile import summarize


class ReferencePrivacyTests(unittest.TestCase):
    def test_credentials_and_unknown_fields_never_reach_summary(self):
        secret = "private-canary-value"
        data = {
            "dns": {"nameserver": ["https://example.test/" + secret], "fake-ip-filter": [secret]},
            "proxies": [{"type": "anytls", "name": secret, "server": secret, "password": secret,
                         "idle-session-timeout": secret, "skip-cert-verify": True}, {"type": secret}],
            "proxy-groups": [{"name": "AI", "type": "select", "proxies": [secret]}, {"name": secret, "type": secret}],
            "hosts": {secret: secret}, "rules": [secret],
        }
        result = summarize(data)
        self.assertNotIn(secret, json.dumps(result))
        self.assertEqual(result["protocol_counts"], {"anytls": 1, "other": 1})
        self.assertEqual(result["services"]["AI"], 1)
        self.assertFalse(result["dns"]["fake_ip_explicit"])
