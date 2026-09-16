"""验证常用业务首条命中、应用条件与未知语法失败边界。"""
from pathlib import Path
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import check_common_routes as common


class CommonRouteTests(unittest.TestCase):
    def test_suffix_does_not_match_similar_unrelated_domain(self):
        rule = "DOMAIN-SUFFIX,alipay.com"
        self.assertTrue(common.matches(rule, "mobilegw.alipay.com", "browser"))
        self.assertFalse(common.matches(rule, "notalipay.com", "browser"))
        self.assertFalse(common.matches(rule, "alipay.com.example.org", "browser"))

    def test_nested_app_and_protocol_conditions(self):
        rule = "AND,((PROCESS-NAME,app),(OR,((DOMAIN,a.example),(DOMAIN,b.example))),(NETWORK,udp))"
        self.assertTrue(common.matches(rule, "b.example", "app", "udp"))
        self.assertFalse(common.matches(rule, "b.example", "browser", "udp"))
        self.assertFalse(common.matches(rule, "b.example", "app", "tcp"))

    def test_no_ip_evidence_is_not_fabricated(self):
        self.assertFalse(common.matches("IP-CIDR,1.0.0.0/8,no-resolve", "a.example", "app"))
        for rule in ("IP-CIDR,1.0.0.0/8", "UNKNOWN,a.example", "AND,((DOMAIN,a.example)"):
            with self.subTest(rule=rule), self.assertRaises(ValueError):
                common.matches(rule, "a.example", "app")

    def test_first_match_catches_broad_process_shadowing(self):
        lines = ["rules:", "  - PROCESS-NAME,app,PROXY", "  - DOMAIN,a.example,DIRECT", "  - MATCH,DIRECT"]
        self.assertEqual(common.route(lines, "a.example", "app"), ("PROXY", "PROCESS-NAME"))
        self.assertEqual(common.route(lines, "a.example", "browser"), ("DIRECT", "DOMAIN"))

    def test_unregistered_or_external_provider_is_not_silently_skipped(self):
        for lines in (["rules:", "  - RULE-SET,missing,DIRECT", "  - MATCH,DIRECT"],
                      ["rule-providers:", "  custom:", "    url: https://example.org/rules.yaml", "rules:", "  - RULE-SET,custom,DIRECT", "  - MATCH,DIRECT"]):
            with self.assertRaises(ValueError):
                common.route(lines, "a.example", "app")

    def test_current_public_template_covers_common_businesses(self):
        path = ROOT / "docs/examples/mihomo-public.yaml"
        cases = json.loads(common.CASES.read_text("utf-8"))
        required = {"Google", "YouTube", "Google Play", "ChatGPT", "Telegram", "支付宝", "淘宝", "闲鱼", "微信", "抖音", "小红书", "豆包", "元宝", "京东", "拼多多", "滴滴", "大智慧", "国内下载"}
        self.assertTrue(required <= {case["service"] for case in cases})
        with self.assertRaises(ValueError):
            common.audit(path, path.read_text("utf-8").splitlines(), [])
        results = common.audit(path, path.read_text("utf-8").splitlines(), cases)
        self.assertEqual([r for r in results if not r["passed"]], [])

    def test_private_contract_cannot_reintroduce_alias_or_download_bypass(self):
        path = Path("rulemesh-substore-mihomo-flclash-android.yaml")
        good = [common.MARKER, "rules:", "  - MATCH,DIRECT"]
        self.assertEqual(common.profile_contract(path, good), [])
        for extra in ("  - PROCESS-NAME,com.android.providers.downloads,DIRECT",
                      "  - PROCESS-NAME,com.android.providers.downloads.ui,PROXY",
                      "    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/region/hk/alibaba_hk.yaml",
                      "  - AND,((PROCESS-NAME,com.eg.android.AlipayGphone),(DOMAIN,gw.alipayobjects.com)),DIRECT"):
            self.assertTrue(common.profile_contract(path, good + [extra]))
        self.assertTrue(common.profile_contract(path, good[1:]))


if __name__ == "__main__":
    unittest.main()
