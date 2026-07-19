from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import sys


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import monitor_surge  # noqa: E402


class MonitorSurgeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.state_dir = Path(self.temporary.name) / "surge-monitor-test"
        monitor_surge.ensure_private_dir(self.state_dir)
        self.connection = monitor_surge.connect_database(self.state_dir)
        self.addCleanup(self.connection.close)
        self.secret = b"s" * 32
        self.config = monitor_surge.deep_merge(
            monitor_surge.DEFAULT_CONFIG,
            {
                "state_dir": str(self.state_dir),
                "thresholds": {
                    "minimum_samples": 5,
                    "minimum_failures": 3,
                    "failure_ratio": 0.2,
                    "final_hit_count": 5,
                    "dns_slow_ms": 1000,
                    "connect_slow_ms": 3000,
                },
            },
        )

    def request_item(
        self,
        request_id: int,
        host: str,
        *,
        rule: str = "FINAL,policy",
        policy: str = "私有美国节点",
        failed: bool = True,
        notes: list[str] | None = None,
        started_at: float = 1_700_000_000,
        completed: bool = True,
        total_seconds: float = 1.0,
        dns_ms: float = 20.0,
        connect_ms: float = 800.0,
        engine: str = "engine-a",
    ) -> dict[str, object]:
        result: dict[str, object] = {
            "id": request_id,
            "engineIdentifier": engine,
            "remoteHost": host,
            "deviceName": "真实设备名称",
            "sourceAddress": "192.0.2.10",
            "policyName": policy,
            "originalPolicyName": "私有美国策略组",
            "rule": rule,
            "failed": failed,
            "rejected": False,
            "completed": completed,
            "notes": notes if notes is not None else (["Connection timed out"] if failed else []),
            "startDate": started_at,
            "timingRecords": [
                {"name": "DNS Lookup", "durationInMillisecond": dns_ms},
                {"name": "Establishing TCP Connection", "durationInMillisecond": connect_ms},
            ],
        }
        if completed:
            result["completedDate"] = started_at + total_seconds
        return result

    def test_normalize_hostname_removes_url_path_and_port(self) -> None:
        self.assertEqual(
            monitor_surge.normalize_hostname("https://Example.COM:443/private?q=secret"),
            "example.com",
        )
        self.assertEqual(monitor_surge.normalize_hostname("example.com:443"), "example.com")

    def test_load_config_refuses_privacy_boundary_override(self) -> None:
        config_path = Path(self.temporary.name) / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "surge_monitor": {
                        "privacy": {"store_url_paths_queries": True}
                    }
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(monitor_surge.MonitorError, "privacy_url_storage_forbidden"):
            monitor_surge.load_config(config_path)

    def test_load_config_accepts_documented_schema(self) -> None:
        config_path = Path(self.temporary.name) / "config.json"
        config_path.write_text(
            json.dumps({"surge_monitor": {"state_dir": str(self.state_dir)}}),
            encoding="utf-8",
        )
        loaded = monitor_surge.load_config(config_path)
        self.assertEqual(loaded["request_poll_seconds"], 20)
        self.assertEqual(Path(loaded["state_dir"]), self.state_dir.resolve())

    def test_load_config_rejects_string_booleans(self) -> None:
        for payload, code in (
            ({"enabled": "false"}, "invalid_config_enabled"),
            (
                {"privacy": {"store_final_hostnames": "false"}},
                "invalid_config_store_final_hostnames",
            ),
        ):
            config_path = Path(self.temporary.name) / (code + ".json")
            config_path.write_text(
                json.dumps({"surge_monitor": payload}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(monitor_surge.MonitorError, code):
                monitor_surge.load_config(config_path)

    def test_load_config_rejects_broad_state_directories(self) -> None:
        for index, state_dir in enumerate(
            ("/", str(Path.home()), str(Path.home() / "Documents"), "/private/tmp")
        ):
            config_path = Path(self.temporary.name) / "unsafe-{}.json".format(index)
            config_path.write_text(
                json.dumps({"surge_monitor": {"state_dir": state_dir}}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(monitor_surge.MonitorError, "unsafe_state_dir"):
                monitor_surge.load_config(config_path)

    def test_repository_example_config_is_accepted(self) -> None:
        loaded = monitor_surge.load_config(ROOT / ".rulemesh.local.example.json")
        self.assertFalse(loaded["enabled"])
        self.assertEqual(
            {probe["category"] for probe in loaded["probes"]},
            {"domestic", "google", "openai"},
        )

    def test_classification_helpers(self) -> None:
        self.assertEqual(monitor_surge.classify_rule("FINAL,US"), ("FINAL", True))
        self.assertEqual(monitor_surge.classify_rule("RULE-SET,foo"), ("RULE-SET", False))
        self.assertEqual(
            monitor_surge.classify_error(["No upstream DNS server"], True, False),
            "dns",
        )
        self.assertEqual(
            monitor_surge.classify_error(["No route to host"], True, False),
            "no_route",
        )
        self.assertEqual(
            monitor_surge.classify_host("cdn.oaistatic.com", {}, ("cn",)),
            "openai",
        )
        self.assertEqual(
            monitor_surge.classify_host("service.example", {}, ("cn",), "RULE-SET,google_us"),
            "google",
        )

    def test_collect_requests_only_stores_minimized_fields(self) -> None:
        item = self.request_item(1, "missing.example.cn")
        item["URL"] = "https://missing.example.cn/private?token=secret"
        payload = {"recent-requests": [item]}
        inserted = monitor_surge.collect_requests(
            self.connection,
            self.config,
            self.secret,
            ("cn",),
            now=1_700_000_010,
            payload=payload,
        )
        self.assertEqual(inserted, 1)
        row = self.connection.execute("SELECT * FROM requests").fetchone()
        self.assertEqual(row["host_key"], "missing.example.cn")
        self.assertEqual(row["host_scope"], "domestic")
        self.assertEqual(row["error_category"], "timeout")
        self.assertTrue(str(row["client_id"]).startswith("client#"))
        serialized = json.dumps(dict(row), ensure_ascii=False)
        self.assertNotIn("真实设备名称", serialized)
        self.assertNotIn("192.0.2.10", serialized)
        self.assertNotIn("private", serialized)
        self.assertNotIn("secret", serialized)

    def test_collect_requests_hashes_nonfinal_unfocused_host(self) -> None:
        item = self.request_item(2, "private.example", rule="RULE-SET,private", failed=False)
        monitor_surge.collect_requests(
            self.connection,
            self.config,
            self.secret,
            ("cn",),
            now=1_700_000_010,
            payload={"recent-requests": [item]},
        )
        self.assertIsNone(self.connection.execute("SELECT * FROM requests").fetchone())
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM request_seen").fetchone()[0],
            1,
        )

    def test_collect_requests_updates_active_request_to_completed_failure(self) -> None:
        active = self.request_item(
            20,
            "chatgpt.com",
            failed=False,
            completed=False,
            started_at=1_700_000_000,
        )
        finished = self.request_item(
            20,
            "chatgpt.com",
            failed=True,
            completed=True,
            started_at=1_700_000_000,
            total_seconds=30,
        )
        first = monitor_surge.collect_requests(
            self.connection,
            self.config,
            self.secret,
            ("cn",),
            now=1_700_000_010,
            payload={"recent-requests": [active]},
        )
        second = monitor_surge.collect_requests(
            self.connection,
            self.config,
            self.secret,
            ("cn",),
            now=1_700_000_040,
            payload={"recent-requests": [finished]},
        )
        row = self.connection.execute(
            "SELECT failed, completed, total_ms FROM requests"
        ).fetchone()
        self.assertEqual((first, second), (1, 0))
        self.assertEqual((row["failed"], row["completed"], row["total_ms"]), (1, 1, 30000))

    def test_collect_requests_distinguishes_reused_request_id(self) -> None:
        for started_at in (1_700_000_000, 1_700_000_100):
            monitor_surge.collect_requests(
                self.connection,
                self.config,
                self.secret,
                ("cn",),
                now=started_at + 10,
                payload={
                    "recent-requests": [
                        self.request_item(21, "chatgpt.com", started_at=started_at)
                    ]
                },
            )
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM requests").fetchone()[0],
            2,
        )

    def test_collect_requests_preserves_final_candidate_locally(self) -> None:
        item = self.request_item(3, "unknown.example")
        monitor_surge.collect_requests(
            self.connection,
            self.config,
            self.secret,
            ("cn",),
            now=1_700_000_010,
            payload={"recent-requests": [item]},
        )
        row = self.connection.execute("SELECT host_key, host_scope FROM requests").fetchone()
        self.assertEqual(tuple(row), ("unknown.example", "final_candidate"))

    def test_coverage_distinguishes_buffer_gap_from_monitor_downtime(self) -> None:
        monitor_surge.collect_requests(
            self.connection,
            self.config,
            self.secret,
            ("cn",),
            now=1_700_000_000,
            payload={"recent-requests": [self.request_item(1, "chatgpt.com")]},
        )
        monitor_surge.collect_requests(
            self.connection,
            self.config,
            self.secret,
            ("cn",),
            now=1_700_000_020,
            payload={
                "recent-requests": [
                    self.request_item(index, "chatgpt.com")
                    for index in range(4, 204)
                ]
            },
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT code FROM health_events WHERE component = 'coverage' ORDER BY id DESC LIMIT 1"
            ).fetchone()["code"],
            "request_gap",
        )

        monitor_surge.collect_requests(
            self.connection,
            self.config,
            self.secret,
            ("cn",),
            now=1_700_000_200,
            payload={
                "recent-requests": [
                    self.request_item(index, "chatgpt.com")
                    for index in range(300, 500)
                ]
            },
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT code FROM health_events WHERE component = 'coverage' ORDER BY id DESC LIMIT 1"
            ).fetchone()["code"],
            "monitor_gap",
        )

    def test_low_volume_restart_records_monitor_gap(self) -> None:
        monitor_surge.collect_requests(
            self.connection,
            self.config,
            self.secret,
            ("cn",),
            now=1_700_000_000,
            payload={"recent-requests": [self.request_item(600, "chatgpt.com")]},
        )
        monitor_surge.collect_requests(
            self.connection,
            self.config,
            self.secret,
            ("cn",),
            now=1_700_000_300,
            payload={"recent-requests": [self.request_item(601, "chatgpt.com")]},
        )
        row = self.connection.execute(
            "SELECT code FROM health_events WHERE component = 'coverage' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        self.assertEqual(row["code"], "monitor_gap")

    def test_audit_profile_checks_dns_boundary_without_persisting_profile(self) -> None:
        profile = """
[General]
dns-server = 1.1.1.1, 8.8.8.8
encrypted-dns-server = https://cloudflare-dns.com/dns-query
encrypted-dns-follow-outbound-mode = true
use-local-host-item-for-proxy = false
hijack-dns = *:53

[Host]
DOMAIN-SET:https://example.test/cn_dns_domains.list = server:https://dns.alidns.com/dns-query
DOMAIN-SET:https://example.test/proxy-node-domains = server:https://dns.alidns.com/dns-query

[Rule]
DOMAIN,example.com,DIRECT
FINAL,US,dns-failed
""".strip()
        results = monitor_surge.collect_profile_audit(
            self.connection,
            self.config,
            now=1_700_000_020,
            payload={"profile": profile},
        )
        self.assertTrue(all(results.values()))
        database_bytes = (self.state_dir / "monitor.sqlite3").read_bytes()
        self.assertNotIn(b"example.test", database_bytes)
        row = self.connection.execute(
            "SELECT profile_id, COUNT(*) AS count FROM profile_audits GROUP BY profile_id"
        ).fetchone()
        self.assertEqual(len(row["profile_id"]), 16)
        self.assertEqual(row["count"], len(results))

    def test_collect_dns_only_keeps_focus_and_anonymized_answers(self) -> None:
        payload = {
            "dnsCache": [
                {
                    "domain": "www.baidu.com",
                    "server": "https://dns.alidns.com/dns-query",
                    "timeCost": 0.2,
                    "data": ["198.51.100.8"],
                    "logs": ["success"],
                },
                {
                    "domain": "private.example",
                    "server": "https://dns.google/dns-query",
                    "timeCost": 0.1,
                    "data": ["203.0.113.9"],
                    "logs": ["success"],
                },
                {
                    "domain": "unrelated.cn",
                    "server": "https://dns.alidns.com/dns-query",
                    "timeCost": 0.1,
                    "data": ["192.0.2.4"],
                    "logs": ["success"],
                },
            ]
        }
        count = monitor_surge.collect_dns(
            self.connection,
            self.config,
            self.secret,
            ("baidu.com", "cn"),
            now=1_700_000_030,
            payload=payload,
        )
        self.assertEqual(count, 1)
        row = self.connection.execute("SELECT * FROM dns_samples").fetchone()
        self.assertEqual(row["host_key"], "www.baidu.com")
        self.assertEqual(row["server_class"], "domestic")
        self.assertEqual(row["time_ms"], 200)
        self.assertNotEqual(row["answer_id"], "198.51.100.8")

    def test_analyze_creates_cn_final_recommendation(self) -> None:
        payload = {
            "recent-requests": [
                self.request_item(index, "missing.example.cn", started_at=1_700_000_000 + index)
                for index in range(10, 15)
            ]
        }
        monitor_surge.collect_requests(
            self.connection,
            self.config,
            self.secret,
            ("cn",),
            now=1_700_000_020,
            payload=payload,
        )
        recommendations = monitor_surge.analyze(
            self.connection, self.config, hours=24, now=1_700_000_100
        )
        self.assertEqual(len(recommendations), 1)
        self.assertEqual(recommendations[0]["kind"], "CN-FINAL")
        self.assertTrue(
            recommendations[0]["recommendation_id"].startswith("RM-INV-CN-FINAL-")
        )
        self.assertEqual(recommendations[0]["status"], "pending_investigation_approval")

    def test_analyze_creates_us_path_recommendation_with_anonymous_policy(self) -> None:
        payload = {
            "recent-requests": [
                self.request_item(
                    index,
                    "chatgpt.com",
                    rule="RULE-SET,ai_us",
                    started_at=1_700_000_000 + index,
                )
                for index in range(20, 25)
            ]
        }
        monitor_surge.collect_requests(
            self.connection,
            self.config,
            self.secret,
            ("cn",),
            now=1_700_000_030,
            payload=payload,
        )
        recommendations = monitor_surge.analyze(
            self.connection, self.config, hours=24, now=1_700_000_100
        )
        self.assertEqual(recommendations[0]["kind"], "US-PATH")
        self.assertTrue(recommendations[0]["evidence"]["policy"].startswith("policy#"))
        self.assertNotIn("私有美国节点", json.dumps(recommendations[0], ensure_ascii=False))

    def test_analyze_counts_rejected_final_as_failure(self) -> None:
        items = []
        for index in range(700, 705):
            item = self.request_item(
                index,
                "rejected.example",
                failed=False,
                started_at=1_700_000_000 + index,
            )
            item["rejected"] = True
            items.append(item)
        monitor_surge.collect_requests(
            self.connection,
            self.config,
            self.secret,
            ("cn",),
            now=1_700_000_800,
            payload={"recent-requests": items},
        )
        recommendations = monitor_surge.analyze(
            self.connection, self.config, hours=24, now=1_700_000_900
        )
        self.assertEqual([item["kind"] for item in recommendations], ["FINAL-FAIL"])
        self.assertEqual(recommendations[0]["evidence"]["failures"], 5)
        self.assertEqual(recommendations[0]["evidence"]["rejected"], 5)

    def test_analyze_detects_slow_successful_us_requests(self) -> None:
        payload = {
            "recent-requests": [
                self.request_item(
                    index,
                    "cdn.oaistatic.com",
                    rule="RULE-SET,ai_us",
                    failed=False,
                    total_seconds=30,
                    connect_ms=4000,
                    started_at=1_700_000_000 + index,
                )
                for index in range(100, 105)
            ]
        }
        monitor_surge.collect_requests(
            self.connection,
            self.config,
            self.secret,
            ("cn",),
            now=1_700_000_120,
            payload=payload,
        )
        recommendations = monitor_surge.analyze(
            self.connection, self.config, hours=24, now=1_700_000_200
        )
        self.assertEqual([item["kind"] for item in recommendations], ["US-PATH"])
        self.assertEqual(recommendations[0]["evidence"]["failures"], 0)
        self.assertEqual(recommendations[0]["evidence"]["slow_path_samples"], 5)

    def test_profile_change_moves_analysis_window_boundary(self) -> None:
        self.connection.executemany(
            "INSERT INTO profile_audits(sampled_at, profile_id, code, ok) VALUES (?, ?, 'check', 1)",
            [
                (1_700_000_000, "old-profile"),
                (1_700_000_050, "new-profile"),
                (1_700_000_100, "new-profile"),
            ],
        )
        payload = {
            "recent-requests": [
                self.request_item(
                    index,
                    "old.example.cn",
                    started_at=1_700_000_010 + (index - 50),
                )
                for index in range(50, 55)
            ]
        }
        monitor_surge.collect_requests(
            self.connection,
            self.config,
            self.secret,
            ("cn",),
            now=1_700_000_040,
            payload=payload,
        )
        cutoff, changes, changed_at = monitor_surge.profile_window_info(
            self.connection, 1_699_999_000
        )
        self.assertEqual((cutoff, changes, changed_at), (1_700_000_050, 1, 1_700_000_050))
        recommendations = monitor_surge.analyze(
            self.connection, self.config, hours=24, now=1_700_000_200
        )
        self.assertEqual(recommendations, [])

    def test_report_hashes_unclassified_final_hostname(self) -> None:
        payload = {
            "recent-requests": [
                self.request_item(index, "sensitive.example", started_at=1_700_000_000 + index)
                for index in range(30, 35)
            ]
        }
        monitor_surge.collect_requests(
            self.connection,
            self.config,
            self.secret,
            ("cn",),
            now=1_700_000_040,
            payload=payload,
        )
        for component in ("profile", "dns", "event", "probe"):
            monitor_surge.record_health(
                self.connection, component, True, "ok", sampled_at=1_700_000_090
            )
        self.connection.commit()
        report = monitor_surge.report_markdown(
            self.connection, self.config, hours=24, now=1_700_000_100
        )
        self.assertIn("RM-INV-FINAL-FAIL-", report)
        self.assertIn("域名#", report)
        self.assertIn("- 状态：pending_investigation_approval", report)
        self.assertIn("批准调查 RM-INV-FINAL-FAIL-", report)
        self.assertIn("RM-EXEC-*", report)
        self.assertNotIn("sensitive.example", report)
        self.assertNotIn("真实设备名称", report)

    def test_public_recommendation_removes_internal_subject(self) -> None:
        public = monitor_surge.public_recommendation(
            {"recommendation_id": "RM-INV-X", "subject": "sensitive.example", "evidence": {}}
        )
        self.assertNotIn("subject", public)
        self.assertNotIn("sensitive.example", json.dumps(public))

    def test_probe_collector_never_stores_url(self) -> None:
        def fake_runner(_probe: object, _secret: bytes) -> dict[str, object]:
            return {
                "reachable": True,
                "healthy": True,
                "error_category": "none",
                "http_code": 204,
                "dns_ms": 5.0,
                "connect_ms": 20.0,
                "tls_ms": 40.0,
                "total_ms": 60.0,
                "remote_id": "remote#abc",
            }

        count = monitor_surge.collect_probes(
            self.connection,
            self.config,
            self.secret,
            now=1_700_000_050,
            runner=fake_runner,
        )
        self.assertEqual(count, len(self.config["probes"]))
        columns = [row[1] for row in self.connection.execute("PRAGMA table_info(probes)")]
        self.assertNotIn("url", columns)
        self.assertNotIn("path", columns)

    def test_analyze_detects_slow_successful_probe(self) -> None:
        def fake_runner(probe: object, _secret: bytes) -> dict[str, object]:
            is_google = isinstance(probe, dict) and probe.get("name") == "google"
            return {
                "reachable": True,
                "healthy": True,
                "error_category": "none",
                "http_code": 204 if is_google else 200,
                "dns_ms": 5.0,
                "connect_ms": 4000.0 if is_google else 20.0,
                "tls_ms": 40.0,
                "total_ms": 12000.0 if is_google else 60.0,
                "remote_id": "remote#abc",
            }

        for offset in range(5):
            monitor_surge.collect_probes(
                self.connection,
                self.config,
                self.secret,
                now=1_700_000_000 + offset,
                runner=fake_runner,
            )
        recommendations = monitor_surge.analyze(
            self.connection, self.config, hours=24, now=1_700_000_100
        )
        self.assertIn("US-PROBE", [item["kind"] for item in recommendations])

    def test_report_gates_stale_data(self) -> None:
        monitor_surge.collect_requests(
            self.connection,
            self.config,
            self.secret,
            ("cn",),
            now=1_700_000_000,
            payload={
                "recent-requests": [
                    self.request_item(index, "missing.example.cn")
                    for index in range(200, 205)
                ]
            },
        )
        for component in ("profile", "dns", "event", "probe"):
            monitor_surge.record_health(
                self.connection, component, True, "ok", sampled_at=1_700_000_000
            )
        self.connection.commit()
        report = monitor_surge.report_markdown(
            self.connection, self.config, hours=24, now=1_700_010_000
        )
        self.assertIn("采集质量：degraded", report)
        self.assertIn("RM-INV-COLLECTOR-", report)
        self.assertNotIn("RM-INV-CN-FINAL-", report)

    def test_data_quality_requires_recovery_after_monitor_gap(self) -> None:
        gap_time = 1_700_000_000
        monitor_surge.record_health(
            self.connection,
            "coverage",
            False,
            "monitor_gap",
            1,
            sampled_at=gap_time,
        )
        for component in ("request", "profile", "dns", "event", "probe"):
            monitor_surge.record_health(
                self.connection, component, True, "ok", sampled_at=gap_time + 1
            )
        self.connection.commit()
        recovering = monitor_surge.data_quality(
            self.connection, self.config, now=gap_time + 100
        )
        self.assertFalse(recovering["ok"])
        self.assertIn("coverage:recovering_after_monitor_gap", recovering["issues"])

        recovered_at = gap_time + 901
        for component in ("request", "profile", "dns", "event", "probe"):
            monitor_surge.record_health(
                self.connection, component, True, "ok", sampled_at=recovered_at
            )
        self.connection.commit()
        recovered = monitor_surge.data_quality(
            self.connection, self.config, now=recovered_at
        )
        self.assertTrue(recovered["ok"])
        cutoff, _changes, _changed_at = monitor_surge.profile_window_info(
            self.connection, gap_time - 1000
        )
        self.assertEqual(cutoff, gap_time)

    def test_data_quality_requires_recovery_after_collector_failure(self) -> None:
        failure_time = 1_700_000_000
        monitor_surge.record_health(
            self.connection,
            "dns",
            False,
            "surge_cli_timeout",
            sampled_at=failure_time,
        )
        recovered_at = failure_time + 100
        for component in ("request", "profile", "dns", "event", "probe"):
            monitor_surge.record_health(
                self.connection, component, True, "ok", sampled_at=recovered_at
            )
        self.connection.commit()

        quality = monitor_surge.data_quality(
            self.connection, self.config, now=recovered_at
        )
        self.assertFalse(quality["ok"])
        self.assertIn(
            "coverage:recovering_after_dns_surge_cli_timeout",
            quality["issues"],
        )

        stable_at = failure_time + 901
        for component in ("request", "profile", "dns", "event", "probe"):
            monitor_surge.record_health(
                self.connection, component, True, "ok", sampled_at=stable_at
            )
        self.connection.commit()
        self.assertTrue(
            monitor_surge.data_quality(self.connection, self.config, now=stable_at)["ok"]
        )

    def test_purge_respects_retention(self) -> None:
        old = 1_600_000_000
        self.connection.execute(
            "INSERT INTO health_events(sampled_at, component, ok, code, count_value) VALUES (?, 'x', 1, 'ok', 0)",
            (old,),
        )
        self.connection.commit()
        monitor_surge.purge_old_data(self.connection, 14, now=old + 15 * 86400)
        count = self.connection.execute("SELECT COUNT(*) FROM health_events").fetchone()[0]
        self.assertEqual(count, 1)
        self.assertEqual(
            self.connection.execute(
                "SELECT code FROM health_events WHERE component = 'storage'"
            ).fetchone()["code"],
            "ok",
        )

    def test_purge_uses_layered_request_retention(self) -> None:
        now = 1_700_200_000
        monitor_surge.collect_requests(
            self.connection,
            self.config,
            self.secret,
            ("cn",),
            now=now - 37 * 3600,
            payload={
                "recent-requests": [
                    self.request_item(300, "chatgpt.com", started_at=now - 37 * 3600)
                ]
            },
        )
        monitor_surge.purge_old_data(self.connection, 14, now=now)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM requests").fetchone()[0], 0)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM request_seen").fetchone()[0], 0)

    def test_purge_enforces_hard_database_budget(self) -> None:
        now = 1_700_300_000
        large_answer = "x" * 700
        self.connection.executemany(
            """
            INSERT INTO dns_samples(
                sampled_at, host_key, server_class, success, error_category,
                time_ms, answer_count, answer_id
            ) VALUES (?, 'www.baidu.com', 'domestic', 1, 'none', 10, 1, ?)
            """,
            ((now, large_answer + str(index)) for index in range(70000)),
        )
        self.connection.commit()
        self.assertGreater(
            monitor_surge.database_size_bytes(self.connection),
            32 * 1024 * 1024,
        )

        monitor_surge.purge_old_data(
            self.connection,
            retention_days=14,
            now=now,
            max_database_mb=32,
        )

        self.assertLessEqual(
            monitor_surge.database_size_bytes(self.connection),
            32 * 1024 * 1024,
        )
        self.assertLessEqual(
            self.connection.execute("SELECT COUNT(*) FROM dns_samples").fetchone()[0],
            25000,
        )
        storage = self.connection.execute(
            "SELECT ok, code FROM health_events WHERE component = 'storage' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        self.assertEqual((storage["ok"], storage["code"]), (0, "budget_compacted"))

    def test_budget_exceeded_applies_collection_backpressure(self) -> None:
        monitor_surge.record_health(
            self.connection, "storage", False, "budget_exceeded", sampled_at=1_700_000_000
        )
        self.connection.commit()
        inserted = monitor_surge.collect_requests(
            self.connection,
            self.config,
            self.secret,
            ("cn",),
            now=1_700_000_010,
            payload={"recent-requests": [self.request_item(800, "chatgpt.com")]},
        )
        self.assertEqual(inserted, 0)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM requests").fetchone()[0], 0)
        request_health = self.connection.execute(
            "SELECT code FROM health_events WHERE component = 'request' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        self.assertEqual(request_health["code"], "storage_backpressure")

    def test_connect_database_migrates_legacy_request_schema(self) -> None:
        legacy_dir = Path(self.temporary.name) / "legacy"
        monitor_surge.ensure_private_dir(legacy_dir)
        database_path = legacy_dir / "monitor.sqlite3"
        legacy = sqlite3.connect(database_path)
        legacy.execute(
            """
            CREATE TABLE requests (
                request_id INTEGER PRIMARY KEY, started_at REAL NOT NULL,
                observed_at REAL NOT NULL, host_key TEXT NOT NULL,
                host_scope TEXT NOT NULL, client_id TEXT NOT NULL,
                policy_id TEXT NOT NULL, original_policy_id TEXT NOT NULL,
                rule_type TEXT NOT NULL, is_final INTEGER NOT NULL,
                is_direct INTEGER NOT NULL, failed INTEGER NOT NULL,
                rejected INTEGER NOT NULL, completed INTEGER NOT NULL,
                error_category TEXT NOT NULL, total_ms REAL, dns_ms REAL,
                connect_ms REAL
            )
            """
        )
        legacy.execute(
            """
            INSERT INTO requests VALUES (
                7, 1700000000, 1700000001, 'legacy.example', 'final_candidate',
                'client#x', 'policy#x', 'policy#y', 'FINAL', 1, 0, 1, 0, 1,
                'timeout', 1000, 20, 800
            )
            """
        )
        legacy.commit()
        legacy.close()
        migrated = monitor_surge.connect_database(legacy_dir)
        self.addCleanup(migrated.close)
        columns = [value[1] for value in migrated.execute("PRAGMA table_info(requests)")]
        self.assertEqual(migrated.execute("SELECT COUNT(*) FROM requests").fetchone()[0], 0)
        self.assertNotIn("request_id", columns)


if __name__ == "__main__":
    unittest.main()
