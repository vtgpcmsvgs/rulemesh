import sys
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import sync_upstream_rules  # noqa: E402


class BuildAwsSnapshotTextTests(unittest.TestCase):
    def test_uses_chinese_headers(self) -> None:
        payload = {
            "syncToken": "123",
            "createDate": "2026-03-22-00-00-00",
            "prefixes": [
                {"region": "ap-east-1", "ip_prefix": "203.0.113.0/24"},
            ],
        }
        snapshot = sync_upstream_rules.AWS_REGION_SNAPSHOTS[0]

        text = sync_upstream_rules.build_aws_snapshot_text(payload, snapshot)

        self.assertIn("# 来源: https://ip-ranges.amazonaws.com/ip-ranges.json", text)
        self.assertIn("# 标题: AWS 香港 IPv4（ap-east-1）", text)
        self.assertIn("# 范围: 所选 AWS 区域公开发布的全部 IPv4 前缀。", text)


class BuildAlicloudSnapshotTextTests(unittest.TestCase):
    def test_uses_chinese_headers(self) -> None:
        payload = {
            "publicIpAddress": ["203.0.113.0/24"],
            "syncedAt": "2026-03-22T00:00:00+00:00",
            "reportedTotalCount": 1,
            "pageCount": 1,
        }
        snapshot = sync_upstream_rules.ALICLOUD_REGION_SNAPSHOTS[0]

        ipv4_text = sync_upstream_rules.build_alicloud_snapshot_text(payload, snapshot)
        ssh_text = sync_upstream_rules.build_alicloud_ssh_snapshot_text(payload, snapshot)

        self.assertIn("# 标题: 阿里云香港 IPv4（cn-hongkong）", ipv4_text)
        self.assertIn("# 范围: 官方阿里云 API 返回的全部 VPC 公网 IPv4 CIDR 前缀。", ipv4_text)
        self.assertIn("# 标题: 阿里云香港 IPv4（cn-hongkong） SSH TCP/22 直连规则", ssh_text)
        self.assertIn("# 派生自: alicloud/hk_ipv4.txt", ssh_text)


if __name__ == "__main__":
    unittest.main()
