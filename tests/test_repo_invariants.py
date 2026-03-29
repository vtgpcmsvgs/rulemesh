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
            ["rules"],
        )
        self.assertEqual(
            sorted(path.name for path in mihomo_root.iterdir() if path.is_dir()),
            ["classical"],
        )

    def test_repo_text_files_use_utf8_without_bom(self) -> None:
        offenders = [
            path.relative_to(ROOT).as_posix()
            for path in iter_text_files()
            if path.read_bytes().startswith(UTF8_BOM)
        ]
        self.assertEqual(offenders, [], f"以下文件仍包含 UTF-8 BOM: {offenders}")

    def test_sources_yaml_covers_all_rule_sources(self) -> None:
        self.assertEqual(collect_sources_yaml_entries(), collect_source_rule_paths())

    def test_merge_yaml_covers_all_rule_sources(self) -> None:
        self.assertEqual(collect_merge_yaml_targets(), collect_source_rule_paths())

    def test_public_surge_template_keeps_http_testing_urls(self) -> None:
        findings = validate_surge_test_urls.validate_surge_profile(
            ROOT / "docs" / "examples" / "surge-public.conf"
        )
        self.assertEqual(findings, [])

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
            "id: unit_tests",
            "id: sync_upstream",
            "id: build_dist",
            "id: commit_changes",
        ):
            self.assertIn(needle, workflow)
