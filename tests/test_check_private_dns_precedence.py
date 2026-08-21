import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import check_private_dns_precedence as precedence_checker  # noqa: E402
from check_private_dns_precedence import (  # noqa: E402
    required_mihomo_exceptions,
    required_surge_exceptions,
    validate_profile,
)


class PrivateDnsPrecedenceTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

        surge_rule = self.root / "dist/surge/rules/region/us/ai_us.list"
        surge_rule.parent.mkdir(parents=True)
        surge_rule.write_text("DOMAIN-SUFFIX,openai.com\n", encoding="utf-8")

        mihomo_rule = self.root / "dist/mihomo/classical/region/us/ai_us.yaml"
        mihomo_rule.parent.mkdir(parents=True)
        mihomo_rule.write_text(
            "payload:\n  - 'DOMAIN-SUFFIX,openai.com'\n", encoding="utf-8"
        )

        mihomo_ip_rule = (
            self.root / "dist/mihomo/classical/region/us/pure_ip.yaml"
        )
        mihomo_ip_rule.write_text(
            "payload:\n  - 'IP-CIDR,203.0.113.0/24,no-resolve'\n",
            encoding="utf-8",
        )

    def write_profile(self, name: str, content: str) -> Path:
        path = self.root / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_safe_nameserver_summary_never_exposes_raw_values(self) -> None:
        raw_values = (
            "https://private-dns.invalid/dns-query/private-token",
            "https://backup-dns.invalid/dns-query/backup-token",
        )

        self.assertTrue(
            hasattr(precedence_checker, "safe_nameserver_summary"),
            "检查器必须提供不会回显私有 DNS 值的安全摘要接口",
        )
        summary = precedence_checker.safe_nameserver_summary(raw_values)
        rendered = repr(summary)

        self.assertEqual(summary["count"], 2)
        self.assertNotIn("://", rendered)
        for raw_value in raw_values:
            self.assertNotIn(raw_value, rendered)
            self.assertNotIn(raw_value.split("/", 3)[2], rendered)
            self.assertNotIn(raw_value.rsplit("/", 1)[1], rendered)

    def surge_profile(self, host_lines: list[str]) -> Path:
        host = "\n".join(host_lines)
        return self.write_profile(
            "rulemesh-substore-surge-personal.conf",
            f"""[Host]
{host}

[Rule]
RULE-SET,https://example.invalid/dist/surge/rules/region/us/ai_us.list,US
RULE-SET,https://example.invalid/dist/surge/rules/direct/cn_direct.list,DIRECT
FINAL,AUTO
""",
        )

    @staticmethod
    def performance_host_line() -> str:
        return (
            "DOMAIN-SET:https://example.invalid/dist/surge/dns/"
            "cn_performance_dns_domains.list = "
            "server:https://dns.alidns.com/dns-query"
        )

    @staticmethod
    def overseas_host_line(
        server: str = "https://cloudflare-dns.com/dns-query",
    ) -> str:
        return (
            "RULE-SET:https://example.invalid/dist/surge/rules/region/us/"
            f"ai_us.list = server:{server}"
        )

    def test_surge_personal_rejects_missing_required_exception(self) -> None:
        path = self.surge_profile([self.performance_host_line()])

        findings = validate_profile(path, self.root)

        self.assertTrue(any("region/us/ai_us" in item.message for item in findings))

    def test_surge_personal_rejects_exception_after_performance_dns(self) -> None:
        path = self.surge_profile(
            [self.performance_host_line(), self.overseas_host_line()]
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("性能型中国 DNS" in item.message for item in findings))

    def test_surge_personal_accepts_overseas_exception_before_performance_dns(
        self,
    ) -> None:
        path = self.surge_profile(
            [self.overseas_host_line(), self.performance_host_line()]
        )

        self.assertEqual(validate_profile(path, self.root), [])

    def test_surge_personal_rejects_overseas_hostname_in_query_parameter(
        self,
    ) -> None:
        disguised = self.overseas_host_line(
            "https://dns.alidns.com/dns-query?next="
            "https://cloudflare-dns.com/dns-query"
        )
        path = self.surge_profile([disguised, self.performance_host_line()])

        findings = validate_profile(path, self.root)

        self.assertTrue(any("缺少海外 DNS 例外" in item.message for item in findings))

    def test_surge_personal_rejects_overseas_hostname_as_suffix(self) -> None:
        disguised = self.overseas_host_line(
            "https://cloudflare-dns.com.evil.invalid/dns-query"
        )
        path = self.surge_profile([disguised, self.performance_host_line()])

        findings = validate_profile(path, self.root)

        self.assertTrue(any("缺少海外 DNS 例外" in item.message for item in findings))

    def mihomo_profile(self, policy_lines: list[str]) -> Path:
        policy = "\n".join(policy_lines)
        return self.write_profile(
            "rulemesh-substore-mihomo-clash-verge.yaml",
            f"""dns:
  nameserver:
    - https://cloudflare-dns.com/dns-query
    - https://dns.google/dns-query
  nameserver-policy:
{policy}
rule-providers:
  us_ai:
    type: http
    behavior: classical
    url: https://example.invalid/dist/mihomo/classical/region/us/ai_us.yaml
  pure_ip:
    type: http
    behavior: classical
    url: https://example.invalid/dist/mihomo/classical/region/us/pure_ip.yaml
  cn_direct:
    type: http
    behavior: classical
    url: https://example.invalid/dist/mihomo/classical/direct/cn_direct.yaml
  cn-performance-dns-domains:
    type: http
    behavior: domain
    format: text
    url: https://example.invalid/dist/surge/dns/cn_performance_dns_domains.list
rules:
  - RULE-SET,us_ai,US
  - RULE-SET,pure_ip,US
  - RULE-SET,cn_direct,DIRECT
  - MATCH,AUTO
""",
        )

    @staticmethod
    def overseas_policy_lines() -> list[str]:
        return [
            '    "rule-set:us_ai":',
            "      - https://cloudflare-dns.com/dns-query",
            "      - https://dns.google/dns-query",
        ]

    @staticmethod
    def performance_policy_lines() -> list[str]:
        return [
            '    "rule-set:cn-performance-dns-domains":',
            "      - https://dns.alidns.com/dns-query",
        ]

    def test_mihomo_rejects_missing_overseas_policy(self) -> None:
        path = self.mihomo_profile(self.performance_policy_lines())

        findings = validate_profile(path, self.root)

        self.assertTrue(any("us_ai" in item.message for item in findings))

    def test_mihomo_rejects_overseas_policy_after_performance_dns(self) -> None:
        path = self.mihomo_profile(
            self.performance_policy_lines() + self.overseas_policy_lines()
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("性能型中国 DNS" in item.message for item in findings))

    def test_mihomo_rejects_overseas_policy_not_equal_to_nameserver(self) -> None:
        path = self.mihomo_profile(
            [
                '    "rule-set:us_ai":',
                "      - https://cloudflare-dns.com/dns-query",
            ]
            + self.performance_policy_lines()
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("dns.nameserver 完全相同" in item.message for item in findings))

    def test_mihomo_accepts_exact_overseas_policy_before_performance_dns(self) -> None:
        path = self.mihomo_profile(
            self.overseas_policy_lines() + self.performance_policy_lines()
        )

        self.assertEqual(validate_profile(path, self.root), [])

    def mihomo_profile_with_ai_provider(self, provider_name: str) -> Path:
        path = self.mihomo_profile(
            self.overseas_policy_lines() + self.performance_policy_lines()
        )
        content = path.read_text(encoding="utf-8").replace("us_ai", provider_name)
        path.write_text(content, encoding="utf-8")
        return path

    def test_mihomo_accepts_exact_ai_us_provider_alias(self) -> None:
        path = self.mihomo_profile_with_ai_provider("ai-us")

        self.assertEqual(validate_profile(path, self.root), [])

    def test_mihomo_rejects_not_ai_us_as_required_provider(self) -> None:
        path = self.mihomo_profile_with_ai_provider("not-ai-us")

        findings = validate_profile(path, self.root)

        self.assertTrue(any("ai-us/us_ai" in item.message for item in findings))

    def test_mihomo_rejects_us_ai_backup_as_required_provider(self) -> None:
        path = self.mihomo_profile_with_ai_provider("us_ai_backup")

        findings = validate_profile(path, self.root)

        self.assertTrue(any("ai-us/us_ai" in item.message for item in findings))

    def test_required_sets_are_derived_from_active_order_and_skip_pure_ip(
        self,
    ) -> None:
        surge_lines = self.surge_profile(
            [self.overseas_host_line(), self.performance_host_line()]
        ).read_text(encoding="utf-8").splitlines()
        mihomo_lines = self.mihomo_profile(
            self.overseas_policy_lines() + self.performance_policy_lines()
        ).read_text(encoding="utf-8").splitlines()

        self.assertEqual(
            required_surge_exceptions(surge_lines, self.root),
            ["region/us/ai_us"],
        )
        self.assertEqual(
            required_mihomo_exceptions(mihomo_lines, self.root),
            ["us_ai"],
        )

    def test_required_sets_skip_missing_public_artifacts(self) -> None:
        lines = self.surge_profile(
            [self.overseas_host_line(), self.performance_host_line()]
        ).read_text(encoding="utf-8").splitlines()
        cn_direct = next(
            index for index, line in enumerate(lines) if "direct/cn_direct.list" in line
        )
        lines.insert(
            cn_direct,
            "RULE-SET,https://example.invalid/dist/surge/rules/proxy/missing.list,PROXY",
        )

        self.assertEqual(
            required_surge_exceptions(lines, self.root),
            ["region/us/ai_us"],
        )

    def test_mihomo_rejects_empty_nameserver_and_empty_overseas_policy(
        self,
    ) -> None:
        path = self.mihomo_profile(
            ['    "rule-set:us_ai": []'] + self.performance_policy_lines()
        )
        content = path.read_text(encoding="utf-8").replace(
            "  nameserver:\n"
            "    - https://cloudflare-dns.com/dns-query\n"
            "    - https://dns.google/dns-query\n",
            "  nameserver: []\n",
        )
        path.write_text(content, encoding="utf-8")

        findings = validate_profile(path, self.root)

        self.assertTrue(any("dns.nameserver" in item.message for item in findings))

    def test_work_profile_rejects_performance_dns_artifact(self) -> None:
        path = self.write_profile(
            "rulemesh-substore-surge-work-whitelist.conf",
            """[Host]
DOMAIN-SET:https://example.invalid/dist/surge/dns/cn_performance_dns_domains.list = server:https://dns.alidns.com/dns-query
""",
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("工作白名单" in item.message for item in findings))


if __name__ == "__main__":
    unittest.main()
