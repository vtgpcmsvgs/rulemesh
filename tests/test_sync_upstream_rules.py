import inspect
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import sync_upstream_rules  # noqa: E402
import send_upstream_alert  # noqa: E402
import build_rules  # noqa: E402


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
        self.assertIn(
            "AND,((IP-CIDR,203.0.113.0/24,no-resolve),(PROTOCOL,TCP),(DST-PORT,22))",
            ssh_text,
        )
        self.assertIn("alicloud/ssh22_ipv4_history.txt", ssh_text)
        self.assertIn(
            "AND,((IP-ASN,45102,no-resolve),(PROTOCOL,TCP),(DST-PORT,22))",
            ssh_text,
        )

    def test_bgp_snapshot_and_history_are_canonical_and_monotonic(self) -> None:
        bgp_payload = {
            "source": {"minPeersSeeing": 1},
            "asns": list(sync_upstream_rules.ALICLOUD_FALLBACK_ASNS),
            "perAsn": [
                {
                    "asn": asn,
                    "reportedPrefixCount": 1,
                    "reportedIpv4PrefixCount": 1,
                    "uniqueIpv4PrefixCount": 1,
                    "collapsedIpv4PrefixCount": 1,
                }
                for asn in sync_upstream_rules.ALICLOUD_FALLBACK_ASNS
            ],
            "collapsedIpv4PrefixCount": 1,
            "uniqueIpv4AddressCount": 512,
            "ipv4Prefix": ["198.51.100.0/23"],
            "syncedAt": "2026-07-13T00:00:00+00:00",
        }
        self.assertEqual(
            sync_upstream_rules.validate_alicloud_bgp_snapshot_payload(bgp_payload),
            ["198.51.100.0/23"],
        )

        merged = sync_upstream_rules.merge_alicloud_ssh_history(
            ["192.0.2.0/24"],
            ["203.0.113.0/24"],
            bgp_payload["ipv4Prefix"],
        )
        self.assertTrue(
            sync_upstream_rules.ipv4_coverage_contains(merged, ["192.0.2.0/24"])
        )
        self.assertTrue(
            sync_upstream_rules.ipv4_coverage_contains(merged, ["203.0.113.0/24"])
        )
        self.assertTrue(
            sync_upstream_rules.ipv4_coverage_contains(
                merged,
                bgp_payload["ipv4Prefix"],
            )
        )


class AlicloudPaginationTests(unittest.TestCase):
    @staticmethod
    def prefix(index: int) -> str:
        return f"203.0.{index // 256}.{index % 256}/32"

    @staticmethod
    def page_payload(page_number: int, total_count: int, prefixes: list[str]) -> dict[str, object]:
        return {
            "Success": True,
            "PageNumber": page_number,
            "PageSize": 100,
            "TotalCount": total_count,
            "RegionId": "cn-hongkong",
            "RequestId": f"request-{page_number}",
            "PublicIpAddress": prefixes,
        }

    def test_duplicate_entry_does_not_end_pagination_early(self) -> None:
        snapshot = sync_upstream_rules.ALICLOUD_REGION_SNAPSHOTS[0]
        credentials = sync_upstream_rules.AlicloudCredentials("ak", "sk")
        pages = {
            1: self.page_payload(1, 204, [self.prefix(index) for index in range(100)]),
            2: self.page_payload(
                2,
                204,
                [self.prefix(index) for index in range(100, 199)] + [self.prefix(150)],
            ),
            3: self.page_payload(3, 204, [self.prefix(index) for index in range(199, 203)]),
        }

        with mock.patch(
            "sync_upstream_rules.alicloud_rpc_get",
            side_effect=lambda _snapshot, _credentials, *, page_number, **_kwargs: pages[page_number],
        ) as mocked_get:
            payload = sync_upstream_rules.fetch_alicloud_region_snapshot(snapshot, credentials)

        self.assertEqual(mocked_get.call_count, 3)
        self.assertEqual(payload["reportedTotalCount"], 204)
        self.assertEqual(payload["fetchedEntryCount"], 204)
        self.assertEqual(payload["duplicateEntryCount"], 1)
        self.assertEqual(payload["uniquePrefixCount"], 203)
        self.assertEqual(payload["uniqueIpv4AddressCount"], 203)
        self.assertEqual(len(payload["publicIpAddress"]), 203)
        self.assertIn(self.prefix(202), payload["publicIpAddress"])

    def test_empty_page_before_total_count_fails_closed(self) -> None:
        snapshot = sync_upstream_rules.ALICLOUD_REGION_SNAPSHOTS[0]
        credentials = sync_upstream_rules.AlicloudCredentials("ak", "sk")
        pages = {
            1: self.page_payload(1, 101, [self.prefix(index) for index in range(100)]),
            2: self.page_payload(2, 101, []),
        }

        with mock.patch(
            "sync_upstream_rules.alicloud_rpc_get",
            side_effect=lambda _snapshot, _credentials, *, page_number, **_kwargs: pages[page_number],
        ):
            with self.assertRaisesRegex(ValueError, "pagination ended early"):
                sync_upstream_rules.fetch_alicloud_region_snapshot(snapshot, credentials)

    def test_total_count_change_fails_closed(self) -> None:
        snapshot = sync_upstream_rules.ALICLOUD_REGION_SNAPSHOTS[0]
        credentials = sync_upstream_rules.AlicloudCredentials("ak", "sk")
        pages = {
            1: self.page_payload(1, 101, [self.prefix(index) for index in range(100)]),
            2: self.page_payload(2, 102, [self.prefix(100)]),
        }

        with mock.patch(
            "sync_upstream_rules.alicloud_rpc_get",
            side_effect=lambda _snapshot, _credentials, *, page_number, **_kwargs: pages[page_number],
        ):
            with self.assertRaisesRegex(ValueError, "TotalCount changed"):
                sync_upstream_rules.fetch_alicloud_region_snapshot(snapshot, credentials)

    def test_snapshot_metadata_must_match_fetched_and_unique_counts(self) -> None:
        snapshot = sync_upstream_rules.ALICLOUD_REGION_SNAPSHOTS[0]
        payload = {
            "regionId": "cn-hongkong",
            "ipVersion": "ipv4",
            "pageSize": 100,
            "pageCount": 1,
            "reportedTotalCount": 3,
            "fetchedEntryCount": 3,
            "duplicateEntryCount": 1,
            "uniquePrefixCount": 2,
            "uniqueIpv4AddressCount": 512,
            "publicIpAddress": ["203.0.113.0/24", "198.51.100.0/24"],
        }

        self.assertEqual(
            sync_upstream_rules.validate_alicloud_snapshot_payload(payload, snapshot),
            ["203.0.113.0/24", "198.51.100.0/24"],
        )

        payload["fetchedEntryCount"] = 2
        with self.assertRaisesRegex(ValueError, "snapshot is incomplete"):
            sync_upstream_rules.validate_alicloud_snapshot_payload(payload, snapshot)

    def test_snapshot_files_must_match_metadata(self) -> None:
        snapshot = sync_upstream_rules.ALICLOUD_REGION_SNAPSHOTS[0]
        payload = {
            "regionId": "cn-hongkong",
            "ipVersion": "ipv4",
            "pageSize": 100,
            "pageCount": 1,
            "reportedTotalCount": 1,
            "fetchedEntryCount": 1,
            "duplicateEntryCount": 0,
            "uniquePrefixCount": 1,
            "uniqueIpv4AddressCount": 256,
            "publicIpAddress": ["203.0.113.0/24"],
            "syncedAt": "2026-07-11T00:00:00+00:00",
        }
        bgp_payload = {
            "source": {"minPeersSeeing": 1},
            "asns": list(sync_upstream_rules.ALICLOUD_FALLBACK_ASNS),
            "perAsn": [
                {
                    "asn": asn,
                    "reportedPrefixCount": 1,
                    "reportedIpv4PrefixCount": 1,
                    "uniqueIpv4PrefixCount": 1,
                    "collapsedIpv4PrefixCount": 1,
                }
                for asn in sync_upstream_rules.ALICLOUD_FALLBACK_ASNS
            ],
            "collapsedIpv4PrefixCount": 1,
            "uniqueIpv4AddressCount": 256,
            "ipv4Prefix": ["198.51.100.0/24"],
            "syncedAt": "2026-07-11T00:00:00+00:00",
        }
        history_prefixes = ["198.51.100.0/24", "203.0.113.0/24"]

        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(
            sync_upstream_rules,
            "UPSTREAM_ROOT",
            Path(temp_dir),
        ):
            metadata_path = Path(temp_dir) / snapshot.metadata_path
            ipv4_path = Path(temp_dir) / snapshot.path
            ssh_path = Path(temp_dir) / snapshot.ssh_path
            bgp_metadata_path = Path(temp_dir) / snapshot.bgp_metadata_path
            bgp_path = Path(temp_dir) / snapshot.bgp_path
            history_path = Path(temp_dir) / snapshot.history_path
            for path in (
                metadata_path,
                ipv4_path,
                ssh_path,
                bgp_metadata_path,
                bgp_path,
                history_path,
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
            metadata_path.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )
            ipv4_path.write_text(
                sync_upstream_rules.build_alicloud_snapshot_text(payload, snapshot),
                encoding="utf-8",
            )
            bgp_metadata_path.write_text(
                json.dumps(bgp_payload, ensure_ascii=False),
                encoding="utf-8",
            )
            bgp_path.write_text(
                sync_upstream_rules.build_alicloud_bgp_snapshot_text(bgp_payload),
                encoding="utf-8",
            )
            history_path.write_text(
                sync_upstream_rules.build_alicloud_history_snapshot_text(
                    payload,
                    bgp_payload,
                    snapshot,
                    history_prefixes,
                ),
                encoding="utf-8",
            )
            ssh_path.write_text(
                sync_upstream_rules.build_alicloud_ssh_snapshot_text(
                    payload,
                    snapshot,
                    history_prefixes=history_prefixes,
                    bgp_payload=bgp_payload,
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                sync_upstream_rules.validate_alicloud_snapshot_files(snapshot),
                payload,
            )
            self.assertFalse(build_rules.alicloud_snapshots_need_sync())

            ssh_path.write_text("# 残缺文件\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "does not match metadata"):
                sync_upstream_rules.validate_alicloud_snapshot_files(snapshot)
            self.assertTrue(build_rules.alicloud_snapshots_need_sync())

    def test_stable_fetch_requires_two_matching_full_snapshots(self) -> None:
        snapshot = sync_upstream_rules.ALICLOUD_REGION_SNAPSHOTS[0]
        credentials = sync_upstream_rules.AlicloudCredentials("ak", "sk")
        first = {
            "reportedTotalCount": 1,
            "fetchedEntryCount": 1,
            "duplicateEntryCount": 0,
            "uniquePrefixCount": 1,
            "uniqueIpv4AddressCount": 256,
            "publicIpAddress": ["203.0.113.0/24"],
        }
        second = {**first, "syncToken": "newer"}

        with mock.patch(
            "sync_upstream_rules.fetch_alicloud_region_snapshot",
            side_effect=[first, second],
        ) as mocked_fetch:
            payload = sync_upstream_rules.fetch_stable_alicloud_region_snapshot(
                snapshot,
                credentials,
            )

        self.assertEqual(mocked_fetch.call_count, 2)
        self.assertEqual(payload, second)

    def test_unstable_full_snapshots_fail_closed(self) -> None:
        snapshot = sync_upstream_rules.ALICLOUD_REGION_SNAPSHOTS[0]
        credentials = sync_upstream_rules.AlicloudCredentials("ak", "sk")
        payloads = [
            {
                "reportedTotalCount": 1,
                "fetchedEntryCount": 1,
                "duplicateEntryCount": 0,
                "uniquePrefixCount": 1,
                "uniqueIpv4AddressCount": 256,
                "publicIpAddress": [f"203.0.{index}.0/24"],
            }
            for index in range(sync_upstream_rules.ALICLOUD_STABILITY_FETCH_ATTEMPTS)
        ]

        with mock.patch(
            "sync_upstream_rules.fetch_alicloud_region_snapshot",
            side_effect=payloads,
        ):
            with self.assertRaisesRegex(ValueError, "consecutive full fetches"):
                sync_upstream_rules.fetch_stable_alicloud_region_snapshot(
                    snapshot,
                    credentials,
                )


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


class GeodataSnapshotTests(unittest.TestCase):
    def test_build_geodata_snapshot_text_contains_rulemesh_mirror(self) -> None:
        text = sync_upstream_rules.build_geodata_snapshot_text()

        self.assertIn(sync_upstream_rules.META_RULES_DAT_REPO_URL, text)
        self.assertIn(sync_upstream_rules.RULEMESH_GEOIP_MIRROR_URL, text)
        self.assertIn(sync_upstream_rules.RULEMESH_GEOIP_RELEASE_TAG, text)
        self.assertIn(sync_upstream_rules.RULEMESH_GEOIP_ASSET_NAME, text)

    def test_validate_meta_rules_dat_readme_requires_known_markers(self) -> None:
        readme_text = "\n".join(sync_upstream_rules.META_RULES_DAT_REQUIRED_MARKERS)

        sync_upstream_rules.validate_meta_rules_dat_readme(readme_text)

        with self.assertRaises(ValueError):
            sync_upstream_rules.validate_meta_rules_dat_readme("missing markers")


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


class AlicloudCredentialResolutionTests(unittest.TestCase):
    def test_resolve_alicloud_credentials_falls_back_to_local_config(self) -> None:
        local_payload = {
            "alicloud": {
                "access_key_id": "local-ak",
                "access_key_secret": "local-sk",
                "security_token": "local-sts",
            }
        }

        with mock.patch.dict(os.environ, {}, clear=True), mock.patch(
            "sync_upstream_rules.load_local_config",
            return_value=local_payload,
        ):
            credentials = sync_upstream_rules.resolve_alicloud_credentials()

        self.assertEqual(
            credentials,
            sync_upstream_rules.AlicloudCredentials(
                access_key_id="local-ak",
                access_key_secret="local-sk",
                security_token="local-sts",
            ),
        )

    def test_http_error_log_does_not_expose_signed_request_details(self) -> None:
        body = json.dumps(
            {
                "Code": "IncompleteSignature",
                "RequestId": "request-id",
                "Message": "server string contains AccessKeyId=private-id&Signature=private-signature",
            }
        ).encode("utf-8")
        error = urllib.error.HTTPError(
            "https://vpc.cn-hongkong.aliyuncs.com/",
            400,
            "Bad Request",
            hdrs=None,
            fp=io.BytesIO(body),
        )

        message = sync_upstream_rules.parse_alicloud_http_error(error)

        self.assertIn("IncompleteSignature", message)
        self.assertIn("request-id", message)
        self.assertNotIn("private-id", message)
        self.assertNotIn("private-signature", message)


class SendUpstreamAlertScriptTests(unittest.TestCase):
    def test_build_workflow_failure_message_contains_step_results_and_run_url(self) -> None:
        env = {
            "GITHUB_SERVER_URL": "https://github.com",
            "GITHUB_REPOSITORY": "vtgpcmsvgs/rulemesh",
            "GITHUB_RUN_ID": "123456",
            "GITHUB_WORKFLOW": "sync-upstream-rules",
            "GITHUB_EVENT_NAME": "schedule",
            "GITHUB_RUN_ATTEMPT": "2",
            "GITHUB_SHA": "0123456789abcdef",
            "GITHUB_JOB": "sync",
            "GITHUB_REF_NAME": "main",
        }

        with mock.patch.dict(os.environ, env, clear=False):
            message = send_upstream_alert.build_workflow_failure_message(
                "checkout_repo=success;sync_upstream=failure"
            )

        self.assertIn("RuleMesh upstream 工作流失败", message)
        self.assertIn("https://github.com/vtgpcmsvgs/rulemesh/actions/runs/123456", message)
        self.assertIn("步骤结果: checkout_repo=success;sync_upstream=failure", message)


class SyncFailureTests(unittest.TestCase):
    def test_main_returns_nonzero_when_any_sync_task_fails(self) -> None:
        task = sync_upstream_rules.SyncTask(
            name="failing",
            runner=lambda _failures: (0, 1),
        )

        with mock.patch.object(sync_upstream_rules, "SYNC_TASKS", (task,)):
            self.assertEqual(sync_upstream_rules.main(), 1)

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
        ), mock.patch(
            "sync_upstream_rules.running_in_github_actions",
            return_value=True,
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
        ), mock.patch(
            "sync_upstream_rules.load_existing_alicloud_official_snapshot",
            return_value=None,
        ):
            changed, failed = sync_upstream_rules.sync_alicloud_snapshots(failures)

        self.assertEqual((changed, failed), (0, len(sync_upstream_rules.ALICLOUD_REGION_SNAPSHOTS)))
        self.assertEqual(len(failures), len(sync_upstream_rules.ALICLOUD_REGION_SNAPSHOTS))
        self.assertEqual(failures[0].category, "缺少凭据")
        self.assertEqual(failures[0].resource, "alicloud/hk_ipv4.txt")

    def test_sync_alicloud_snapshots_refreshes_bgp_without_local_credentials(self) -> None:
        failures: list[sync_upstream_rules.UpstreamFailure] = []
        snapshot = sync_upstream_rules.ALICLOUD_REGION_SNAPSHOTS[0]
        official_payload = json.loads(
            (
                sync_upstream_rules.UPSTREAM_ROOT / snapshot.metadata_path
            ).read_text(encoding="utf-8")
        )
        bgp_payload = json.loads(
            (
                sync_upstream_rules.UPSTREAM_ROOT / snapshot.bgp_metadata_path
            ).read_text(encoding="utf-8")
        )

        with mock.patch(
            "sync_upstream_rules.resolve_alicloud_credentials",
            return_value=None,
        ), mock.patch(
            "sync_upstream_rules.load_existing_alicloud_official_snapshot",
            return_value=official_payload,
        ), mock.patch(
            "sync_upstream_rules.fetch_stable_alicloud_bgp_snapshot",
            return_value=bgp_payload,
        ), mock.patch(
            "sync_upstream_rules.write_if_changed",
            return_value=False,
        ), mock.patch(
            "sync_upstream_rules.validate_alicloud_snapshot_files",
            return_value=official_payload,
        ):
            changed, failed = sync_upstream_rules.sync_alicloud_snapshots(failures)

        self.assertEqual((changed, failed), (0, 0))
        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
