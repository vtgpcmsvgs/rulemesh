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
        # 业务层已由 Google/YouTube 香港节点筛选组承接；夹具只补安卓专属规则。
        for name in ("Google", "YouTube"):
            anchor = f'  - name: "{name}"\n    type: select\n    hidden: false\n'
            self.assertEqual(text.count(anchor), 1)
        policy = ''.join(f'    "rule-set:{key}":\n' + ''.join(f'      - "{url}#{outbound}"\n' for url in baseline.OVERSEAS)
                         for key, outbound in (("proxy_youtube", "YouTube"), ("hk_google", "Google")))
        text = text.replace("  fake-ip-filter:\n", policy + "  fake-ip-filter:\n", 1)
        rules = ["RULE-SET,hk_google,Google"]
        rules += [f"PROCESS-NAME,{package},Google" for package in android.PACKAGES]
        self.assertEqual(text.count("  - RULE-SET,hk_google,Google"), 1)
        text = text.replace("  - RULE-SET,hk_google,Google", "\n".join("  - " + rule for rule in rules), 1)
        apple = "  - RULE-SET,direct_apple,Apple\n"
        self.assertEqual(text.count(apple), 1)
        text = text.replace(apple, "")
        text = text.replace("  - RULE-SET,reject_os_update,REJECT\n", "  - RULE-SET,reject_os_update,REJECT\n" + apple, 1)
        anchor = "  - RULE-SET,direct_ips5,DIRECT\n"
        self.assertEqual(text.count(anchor), 1)
        components = "  " + android.ALIPAY_MARKER + "\n" + "".join("  - " + rule + "\n" for rule in android.alipay_component_rules())
        text = text.replace(anchor, anchor + components, 1)
        return Path(android.PROFILE), text

    def test_complete_profile_preserves_base_and_regional_contracts(self):
        path, text = self.fixture()
        self.assertEqual(baseline.check(path, text.splitlines()), [])

    def test_download_processes_cannot_be_removed_or_shadowed(self):
        path, text = self.fixture()
        protected = [f"PROCESS-NAME,{p},Google" for p in android.PACKAGES]
        for rule in protected:
            line = "  - " + rule
            for changed in (text.replace(line + "\n", ""), text.replace(line + "\n", "") + "\n" + line):
                with self.subTest(rule=rule):
                    self.assertTrue(android.check(path, changed.splitlines()))

    def test_alipay_components_cannot_be_removed_duplicated_or_shadowed(self):
        path, text = self.fixture()
        for rule in android.alipay_component_rules():
            line = "  - " + rule + "\n"
            for changed in (text.replace(line, ""), text.replace(line, line * 2),
                            text.replace(line, "") + line,
                            text.replace(line, "").replace("rules:\n", "rules:\n" + line)):
                with self.subTest(rule=rule):
                    self.assertTrue(android.check(path, changed.splitlines()))

    def test_alipay_component_repair_cannot_expand_scope_or_reject_udp(self):
        path, text = self.fixture()
        broad = [
            f"PROCESS-NAME,{android.ALIPAY_PACKAGE},DIRECT",
            "DOMAIN-SUFFIX,alipayobjects.com,DIRECT",
            "DOMAIN,gw.alipayobjects.com,DIRECT",
            f"AND,((PROCESS-NAME,{android.ALIPAY_PACKAGE}),(DOMAIN-SUFFIX,alipayobjects.com)),DIRECT",
            f"AND,((PROCESS-NAME,{android.ALIPAY_PACKAGE}),(NETWORK,udp)),REJECT",
        ]
        for rule in broad:
            with self.subTest(rule=rule):
                changed = text.replace("rules:\n", "rules:\n  - " + rule + "\n", 1)
                self.assertTrue(android.check(path, changed.splitlines()))
        changed = text.replace("  " + android.ALIPAY_MARKER + "\n", "")
        self.assertTrue(android.check(path, changed.splitlines()))

    def test_alipay_marker_alone_activates_android_boundary(self):
        self.assertTrue(android.active(Path("mihomo-public.yaml"), ["  " + android.ALIPAY_MARKER]))

    def test_daily_baseline_removes_component_and_shared_download_patches(self):
        import check_common_routes as common
        path, text = self.fixture()
        text = common.MARKER + "\n" + text
        text = text.replace("  " + android.ALIPAY_MARKER + "\n", "")
        for rule in android.alipay_component_rules():
            text = text.replace("  - " + rule + "\n", "")
        for package in android.PACKAGES[3:]:
            text = text.replace(f"  - PROCESS-NAME,{package},Google\n", "")
        self.assertEqual(baseline.check(path, text.splitlines()), [])
        for package in android.PACKAGES[3:]:
            changed = text.replace("rules:\n", f"rules:\n  - PROCESS-NAME,{package},Google\n", 1)
            self.assertTrue(android.check(path, changed.splitlines()))

    def test_cronet_quic_rejection_cannot_return(self):
        path, text = self.fixture()
        retired = android.retired_quic_rules() + [
            "AND,((NETWORK,udp),(DST-PORT,443)),REJECT",
            "AND,((DST-PORT,443),(NETWORK,udp)),REJECT",
        ]
        for rule in retired:
            for reject in ("REJECT", "REJECT-DROP"):
                changed = text.replace("rules:\n", "rules:\n  - " + rule.replace("REJECT", reject) + "\n")
                with self.subTest(rule=rule, reject=reject):
                    self.assertTrue(android.check(path, changed.splitlines()))
        google = '  - name: "Google"\n    type: select\n    hidden: false\n'
        self.assertEqual(text.count(google), 1)
        disabled = text.replace(google, google + "    disable-udp: true\n", 1)
        self.assertTrue(android.check(path, disabled.splitlines()))

    def test_google_dns_must_follow_ai_and_use_same_download_group(self):
        path, text = self.fixture()
        policies = re.search(r"  nameserver-policy:\n(.*?)  fake-ip-filter:", text, re.S).group(1)
        start = policies.index('    "rule-set:hk_google":')
        changed = text.replace(policies, policies[start:] + policies[:start])
        self.assertTrue(android.check(path, changed.splitlines()))
        for business in ("Google", "YouTube"):
            changed = text.replace("#" + business, "#DIRECT")
            self.assertNotEqual(changed, text)
            self.assertTrue(android.check(path, changed.splitlines()))
        self.assertTrue(baseline.check(path, text.replace("#AI", "#下载稳定").splitlines()))

    def test_stable_group_cannot_become_fastest_or_nested_auto(self):
        path, text = self.fixture()
        google = '  - name: "Google"\n    type: select\n    hidden: false\n'
        self.assertEqual(text.count(google), 1)
        for changed in (text.replace(google, google.replace("type: select", "type: url-test"), 1),
                        text.replace(google, google + "    proxies: [DIRECT]\n", 1),
                        text.replace('    filter: "(?i)🇭🇰|香港|hong kong|\\\\bhk\\\\b"', '    filter: US', 1)):
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
