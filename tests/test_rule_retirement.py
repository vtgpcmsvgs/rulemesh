"""业务撤销后，上游同步与构建不得恢复已删除的规则。"""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_rules
import sync_upstream_rules as sync


class RuleRetirementTests(unittest.TestCase):
    def test_gfw_refresh_cannot_restore_webshare_or_remove_similar_domains(self):
        item = next(item for item in sync.UPSTREAM_FILES if item.path == Path("loyalsoldier/gfw.txt"))
        payload = (
            ".webshare.io\napi.webshare.io\nDOMAIN-SUFFIX,WebShare.IO\n"
            "DOMAIN,app.webshare.io\n.webshare.io.example.org\n.notwebshare.io\n.example.com\n"
        )
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.object(sync, "UPSTREAM_ROOT", Path(temp)), mock.patch.object(sync, "fetch_text", return_value=payload):
                failures = []
                self.assertEqual(sync.sync_one(item, failures), (True, False))
                self.assertEqual(failures, [])
                text = (Path(temp) / item.path).read_text("utf-8")
        self.assertEqual(text, ".webshare.io.example.org\n.notwebshare.io\n.example.com\n")

    def test_remaining_source_graph_does_not_publish_retired_businesses(self):
        sources = build_rules.iter_source_files()
        self.assertFalse(any("adspower" in str(path).lower() for path in sources))
        for relative in ("rules/app/adspower.txt", "tools/sync_adspower_rules.py"):
            self.assertFalse((ROOT / relative).exists(), relative)
        for relative in ("region/multi/residential_proxy.list", "proxy/gfw.list", "proxy/gfw_precise.list"):
            result = build_rules.build_source(ROOT / "rules" / relative)
            for output in result.outputs.values():
                self.assertFalse(any("webshare.io" in rule.lower() for rule in output), relative)


if __name__ == "__main__":
    unittest.main()
