import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import validate_surge_test_urls  # noqa: E402


class ValidateSurgeTestUrlsTests(unittest.TestCase):
    def write_profile(self, content: str) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "sample.conf"
        path.write_text(content, encoding="utf-8")
        return path

    def test_accepts_http_testing_urls(self) -> None:
        path = self.write_profile(
            "[General]\n"
            "internet-test-url = http://www.baidu.com\n"
            "proxy-test-url = http://www.google.com/generate_204\n"
            "\n"
            "[Proxy Group]\n"
            "AUTO = url-test, policy-path=https://example.com/sub, url=http://www.gstatic.com/generate_204\n"
            "\n"
            "[Proxy]\n"
            "HK = trojan, example.com, 443, test-url=http://www.google.com/generate_204\n"
        )

        self.assertEqual(validate_surge_test_urls.validate_surge_profile(path), [])

    def test_rejects_https_general_test_urls(self) -> None:
        path = self.write_profile(
            "[General]\n"
            "internet-test-url = https://www.baidu.com\n"
            "proxy-test-url = https://www.google.com/generate_204\n"
        )

        findings = validate_surge_test_urls.validate_surge_profile(path)
        self.assertEqual(len(findings), 2)
        self.assertTrue(any("internet-test-url" in finding for finding in findings))
        self.assertTrue(any("proxy-test-url" in finding for finding in findings))

    def test_rejects_https_url_parameter_in_url_test_group(self) -> None:
        path = self.write_profile(
            "[Proxy Group]\n"
            "AUTO = url-test, policy-path=https://example.com/sub, url=https://www.gstatic.com/generate_204\n"
        )

        findings = validate_surge_test_urls.validate_surge_profile(path)
        self.assertEqual(len(findings), 1)
        self.assertIn("url-test", findings[0])

    def test_rejects_https_test_url_parameter(self) -> None:
        path = self.write_profile(
            "[Proxy]\n"
            "HK = trojan, example.com, 443, test-url=https://www.google.com/generate_204\n"
        )

        findings = validate_surge_test_urls.validate_surge_profile(path)
        self.assertEqual(len(findings), 1)
        self.assertIn("test-url", findings[0])

    def test_rejects_url_without_http_scheme(self) -> None:
        path = self.write_profile(
            "[Proxy Group]\n"
            "AUTO = url-test, policy-path=https://example.com/sub, url=www.gstatic.com/generate_204\n"
        )

        findings = validate_surge_test_urls.validate_surge_profile(path)
        self.assertEqual(len(findings), 1)
        self.assertIn("url-test", findings[0])

    def test_ignores_other_https_resource_urls(self) -> None:
        path = self.write_profile(
            "[General]\n"
            "geoip-maxmind-url = https://example.com/country.mmdb\n"
            "\n"
            "[Proxy Group]\n"
            "AUTO = select, policy-path=https://example.com/sub\n"
            "\n"
            "[Rule]\n"
            "RULE-SET,https://example.com/rules.list,DIRECT\n"
        )

        self.assertEqual(validate_surge_test_urls.validate_surge_profile(path), [])


if __name__ == "__main__":
    unittest.main()
