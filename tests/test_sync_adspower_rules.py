import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import sync_adspower_rules  # noqa: E402


class SyncAdsPowerRulesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.repo_root = Path(self.temp_dir.name)
        self.rules_root = self.repo_root / "rules"
        (self.rules_root / "app").mkdir(parents=True, exist_ok=True)

    def write_manifest(self, content: str) -> Path:
        path = self.rules_root / "app" / "adspower.txt"
        path.write_text(content, encoding="utf-8")
        return path

    def test_sync_generates_three_rule_files(self) -> None:
        self.write_manifest(
            "# AdsPower 主清单\n"
            "\n"
            "[reject]\n"
            "# 拒绝规则\n"
            "DOMAIN,sentry.adspower.com\n"
            "DOMAIN,sentry.adspower.net\n"
            "\n"
            "[proxy]\n"
            "# 代理规则\n"
            "DOMAIN,api-global.adspower.com\n"
            "DOMAIN,api-global.adspower.net\n"
            "\n"
            "[direct]\n"
            "# 直连规则\n"
            "DOMAIN,check.adspower.com\n"
            "DOMAIN,check.adspower.net\n"
        )

        result = sync_adspower_rules.sync_adspower_rules(self.repo_root, self.rules_root)

        self.assertEqual(
            result.rule_counts,
            {"reject": 2, "proxy": 2, "direct": 2},
        )
        reject_text = (self.rules_root / "reject" / "adspower_reject.list").read_text(
            encoding="utf-8"
        )
        proxy_text = (self.rules_root / "proxy" / "adspower_proxy.list").read_text(
            encoding="utf-8"
        )
        direct_text = (self.rules_root / "direct" / "adspower_direct.list").read_text(
            encoding="utf-8"
        )

        self.assertIn("生成来源：rules/app/adspower.txt", reject_text)
        self.assertIn("DOMAIN,sentry.adspower.com", reject_text)
        self.assertIn("DOMAIN,api-global.adspower.net", proxy_text)
        self.assertIn("DOMAIN,check.adspower.net", direct_text)

    def test_missing_counterpart_raises_error(self) -> None:
        self.write_manifest(
            "[reject]\n"
            "DOMAIN,sentry.adspower.com\n"
            "\n"
            "[proxy]\n"
            "DOMAIN,api-global.adspower.com\n"
            "DOMAIN,api-global.adspower.net\n"
            "\n"
            "[direct]\n"
            "DOMAIN,check.adspower.com\n"
            "DOMAIN,check.adspower.net\n"
        )

        with self.assertRaises(sync_adspower_rules.AdspowerSyncError) as context:
            sync_adspower_rules.sync_adspower_rules(self.repo_root, self.rules_root)

        self.assertIn("缺少镜像规则", str(context.exception))

    def test_manifest_rule_must_not_contain_action_field(self) -> None:
        self.write_manifest(
            "[reject]\n"
            "DOMAIN,sentry.adspower.com,REJECT\n"
            "DOMAIN,sentry.adspower.net\n"
            "\n"
            "[proxy]\n"
            "DOMAIN,api-global.adspower.com\n"
            "DOMAIN,api-global.adspower.net\n"
            "\n"
            "[direct]\n"
            "DOMAIN,check.adspower.com\n"
            "DOMAIN,check.adspower.net\n"
        )

        with self.assertRaises(sync_adspower_rules.AdspowerSyncError) as context:
            sync_adspower_rules.sync_adspower_rules(self.repo_root, self.rules_root)

        self.assertIn("不要在主清单里写动作字段", str(context.exception))


if __name__ == "__main__":
    unittest.main()
