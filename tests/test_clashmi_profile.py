"""验证移动端派生不丢业务数据，且不把 Android 进程边界带到 iOS。"""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from derive_clashmi_profile import derive

SOURCE = """# 桌面配置
find-process-mode: strict
tun:
  enable: true
  stack: mixed
dns:
  listen: 0.0.0.0:1053
  nameserver:
    - https://dns.alidns.com/dns-query
proxy-providers:
  sample:
    url: https://example.invalid/private?token=TEST
    proxy: DIRECT
    interval: 86400
    health-check:
      interval: 300
proxy-groups:
  - name: 自动
    type: url-test
    interval: 300
    lazy: false
rule-providers:
  example:
    interval: 86400
rules:
  - RULE-SET,example,自动
  - MATCH,DIRECT
"""


class ClashMiProfileTests(unittest.TestCase):
    def test_subscription_update_interval_is_not_health_interval(self):
        result = derive(SOURCE.replace("    interval: 86400", "    interval: 300"))
        self.assertEqual(result.count("interval: 300"), 2)
        self.assertEqual(result.count("interval: 600"), 2)

    def test_asn_is_removed_but_exact_ssh_ranges_remain(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            relative = "dist/mihomo/classical/direct/alicloud_hk_ipv4_ssh22_direct.yaml"
            rules = root / relative
            rules.parent.mkdir(parents=True)
            rules.write_text('payload:\n  - "AND,((IP-CIDR,192.0.2.0/24,no-resolve),(NETWORK,tcp),(DST-PORT,22))"\n  - "AND,((IP-ASN,45102,no-resolve),(NETWORK,tcp),(DST-PORT,22))"\n', encoding="utf-8")
            source = SOURCE.replace("  example:\n    interval: 86400", "  example:\n    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/" + relative)
            source = source.replace("  - MATCH,DIRECT", "  - AND,((IP-ASN,45102,no-resolve),(NETWORK,tcp),(DST-PORT,22)),DIRECT\n  - MATCH,DIRECT")
            result = derive(source, root)
            self.assertNotIn("IP-ASN,", result)
            self.assertIn("type: inline", result)
            self.assertIn("IP-CIDR,192.0.2.0/24,no-resolve", result)
            self.assertIn("  - RULE-SET,example,自动", result)
            with self.assertRaises(ValueError):
                derive(source.replace("(DST-PORT,22)", "(DST-PORT,443)"), root)

    def test_markers_in_body_are_not_duplicated(self):
        marker = "# RuleMesh 业务策略组：2026-09-25"
        common_marker = "# RuleMesh 日常连通性基线：2026-09-16"
        result = derive(common_marker + "\n" + SOURCE.replace("proxy-groups:\n", marker + "\nproxy-groups:\n"))
        self.assertEqual(result.splitlines().count(marker), 1)
        self.assertEqual(result.splitlines().count(common_marker), 1)
        self.assertEqual(result.splitlines().count("# RuleMesh 性能基线：2026-09-09"), 1)

    def test_preserves_subscription_routes_and_dns(self):
        result = derive(SOURCE.replace("\n", "\r\n"))
        for block in ("rule-providers:", "rules:"):
            self.assertEqual(result.split(block, 1)[1], SOURCE.split(block, 1)[1])
        self.assertIn("url: https://example.invalid/private?token=TEST", result)
        self.assertIn("    proxy: DIRECT", result)
        self.assertEqual(result.count("interval: 86400"), 2)
        self.assertEqual(result.count("interval: 600"), 2)
        self.assertIn("find-process-mode: off", result)
        self.assertIn("    - https://dns.alidns.com/dns-query", result)
        self.assertNotIn("\ntun:", result)
        self.assertNotIn("  listen:", result)
        self.assertNotIn("\r", result)

    def test_rejects_ambiguous_or_changed_source(self):
        for source in (
            SOURCE + "dns:\n",
            SOURCE.replace("dns:\n", ""),
            SOURCE.replace("  listen: 0.0.0.0:1053\n", ""),
            SOURCE.replace("find-process-mode: strict", "find-process-mode: always"),
            SOURCE.replace("  - MATCH,DIRECT", "  - PROCESS-NAME,com.example.app,DIRECT\n  - MATCH,DIRECT"),
            "\ufeff" + SOURCE,
        ):
            with self.assertRaises(ValueError):
                derive(source)


if __name__ == "__main__":
    unittest.main()
