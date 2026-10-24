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
import check_service_groups as service
import build_rules
import check_common_routes as common


class AndroidStabilityTests(unittest.TestCase):
    def test_hong_kong_cannot_auto_fallback_after_a_cold_health_failure(self):
        path,text=self.fixture()
        hk=next(n for n,region in service.REGIONS.items() if region=='hk')
        anchor=f'  - name: "{hk}"\n    type: select\n'
        self.assertEqual(text.count(anchor),1)
        self.assertEqual(baseline.check(path,text.splitlines()),[])
        for replacement in (anchor.replace('select','url-test'),anchor+'    interval: 600\n'):
            self.assertTrue(android.check(path,text.replace(anchor,replacement).splitlines()))

    def chatgpt_fixture(self):
        path, text = self.fixture()
        ai = next(p[2] for _, p in parser._parse_mihomo_rules(text.splitlines()) if p[:2] == ["RULE-SET", "us_ai"])
        rule = f"  - PROCESS-NAME,{android.CHATGPT_PACKAGE},{ai}\n"
        return path, text, rule, ai

    def test_chatgpt_unknown_destination_and_other_apps(self):
        path, text, rule, ai = self.chatgpt_fixture()
        self.assertEqual(baseline.check(path, text.splitlines()), [])
        for network in ("tcp", "udp"):
            for destination in ("unlisted-chatgpt-component.invalid", ""):
                self.assertEqual(common.route(text.splitlines(), destination, android.CHATGPT_PACKAGE, network), (ai, "PROCESS-NAME"))
            self.assertEqual(common.route(text.splitlines(), "unlisted-chatgpt-component.invalid", "com.android.chrome", network), ("DIRECT", "MATCH"))

    def test_chatgpt_fallback_cannot_be_missing_duplicated_late_or_direct(self):
        path, text, rule, ai = self.chatgpt_fixture()
        self.assertEqual(android.check_chatgpt(path, text.splitlines()), [])
        changes = [text.replace(rule, ""), text.replace(rule, "").replace(android.CHATGPT_MARKER, ""), text.replace(rule, rule * 2),
                   text.replace(rule, "") + rule, text.replace(rule, rule.replace(ai, "DIRECT")),
                   text.replace("find-process-mode: always", "find-process-mode: off"),
                   text.replace(rule, f"  - AND,((PROCESS-NAME,{android.CHATGPT_PACKAGE}),(NETWORK,udp)),REJECT\n")]
        for changed in changes:
            self.assertNotEqual(changed, text)
            self.assertTrue(android.check_chatgpt(path, changed.splitlines()))
        self.assertTrue(android.check_chatgpt(Path("desktop.yaml"), text.splitlines()))

    def fixture(self):
        text = (ROOT / "docs/examples/mihomo-public.yaml").read_text(encoding="utf-8")
        # 公开模板保持自动；私人夹具复用完整例外清单，避免只转换 AI 而遗漏新增手动业务。
        for name in service.MANUAL_FIXED_SERVICES:
            matches = list(re.finditer(rf'^  - name: "{name}"\n.*?(?=^  - name:)', text, re.M | re.S))
            self.assertEqual(len(matches), 1)
            match = matches[0]
            block = match.group().replace('    type: url-test\n', '    type: select\n')
            block, removed = re.subn(r'^    (url|interval|tolerance|timeout|lazy):.*\n', '', block, flags=re.M)
            self.assertEqual(removed, 5)
            text = text[:match.start()] + block + text[match.end():]
        text = text.replace("interval: 300", "interval: 600")
        text = text.replace("\n", "\n" + android.MARKER + "\n", 1)
        text += "\n# PRIVATE_SUBSCRIPTION_DIRECT_START\n# PRIVATE_SUBSCRIPTION_DIRECT_END\n"
        broker_rule = '  - RULE-SET,hk_securities,香港券商\n'
        self.assertEqual(text.count(broker_rule), 1)
        text = text.replace(broker_rule, broker_rule + ''.join(f'  - PROCESS-NAME,{p},香港券商\n' for p in android.BROKER_PACKAGES))
        # 普通 Google 默认香港；修复可用性时同样必须遵守用户地区要求。
        import json
        import yaml
        hk = next(n for n, region in service.REGIONS.items() if region == 'hk')
        names = ['HK mobile failure (1)', 'HK mobile failure +2']
        text += f'\n{android.GOOGLE_HK_QUARANTINE}:\n' + ''.join('  - ' + json.dumps(n) + '\n' for n in names)
        start = text.index(f'  - name: "{hk}"\n')
        end = text.index('  - name:', start + 1)
        block = text[start:end]
        self.assertEqual(block.count('    hidden: true\n'), 1)
        block = block.replace('    hidden: true\n', '    hidden: false\n')
        block = block.replace('    type: url-test\n', '    type: select\n')
        block, removed = re.subn(r'^    (url|interval|tolerance|timeout|lazy):.*\n', '', block, flags=re.M)
        self.assertEqual(removed, 5)
        rows = [s for s in block.splitlines() if s.startswith('    exclude-filter:')]
        self.assertEqual(len(rows), 1)
        existing = yaml.safe_load(rows[0])['exclude-filter']
        replacement = '    exclude-filter: ' + json.dumps(existing + android.google_hk_exclusion(names), ensure_ascii=False)
        text = text[:start] + block.replace(rows[0], replacement) + text[end:]
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
        anchor = "  - RULE-SET,direct_cn_social,DIRECT\n"
        self.assertEqual(text.count(anchor), 1)
        components = "  " + android.ALIPAY_MARKER + "\n" + "".join("  - " + rule + "\n" for rule in android.alipay_component_rules())
        text = text.replace(anchor, anchor + components, 1)
        ai = next(p[2] for _, p in parser._parse_mihomo_rules(text.splitlines()) if p[:2] == ["RULE-SET", "us_ai"])
        anchor = "  - RULE-SET,direct_cn_services,DIRECT\n"
        self.assertEqual(text.count(anchor), 1)
        text = text.replace(anchor, anchor + f"  - PROCESS-NAME,{android.CHATGPT_PACKAGE},{ai}\n", 1)
        text = text.replace("find-process-mode: strict", "find-process-mode: always")
        text = android.CHATGPT_MARKER + "\n" + text
        return Path(android.PROFILE), text

    def test_complete_profile_preserves_base_and_regional_contracts(self):
        path, text = self.fixture()
        self.assertEqual(baseline.check(path, text.splitlines()), [])

    def test_google_hk_default_rejects_other_regions_and_preserves_saved_selection(self):
        path, text = self.fixture()
        groups = parser._parse_mihomo_groups(text.splitlines())
        self.assertEqual(service.REGIONS[service.default_target('Google', groups)], 'hk')
        self.assertEqual(service.REGIONS[service.default_target('YouTube', groups)], 'hk')
        self.assertEqual(set(groups['Google'].members), set(service.REGIONS))
        start = text.index('  - name: "Google"\n')
        end = text.index('  - name:', start + 1)
        block = text[start:end]
        for region in ('us', 'tw', 'jp', 'kr', 'sg'):
            candidate = next(n for n, r in service.REGIONS.items() if r == region)
            member_line = f'      - "{candidate}"\n'
            self.assertEqual(block.count(member_line), 1)
            regressed = block.replace(member_line, '').replace('    proxies:\n', '    proxies:\n' + member_line, 1)
            changed = text[:start] + regressed + text[end:]
            self.assertNotEqual(changed, text)
            self.assertTrue(any('默认' in e for e in baseline.check(path, changed.splitlines())))
        changed = text.replace('  store-selected: true', '  store-selected: false')
        self.assertNotEqual(changed, text)
        self.assertTrue(any('store-selected' in e for e in baseline.check(path, changed.splitlines())))

    def test_hk_quarantine_cannot_be_removed_or_detached_and_is_exact(self):
        path, text = self.fixture()
        hk = next(n for n, region in service.REGIONS.items() if region == 'hk')
        self.assertEqual(android.check_google_hk_quarantine(text.splitlines(), hk), [])
        import yaml
        data = yaml.safe_load(text)
        names = data[android.GOOGLE_HK_QUARANTINE]
        group = next(g for g in data['proxy-groups'] if g['name'] == hk)
        for name in names:
            self.assertTrue(re.search(group['exclude-filter'], name))
            self.assertFalse(re.search(group['exclude-filter'], name + ' legitimate sibling'))
        for mutation in (text.replace(android.GOOGLE_HK_QUARANTINE, 'removed-quarantine'),
                         text.replace('HK mobile failure (1)', 'different node'),
                         text + f'\n{android.GOOGLE_HK_QUARANTINE}: []\n'):
            errors = android.check_google_hk_quarantine(mutation.splitlines(), hk)
            self.assertTrue(errors)
            self.assertFalse(any(name in error for error in errors for name in names))
        start = text.index(f'  - name: "{hk}"\n')
        end = text.index('  - name:', start + 1)
        block = text[start:end]
        hidden = block.replace('    hidden: false\n', '    hidden: true\n')
        self.assertNotEqual(block, hidden)
        self.assertTrue(android.check_google_hk_quarantine((text[:start] + hidden + text[end:]).splitlines(), hk))

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
        for name in ("mihomo-public.yaml", "rulemesh-flclash-desktop-20261023.yaml"):
            self.assertTrue(any("不得自动扩散" in x for x in android.check(Path(name), text.splitlines())))

    def test_broker_process_allowlist_is_exact_and_private_profile_passes(self):
        self.assertEqual(len(android.BROKER_PACKAGES), 9)
        self.assertTrue(all(android.allowed_hk_broker_rule(["PROCESS-NAME", package, "HK"]) for package in android.BROKER_PACKAGES))
        self.assertFalse(android.allowed_hk_broker_rule(["PROCESS-NAME", "com.example.other", "HK"]))
        private = Path.home() / "Desktop" / "rulemesh-local" / "rulemesh-flclash-android-20261023.yaml"
        if not private.is_file():
            self.skipTest("未发现本机私人安卓配置")
        lines = private.read_text(encoding="utf-8").splitlines()
        self.assertEqual(baseline.check(private, lines), [])
        self.assertEqual(android.check(private, lines), [])

    def test_unified_broker_process_guards_cannot_all_disappear(self):
        path, text = self.fixture()
        self.assertEqual(android.check(path, text.splitlines()), [])
        changed = text
        for package in android.BROKER_PACKAGES:
            changed = changed.replace(f'  - PROCESS-NAME,{package},香港券商\n', '')
        self.assertNotEqual(changed, text)
        self.assertTrue(any('逐项保留' in e for e in android.check(path, changed.splitlines())))

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
