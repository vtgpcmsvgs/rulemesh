"""防止模板正常、私人配置却遗漏 Notion 香港入口。"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import check_notion_routing as notion
import check_private_dns_precedence as parser
import check_common_routes as common


class NotionRoutingTests(unittest.TestCase):
    def fixture(self, client="mihomo"):
        path = ROOT / "docs/examples" / ("mihomo-public.yaml" if client == "mihomo" else "surge-public.conf")
        lines = path.read_text("utf-8").splitlines()
        groups = parser._parse_mihomo_groups(lines) if client == "mihomo" else parser._parse_surge_groups(lines)
        auto = next(n for n, g in groups.items() if g.group_type in {"url-test", "smart"})
        return path, lines, auto

    def test_actual_profiles_and_templates(self):
        for path in parser.default_paths(ROOT):
            if not path.is_file():
                continue
            lines = path.read_text("utf-8").splitlines()
            groups = parser._parse_surge_groups(lines) if path.suffix == ".conf" else parser._parse_mihomo_groups(lines)
            auto = next(n for n, g in groups.items() if g.group_type in {"smart", "url-test"})
            with self.subTest(profile=path.name):
                self.assertEqual(notion.check(path, lines, auto), [])

    def test_missing_duplicate_late_or_direct_rule_is_rejected(self):
        for client in ("surge", "mihomo"):
            path, lines, auto = self.fixture(client)
            index = next(i for i, s in enumerate(lines) if "RULE-SET," in s and ("notion_hk.list," in s or "RULE-SET,hk_notion," in s))
            line = lines[index]
            for changed in (lines[:index]+lines[index+1:], lines+[line],
                            lines[:index]+lines[index+1:]+[line],
                            lines[:index]+[line.rsplit(",",1)[0]+",DIRECT"]+lines[index+1:]):
                self.assertTrue(notion.check(path, changed, auto))

    def test_hong_kong_group_is_required_and_legacy_group_is_rejected(self):
        path, lines, auto = self.fixture()
        self.assertEqual(notion.target(lines), notion.HK_GROUP)
        changed = [line.replace(notion.HK_GROUP, auto, 1) if "RULE-SET,hk_notion," in line else line for line in lines]
        self.assertTrue(notion.check(path, changed, auto))
        legacy = lines.copy()
        insert = next(i for i, s in enumerate(legacy) if s.startswith('  - name: "🇭🇰 香港-自动选择"'))
        legacy[insert:insert] = [
            '  - name: "📝 Notion-自动选择"',
            '    type: url-test',
            '    url: "https://app.notion.com/"',
            '    interval: 300',
            '    lazy: false',
            '    use:',
            '      - provider_a',
        ]
        self.assertTrue(notion.check(path, legacy, auto))

    def test_website_api_public_assets_share_exact_first_match(self):
        path, lines, _ = self.fixture()
        for domain in ("notion.com", "app.notion.com", "api.notion.com", "broker-guide.notion.site",
                       "img.notionusercontent.com", "secure.notion-static.com", "www.notion.so", "msgstore.www.notion.so"):
            for network in ("tcp", "udp"):
                self.assertEqual(common.route(lines,domain,"browser",network),(notion.HK_GROUP,"hk_notion"))
        shadowed=lines.copy()
        shadowed.insert(next(i for i,s in enumerate(lines) if s.startswith('  - RULE-SET,hk_notion,')), '  - DOMAIN-SUFFIX,notion.site,DIRECT')
        self.assertNotEqual(common.route(shadowed,'broker-guide.notion.site','browser')[0], notion.HK_GROUP)

    def test_work_whitelist_does_not_gain_notion(self):
        _, lines, auto = self.fixture("surge")
        self.assertTrue(notion.check(Path('work-whitelist.conf'), lines, auto))
