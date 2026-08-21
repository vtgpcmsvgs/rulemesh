import contextlib
import io
import json
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import build_rules  # noqa: E402
import sync_upstream_rules  # noqa: E402
import validate_surge_test_urls  # noqa: E402


UTF8_BOM = b"\xef\xbb\xbf"
TEXT_FILE_ROOTS = (
    ROOT / ".github",
    ROOT / "docs",
    ROOT / "rules",
    ROOT / "tools",
    ROOT / "tests",
)
TEXT_FILE_PATHS = (
    ROOT / "AGENTS.md",
    ROOT / "README.md",
    ROOT / "private-repository.json",
    ROOT / ".rulemesh.local.example.json",
)
SOURCE_RULE_GROUPS = ("reject", "direct", "proxy", "region")


def iter_text_files() -> list[Path]:
    files: list[Path] = []
    for path in TEXT_FILE_PATHS:
        if path.exists():
            files.append(path)
    for root in TEXT_FILE_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if (
                path.is_file()
                and "__pycache__" not in path.parts
                and path.suffix != ".pyc"
            ):
                files.append(path)
    return sorted(set(files))


def collect_source_rule_paths() -> list[str]:
    files: list[str] = []
    rules_root = ROOT / "rules"
    for group in SOURCE_RULE_GROUPS:
        root = rules_root / group
        if not root.exists():
            continue
        for path in root.rglob("*.list"):
            files.append(path.relative_to(rules_root).as_posix())
    return sorted(files)


def collect_sources_yaml_entries() -> list[str]:
    entries: list[str] = []
    category: str | None = None
    pattern = re.compile(r"^\s{4}([A-Za-z0-9_./-]+\.list):\s*$")
    path = ROOT / "rules" / "upstream" / "sources.yaml"
    for raw in path.read_text(encoding="utf-8").splitlines():
        header = re.match(r"^\s{2}(reject|direct|proxy|region):\s*$", raw)
        if header:
            category = header.group(1)
            continue
        match = pattern.match(raw)
        if not match or not category:
            continue
        key = match.group(1)
        if category == "region":
            entries.append(f"region/{key}")
        else:
            entries.append(f"{category}/{key}")
    return sorted(entries)


def collect_merge_yaml_targets() -> list[str]:
    pattern = re.compile(r"^\s*target:\s+rules/([A-Za-z0-9_./-]+\.list)\s*$")
    path = ROOT / "rules" / "upstream" / "merge.yaml"
    targets = [
        match.group(1)
        for raw in path.read_text(encoding="utf-8").splitlines()
        if (match := pattern.match(raw))
    ]
    return sorted(targets)


class RepoInvariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            cls.build_status = build_rules.run_build()
        cls.build_stdout = stdout.getvalue()
        cls.build_stderr = stderr.getvalue()

        cls.report_path = ROOT / "dist" / "build-report.json"
        if cls.report_path.exists():
            cls.report = json.loads(cls.report_path.read_text(encoding="utf-8"))
        else:
            cls.report = None

    def test_run_build_succeeds(self) -> None:
        self.assertEqual(self.build_status, 0, self.build_stderr or self.build_stdout)

    def test_build_report_has_zero_warnings(self) -> None:
        self.assertIsNotNone(self.report, "缺少 dist/build-report.json")
        self.assertEqual(self.report["summary"]["total_warnings"], 0, self.report["warnings"])
        self.assertEqual(self.report["warnings"], [])

    def test_alicloud_snapshot_and_built_rules_are_complete_and_consistent(self) -> None:
        snapshot = sync_upstream_rules.ALICLOUD_REGION_SNAPSHOTS[0]
        metadata_path = ROOT / "rules" / "upstream" / snapshot.metadata_path
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        prefixes = sync_upstream_rules.validate_alicloud_snapshot_payload(payload, snapshot)

        expected_page_count = (
            payload["reportedTotalCount"] + payload["pageSize"] - 1
        ) // payload["pageSize"]
        self.assertEqual(payload["pageCount"], expected_page_count)

        ipv4_path = ROOT / "rules" / "upstream" / snapshot.path
        ipv4_prefixes = [
            line
            for line in ipv4_path.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#")
        ]
        self.assertEqual(ipv4_prefixes, prefixes)

        bgp_payload = json.loads(
            (ROOT / "rules" / "upstream" / snapshot.bgp_metadata_path).read_text(
                encoding="utf-8"
            )
        )
        bgp_prefixes = sync_upstream_rules.validate_alicloud_bgp_snapshot_payload(
            bgp_payload
        )
        history_prefixes = sync_upstream_rules.parse_ipv4_snapshot_prefixes(
            (ROOT / "rules" / "upstream" / snapshot.history_path).read_text(
                encoding="utf-8"
            ),
            snapshot.history_path.as_posix(),
        )
        self.assertTrue(
            sync_upstream_rules.ipv4_coverage_contains(history_prefixes, prefixes)
        )
        self.assertTrue(
            sync_upstream_rules.ipv4_coverage_contains(history_prefixes, bgp_prefixes)
        )
        self.assertTrue(
            sync_upstream_rules.ipv4_coverage_contains(
                history_prefixes,
                list(sync_upstream_rules.ALICLOUD_LEGACY_IPV4_SEED),
            )
        )

        expected_source_rules = [
            f"AND,((IP-CIDR,{prefix},no-resolve),(PROTOCOL,TCP),(DST-PORT,22))"
            for prefix in history_prefixes
        ]
        expected_source_rules.extend(
            f"AND,((IP-ASN,{asn},no-resolve),(PROTOCOL,TCP),(DST-PORT,22))"
            for asn in sync_upstream_rules.ALICLOUD_FALLBACK_ASNS
        )
        ssh_path = ROOT / "rules" / "upstream" / snapshot.ssh_path
        source_rules = [
            line
            for line in ssh_path.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#")
        ]
        self.assertEqual(source_rules, expected_source_rules)

        surge_path = (
            ROOT / "dist" / "surge" / "rules" / "direct"
            / "alicloud_hk_ipv4_ssh22_direct.list"
        )
        surge_rules = [
            line
            for line in surge_path.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#")
        ]
        self.assertEqual(
            surge_rules,
            [rule.replace("DST-PORT,", "DEST-PORT,") for rule in expected_source_rules],
        )

        mihomo_path = (
            ROOT / "dist" / "mihomo" / "classical" / "direct"
            / "alicloud_hk_ipv4_ssh22_direct.yaml"
        )
        mihomo_rules = [
            json.loads(line.removeprefix("  - "))
            for line in mihomo_path.read_text(encoding="utf-8").splitlines()
            if line.startswith("  - ")
        ]
        self.assertEqual(
            mihomo_rules,
            [
                rule.replace("PROTOCOL,TCP", "NETWORK,tcp")
                for rule in expected_source_rules
            ],
        )

    def test_dist_only_contains_supported_output_roots(self) -> None:
        surge_root = ROOT / "dist" / "surge"
        mihomo_root = ROOT / "dist" / "mihomo"

        self.assertTrue((surge_root / "rules").is_dir())
        self.assertTrue((mihomo_root / "classical").is_dir())
        self.assertFalse((surge_root / "domainset").exists())
        self.assertFalse((mihomo_root / "domain").exists())
        self.assertFalse((mihomo_root / "ipcidr").exists())

        self.assertEqual(
            sorted(path.name for path in surge_root.iterdir() if path.is_dir()),
            ["dns", "rules"],
        )
        self.assertEqual(
            sorted(path.name for path in mihomo_root.iterdir() if path.is_dir()),
            ["classical"],
        )

    def test_cn_dns_domains_keep_domestic_app_runtime_families(self) -> None:
        path = ROOT / "rules" / "dns" / "cn_dns_domains.list"
        entries = [
            line.strip().lower()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        unique_entries = set(entries)
        expected = {
            ".amemv.com",
            ".douyinvod.com",
            ".heweather.com",
            ".heweather.net",
            ".idouyinvod.com",
            ".ixigua.com",
            ".ixiguavideo.com",
            ".miui.com",
            ".pddpic.com",
            ".pinduoduo.com",
            ".qweather.com",
            ".qweather.net",
            ".qweatherapi.com",
            ".servicewechat.com",
            ".serviceweixin.com",
            ".weixin.com",
            ".xhscdn.com",
            ".xhscdn.net",
            ".xiaohongshu.com",
            ".xiaomi.net",
            ".yikaiying.com",
            ".yangkeduo.com",
            ".zsxq.com",
            "lf3-static.bytednsdoc.com",
            "v5-dy-o-abtest.zjcdn.com",
        }
        self.assertEqual(len(entries), len(unique_entries), "国内 DNS 清单仍有重复项")
        self.assertEqual(len(entries), 241)
        self.assertTrue(expected <= unique_entries, sorted(expected - unique_entries))

    def test_yikaiying_keeps_explicit_cn_direct_fallback(self) -> None:
        source = (ROOT / "rules" / "direct" / "cn_direct.list").read_text(
            encoding="utf-8"
        )

        self.assertEqual(source.count("DOMAIN-SUFFIX,yikaiying.com"), 1)

    def test_domestic_direct_rules_precede_hk_global_media(self) -> None:
        surge = (ROOT / "docs" / "examples" / "surge-public.conf").read_text(
            encoding="utf-8"
        )
        mihomo = (ROOT / "docs" / "examples" / "mihomo-public.yaml").read_text(
            encoding="utf-8"
        )
        surge_needles = (
            "direct/ai_cn_direct.list,DIRECT",
            "direct/bytedance_direct.list,DIRECT",
            "region/hk/global_media.list,\"🇭🇰 香港-自动选择\"",
        )
        mihomo_needles = (
            "RULE-SET,direct_ai_cn,DIRECT",
            "RULE-SET,direct_bytedance,DIRECT",
            "RULE-SET,hk_global_media,🇭🇰 香港-自动选择",
        )

        for content, needles in ((surge, surge_needles), (mihomo, mihomo_needles)):
            for needle in needles:
                self.assertEqual(content.count(needle), 1, needle)
            self.assertLess(content.index(needles[0]), content.index(needles[1]))
            self.assertLess(content.index(needles[1]), content.index(needles[2]))

    def test_public_surge_template_keeps_weixin_loopback_real_ip(self) -> None:
        surge = (ROOT / "docs" / "examples" / "surge-public.conf").read_text(
            encoding="utf-8"
        )
        always_real_line = next(
            line for line in surge.splitlines() if line.startswith("always-real-ip =")
        )
        hosts = {
            item.strip().lower()
            for item in always_real_line.split("=", 1)[1].split(",")
        }

        self.assertIn("localhost.weixin.qq.com", hosts)
        self.assertNotIn("*.weixin.qq.com", hosts)
        self.assertEqual(surge.count("localhost.weixin.qq.com"), 1)

    def test_repo_text_files_use_utf8_without_bom(self) -> None:
        offenders = [
            path.relative_to(ROOT).as_posix()
            for path in iter_text_files()
            if path.read_bytes().startswith(UTF8_BOM)
        ]
        self.assertEqual(offenders, [], f"以下文件仍包含 UTF-8 BOM: {offenders}")

    def test_ubuntu_full_suite_workflows_prepare_zsh(self) -> None:
        workflow_root = ROOT / ".github" / "workflows"
        test_command = 'python -m unittest discover -s tests -p "test_*.py"'
        required_before_tests = (
            "sudo apt-get install --yes --no-install-recommends zsh",
            "zsh --version",
        )
        offenders: list[str] = []

        for path in sorted(workflow_root.glob("*.yml")):
            workflow = path.read_text(encoding="utf-8")
            if "runs-on: ubuntu" not in workflow or test_command not in workflow:
                continue

            test_position = workflow.index(test_command)
            missing_or_late = [
                needle
                for needle in required_before_tests
                if needle not in workflow or workflow.index(needle) > test_position
            ]
            if missing_or_late:
                offenders.append(f"{path.name}: 缺少或顺序错误 {missing_or_late}")

        self.assertEqual(offenders, [])

    def test_workflows_avoid_deprecated_node20_action_versions(self) -> None:
        workflow_root = ROOT / ".github" / "workflows"
        deprecated = (
            "actions/checkout@v4",
            "actions/setup-python@v5",
            "actions/upload-artifact@v4",
        )
        offenders: list[str] = []

        for path in sorted(workflow_root.glob("*.yml")):
            workflow = path.read_text(encoding="utf-8")
            matches = [needle for needle in deprecated if needle in workflow]
            if matches:
                offenders.append(f"{path.name}: 仍引用已弃用的 Node 20 Action {matches}")

        self.assertEqual(offenders, [])

    def test_sources_yaml_covers_all_rule_sources(self) -> None:
        self.assertEqual(collect_sources_yaml_entries(), collect_source_rule_paths())

    def test_merge_yaml_covers_all_rule_sources(self) -> None:
        self.assertEqual(collect_merge_yaml_targets(), collect_source_rule_paths())

    def test_public_surge_template_keeps_http_testing_urls(self) -> None:
        findings = validate_surge_test_urls.validate_surge_profile(
            ROOT / "docs" / "examples" / "surge-public.conf"
        )
        self.assertEqual(findings, [])

    def test_wps_kdocs_hk_route_precedes_cn_direct_and_final_fallbacks(self) -> None:
        surge = (ROOT / "docs" / "examples" / "surge-public.conf").read_text(
            encoding="utf-8"
        )
        mihomo = (ROOT / "docs" / "examples" / "mihomo-public.yaml").read_text(
            encoding="utf-8"
        )

        self.assertLess(
            surge.index("region/hk/wps_kdocs.list,\"🇭🇰 香港-自动选择\""),
            surge.index("direct/cn_direct.list,DIRECT"),
        )
        self.assertLess(
            surge.index("region/hk/wps_kdocs.list,\"🇭🇰 香港-自动选择\""),
            surge.index("FINAL,🚀 节点选择"),
        )
        self.assertLess(
            mihomo.index("RULE-SET,hk_wps_kdocs,🇭🇰 香港-自动选择"),
            mihomo.index("RULE-SET,direct_cn,DIRECT"),
        )
        self.assertLess(
            mihomo.index("RULE-SET,hk_wps_kdocs,🇭🇰 香港-自动选择"),
            mihomo.index("MATCH,🚀 节点选择"),
        )

    def test_wps_kdocs_rule_avoids_overbroad_wps_keyword(self) -> None:
        content = (ROOT / "rules" / "region" / "hk" / "wps_kdocs.list").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("\nDOMAIN-KEYWORD,wps\n", f"\n{content}\n")

    def test_alibaba_hk_rule_keeps_xianyu_coverage_and_stays_opt_in(self) -> None:
        content = (ROOT / "rules" / "region" / "hk" / "alibaba_hk.list").read_text(
            encoding="utf-8"
        )
        required = {
            "INCLUDE,upstream/blackmatrix7/alibaba.list",
            "INCLUDE,upstream/blackmatrix7/xianyu.list",
            "DOMAIN-SUFFIX,goofish.com",
            "DOMAIN-SUFFIX,xianyu.mobi",
            "DOMAIN-KEYWORD,goofish",
            "DOMAIN-KEYWORD,xianyu",
            "DOMAIN-KEYWORD,idlefish",
        }
        self.assertTrue(required <= set(content.splitlines()))

        surge = (ROOT / "docs" / "examples" / "surge-public.conf").read_text(
            encoding="utf-8"
        )
        mihomo = (ROOT / "docs" / "examples" / "mihomo-public.yaml").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("alibaba_hk", surge)
        self.assertNotIn("alibaba_hk", mihomo)

    def test_all_scheduled_workflows_keep_webhook_guardrails(self) -> None:
        workflow_root = ROOT / ".github" / "workflows"
        offenders: list[str] = []

        for path in sorted(workflow_root.glob("*.yml")):
            workflow = path.read_text(encoding="utf-8")
            if "schedule:" not in workflow:
                continue

            missing = [
                needle
                for needle in (
                    'RULEMESH_UPSTREAM_ALERT_REQUIRED: "1"',
                    "RULEMESH_UPSTREAM_ALERT_FEISHU_WEBHOOK_URL",
                    "RULEMESH_UPSTREAM_ALERT_FEISHU_SECRET",
                    "Warn when upstream webhook is not configured",
                    "marker: upstream-workflow-failure-alert",
                    "if: ${{ env.RULEMESH_UPSTREAM_ALERT_FEISHU_WEBHOOK_URL == '' }}",
                    "if: ${{ failure() && env.RULEMESH_UPSTREAM_ALERT_FEISHU_WEBHOOK_URL != '' }}",
                    "python3 - <<'PY'",
                    "id: workflow_failure_alert",
                )
                if needle not in workflow
            ]
            if missing:
                offenders.append(f"{path.name}: missing {missing}")

        self.assertEqual(offenders, [])

    def test_sync_workflow_keeps_expected_step_ids(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "sync-upstream-rules.yml").read_text(
            encoding="utf-8"
        )

        for needle in (
            "id: checkout_repo",
            "id: setup_python",
            "id: setup_zsh",
            "id: unit_tests",
            "id: sync_upstream",
            "id: validate_synced_snapshots",
            "id: build_dist",
            "id: commit_changes",
        ):
            self.assertIn(needle, workflow)
