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
use-local-host-item-for-proxy = true
dns-server = system, 223.5.5.5, 119.29.29.29
encrypted-dns-server = https://dns.alidns.com/dns-query, https://doh.pub/dns-query

[Host]
raw.githubusercontent.com = server:system
""",
        )

        findings = check_dns_safety.validate_path(path)

        self.assertTrue(any("高风险组合" in finding.message for finding in findings))
        self.assertTrue(any("全局 dns-server" in finding.message for finding in findings))
        self.assertTrue(any("proxy-node-domains" in finding.message for finding in findings))

    def test_surge_accepts_overseas_global_dns_and_node_host_set(self) -> None:
        path = self.write_temp(
            "surge-public.conf",
            """[General]
use-local-host-item-for-proxy = true
dns-server = 1.1.1.1, 8.8.8.8, 9.9.9.9
encrypted-dns-server = https://cloudflare-dns.com/dns-query, https://dns.google/dns-query

[Host]
raw.githubusercontent.com = server:system
DOMAIN-SET:https://example.com/api/file/proxy-node-domains = server:https://dns.alidns.com/dns-query
""",
        )

        self.assertEqual(check_dns_safety.validate_path(path), [])

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
        self.assertTrue(any("缺少 proxy-server-nameserver" in finding.message for finding in findings))

    def test_mihomo_accepts_proxy_server_nameserver_domestic_exception(self) -> None:
        path = self.write_temp(
            "mihomo-public.yaml",
            """dns:
  enable: true
  default-nameserver:
    - 1.1.1.1
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
DOMAIN-SET:https://example.com/api/file/proxy-node-domains = server:https://dns.alidns.com/dns-query
proxy-providers: {}
""",
        )

        findings = check_dns_safety.validate_path(path)

        self.assertTrue(any("Surge 的 [Host]" in finding.message for finding in findings))


if __name__ == "__main__":
    unittest.main()
