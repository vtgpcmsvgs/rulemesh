import inspect
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import sync_upstream_rules  # noqa: E402
import send_upstream_alert  # noqa: E402


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


class BuildOnepasswordRulesTests(unittest.TestCase):
    def test_extracts_only_conservative_core_rules(self) -> None:
        raw_text = """
        <html>
          <body>
            *.1password.com
            *.1password.ca
            *.1password.eu
            *.1passwordservices.com
            *.1passwordusercontent.com
            *.1passwordusercontent.ca
            *.1passwordusercontent.eu
            app-updates.agilebits.com
            app-updates.us.svc.1infra.net
            *.1infra.net
            cache.agilebits.com
            api.pwnedpasswords.com
            accounts.brex.com
          </body>
        </html>
        """

        rules = sync_upstream_rules.build_onepassword_core_rules(raw_text)

        self.assertEqual(
            rules,
            [
                "DOMAIN-SUFFIX,1password.com",
                "DOMAIN-SUFFIX,1password.ca",
                "DOMAIN-SUFFIX,1password.eu",
                "DOMAIN-SUFFIX,1passwordservices.com",
                "DOMAIN-SUFFIX,1passwordusercontent.com",
                "DOMAIN-SUFFIX,1passwordusercontent.ca",
                "DOMAIN-SUFFIX,1passwordusercontent.eu",
                "DOMAIN,app-updates.agilebits.com",
                "DOMAIN-SUFFIX,1infra.net",
                "DOMAIN,cache.agilebits.com",
            ],
        )

    def test_raises_when_required_core_rules_are_missing(self) -> None:
        with self.assertRaises(ValueError) as context:
            sync_upstream_rules.build_onepassword_core_rules("*.1password.com")

        self.assertIn("1Password 官方页面缺少核心域名", str(context.exception))


class BuildOnepasswordSnapshotTextTests(unittest.TestCase):
    def test_uses_expected_headers(self) -> None:
        text = sync_upstream_rules.build_onepassword_snapshot_text(
            [
                "DOMAIN-SUFFIX,1password.com",
                "DOMAIN-SUFFIX,1passwordservices.com",
                "DOMAIN-SUFFIX,1passwordusercontent.com",
                "DOMAIN,app-updates.agilebits.com",
                "DOMAIN-SUFFIX,1infra.net",
                "DOMAIN,cache.agilebits.com",
            ]
        )

        self.assertIn(sync_upstream_rules.ONEPASSWORD_PORTS_DOMAINS_URL, text)
        self.assertIn(sync_upstream_rules.ONEPASSWORD_CORE_TITLE, text)
        self.assertIn("不自动并入 Watchtower、Fastmail、Brex、Privacy Cards", text)
        self.assertIn("DOMAIN-SUFFIX,1password.com", text)


class ChainlistRpcHelpersTests(unittest.TestCase):
    def test_normalize_chainlist_rpc_host_strips_path_query_and_port(self) -> None:
        self.assertEqual(
            sync_upstream_rules.normalize_chainlist_rpc_host(
                "https://api-polygon-mainnet-full.n.dwellir.com/2ccf/demo?token=1"
            ),
            "api-polygon-mainnet-full.n.dwellir.com",
        )
        self.assertEqual(
            sync_upstream_rules.normalize_chainlist_rpc_host("wss://bsc-rpc.publicnode.com:443/ws"),
            "bsc-rpc.publicnode.com",
        )
        self.assertIsNone(
            sync_upstream_rules.normalize_chainlist_rpc_host("ftp://example.com/archive")
        )

    def test_extract_chainlist_rpc_hosts_filters_and_dedupes(self) -> None:
        payload = [
            {
                "chainId": 137,
                "rpc": [
                    {"url": "https://polygon-rpc.com"},
                    {"url": "wss://polygon-rpc.com/ws"},
                    {"url": "https://1rpc.io/matic"},
                    {"url": "https://api.zan.top/polygon-mainnet"},
                ],
            },
            {
                "chainId": 56,
                "rpc": [
                    {"url": "https://bsc-dataseed.bnbchain.org"},
                ],
            },
        ]

        hosts = sync_upstream_rules.extract_chainlist_rpc_hosts(payload, 137)

        self.assertEqual(
            hosts,
            [
                "polygon-rpc.com",
                "1rpc.io",
                "api.zan.top",
            ],
        )

    def test_merge_chainlist_rpc_hosts_keeps_existing_and_manual_hosts(self) -> None:
        merged = sync_upstream_rules.merge_chainlist_rpc_hosts(
            current_hosts=["polygon-rpc.com", "rpc.sentio.xyz"],
            existing_hosts=["lb.drpc.live"],
            preserve_hosts=("polygon.llamarpc.com",),
        )

        self.assertEqual(
            merged,
            [
                "lb.drpc.live",
                "polygon-rpc.com",
                "polygon.llamarpc.com",
                "rpc.sentio.xyz",
            ],
        )


class BuildChainlistRpcSnapshotTextTests(unittest.TestCase):
    def test_uses_expected_headers(self) -> None:
        snapshot = sync_upstream_rules.CHAINLIST_RPC_SNAPSHOTS[0]

        text = sync_upstream_rules.build_chainlist_rpc_snapshot_text(
            snapshot,
            current_hosts=["polygon-rpc.com", "rpc.sentio.xyz"],
            cumulative_hosts=["lb.drpc.live", "polygon-rpc.com", "rpc.sentio.xyz"],
        )

        self.assertIn(sync_upstream_rules.CHAINLIST_RPCS_URL, text)
        self.assertIn(sync_upstream_rules.CHAINLIST_REPO_URL, text)
        self.assertIn(snapshot.title, text)
        self.assertIn("只增不减", text)
        self.assertIn("DOMAIN,lb.drpc.live", text)
        self.assertIn("DOMAIN-WILDCARD,*.rpc.sentio.xyz", text)


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


class SyncTaskRegistryTests(unittest.TestCase):
    def test_all_top_level_sync_functions_are_registered_or_explicit_helpers(self) -> None:
        sync_function_names = {
            name
            for name, obj in inspect.getmembers(sync_upstream_rules, inspect.isfunction)
            if name.startswith("sync_")
        }
        registered_names = {task.runner.__name__ for task in sync_upstream_rules.SYNC_TASKS}

        self.assertEqual(
            sync_function_names - sync_upstream_rules.SYNC_HELPER_FUNCTIONS,
            registered_names,
        )


class UpstreamWebhookRequirementTests(unittest.TestCase):
    def test_upstream_webhook_required_respects_truthy_env_values(self) -> None:
        with mock.patch.dict(os.environ, {"RULEMESH_UPSTREAM_ALERT_REQUIRED": "1"}, clear=False):
            self.assertTrue(sync_upstream_rules.upstream_webhook_required())

    def test_ensure_upstream_failure_alerts_sent_raises_when_required_but_missing_config(self) -> None:
        failures = [
            sync_upstream_rules.UpstreamFailure(
                source="test",
                resource="demo.txt",
                url="https://example.com/demo.txt",
                category="抓取失败",
                detail="timeout",
            )
        ]

        with mock.patch.dict(os.environ, {"RULEMESH_UPSTREAM_ALERT_REQUIRED": "1"}, clear=False), mock.patch(
            "sync_upstream_rules.resolve_feishu_webhook_config",
            return_value=None,
        ):
            with self.assertRaises(RuntimeError):
                sync_upstream_rules.ensure_upstream_failure_alerts_sent(failures)


class SendUpstreamAlertScriptTests(unittest.TestCase):
    def test_build_heartbeat_message_contains_github_run_url(self) -> None:
        env = {
            "GITHUB_SERVER_URL": "https://github.com",
            "GITHUB_REPOSITORY": "vtgpcmsvgs/rulemesh",
            "GITHUB_RUN_ID": "123456",
            "GITHUB_WORKFLOW": "sync-upstream-rules",
            "GITHUB_EVENT_NAME": "schedule",
            "GITHUB_RUN_ATTEMPT": "2",
            "GITHUB_SHA": "0123456789abcdef",
        }

        with mock.patch.dict(os.environ, env, clear=False):
            message = send_upstream_alert.build_heartbeat_message()

        self.assertIn("RuleMesh upstream webhook 健康检查", message)
        self.assertIn("https://github.com/vtgpcmsvgs/rulemesh/actions/runs/123456", message)
        self.assertIn("提交: 0123456789ab", message)


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

    def test_sync_alicloud_snapshots_records_missing_credentials(self) -> None:
        failures: list[sync_upstream_rules.UpstreamFailure] = []

        with mock.patch(
            "sync_upstream_rules.resolve_alicloud_credentials",
            return_value=None,
        ):
            changed, failed = sync_upstream_rules.sync_alicloud_snapshots(failures)

        self.assertEqual((changed, failed), (0, len(sync_upstream_rules.ALICLOUD_REGION_SNAPSHOTS)))
        self.assertEqual(len(failures), len(sync_upstream_rules.ALICLOUD_REGION_SNAPSHOTS))
        self.assertEqual(failures[0].category, "缺少凭据")
        self.assertEqual(failures[0].resource, "alicloud/hk_ipv4.txt")


if __name__ == "__main__":
    unittest.main()
