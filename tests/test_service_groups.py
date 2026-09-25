"""业务入口必须真正可控，且不能通过手动选项绕过地区和下载约束。"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_rules
import check_common_routes as common
import check_performance_baseline as baseline
import check_private_dns_precedence as parser
import check_service_groups as service


class ServiceGroupTests(unittest.TestCase):
    def fixture(self, client="mihomo"):
        path = ROOT / "docs/examples" / ("surge-public.conf" if client == "surge" else "mihomo-public.yaml")
        return path, path.read_text("utf-8")

    def test_youtube_scope_keeps_play_shared_cdn_and_ai_out(self):
        rules = build_rules.build_source(ROOT / "rules/proxy/youtube.list").outputs["surge_rules"]
        for domain in ("www.youtube.com", "i.ytimg.com", "youtu.be", "yt.be", "rr1.googlevideo.com", "youtubei.googleapis.com", "youtube.co.uk"):
            self.assertTrue(any(common.matches(r, domain, "browser") for r in rules), domain)
        for domain in ("redirector.gvt1.com", "redirector.gvt2.com", "lh3.ggpht.com", "play.googleapis.com", "gemini.google.com", "accounts.google.com"):
            self.assertFalse(any(common.matches(r, domain, "browser") for r in rules), domain)
        self.assertTrue(all(r.startswith("DOMAIN") for r in rules))

    def test_visible_groups_cannot_be_removed_hidden_or_retyped(self):
        path, text = self.fixture()
        for name in service.SERVICES:
            for changed in (
                text.replace(f'  - name: "{name}"', f'  - name: "missing-{name}"'),
                text.replace(f'  - name: "{name}"\n    type: select\n    hidden: false', f'  - name: "{name}"\n    type: select\n    hidden: true'),
                text.replace(f'  - name: "{name}"\n    type: select', f'  - name: "{name}"\n    type: url-test'),
            ):
                self.assertNotEqual(changed, text)
                self.assertTrue(baseline.check(path, changed.splitlines()), name)

    def test_region_wrapper_cannot_hide_unfiltered_external_nodes(self):
        path, text = self.fixture()
        for name in ("AI", "Crypto"):
            groups = parser._parse_mihomo_groups(text.splitlines())
            start = text.index(f'  - name: "{name}"')
            end = text.index('  - name:', start+1)
            block = text[start:end]
            filtered = next(line for line in block.splitlines() if line.startswith("    filter:"))
            changed = text[:start] + block.replace(filtered, '') + text[end:]
            self.assertTrue(any("地区过滤器" in e for e in baseline.check(path, changed.splitlines())))
            bad = block.replace('    proxies:\n', '    proxies:\n      - DIRECT\n')
            self.assertTrue(any("地区约束" in e for e in baseline.check(path, (text[:start]+bad+text[end:]).splitlines())))

    def test_dns_follows_ai_selector_and_default_engines_stay_active(self):
        path, text = self.fixture()
        changed = text.replace('#AI"', '#🇺🇸 美国-自动选择"')
        self.assertTrue(any('DoH' in e for e in baseline.check(path, changed.splitlines())))
        groups = parser._parse_mihomo_groups(text.splitlines())
        self.assertEqual(service.default_target('Google', groups), 'Google')
        self.assertEqual(service.default_target('YouTube', groups), 'YouTube')
        self.assertEqual(service.default_target('Telegram', groups), 'Telegram')
        self.assertEqual(service.default_target('Microsoft', groups), 'DIRECT')

    def test_business_groups_expose_only_the_requested_regions(self):
        path, text = self.fixture()
        groups = parser._parse_mihomo_groups(text.splitlines())
        for name in ('Google', 'YouTube', 'Telegram'):
            self.assertTrue(groups[name].has_external_source)
            self.assertIn('香港', groups[name].filter_text)
            self.assertFalse(groups[name].members)
        self.assertTrue(groups['Microsoft'].has_external_source)
        self.assertIn('美国', groups['Microsoft'].filter_text)
        self.assertEqual(groups['Microsoft'].members, ['DIRECT'])

    def test_mihomo_rejects_nested_provider_quotes(self):
        path, text = self.fixture()
        changed = text.replace('      - provider_a', '      - \'"provider_a"\'', 1)
        errors = baseline.check(path, changed.splitlines())
        self.assertTrue(any('嵌套两层' in error for error in errors))

    def test_youtube_must_precede_google_and_remain_independent(self):
        for client in ('mihomo','surge'):
            path, text = self.fixture(client)
            lines=text.splitlines()
            indexes=[i for i,s in enumerate(lines) if (s.startswith('  - RULE-SET,') or s.startswith('RULE-SET,')) and (('proxy_youtube,' in s or '/youtube.list,' in s) or ('hk_google,' in s or '/google_hk.list,' in s))]
            self.assertEqual(len(indexes),2)
            a,b=indexes;lines[a],lines[b]=lines[b],lines[a]
            self.assertTrue(any('YouTube 必须早于' in e for e in baseline.check(path,lines)))

    def test_cycles_are_rejected_even_in_non_default_candidates(self):
        path,text=self.fixture()
        old='  - name: "Google"\n    type: select\n    hidden: false\n    use:\n'
        self.assertEqual(text.count(old),1)
        changed=text.replace(old,old+'      - Google\n')
        self.assertTrue(any('环' in e for e in baseline.check(path,changed.splitlines())))

    def test_private_apple_update_rejection_and_work_scope_are_protected(self):
        _, text = self.fixture()
        path = Path('rulemesh-substore-mihomo-flclash-desktop.yaml')
        self.assertTrue(any('更新拒绝必须早于' in e for e in baseline.check(path,text.splitlines())))
        apple = '  - RULE-SET,direct_apple,Apple\n'
        changed = text.replace(apple, '').replace('  - RULE-SET,reject_os_update,REJECT\n', '  - RULE-SET,reject_os_update,REJECT\n' + apple)
        self.assertFalse(any('更新拒绝必须早于' in e for e in baseline.check(path,changed.splitlines())))
        _, surge = self.fixture('surge')
        self.assertTrue(any('Apple 全域放行' in e for e in baseline.check(Path('work-whitelist.conf'),surge.splitlines())))

    def test_selector_does_not_add_periodic_probe_and_ai_leaf_keeps_tolerance(self):
        path, text = self.fixture()
        anchor = '  - name: "YouTube"\n    type: select\n'
        self.assertEqual(text.count(anchor), 1)
        changed = text.replace(anchor, anchor + '    interval: 60\n')
        self.assertTrue(any('重复建立测速' in e for e in baseline.check(path,changed.splitlines())))
        start = text.index('  - name: "🇺🇸 美国-自动选择"')
        changed = text[:start] + text[start:].replace('    tolerance: 100', '    tolerance: 1', 1)
        self.assertNotEqual(text, changed)
        self.assertTrue(any('切换容差' in e for e in baseline.check(path,changed.splitlines())))
