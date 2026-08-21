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


PUBLIC_RAW_ROOT = "https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main"
SURGE_APPROVED_US_FILTER = "((🇺🇸)|(美国)|(United States)|(US))"
MIHOMO_APPROVED_US_FILTER = r"(?i)🇺🇸|美国|united states|\\bus\\b"


class PrivateDnsPrecedenceTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

        surge_rule = self.root / "dist/surge/rules/region/us/ai_us.list"
        surge_rule.parent.mkdir(parents=True)
        surge_rule.write_text("DOMAIN-SUFFIX,openai.com\n", encoding="utf-8")

        surge_google_rule = (
            self.root / "dist/surge/rules/region/us/google_us.list"
        )
        surge_google_rule.write_text(
            "IP-CIDR,203.0.113.0/24,no-resolve\n", encoding="utf-8"
        )

        mihomo_rule = self.root / "dist/mihomo/classical/region/us/ai_us.yaml"
        mihomo_rule.parent.mkdir(parents=True)
        mihomo_rule.write_text(
            "payload:\n  - 'DOMAIN-SUFFIX,openai.com'\n", encoding="utf-8"
        )

        mihomo_google_rule = (
            self.root / "dist/mihomo/classical/region/us/google_us.yaml"
        )
        mihomo_google_rule.write_text(
            "payload:\n  - 'IP-CIDR,203.0.113.0/24,no-resolve'\n",
            encoding="utf-8",
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
        *,
        ai_url: str | None = (
            f"{PUBLIC_RAW_ROOT}/dist/surge/rules/region/us/ai_us.list"
        ),
        ai_target: str = "US-AUTO",
        other_us_target: str | None = None,
        other_us_url: str = (
            f"{PUBLIC_RAW_ROOT}/dist/surge/rules/region/us/google_us.list"
        ),
        group_lines: list[str] | None = None,
    ) -> Path:
        host = "\n".join(host_lines)
        if other_us_target is None:
            other_us_target = ai_target
        if group_lines is None:
            group_lines = [
                "US-AUTO = smart, policy-path=https://subscriptions.invalid/all, "
                f"policy-regex-filter={SURGE_APPROVED_US_FILTER}",
                "AUTO = smart, policy-path=https://subscriptions.invalid/all, "
                "policy-regex-filter=^.*((香港)|(HK)|(美国)|(US)).*$",
            ]
        groups = "\n".join(group_lines)
        ai_rule = (
            f"RULE-SET,{ai_url},{ai_target}\n" if ai_url is not None else ""
        )
        return self.write_profile(
            "rulemesh-substore-surge-personal.conf",
            f"""[Host]
{host}

[Proxy Group]
{groups}

[Rule]
RULE-SET,{other_us_url},{other_us_target}
{ai_rule}RULE-SET,{PUBLIC_RAW_ROOT}/dist/surge/rules/direct/cn_direct.list,DIRECT
FINAL,AUTO
""",
        )

    @staticmethod
    def performance_host_line(
        artifact_url: str = (
            f"{PUBLIC_RAW_ROOT}/dist/surge/dns/"
            "cn_performance_dns_domains.list"
        ),
    ) -> str:
        return (
            f"DOMAIN-SET:{artifact_url} = "
            "server:https://dns.alidns.com/dns-query"
        )

    @staticmethod
    def overseas_host_line(
        server: str = "https://cloudflare-dns.com/dns-query",
    ) -> str:
        return (
            f"RULE-SET:{PUBLIC_RAW_ROOT}/dist/surge/rules/region/us/"
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
            ai_url=None,
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("region/us/ai_us" in item.message for item in findings))

    def test_surge_personal_rejects_canonical_ai_rule_with_non_us_target(
        self,
    ) -> None:
        path = self.surge_profile(
            [self.overseas_host_line(), self.performance_host_line()],
            ai_target="AUTO",
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("美国" in item.message for item in findings))

    def test_surge_personal_rejects_missing_ai_target_group(self) -> None:
        path = self.surge_profile(
            [self.overseas_host_line(), self.performance_host_line()],
            ai_target="US-MISSING",
            group_lines=[],
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("美国" in item.message for item in findings))

    def test_surge_personal_rejects_not_us_named_fake_group(self) -> None:
        path = self.surge_profile(
            [self.overseas_host_line(), self.performance_host_line()],
            ai_target="not-us",
            group_lines=[
                "not-us = smart, policy-path=https://subscriptions.invalid/all, "
                "policy-regex-filter=^.*((香港)|(Hong Kong)|(HK)).*$"
            ],
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("美国" in item.message for item in findings))

    def test_surge_personal_rejects_us_named_group_with_non_us_filter(self) -> None:
        path = self.surge_profile(
            [self.overseas_host_line(), self.performance_host_line()],
            group_lines=[
                "US-AUTO = smart, policy-path=https://subscriptions.invalid/all, "
                "policy-regex-filter=^.*((香港)|(Hong Kong)|(HK)).*$"
            ],
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("美国" in item.message for item in findings))

    def test_surge_personal_rejects_unapproved_us_filter_shapes(self) -> None:
        invalid_filters = (
            "not-us",
            "(?i).*|US",
            "(?i)(?!US).*",
            "(?i)US|CA",
        )
        for filter_text in invalid_filters:
            with self.subTest(filter_text=filter_text):
                path = self.surge_profile(
                    [self.overseas_host_line(), self.performance_host_line()],
                    group_lines=[
                        "US-AUTO = smart, "
                        "policy-path=https://subscriptions.invalid/all, "
                        f"policy-regex-filter={filter_text}"
                    ],
                )

                findings = validate_profile(path, self.root)

                self.assertTrue(any("美国" in item.message for item in findings))

    def test_surge_personal_rejects_us_group_without_node_source(self) -> None:
        path = self.surge_profile(
            [self.overseas_host_line(), self.performance_host_line()],
            group_lines=[
                "US-AUTO = smart, policy-path=, "
                f"policy-regex-filter={SURGE_APPROVED_US_FILTER}"
            ],
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("美国" in item.message for item in findings))

    def test_surge_personal_rejects_invalid_policy_path_sources(self) -> None:
        invalid_sources = (
            "not-a-url",
            "subscriptions.invalid/all",
            "http://subscriptions.invalid/all",
            "https:///all",
            "https://[not-an-ip]/all",
            "https://private-user:private-pass@private-source-canary.invalid/"
            "private-token",
        )
        for source in invalid_sources:
            with self.subTest(source_type=source.split(":", 1)[0]):
                path = self.surge_profile(
                    [self.overseas_host_line(), self.performance_host_line()],
                    group_lines=[
                        f"US-AUTO = smart, policy-path={source}, "
                        f"policy-regex-filter={SURGE_APPROVED_US_FILTER}"
                    ],
                )

                findings = validate_profile(path, self.root)
                rendered = " ".join(
                    f"{item.message} {item.remediation}" for item in findings
                )

                self.assertTrue(any("美国" in item.message for item in findings))
                self.assertNotIn(source, rendered)
                for sensitive_part in (
                    "private-user",
                    "private-pass",
                    "private-source-canary.invalid",
                    "private-token",
                ):
                    self.assertNotIn(sensitive_part, rendered)

    def test_surge_personal_accepts_https_policy_path_with_query(self) -> None:
        path = self.surge_profile(
            [self.overseas_host_line(), self.performance_host_line()],
            group_lines=[
                "US-AUTO = smart, "
                "policy-path=https://subscriptions.invalid/api/sub?target=Surge&all=1, "
                f"policy-regex-filter={SURGE_APPROVED_US_FILTER}"
            ],
        )

        self.assertEqual(validate_profile(path, self.root), [])

    def test_surge_personal_rejects_false_include_all_source(self) -> None:
        path = self.surge_profile(
            [self.overseas_host_line(), self.performance_host_line()],
            group_lines=[
                "US-AUTO = smart, include-all-proxies=0, "
                f"policy-regex-filter={SURGE_APPROVED_US_FILTER}"
            ],
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("美国" in item.message for item in findings))

    def test_surge_personal_rejects_explicit_non_us_group_member(self) -> None:
        path = self.surge_profile(
            [self.overseas_host_line(), self.performance_host_line()],
            group_lines=[
                "US-AUTO = smart, CA-NODE, "
                "policy-path=https://subscriptions.invalid/all, "
                f"policy-regex-filter={SURGE_APPROVED_US_FILTER}"
            ],
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("美国" in item.message for item in findings))

    def test_surge_personal_accepts_defined_us_group(self) -> None:
        path = self.surge_profile(
            [self.overseas_host_line(), self.performance_host_line()]
        )

        self.assertEqual(validate_profile(path, self.root), [])

    def test_surge_personal_accepts_us_group_through_select_wrapper(self) -> None:
        path = self.surge_profile(
            [self.overseas_host_line(), self.performance_host_line()],
            ai_target="US-WRAPPER",
            group_lines=[
                "US-WRAPPER = select, US-LEAF",
                "US-LEAF = smart, policy-path=https://subscriptions.invalid/all, "
                f"policy-regex-filter={SURGE_APPROVED_US_FILTER}",
            ],
        )

        self.assertEqual(validate_profile(path, self.root), [])

    def test_surge_personal_rejects_cyclic_us_group_wrappers(self) -> None:
        path = self.surge_profile(
            [self.overseas_host_line(), self.performance_host_line()],
            ai_target="US-CYCLE",
            group_lines=[
                "US-CYCLE = select, CYCLE-NEXT",
                "CYCLE-NEXT = select, US-CYCLE",
            ],
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("美国" in item.message for item in findings))

    def test_surge_personal_rejects_excessively_deep_us_group_wrappers(self) -> None:
        group_lines = [f"US-WRAPPER-{index} = select, US-WRAPPER-{index + 1}" for index in range(40)]
        group_lines.append(
            "US-WRAPPER-40 = smart, policy-path=https://subscriptions.invalid/all, "
            f"policy-regex-filter={SURGE_APPROVED_US_FILTER}"
        )
        path = self.surge_profile(
            [self.overseas_host_line(), self.performance_host_line()],
            ai_target="US-WRAPPER-0",
            group_lines=group_lines,
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("美国" in item.message for item in findings))

    def test_surge_personal_rejects_untrusted_canonical_ai_urls(self) -> None:
        valid_path = "/dist/surge/rules/region/us/ai_us.list"
        invalid_urls = {
            "http": f"http://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main{valid_path}",
            "forged-origin": f"https://rules.invalid/vtgpcmsvgs/rulemesh/main{valid_path}",
            "wrong-repository": f"https://raw.githubusercontent.com/vtgpcmsvgs/not-rulemesh/main{valid_path}",
            "wrong-ref": f"https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/dev{valid_path}",
            "query": f"{PUBLIC_RAW_ROOT}{valid_path}?mirror=1",
            "fragment": f"{PUBLIC_RAW_ROOT}{valid_path}#mirror",
            "empty-query": f"{PUBLIC_RAW_ROOT}{valid_path}?",
            "empty-fragment": f"{PUBLIC_RAW_ROOT}{valid_path}#",
        }
        for label, ai_url in invalid_urls.items():
            with self.subTest(label=label):
                path = self.surge_profile(
                    [self.overseas_host_line(), self.performance_host_line()],
                    ai_url=ai_url,
                )

                findings = validate_profile(path, self.root)

                self.assertTrue(
                    any("region/us/ai_us" in item.message for item in findings)
                )

    def test_surge_personal_rejects_untrusted_us_cross_check_url(self) -> None:
        path = self.surge_profile(
            [self.overseas_host_line(), self.performance_host_line()],
            other_us_url=(
                "https://rules.invalid/vtgpcmsvgs/rulemesh/main/"
                "dist/surge/rules/region/us/google_us.list"
            ),
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("美国" in item.message for item in findings))

    def test_surge_personal_rejects_untrusted_performance_artifact_url(
        self,
    ) -> None:
        fake_performance = self.performance_host_line(
            "https://rules.invalid/vtgpcmsvgs/rulemesh/main/"
            "dist/surge/dns/cn_performance_dns_domains.list"
        )
        path = self.surge_profile([self.overseas_host_line(), fake_performance])

        findings = validate_profile(path, self.root)

        self.assertTrue(any("性能型中国 DNS DOMAIN-SET" in item.message for item in findings))

    def test_surge_personal_rejects_different_us_cross_check_target(self) -> None:
        path = self.surge_profile(
            [self.overseas_host_line(), self.performance_host_line()],
            other_us_target="OTHER-US",
            group_lines=[
                "US-AUTO = smart, policy-path=https://subscriptions.invalid/all, "
                f"policy-regex-filter={SURGE_APPROVED_US_FILTER}",
                "OTHER-US = smart, policy-path=https://subscriptions.invalid/all, "
                f"policy-regex-filter={SURGE_APPROVED_US_FILTER}",
                "AUTO = smart, policy-path=https://subscriptions.invalid/all, "
                "policy-regex-filter=^.*((香港)|(HK)|(美国)|(US)).*$",
            ],
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("美国" in item.message for item in findings))

    def mihomo_profile(
        self,
        policy_lines: list[str],
        *,
        ai_url: str = (
            f"{PUBLIC_RAW_ROOT}/dist/mihomo/classical/region/us/ai_us.yaml"
        ),
        ai_target: str = "US-AUTO",
        other_us_target: str | None = None,
        other_us_url: str = (
            f"{PUBLIC_RAW_ROOT}/dist/mihomo/classical/region/us/google_us.yaml"
        ),
        pure_ip_url: str = (
            f"{PUBLIC_RAW_ROOT}/dist/mihomo/classical/region/us/pure_ip.yaml"
        ),
        performance_url: str = (
            f"{PUBLIC_RAW_ROOT}/dist/surge/dns/"
            "cn_performance_dns_domains.list"
        ),
        group_block: str | None = None,
    ) -> Path:
        policy = "\n".join(policy_lines)
        if other_us_target is None:
            other_us_target = ai_target
        if group_block is None:
            group_block = f"""  - name: US-AUTO
    type: url-test
    use: [provider_a]
    filter: "{MIHOMO_APPROVED_US_FILTER}"
  - name: AUTO
    type: url-test
    use: [provider_a]
    filter: "(?i)香港|\\bhk\\b|美国|\\bus\\b"""
        return self.write_profile(
            "rulemesh-substore-mihomo-clash-verge.yaml",
            f"""dns:
  nameserver:
    - https://cloudflare-dns.com/dns-query
    - https://dns.google/dns-query
  nameserver-policy:
{policy}
proxy-groups:
{group_block}
proxy-providers:
  provider_a:
    type: http
rule-providers:
  us_google:
    type: http
    behavior: classical
    url: {other_us_url}
  us_ai:
    type: http
    behavior: classical
    url: {ai_url}
  pure_ip:
    type: http
    behavior: classical
    url: {pure_ip_url}
  cn_direct:
    type: http
    behavior: classical
    url: {PUBLIC_RAW_ROOT}/dist/mihomo/classical/direct/cn_direct.yaml
  cn-performance-dns-domains:
    type: http
    behavior: domain
    format: text
    url: {performance_url}
rules:
  - RULE-SET,us_google,{other_us_target}
  - RULE-SET,us_ai,{ai_target}
  - RULE-SET,pure_ip,{ai_target}
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
                f"{PUBLIC_RAW_ROOT}/dist/mihomo/classical/"
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

    def test_mihomo_rejects_missing_ai_target_group(self) -> None:
        path = self.mihomo_profile(
            self.overseas_policy_lines() + self.performance_policy_lines(),
            ai_target="US-MISSING",
            group_block="",
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("美国" in item.message for item in findings))

    def test_mihomo_rejects_not_us_named_fake_group(self) -> None:
        path = self.mihomo_profile(
            self.overseas_policy_lines() + self.performance_policy_lines(),
            ai_target="not-us",
            group_block="""  - name: not-us
    type: url-test
    use: [provider_a]
    filter: "(?i)香港|hong kong|\\bhk\\b""",
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("美国" in item.message for item in findings))

    def test_mihomo_rejects_us_named_group_with_non_us_filter(self) -> None:
        path = self.mihomo_profile(
            self.overseas_policy_lines() + self.performance_policy_lines(),
            group_block="""  - name: US-AUTO
    type: url-test
    use: [provider_a]
    filter: "(?i)香港|hong kong|\\bhk\\b""",
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("美国" in item.message for item in findings))

    def test_mihomo_rejects_unapproved_us_filter_shapes(self) -> None:
        invalid_filters = (
            "not-us",
            "(?i).*|US",
            "(?i)(?!US).*",
            "(?i)US|CA",
        )
        for filter_text in invalid_filters:
            with self.subTest(filter_text=filter_text):
                path = self.mihomo_profile(
                    self.overseas_policy_lines() + self.performance_policy_lines(),
                    group_block=f'''  - name: US-AUTO
    type: url-test
    use: [provider_a]
    filter: "{filter_text}"''',
                )

                findings = validate_profile(path, self.root)

                self.assertTrue(any("美国" in item.message for item in findings))

    def test_mihomo_rejects_us_group_without_node_source(self) -> None:
        path = self.mihomo_profile(
            self.overseas_policy_lines() + self.performance_policy_lines(),
            group_block=f'''  - name: US-AUTO
    type: url-test
    use: []
    filter: "{MIHOMO_APPROVED_US_FILTER}"''',
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("美国" in item.message for item in findings))

    def test_mihomo_rejects_use_of_undeclared_provider(self) -> None:
        private_provider = "private-provider-canary"
        path = self.mihomo_profile(
            self.overseas_policy_lines() + self.performance_policy_lines(),
            group_block=f'''  - name: US-AUTO
    type: url-test
    use: [{private_provider}]
    filter: "{MIHOMO_APPROVED_US_FILTER}"''',
        )

        findings = validate_profile(path, self.root)
        rendered = " ".join(
            f"{item.message} {item.remediation}" for item in findings
        )

        self.assertTrue(any("美国" in item.message for item in findings))
        self.assertNotIn(private_provider, rendered)

    def test_mihomo_rejects_empty_item_in_use_block(self) -> None:
        path = self.mihomo_profile(
            self.overseas_policy_lines() + self.performance_policy_lines(),
            group_block=f'''  - name: US-AUTO
    type: url-test
    use:
      - provider_a
      -
    filter: "{MIHOMO_APPROVED_US_FILTER}"''',
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("美国" in item.message for item in findings))

    def test_mihomo_accepts_declared_provider_in_use_block(self) -> None:
        path = self.mihomo_profile(
            self.overseas_policy_lines() + self.performance_policy_lines(),
            group_block=f'''  - name: US-AUTO
    type: url-test
    use:
      - provider_a
    filter: "{MIHOMO_APPROVED_US_FILTER}"''',
        )

        self.assertEqual(validate_profile(path, self.root), [])

    def test_mihomo_accepts_truthy_include_all_as_source(self) -> None:
        path = self.mihomo_profile(
            self.overseas_policy_lines() + self.performance_policy_lines(),
            group_block=f'''  - name: US-AUTO
    type: url-test
    include-all: true
    filter: "{MIHOMO_APPROVED_US_FILTER}"''',
        )

        self.assertEqual(validate_profile(path, self.root), [])

    def test_mihomo_rejects_false_include_all_source(self) -> None:
        path = self.mihomo_profile(
            self.overseas_policy_lines() + self.performance_policy_lines(),
            group_block=f'''  - name: US-AUTO
    type: url-test
    include-all: false
    filter: "{MIHOMO_APPROVED_US_FILTER}"''',
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("美国" in item.message for item in findings))

    def test_mihomo_rejects_explicit_non_us_group_member(self) -> None:
        path = self.mihomo_profile(
            self.overseas_policy_lines() + self.performance_policy_lines(),
            group_block=f'''  - name: US-AUTO
    type: url-test
    use: [provider_a]
    proxies: [CA-NODE]
    filter: "{MIHOMO_APPROVED_US_FILTER}"''',
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("美国" in item.message for item in findings))

    def test_mihomo_accepts_defined_us_group(self) -> None:
        path = self.mihomo_profile(
            self.overseas_policy_lines() + self.performance_policy_lines()
        )

        self.assertEqual(validate_profile(path, self.root), [])

    def test_mihomo_accepts_us_group_through_select_wrapper(self) -> None:
        path = self.mihomo_profile(
            self.overseas_policy_lines() + self.performance_policy_lines(),
            ai_target="US-WRAPPER",
            group_block=f'''  - name: US-WRAPPER
    type: select
    proxies:
      - US-LEAF
  - name: US-LEAF
    type: url-test
    use: [provider_a]
    filter: "{MIHOMO_APPROVED_US_FILTER}"''',
        )

        self.assertEqual(validate_profile(path, self.root), [])

    def test_mihomo_rejects_cyclic_us_group_wrappers(self) -> None:
        path = self.mihomo_profile(
            self.overseas_policy_lines() + self.performance_policy_lines(),
            ai_target="US-CYCLE",
            group_block="""  - name: US-CYCLE
    type: select
    proxies: [CYCLE-NEXT]
  - name: CYCLE-NEXT
    type: select
    proxies: [US-CYCLE]""",
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("美国" in item.message for item in findings))

    def test_mihomo_rejects_excessively_deep_us_group_wrappers(self) -> None:
        groups = []
        for index in range(40):
            groups.extend(
                [
                    f"  - name: US-WRAPPER-{index}",
                    "    type: select",
                    f"    proxies: [US-WRAPPER-{index + 1}]",
                ]
            )
        groups.extend(
            [
                "  - name: US-WRAPPER-40",
                "    type: url-test",
                "    use: [provider_a]",
                '    filter: "(?i)🇺🇸|美国|united states|\\bus\\b"',
            ]
        )
        path = self.mihomo_profile(
            self.overseas_policy_lines() + self.performance_policy_lines(),
            ai_target="US-WRAPPER-0",
            group_block="\n".join(groups),
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("美国" in item.message for item in findings))

    def test_mihomo_rejects_untrusted_canonical_ai_urls(self) -> None:
        valid_path = "/dist/mihomo/classical/region/us/ai_us.yaml"
        invalid_urls = {
            "http": f"http://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main{valid_path}",
            "forged-origin": f"https://rules.invalid/vtgpcmsvgs/rulemesh/main{valid_path}",
            "wrong-repository": f"https://raw.githubusercontent.com/vtgpcmsvgs/not-rulemesh/main{valid_path}",
            "wrong-ref": f"https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/dev{valid_path}",
            "query": f"{PUBLIC_RAW_ROOT}{valid_path}?mirror=1",
            "fragment": f"{PUBLIC_RAW_ROOT}{valid_path}#mirror",
            "empty-query": f"{PUBLIC_RAW_ROOT}{valid_path}?",
            "empty-fragment": f"{PUBLIC_RAW_ROOT}{valid_path}#",
            "yml-suffix": (
                f"{PUBLIC_RAW_ROOT}/dist/mihomo/classical/region/us/ai_us.yml"
            ),
        }
        for label, ai_url in invalid_urls.items():
            with self.subTest(label=label):
                path = self.mihomo_profile(
                    self.overseas_policy_lines() + self.performance_policy_lines(),
                    ai_url=ai_url,
                )

                findings = validate_profile(path, self.root)

                self.assertTrue(
                    any("region/us/ai_us" in item.message for item in findings)
                )

    def test_mihomo_rejects_untrusted_us_cross_check_url(self) -> None:
        path = self.mihomo_profile(
            self.overseas_policy_lines() + self.performance_policy_lines(),
            other_us_url=(
                "https://rules.invalid/vtgpcmsvgs/rulemesh/main/"
                "dist/mihomo/classical/region/us/google_us.yaml"
            ),
            pure_ip_url=(
                f"{PUBLIC_RAW_ROOT}/dist/mihomo/classical/region/us/missing.yaml"
            ),
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("美国" in item.message for item in findings))

    def test_mihomo_rejects_untrusted_performance_artifact_url(self) -> None:
        path = self.mihomo_profile(
            self.overseas_policy_lines() + self.performance_policy_lines(),
            performance_url=(
                "https://rules.invalid/vtgpcmsvgs/rulemesh/main/"
                "dist/surge/dns/cn_performance_dns_domains.list"
            ),
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("性能型中国 DNS provider" in item.message for item in findings))

    def test_mihomo_rejects_different_us_cross_check_target(self) -> None:
        path = self.mihomo_profile(
            self.overseas_policy_lines() + self.performance_policy_lines(),
            other_us_target="OTHER-US",
            group_block="""  - name: US-AUTO
    type: url-test
    use: [provider_a]
    filter: "(?i)🇺🇸|美国|united states|\\bus\\b"
  - name: OTHER-US
    type: url-test
    use: [provider_a]
    filter: "(?i)🇺🇸|美国|united states|\\bus\\b"
  - name: AUTO
    type: url-test
    use: [provider_a]
    filter: "(?i)香港|\\bhk\\b|美国|\\bus\\b""",
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
            f"RULE-SET,{PUBLIC_RAW_ROOT}/dist/surge/rules/proxy/missing.list,PROXY",
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
            f"RULE-SET,{PUBLIC_RAW_ROOT}/dist/surge/rules/"
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
            f"    url: {PUBLIC_RAW_ROOT}/dist/mihomo/classical/"
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
DOMAIN-SET:https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/dns/cn_performance_dns_domains.list = server:https://dns.alidns.com/dns-query
""",
        )

        findings = validate_profile(path, self.root)

        self.assertTrue(any("工作白名单" in item.message for item in findings))


if __name__ == "__main__":
    unittest.main()
