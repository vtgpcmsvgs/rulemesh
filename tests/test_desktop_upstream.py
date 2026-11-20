from copy import deepcopy
from pathlib import Path
import sys
import unittest

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import check_desktop_upstream as upstream


def fixture():
    return {"listeners": [{"name": upstream.NAME, "type": "socks", "listen": "127.0.0.1",
                           "port": 7898, "proxy": "Automatic"}],
            "proxy-groups": [{"name": "Automatic", "type": "url-test", "use": ["airport"]}],
            "rules": ["RULE-SET,proxy_gfw,Automatic", "MATCH,DIRECT"]}


class DesktopUpstreamTests(unittest.TestCase):
    def errors(self, document, name=upstream.DESKTOP):
        return upstream.check(Path(name), yaml.safe_dump(document, allow_unicode=True).splitlines())

    def test_only_desktop_can_use_the_loopback_upstream(self):
        self.assertEqual(self.errors(fixture()), [])
        for name in ("rulemesh-flclash-android.yaml", "rulemesh-clashmi-ios.yaml", "mihomo-public.yaml"):
            self.assertTrue(self.errors(fixture(), name))

    def test_does_not_restore_retired_domain_process_or_provider_assets(self):
        for rule in ("DOMAIN-KEYWORD,adspower,DIRECT", "PROCESS-NAME,AdsPower.exe,Automatic",
                     "RULE-SET,reject_adspower,REJECT"):
            document = fixture()
            document["rules"].insert(0, rule)
            self.assertTrue(self.errors(document))
        document = fixture()
        document["rule-providers"] = {"direct_adspower": {"type": "inline"}}
        self.assertTrue(self.errors(document))

    def test_rejects_exposure_direct_routing_and_unreviewed_fields(self):
        for key, value in (("listen", "0.0.0.0"), ("listen", "::"), ("type", "mixed"), ("type", "http"),
                           ("port", 7890), ("port", "7898"), ("proxy", "DIRECT"),
                           ("proxy", "Other"), ("rule", "unreviewed")):
            document = fixture()
            document["listeners"][0][key] = value
            self.assertTrue(self.errors(document))
        for change in ({"type": "select"}, {"proxies": ["DIRECT"]}, {"include-all": True},
                       {"include-all-proxies": True}, {"include-all-providers": True}, {"use": []}, {"use": "airport"}):
            document = fixture()
            document["proxy-groups"][0].update(change)
            self.assertTrue(self.errors(document))
        document = fixture()
        document["listeners"].append(deepcopy(document["listeners"][0]))
        self.assertTrue(self.errors(document))

    def test_missing_or_malformed_listener_fails_without_echoing_private_text(self):
        lines = ["listeners: [", "secret: DO_NOT_PRINT_adspower"]
        errors = upstream.check(Path(upstream.DESKTOP), lines)
        self.assertTrue(errors)
        self.assertNotIn("DO_NOT_PRINT", str(errors))


if __name__ == "__main__":
    unittest.main()
