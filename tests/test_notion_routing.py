"""防止模板正常、私人配置却遗漏 Notion，以及无效的专用测速。"""
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

    def test_health_url_and_direct_provider_membership_are_required(self):
        path, lines, auto = self.fixture()
        dest = notion.target(lines)
        start = next(i for i, s in enumerate(lines) if s == f'  - name: "{dest}"')
        end = next(i for i in range(start+1,len(lines)) if lines[i].startswith('  - name:'))
        block = "\n".join(lines[start:end])
        for old, new in ((notion.URL,"https://www.google.com/generate_204"),
                         ("tolerance: 150","tolerance: 0"),
                         ("lazy: false","lazy: true"),
                         ("    use:","    proxies:"),
                         ("      - provider_a", "")):
            changed = lines[:start]+block.replace(old,new).splitlines()+lines[end:]
            self.assertTrue(notion.check(path,changed,auto))

    def test_website_api_public_assets_share_exact_first_match(self):
        path, lines, _ = self.fixture()
        for domain in ("notion.com", "app.notion.com", "api.notion.com", "broker-guide.notion.site",
                       "img.notionusercontent.com", "secure.notion-static.com", "www.notion.so", "msgstore.www.notion.so"):
            for network in ("tcp", "udp"):
                self.assertEqual(common.route(lines,domain,"browser",network),(notion.target(lines),"hk_notion"))
        shadowed=lines.copy()
        shadowed.insert(next(i for i,s in enumerate(lines) if s.startswith('  - RULE-SET,hk_notion,')), '  - DOMAIN-SUFFIX,notion.site,DIRECT')
        self.assertNotEqual(common.route(shadowed,'broker-guide.notion.site','browser')[0], notion.target(lines))

    def test_work_whitelist_does_not_gain_notion(self):
        _, lines, auto = self.fixture("surge")
        self.assertTrue(notion.check(Path('work-whitelist.conf'), lines, auto))
