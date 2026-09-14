"""保护安卓下载的协议、进程、解析顺序及稳定出站，避免只验证首页域名。"""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import check_android_stability as android
import check_performance_baseline as baseline
import check_private_dns_precedence as parser
import build_rules


class AndroidStabilityTests(unittest.TestCase):
    def fixture(self):
        text = (ROOT / "docs/examples/mihomo-public.yaml").read_text(encoding="utf-8")
        text = text.replace("interval: 300", "interval: 600")
        text = text.replace("\n", "\n" + android.MARKER + "\n", 1)
        text += "\n# PRIVATE_SUBSCRIPTION_DIRECT_START\n# PRIVATE_SUBSCRIPTION_DIRECT_END\n"
        auto = android.stable_target(text.splitlines())
        stable = "下载稳定"
        group = '\n  - name: "下载稳定"\n    type: fallback\n    interval: 600\n    lazy: false\n    url: "https://www.google.com/generate_204"\n    use:\n      - provider_a\n      - provider_b\n      - provider_c\n\n'
        text = text.replace("rule-providers:\n", group + "rule-providers:\n", 1)
        policy = '    "rule-set:hk_google":\n' + "".join(f'      - "{url}#{stable}"\n' for url in baseline.OVERSEAS)
        text = text.replace("  fake-ip-filter:\n", policy + "  fake-ip-filter:\n", 1)
        rules = android.quic_rules() + ["RULE-SET,hk_google," + stable]
        rules += [f"PROCESS-NAME,{package},{stable}" for package in android.PACKAGES]
        text = text.replace("  - RULE-SET,hk_google," + auto, "\n".join("  - " + rule for rule in rules), 1)
        return Path(android.PROFILE), text

    def test_complete_profile_preserves_base_and_regional_contracts(self):
        path, text = self.fixture()
        self.assertEqual(baseline.check(path, text.splitlines()), [])

    def test_download_processes_and_quic_cannot_be_removed_or_shadowed(self):
        path, text = self.fixture()
        protected = android.quic_rules() + [f"PROCESS-NAME,{p},下载稳定" for p in android.PACKAGES]
        for rule in protected:
            line = "  - " + rule
            for changed in (text.replace(line + "\n", ""), text.replace(line + "\n", "") + "\n" + line):
                with self.subTest(rule=rule):
                    self.assertTrue(android.check(path, changed.splitlines()))
        self.assertTrue(android.check(path, text.replace(",REJECT\n", ",REJECT-DROP\n").splitlines()))

    def test_google_dns_must_follow_ai_and_use_same_download_group(self):
        path, text = self.fixture()
        policies = re.search(r"  nameserver-policy:\n(.*?)  fake-ip-filter:", text, re.S).group(1)
        start = policies.index('    "rule-set:hk_google":')
        changed = text.replace(policies, policies[start:] + policies[:start])
        self.assertTrue(android.check(path, changed.splitlines()))
        self.assertTrue(android.check(path, text.replace("#下载稳定", "#DIRECT").splitlines()))
        self.assertTrue(baseline.check(path, text.replace("#🇺🇸 美国-自动选择", "#下载稳定").splitlines()))

    def test_stable_group_cannot_become_fastest_or_nested_auto(self):
        path, text = self.fixture()
        for changed in (text.replace("type: fallback", "type: url-test"),
                        text.replace("type: fallback", "type: fallback\n    proxies: [DIRECT]"),
                        text.replace("type: fallback", "type: fallback\n    filter: US")):
            self.assertTrue(android.check(path, changed.splitlines()))

    def test_play_api_real_ip_and_global_udp_rejection_are_not_reintroduced(self):
        path, text = self.fixture()
        for changed in (text.replace("  fake-ip-filter:\n", '  fake-ip-filter:\n    - "android.clients.google.com"\n'),
                        text.replace("rules:\n", "rules:\n  - NETWORK,udp,REJECT\n")):
            self.assertTrue(android.check(path, changed.splitlines()))

    def test_android_exception_does_not_silently_spread_to_other_profiles(self):
        _, text = self.fixture()
        for name in ("mihomo-public.yaml", "rulemesh-substore-mihomo-flclash-desktop.yaml"):
            self.assertTrue(any("不得自动扩散" in x for x in android.check(Path(name), text.splitlines())))

    def test_google_download_domains_remain_in_existing_public_asset(self):
        compiled = build_rules.build_source(ROOT / "rules/region/hk/google_hk.list").outputs["surge_rules"]
        def matches(domain, rule):
            parts = rule.split(",")
            if len(parts) < 2:
                return False
            kind, value = parts[:2]
            return (kind == "DOMAIN" and domain == value or
                    kind == "DOMAIN-SUFFIX" and (domain == value or domain.endswith("." + value)) or
                    kind == "DOMAIN-KEYWORD" and value in domain)
        for domain in ("play.googleapis.com", "android.clients.google.com", "play-fe.googleapis.com",
                       "dl.google.com", "dl-ssl.google.com", "redirector.gvt1.com",
                       "r1---sn-download.gvt1.com", "r1---sn-download.gvt2.com",
                       "r1---sn-download.gvt3.com", "redirector.xn--ngstr-lra8j.com",
                       "play-lh.googleusercontent.com", "www.google.com", "www.youtube.com",
                       "r1---sn-video.googlevideo.com"):
            with self.subTest(domain=domain):
                self.assertTrue(any(matches(domain, rule) for rule in compiled))


if __name__ == "__main__":
    unittest.main()
