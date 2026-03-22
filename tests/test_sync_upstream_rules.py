import json
import sys
import unittest
from pathlib import Path
from unittest import mock


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import sync_upstream_rules  # noqa: E402


class BuildAwsSnapshotTextTests(unittest.TestCase):
    def test_uses_expected_headers(self) -> None:
        payload = {
            "syncToken": "123",
            "createDate": "2026-03-22-00-00-00",
            "prefixes": [
                {"region": "ap-east-1", "ip_prefix": "203.0.113.0/24"},
            ],
        }
        snapshot = sync_upstream_rules.AWS_REGION_SNAPSHOTS[0]

        text = sync_upstream_rules.build_aws_snapshot_text(payload, snapshot)

        self.assertIn(sync_upstream_rules.AWS_IP_RANGES_URL, text)
        self.assertIn(snapshot.title, text)
        self.assertIn("203.0.113.0/24", text)
        self.assertIn("123", text)


class BuildAlicloudSnapshotTextTests(unittest.TestCase):
    def test_uses_expected_headers(self) -> None:
        payload = {
            "publicIpAddress": ["203.0.113.0/24"],
            "syncedAt": "2026-03-22T00:00:00+00:00",
            "reportedTotalCount": 1,
            "pageCount": 1,
        }
        snapshot = sync_upstream_rules.ALICLOUD_REGION_SNAPSHOTS[0]

        ipv4_text = sync_upstream_rules.build_alicloud_snapshot_text(payload, snapshot)
        ssh_text = sync_upstream_rules.build_alicloud_ssh_snapshot_text(payload, snapshot)

        self.assertIn(sync_upstream_rules.ALICLOUD_PUBLIC_IP_DOC_URL, ipv4_text)
        self.assertIn(sync_upstream_rules.ALICLOUD_VPC_ENDPOINT_DOC_URL, ipv4_text)
        self.assertIn(snapshot.title, ipv4_text)
        self.assertIn("203.0.113.0/24", ipv4_text)
        self.assertIn(f"{snapshot.title} SSH TCP/22", ssh_text)
        self.assertIn("AND,((IP-CIDR,203.0.113.0/24),(DST-PORT,22))", ssh_text)
        self.assertIn("alicloud/hk_ipv4.txt", ssh_text)


class FeishuWebhookTests(unittest.TestCase):
    def test_build_feishu_sign_uses_expected_algorithm(self) -> None:
        sign = sync_upstream_rules.build_feishu_sign("1711100000", "test-secret")
        self.assertEqual(sign, "XgBUpHOwFC8S5KJUwT7uVEAER3Md1o7vU5yOID9EK/A=")

    def test_send_feishu_webhook_message_posts_signed_payload(self) -> None:
        config = sync_upstream_rules.FeishuWebhookConfig(
            url="https://example.com/hook",
            secret="test-secret",
        )

        response = mock.MagicMock()
        response.read.return_value = b'{"code":0,"msg":"success"}'
        urlopen_result = mock.MagicMock()
        urlopen_result.__enter__.return_value = response
        urlopen_result.__exit__.return_value = None

        with mock.patch("sync_upstream_rules.urllib.request.urlopen", return_value=urlopen_result) as mocked:
            sync_upstream_rules.send_feishu_webhook_message(
                config,
                "upstream failed",
                timestamp="1711100000",
            )

        request = mocked.call_args.args[0]
        self.assertEqual(request.full_url, "https://example.com/hook")
        self.assertEqual(
            json.loads(request.data.decode("utf-8")),
            {
                "timestamp": "1711100000",
                "sign": "XgBUpHOwFC8S5KJUwT7uVEAER3Md1o7vU5yOID9EK/A=",
                "msg_type": "text",
                "content": {"text": "upstream failed"},
            },
        )


class SyncFailureTests(unittest.TestCase):
    def test_sync_one_records_empty_upstream_content(self) -> None:
        failures: list[sync_upstream_rules.UpstreamFailure] = []
        item = sync_upstream_rules.UpstreamFile(
            Path("example/test.list"),
            "https://example.com/test.list",
        )

        with mock.patch("sync_upstream_rules.fetch_text", return_value="\n"), mock.patch(
            "sync_upstream_rules.write_if_changed"
        ) as mocked_write:
            updated, failed = sync_upstream_rules.sync_one(item, failures)

        self.assertEqual((updated, failed), (False, True))
        mocked_write.assert_not_called()
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0].category, "上游内容为空")
        self.assertEqual(failures[0].resource, "example/test.list")

    def test_sync_alicloud_snapshots_records_auth_failure(self) -> None:
        failures: list[sync_upstream_rules.UpstreamFailure] = []
        credentials = sync_upstream_rules.AlicloudCredentials("ak", "sk")

        with mock.patch(
            "sync_upstream_rules.resolve_alicloud_credentials",
            return_value=credentials,
        ), mock.patch(
            "sync_upstream_rules.fetch_alicloud_region_snapshot",
            side_effect=ValueError("HTTP 403 Forbidden: InvalidAccessKeyId.NotFound"),
        ):
            changed, failed = sync_upstream_rules.sync_alicloud_snapshots(failures)

        self.assertEqual((changed, failed), (0, 1))
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0].category, "鉴权失败")
        self.assertEqual(failures[0].resource, "alicloud/hk_ipv4.txt")


if __name__ == "__main__":
    unittest.main()
