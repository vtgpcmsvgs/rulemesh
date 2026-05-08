import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import check_dns_safety  # noqa: E402


class DnsSafetyTests(unittest.TestCase):
    def write_temp(self, name: str, content: str) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_surge_rejects_domestic_global_dns_combo(self) -> None:
        path = self.write_temp(
            "surge-public.conf",
            """[General]
use-local-host-item-for-proxy = false
dns-server = system, 223.5.5.5, 119.29.29.29
encrypted-dns-server = https://dns.alidns.com/dns-query, https://doh.pub/dns-query

[Host]
raw.githubusercontent.com = server:system
""",
        )

        findings = check_dns_safety.validate_path(path)

        self.assertTrue(any("223.5.5.5" in finding.message for finding in findings))
        self.assertTrue(any("dns-server" in finding.message for finding in findings))
        self.assertTrue(any("proxy-node-domains" in finding.message for finding in findings))

    def test_surge_accepts_overseas_global_dns_and_node_host_set(self) -> None:
        path = self.write_temp(
            "surge-public.conf",
            """[General]
use-local-host-item-for-proxy = false
dns-server = 1.1.1.1, 8.8.8.8, 9.9.9.9
encrypted-dns-server = https://cloudflare-dns.com/dns-query, https://dns.google/dns-query

[Host]
raw.githubusercontent.com = server:system
DOMAIN-SET:https://example.com/share/file/proxy-node-domains = server:https://dns.alidns.com/dns-query
""",
        )

        self.assertEqual(check_dns_safety.validate_path(path), [])

    def test_surge_rejects_api_file_proxy_node_domains(self) -> None:
        path = self.write_temp(
            "surge-public.conf",
            """[General]
use-local-host-item-for-proxy = false
dns-server = 1.1.1.1, 8.8.8.8, 9.9.9.9
encrypted-dns-server = https://cloudflare-dns.com/dns-query, https://dns.google/dns-query

[Host]
raw.githubusercontent.com = server:system
DOMAIN-SET:https://example.com/api/file/proxy-node-domains = server:https://dns.alidns.com/dns-query
""",
        )

        findings = check_dns_safety.validate_path(path)

        self.assertTrue(any("/api/file/" in finding.message for finding in findings))

    def test_surge_rejects_dns_mode_from_other_clients(self) -> None:
        path = self.write_temp(
            "surge-public.conf",
            """[General]
use-local-host-item-for-proxy = false
dns-mode = fake-ip
dns-server = 1.1.1.1, 8.8.8.8, 9.9.9.9
encrypted-dns-server = https://cloudflare-dns.com/dns-query, https://dns.google/dns-query

[Host]
raw.githubusercontent.com = server:system
DOMAIN-SET:https://example.com/share/file/proxy-node-domains = server:https://dns.alidns.com/dns-query
""",
        )

        findings = check_dns_safety.validate_path(path)

        self.assertTrue(any("dns-mode" in finding.message for finding in findings))

    def test_mihomo_rejects_domestic_business_nameserver(self) -> None:
        path = self.write_temp(
            "mihomo-public.yaml",
            """dns:
  enable: true
  nameserver:
    - https://dns.alidns.com/dns-query
proxy-providers: {}
""",
        )

        findings = check_dns_safety.validate_path(path)

        self.assertTrue(any("dns.nameserver" in finding.message for finding in findings))
        self.assertTrue(any("proxy-server-nameserver" in finding.message for finding in findings))

    def test_mihomo_accepts_domestic_bootstrap_exceptions(self) -> None:
        path = self.write_temp(
            "mihomo-public.yaml",
            """dns:
  enable: true
  default-nameserver:
    - 223.5.5.5
    - 119.29.29.29
  nameserver:
    - https://cloudflare-dns.com/dns-query
    - https://dns.google/dns-query
  proxy-server-nameserver:
    - https://dns.alidns.com/dns-query
    - https://doh.pub/dns-query
proxy-providers: {}
""",
        )

        self.assertEqual(check_dns_safety.validate_path(path), [])

    def test_mihomo_accepts_cn_dns_domain_policy(self) -> None:
        path = self.write_temp(
            "mihomo-public.yaml",
            """dns:
  enable: true
  default-nameserver:
    - 223.5.5.5
  nameserver:
    - https://cloudflare-dns.com/dns-query
    - https://dns.google/dns-query
  nameserver-policy:
    "rule-set:cn-dns-domains":
      - https://dns.alidns.com/dns-query
      - https://doh.pub/dns-query
  proxy-server-nameserver:
    - https://dns.alidns.com/dns-query
proxy-providers: {}
""",
        )

        self.assertEqual(check_dns_safety.validate_path(path), [])

    def test_mihomo_rejects_surge_host_mixing(self) -> None:
        path = self.write_temp(
            "mihomo-public.yaml",
            """dns:
  enable: true
  nameserver:
    - https://cloudflare-dns.com/dns-query
  proxy-server-nameserver:
    - https://dns.alidns.com/dns-query
[Host]
DOMAIN-SET:https://example.com/share/file/proxy-node-domains = server:https://dns.alidns.com/dns-query
proxy-providers: {}
""",
        )

        findings = check_dns_safety.validate_path(path)

        self.assertTrue(any("[Host]" in finding.message for finding in findings))

    def test_private_mihomo_accepts_single_dns_truth_baseline(self) -> None:
        path = self.write_temp(
            "rulemesh-substore-mihomo-clash-verge.yaml",
            """ipv6: false
dns:
  enable: true
  ipv6: false
  use-hosts: false
  use-system-hosts: false
  respect-rules: false
  default-nameserver:
    - 223.5.5.5
    - 119.29.29.29
  nameserver:
    - https://cloudflare-dns.com/dns-query
    - https://dns.google/dns-query
proxy-providers: {}
proxy-groups:
  - name: auto
    type: url-test
    url: "https://www.google.com/generate_204"
""",
        )

        self.assertEqual(check_dns_safety.validate_path(path), [])

    def test_private_mihomo_rejects_layered_dns_fields(self) -> None:
        path = self.write_temp(
            "rulemesh-substore-mihomo-clash-meta.yaml",
            """ipv6: false
dns:
  enable: true
  ipv6: false
  use-hosts: false
  use-system-hosts: false
  respect-rules: true
  default-nameserver:
    - 223.5.5.5
  nameserver:
    - https://cloudflare-dns.com/dns-query
  proxy-server-nameserver:
    - https://dns.alidns.com/dns-query
proxy-providers: {}
""",
        )

        findings = check_dns_safety.validate_path(path)

        self.assertTrue(any("respect-rules" in finding.message for finding in findings))
        self.assertTrue(any("proxy-server-nameserver" in finding.message for finding in findings))

    def test_private_mihomo_rejects_http_generate_204(self) -> None:
        path = self.write_temp(
            "rulemesh-substore-mihomo-clash-verge.yaml",
            """ipv6: false
dns:
  enable: true
  ipv6: false
  use-hosts: false
  use-system-hosts: false
  respect-rules: false
  default-nameserver:
    - 223.5.5.5
  nameserver:
    - https://cloudflare-dns.com/dns-query
proxy-providers:
  sample:
    health-check:
      enable: true
      url: "http://www.google.com/generate_204"
""",
        )

        findings = check_dns_safety.validate_path(path)

        self.assertTrue(any("generate_204" in finding.message for finding in findings))


if __name__ == "__main__":
    unittest.main()