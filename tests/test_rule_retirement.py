"""业务撤销必须清理依赖图；网站访问与购买的代理端点分别核对。"""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_rules
import sync_upstream_rules as sync


class RuleRetirementTests(unittest.TestCase):
    def test_gfw_refresh_preserves_webshare_website(self):
        item = next(item for item in sync.UPSTREAM_FILES if item.path == Path("loyalsoldier/gfw.txt"))
        payload = ".webshare.io\n.example.com\n"
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.object(sync, "UPSTREAM_ROOT", Path(temp)), mock.patch.object(sync, "fetch_text", return_value=payload):
                failures = []
                self.assertEqual(sync.sync_one(item, failures), (True, False))
                self.assertEqual(failures, [])
                text = (Path(temp) / item.path).read_text("utf-8")
        self.assertEqual(text, payload)

    def test_webshare_survives_residential_and_general_gfw_builds(self):
        for relative in ("region/multi/residential_proxy.list", "proxy/gfw.list", "proxy/gfw_precise.list"):
            result = build_rules.build_source(ROOT / "rules" / relative)
            self.assertIn("DOMAIN-SUFFIX,webshare.io", result.outputs["surge_rules"], relative)
        source = ROOT / "rules/region/multi/residential_proxy.list"
        self.assertEqual(sum(s.startswith("DOMAIN-SUFFIX,") for s in source.read_text("utf-8").splitlines()), 25)

    def test_deleted_asset_families_cannot_be_republished(self):
        forbidden = ("adspower", "ips5_direct", "alibaba_hk", "aws_ipv4", "chain_socks5", "onepassword_proxy", "polygon_rpc_proxy", "bsc_rpc_proxy")
        for source in build_rules.iter_source_files():
            self.assertFalse(any(token in str(source).lower() for token in forbidden), source.name)
        for relative in ("rules/app/adspower.txt", "tools/sync_adspower_rules.py", "rules/upstream/aws", "rules/upstream/blackmatrix7/alibaba.list", "rules/upstream/blackmatrix7/xianyu.list"):
            path = ROOT / relative
            self.assertFalse(path.is_file() or (path.is_dir() and any(path.iterdir())), relative)
        self.assertFalse(hasattr(sync, "AWS_REGION_SNAPSHOTS"))
        self.assertFalse(hasattr(sync, "sync_aws_snapshots"))
        self.assertFalse(hasattr(build_rules, "aws_snapshots_need_sync"))
        self.assertNotIn("aws", [task.name for task in sync.SYNC_TASKS])

    def test_consolidation_preserves_all_official_snapshot_rules(self):
        for destination, components in (
            ("proxy/general_proxy.list", ("proxy/github_core_proxy.list", "upstream/onepassword/core_domains.list")),
            ("region/tw/crypto_tw.list", ("upstream/chainlist/polygon_rpc_domains.list", "upstream/chainlist/bsc_rpc_domains.list")),
        ):
            actual = build_rules.build_source(ROOT / "rules" / destination).outputs
            for component in components:
                expected = build_rules.build_source(ROOT / "rules" / component).outputs
                for client in ("surge_rules", "mihomo_classical"):
                    self.assertTrue(set(expected[client]) <= set(actual[client]), (destination, component, client))

    def test_rpc_route_samples_are_current_snapshot_members(self):
        cases = json.loads((ROOT / "tools/common_route_cases.json").read_text("utf-8"))
        for service, snapshot in (("Polygon RPC", "polygon"), ("BSC RPC", "bsc")):
            sample = next(case for case in cases if case["service"] == service)
            rules = build_rules.build_source(ROOT / f"rules/upstream/chainlist/{snapshot}_rpc_domains.list").outputs["surge_rules"]
            self.assertIn("DOMAIN," + sample["domain"], rules)


if __name__ == "__main__":
    unittest.main()
