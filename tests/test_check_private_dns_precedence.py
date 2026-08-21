import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import check_private_dns_precedence as precedence_checker  # noqa: E402
import check_dns_safety  # noqa: E402
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

        surge_regex_rule = self.root / "dist/surge/rules/proxy/regex_only.list"
        surge_regex_rule.parent.mkdir(parents=True, exist_ok=True)
        surge_regex_rule.write_text(
            "DOMAIN-REGEX,^api[0-9]+\\.example\\.com$\n", encoding="utf-8"
        )

        mihomo_regex_rule = (
            self.root / "dist/mihomo/classical/proxy/regex_only.yaml"
        )
        mihomo_regex_rule.parent.mkdir(parents=True, exist_ok=True)
        mihomo_regex_rule.write_text(
            "payload:\n  - 'DOMAIN-REGEX,^api[0-9]+\\.example\\.com$'\n",
            encoding="utf-8",
        )

        mihomo_other_rule = (
            self.root / "dist/mihomo/classical/region/us/not_ai.yaml"
        )
        mihomo_other_rule.write_text(
            "payload:\n  - 'DOMAIN-SUFFIX,example.com'\n", encoding="utf-8"
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

        self.assertEqual(set(summary), {"count", "sha256"})
        self.assertEqual(summary["count"], 2)
        self.assertIsInstance(summary["sha256"], str)
        self.assertEqual(len(summary["sha256"]), 16)
        self.assertRegex(summary["sha256"], r"^[0-9a-f]{16}$")
        self.assertNotIn("://", rendered)
        for raw_value in raw_values:
            self.assertNotIn(raw_value, rendered)
            self.assertNotIn(raw_value.split("/", 3)[2], rendered)
            self.assertNotIn(raw_value.rsplit("/", 1)[1], rendered)

    def surge_profile(
        self,
        host_lines: list[str],
        ai_rule: str | None = (
            "RULE-SET,https://example.invalid/dist/surge/rules/"
            "region/us/ai_us.list,US"
        ),
    ) -> Path:
        host = "\n".join(host_lines)
        rule = f"{ai_rule}\n" if ai_rule is not None else ""
        return self.write_profile(
            "rulemesh-substore-surge-personal.conf",
            f"""[Host]
{host}

[Rule]
{rule}RULE-SET,https://example.invalid/dist/surge/rules/direct/cn_direct.list,DIRECT
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

    def test_surge_personal_rejects_allowed_hostname_with_wrong_path(self) -> None:
        disguised = self.overseas_host_line(
            "https://cloudflare-dns.com/not-dns-query"
        )
        path = self.surge_profile([disguised, self.performance_host_line()])

        findings = validate_profile(path, self.root)

        self.assertTrue(any("缺少海外 DNS 例外" in item.message for item in findings))

    def test_surge_personal_rejects_missing_canonical_ai_rule(self) -> None:
        path = self.surge_profile(
            [self.overseas_host_line(), self.performance_host_line()],
            ai_rule=None,
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("region/us/ai_us" in item.message for item in findings))

    def test_surge_personal_rejects_canonical_ai_rule_with_non_us_target(
        self,
    ) -> None:
        path = self.surge_profile(
            [self.overseas_host_line(), self.performance_host_line()],
            ai_rule=(
                "RULE-SET,https://example.invalid/dist/surge/rules/"
                "region/us/ai_us.list,AUTO"
            ),
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("美国" in item.message for item in findings))

    def mihomo_profile(
        self,
        policy_lines: list[str],
        *,
        ai_url: str = (
            "https://example.invalid/dist/mihomo/classical/region/us/ai_us.yaml"
        ),
        ai_target: str = "US",
    ) -> Path:
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
    url: {ai_url}
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
  - RULE-SET,us_ai,{ai_target}
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

        self.assertTrue(any("region/us/ai_us" in item.message for item in findings))

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

    def test_mihomo_rejects_old_small_policy_beside_performance_policy(
        self,
    ) -> None:
        path = self.mihomo_profile(
            self.overseas_policy_lines()
            + [
                '    "rule-set:cn-dns-domains":',
                "      - https://dns.alidns.com/dns-query",
            ]
            + self.performance_policy_lines()
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("未登记" in item.message for item in findings))

    def test_mihomo_rejects_bootstrap_alias_as_extra_policy(self) -> None:
        path = self.mihomo_profile(
            self.overseas_policy_lines()
            + [
                '    "rule-set:bootstrap-canary":',
                "      - https://dns.alidns.com/dns-query",
            ]
            + self.performance_policy_lines()
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("未登记" in item.message for item in findings))

    def test_mihomo_rejects_any_extra_overseas_policy(self) -> None:
        path = self.mihomo_profile(
            self.overseas_policy_lines()
            + [
                '    "rule-set:overseas-canary":',
                "      - https://cloudflare-dns.com/dns-query",
                "      - https://dns.google/dns-query",
            ]
            + self.performance_policy_lines()
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("未登记" in item.message for item in findings))

    def test_mihomo_rejects_empty_rule_set_policy_key(self) -> None:
        path = self.mihomo_profile(
            self.overseas_policy_lines()
            + ['    "rule-set:": []']
            + self.performance_policy_lines()
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("未登记" in item.message for item in findings))

    def test_mihomo_rejects_unresolved_yaml_policy_alias(self) -> None:
        path = self.mihomo_profile(
            self.overseas_policy_lines()
            + ['    "rule-set:cn-performance-dns-domains": *domestic']
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("YAML anchor/alias" in item.message for item in findings))

    def test_mihomo_rejects_unapproved_default_nameserver(self) -> None:
        path = self.mihomo_profile(
            self.overseas_policy_lines() + self.performance_policy_lines()
        )
        content = path.read_text(encoding="utf-8").replace(
            "cloudflare-dns.com", "unapproved-overseas.invalid"
        )
        path.write_text(content, encoding="utf-8")

        findings = validate_profile(path, self.root)

        self.assertTrue(any("默认海外端点" in item.message for item in findings))

    def test_mihomo_rejects_allowed_nameserver_hostname_with_wrong_path(
        self,
    ) -> None:
        path = self.mihomo_profile(
            self.overseas_policy_lines() + self.performance_policy_lines()
        )
        content = path.read_text(encoding="utf-8").replace(
            "cloudflare-dns.com/dns-query", "cloudflare-dns.com/not-dns-query"
        )
        path.write_text(content, encoding="utf-8")

        findings = validate_profile(path, self.root)

        self.assertTrue(any("默认海外端点" in item.message for item in findings))

    def test_mihomo_rejects_performance_policy_using_overseas_dns(self) -> None:
        path = self.mihomo_profile(
            self.overseas_policy_lines()
            + [
                '    "rule-set:cn-performance-dns-domains":',
                "      - https://cloudflare-dns.com/dns-query",
            ]
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("国内 DNS" in item.message for item in findings))

    def test_public_mihomo_example_keeps_small_policy_allowed(self) -> None:
        path = ROOT / "docs/examples/mihomo-public.yaml"

        self.assertEqual(check_dns_safety.validate_path(path), [])

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

    def test_mihomo_accepts_canary_alias_when_public_ai_triad_is_complete(
        self,
    ) -> None:
        path = self.mihomo_profile_with_ai_provider("canary-private-alias")

        self.assertEqual(validate_profile(path, self.root), [])

    def test_mihomo_rejects_canonical_alias_url_pointing_to_other_rule(
        self,
    ) -> None:
        path = self.mihomo_profile(
            self.overseas_policy_lines() + self.performance_policy_lines(),
            ai_url=(
                "https://example.invalid/dist/mihomo/classical/"
                "region/us/not_ai.yaml"
            ),
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("region/us/ai_us" in item.message for item in findings))

    def test_mihomo_rejects_canonical_ai_rule_with_non_us_target(self) -> None:
        path = self.mihomo_profile(
            self.overseas_policy_lines() + self.performance_policy_lines(),
            ai_target="AUTO",
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("美国" in item.message for item in findings))

    def test_mihomo_diagnostic_does_not_expose_canary_alias(self) -> None:
        path = self.mihomo_profile_with_ai_provider("canary-private-alias")
        content = path.read_text(encoding="utf-8").replace(
            '    "rule-set:canary-private-alias":\n'
            "      - https://cloudflare-dns.com/dns-query\n"
            "      - https://dns.google/dns-query\n",
            "",
        )
        path.write_text(content, encoding="utf-8")

        findings = validate_profile(path, self.root)
        rendered = "\n".join(
            f"{item.message}\n{item.remediation}" for item in findings
        )

        self.assertTrue(findings)
        self.assertNotIn("canary-private-alias", rendered)

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

    def test_regex_only_artifacts_require_overseas_exceptions(self) -> None:
        surge_lines = self.surge_profile(
            [self.overseas_host_line(), self.performance_host_line()]
        ).read_text(encoding="utf-8").splitlines()
        surge_cutoff = next(
            index
            for index, line in enumerate(surge_lines)
            if "direct/cn_direct.list" in line
        )
        surge_lines.insert(
            surge_cutoff,
            "RULE-SET,https://example.invalid/dist/surge/rules/"
            "proxy/regex_only.list,PROXY",
        )

        mihomo_path = self.mihomo_profile(
            self.overseas_policy_lines() + self.performance_policy_lines()
        )
        mihomo_lines = mihomo_path.read_text(encoding="utf-8").splitlines()
        provider_cutoff = next(
            index for index, line in enumerate(mihomo_lines) if line == "  cn_direct:"
        )
        mihomo_lines[provider_cutoff:provider_cutoff] = [
            "  regex_canary:",
            "    type: http",
            "    behavior: classical",
            "    url: https://example.invalid/dist/mihomo/classical/"
            "proxy/regex_only.yaml",
        ]
        rule_cutoff = next(
            index
            for index, line in enumerate(mihomo_lines)
            if line.startswith("  - RULE-SET,cn_direct,")
        )
        mihomo_lines.insert(rule_cutoff, "  - RULE-SET,regex_canary,PROXY")

        self.assertIn(
            "proxy/regex_only",
            required_surge_exceptions(surge_lines, self.root),
        )
        self.assertIn(
            "regex_canary",
            required_mihomo_exceptions(mihomo_lines, self.root),
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
