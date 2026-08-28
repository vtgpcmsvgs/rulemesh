import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import check_private_performance  # noqa: E402


class PrivatePerformanceTests(unittest.TestCase):
    def test_both_surge_personal_profiles_are_registered(self) -> None:
        self.assertEqual(
            check_private_performance.SURGE_PERSONAL_NAMES,
            {
                "rulemesh-substore-surge-personal.conf",
                "rulemesh-substore-surge-personal-company.conf",
            },
        )
        self.assertTrue(
            check_private_performance.SURGE_PERSONAL_NAMES
            <= check_private_performance.PRIVATE_PROFILE_NAMES
        )

    def write_temp(self, name: str, content: str) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_surge_personal_rejects_us_final(self) -> None:
        path = self.write_temp(
            "rulemesh-substore-surge-personal.conf",
            """[Proxy Group]
全地区自动选择 = smart, policy-path=a
美国自动选择 = smart, policy-path=b, policy-regex-filter=美国|US

[Rule]
FINAL,美国自动选择,dns-failed
""",
        )

        findings = check_private_performance.validate_profile(path)

        self.assertTrue(any("通用 FINAL" in item.message for item in findings))

    def test_surge_personal_requires_aggressive_rule_entries(self) -> None:
        path = self.write_temp(
            "rulemesh-substore-surge-personal-company.conf",
            """[Proxy Group]
自动选择 = smart, policy-path=a

[Rule]
FINAL,自动选择,dns-failed
""",
        )

        messages = [
            item.message for item in check_private_performance.validate_profile(path)
        ]

        for identifier in (
            "apple_direct",
            "personal_priority_hk",
            "notion_hk",
            "hk_securities_aggressive",
            "microsoft_store_us",
            "outlook_direct",
            "yikaiying.com",
        ):
            self.assertTrue(any(identifier in message for message in messages), identifier)

    def test_surge_personal_accepts_aggressive_rule_order(self) -> None:
        path = self.write_temp(
            "rulemesh-substore-surge-personal-company.conf",
            """[Proxy Group]
自动选择 = smart, policy-path=a

[Rule]
RULE-SET,https://example.com/direct/apple_direct.list,DIRECT
RULE-SET,https://example.com/region/hk/personal_priority_hk.list,HK-AUTO
RULE-SET,https://example.com/region/hk/notion_hk.list,HK-AUTO
RULE-SET,https://example.com/region/hk/hk_securities_aggressive.list,HK-AUTO
RULE-SET,https://example.com/region/us/microsoft_store_us.list,US-AUTO
RULE-SET,https://example.com/direct/outlook_direct.list,DIRECT
DOMAIN-SUFFIX,yikaiying.com,DIRECT
RULE-SET,https://example.com/reject/adblock_reject.list,REJECT
RULE-SET,https://example.com/reject/os_update_reject.list,REJECT
RULE-SET,https://example.com/region/us/microsoft_us.list,US-AUTO
RULE-SET,https://example.com/direct/cn_direct.list,DIRECT
FINAL,自动选择,dns-failed
""",
        )

        self.assertEqual(check_private_performance.validate_profile(path), [])

    def test_surge_work_requires_exact_domestic_entries(self) -> None:
        path = self.write_temp(
            "rulemesh-substore-surge-work-whitelist.conf",
            """[Rule]
RULE-SET,allowed,DIRECT
FINAL,REJECT
""",
        )

        messages = [
            item.message for item in check_private_performance.validate_profile(path)
        ]

        self.assertTrue(any("zsxq.com" in message for message in messages))
        self.assertTrue(any("yikaiying.com" in message for message in messages))

    def test_mihomo_rejects_stale_health_and_us_match(self) -> None:
        path = self.write_temp(
            "rulemesh-substore-mihomo-clash-verge.yaml",
            self.mihomo_fixture(interval=900, lazy="true", match="美国自动选择", tolerance=150),
        )

        messages = [
            item.message for item in check_private_performance.validate_profile(path)
        ]

        self.assertTrue(any("300" in message for message in messages))
        self.assertTrue(any("MATCH" in message for message in messages))
        self.assertTrue(any("tolerance" in message for message in messages))

    def test_mihomo_requires_hk_securities_rule(self) -> None:
        content = self.mihomo_fixture(
            interval=300,
            lazy="false",
            match="自动选择",
            tolerance=100,
        ).replace(
            "  - RULE-SET,hk_securities_aggressive,香港自动选择\n",
            "",
        )
        path = self.write_temp("rulemesh-substore-mihomo-clash-verge.yaml", content)

        messages = [
            item.message for item in check_private_performance.validate_profile(path)
        ]

        self.assertTrue(any("hk_securities_aggressive" in message for message in messages))

    def test_mihomo_requires_hk_securities_provider(self) -> None:
        content = self.mihomo_fixture(
            interval=300,
            lazy="false",
            match="自动选择",
            tolerance=100,
        ).replace(
            "  hk_securities_aggressive:\n",
            "  unrelated_provider:\n",
        )
        path = self.write_temp("rulemesh-substore-mihomo-clash-verge.yaml", content)

        messages = [
            item.message for item in check_private_performance.validate_profile(path)
        ]

        self.assertTrue(any("provider" in message for message in messages))

    def test_mihomo_requires_canonical_hk_securities_provider_url(self) -> None:
        content = self.mihomo_fixture(
            interval=300,
            lazy="false",
            match="自动选择",
            tolerance=100,
        ).replace(
            "dist/mihomo/classical/region/hk/hk_securities_aggressive.yaml",
            "dist/mihomo/classical/region/hk/hk_brokers.yaml",
        )
        path = self.write_temp("rulemesh-substore-mihomo-clash-verge.yaml", content)

        messages = [
            item.message for item in check_private_performance.validate_profile(path)
        ]

        self.assertTrue(any("provider" in message for message in messages))

    def test_mihomo_requires_hk_securities_target_group(self) -> None:
        content = self.mihomo_fixture(
            interval=300,
            lazy="false",
            match="自动选择",
            tolerance=100,
        ).replace(
            "RULE-SET,hk_securities_aggressive,香港自动选择",
            "RULE-SET,hk_securities_aggressive,自动选择",
        )
        path = self.write_temp("rulemesh-substore-mihomo-clash-verge.yaml", content)

        messages = [
            item.message for item in check_private_performance.validate_profile(path)
        ]

        self.assertTrue(any("香港组" in message for message in messages))

    def test_mihomo_requires_hk_securities_before_reject_and_direct(self) -> None:
        content = self.mihomo_fixture(
            interval=300,
            lazy="false",
            match="自动选择",
            tolerance=100,
        ).replace(
            "  - RULE-SET,hk_securities_aggressive,香港自动选择\n"
            "  - RULE-SET,reject_adblock,REJECT\n",
            "  - RULE-SET,reject_adblock,REJECT\n"
            "  - RULE-SET,hk_securities_aggressive,香港自动选择\n",
        )
        path = self.write_temp("rulemesh-substore-mihomo-clash-meta.yaml", content)

        messages = [
            item.message for item in check_private_performance.validate_profile(path)
        ]

        self.assertTrue(any("必须早于 reject_adblock" in message for message in messages))

    def test_accepts_performance_first_profiles(self) -> None:
        personal = self.write_temp(
            "rulemesh-substore-surge-personal.conf",
            """[Proxy Group]
自动选择 = smart, policy-path=a
美国自动选择 = smart, policy-path=b, policy-regex-filter=美国|US

[Rule]
RULE-SET,https://example.com/direct/apple_direct.list,DIRECT
RULE-SET,https://example.com/region/hk/personal_priority_hk.list,HK-AUTO
RULE-SET,https://example.com/region/hk/notion_hk.list,HK-AUTO
RULE-SET,https://example.com/region/hk/hk_securities_aggressive.list,HK-AUTO
RULE-SET,https://example.com/region/us/microsoft_store_us.list,US-AUTO
RULE-SET,https://example.com/direct/outlook_direct.list,DIRECT
DOMAIN-SUFFIX,yikaiying.com,DIRECT
RULE-SET,https://example.com/reject/adblock_reject.list,REJECT
RULE-SET,https://example.com/reject/os_update_reject.list,REJECT
RULE-SET,https://example.com/region/us/microsoft_us.list,US-AUTO
RULE-SET,https://example.com/direct/cn_direct.list,DIRECT
FINAL,自动选择,dns-failed
""",
        )
        work = self.write_temp(
            "rulemesh-substore-surge-work-whitelist.conf",
            """[Rule]
DOMAIN-SUFFIX,zsxq.com,DIRECT
DOMAIN-SUFFIX,yikaiying.com,DIRECT
FINAL,REJECT
""",
        )
        mihomo = self.write_temp(
            "rulemesh-substore-mihomo-clash-meta.yaml",
            self.mihomo_fixture(interval=300, lazy="false", match="自动选择", tolerance=100),
        )

        for path in (personal, work, mihomo):
            self.assertEqual(check_private_performance.validate_profile(path), [])

    @staticmethod
    def mihomo_fixture(
        *, interval: int, lazy: str, match: str, tolerance: int
    ) -> str:
        return f"""rule-providers:
  hk_securities_aggressive:
    type: http
    behavior: classical
    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/region/hk/hk_securities_aggressive.yaml
    path: ./ruleset/region/hk/hk_securities_aggressive.yaml
proxy-providers:
  provider-a:
    type: http
    proxy: DIRECT
    health-check:
      enable: true
      url: https://www.google.com/generate_204
      interval: {interval}
      timeout: 5000
      lazy: {lazy}
proxy-groups:
  - name: 自动选择
    type: url-test
    use:
      - provider-a
    url: https://www.google.com/generate_204
    interval: {interval}
    tolerance: 50
    lazy: {lazy}
  - name: 美国自动选择
    type: url-test
    use:
      - provider-a
    filter: 美国|US
    url: https://www.google.com/generate_204
    interval: {interval}
    tolerance: {tolerance}
    lazy: {lazy}
  - name: 香港自动选择
    type: url-test
    use:
      - provider-a
    filter: 香港|HK
    url: https://www.google.com/generate_204
    interval: {interval}
    tolerance: 50
    lazy: {lazy}
rules:
  - RULE-SET,hk_securities_aggressive,香港自动选择
  - RULE-SET,reject_adblock,REJECT
  - RULE-SET,region-us-ai,美国自动选择
  - RULE-SET,direct_cn,DIRECT
  - MATCH,{match}
"""


if __name__ == "__main__":
    unittest.main()
