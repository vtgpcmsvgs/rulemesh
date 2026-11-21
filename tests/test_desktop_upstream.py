from pathlib import Path
import sys
import unittest

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import check_desktop_upstream as upstream


def install(document):
    document.update({"socks-port": 7898, "allow-lan": False})
    document.setdefault("proxy-providers", {})[upstream.PROVIDER] = {"type": "inline", "payload": [{
        "name": upstream.NODE, "type": "vless", "server": "192.0.2.10", "port": 443,
        "uuid": "00000000-0000-4000-8000-000000000001", "network": "tcp", "tls": True,
        "servername": "example.com", "client-fingerprint": "chrome", "udp": True,
        "reality-opts": {"public-key": "A" * 43, "short-id": "01234567"}}]}
    document.setdefault("proxy-groups", []).append({"name": upstream.PROVIDER, "type": "select", "hidden": True, "use": [upstream.PROVIDER]})
    document.setdefault("rules", []).insert(0, "IN-PORT,7898," + upstream.PROVIDER)
    return document


def relay_blocks():
    class IndentedDumper(yaml.SafeDumper):
        def increase_indent(self, flow=False, indentless=False):
            return super().increase_indent(flow, False)
    document = install({})
    result = {}
    for section, kind in (("proxy-providers", "PROVIDER"), ("proxy-groups", "GROUP")):
        text = yaml.dump({section: document[section]}, Dumper=IndentedDumper, sort_keys=False)
        result[section] = ("  # >>> RULEMESH_DESKTOP_666CLOUDS_" + kind + "\n" + text.split('\n', 1)[1]
                           + "  # <<< RULEMESH_DESKTOP_666CLOUDS_" + kind + "\n")
    return result


def fixture():
    return install({"socks-port": 7898, "allow-lan": False,
            "proxy-groups": [{"name": "Automatic", "type": "url-test", "use": ["airport"]}],
            "rules": ["RULE-SET,proxy_gfw,Automatic", "MATCH,DIRECT"]})


class DesktopUpstreamTests(unittest.TestCase):
    def errors(self, document, name=upstream.DESKTOP):
        return upstream.check(Path(name), [upstream.MARKER, *yaml.safe_dump(document, allow_unicode=True).splitlines()])

    def test_only_desktop_can_use_the_loopback_upstream(self):
        self.assertEqual(self.errors(fixture()), [])
        for name in ("rulemesh-flclash-android.yaml", "rulemesh-clashmi-ios.yaml", "mihomo-public.yaml"):
            self.assertTrue(self.errors(fixture(), name))

    def test_does_not_restore_retired_domain_process_or_provider_assets(self):
        for rule in ("DOMAIN-KEYWORD,adspower,DIRECT", "PROCESS-NAME,AdsPower.exe,Automatic",
                     "RULE-SET,reject_adspower,REJECT"):
            document = fixture()
            document["rules"].insert(1, rule)
            self.assertTrue(self.errors(document))
        document = fixture()
        document["rule-providers"] = {"direct_adspower": {"type": "inline"}}
        self.assertTrue(self.errors(document))

    def test_rejects_port_collision_exposure_and_direct_fallback(self):
        for key, value in (("allow-lan", True), ("bind-address", "0.0.0.0"),
                           ("mixed-port", 7898), ("port", 7898), ("socks-port", "7898"),
                           ("listeners", [{"name": "duplicate", "type": "socks", "port": 7898}])):
            document = fixture()
            document[key] = value
            self.assertTrue(self.errors(document))
        for change in ({"type": "url-test"}, {"hidden": False}, {"proxies": ["DIRECT"]}, {"include-all": True},
                       {"include-all-proxies": True}, {"include-all-providers": True}, {"use": []}, {"use": "airport"}):
            document = fixture()
            document["proxy-groups"][-1].update(change)
            self.assertTrue(self.errors(document))

    def test_relay_cannot_leak_to_business_or_expand_its_payload(self):
        for change in ({"use": ["airport", upstream.PROVIDER]}, {"proxies": [upstream.PROVIDER]},
                       {"include-all-providers": True}, {"include-all": True}):
            document = fixture()
            document["proxy-groups"][0].update(change)
            self.assertTrue(self.errors(document))
        for key, value in (("type", "http"), ("url", "https://example.invalid/secret"),
                           ("payload", []), ("payload", fixture()["proxy-providers"][upstream.PROVIDER]["payload"] * 2)):
            document = fixture()
            document["proxy-providers"][upstream.PROVIDER][key] = value
            self.assertTrue(self.errors(document))
        for key, value in (("dns", "8.8.8.8"), ("dialer-proxy", "Automatic"), ("password", "SSH_SECRET"), ("tls", False)):
            document = fixture()
            document["proxy-providers"][upstream.PROVIDER]["payload"][0][key] = value
            errors = self.errors(document)
            self.assertTrue(errors)
            self.assertNotIn("SSH_SECRET", str(errors))
        document = fixture()
        document["rules"].insert(1, "DOMAIN,example.com," + upstream.PROVIDER)
        self.assertTrue(self.errors(document))
        text = yaml.safe_dump(fixture())
        self.assertTrue(upstream.check(Path(upstream.DESKTOP), text.splitlines()))
        for rules in (["IN-PORT,7898,DIRECT"], ["MATCH,DIRECT"], ["IN-PORT,7898,Automatic"] * 2):
            document = fixture()
            document["rules"] = rules + document["rules"][1:]
            self.assertTrue(self.errors(document))

    def test_missing_or_malformed_listener_fails_without_echoing_private_text(self):
        lines = [upstream.MARKER, "rules: [", "secret: DO_NOT_PRINT_adspower"]
        errors = upstream.check(Path(upstream.DESKTOP), lines)
        self.assertTrue(errors)
        self.assertNotIn("DO_NOT_PRINT", str(errors))
        lines = [upstream.MARKER, *yaml.safe_dump(fixture()).splitlines(), "allow-lan: true"]
        self.assertTrue(upstream.check(Path(upstream.DESKTOP), lines))


if __name__ == "__main__":
    unittest.main()
