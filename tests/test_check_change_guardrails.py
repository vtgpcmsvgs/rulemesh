import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import check_change_guardrails  # noqa: E402


class ChangeGuardrailTests(unittest.TestCase):
    def test_rule_structural_change_requires_both_upstream_metadata_files(self) -> None:
        changes = [
            check_change_guardrails.WorktreeChange(
                status="A",
                paths=("rules/direct/new_direct.list",),
            )
        ]

        findings = check_change_guardrails.evaluate_guardrails(changes)

        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].level, "error")
        self.assertIn("rules/upstream/sources.yaml", findings[0].message)
        self.assertIn("rules/upstream/merge.yaml", findings[0].message)
        self.assertEqual(findings[1].level, "warning")

    def test_rule_structural_change_passes_when_upstream_metadata_changes_are_present(self) -> None:
        changes = [
            check_change_guardrails.WorktreeChange(
                status="R",
                paths=("rules/direct/old.list", "rules/direct/new.list"),
            ),
            check_change_guardrails.WorktreeChange(
                status="M",
                paths=("rules/upstream/sources.yaml",),
            ),
            check_change_guardrails.WorktreeChange(
                status="M",
                paths=("rules/upstream/merge.yaml",),
            ),
        ]

        findings = check_change_guardrails.evaluate_guardrails(changes)

        self.assertEqual(
            findings,
            [
                check_change_guardrails.GuardrailFinding(
                    level="warning",
                    message=(
                        "本次涉及源规则，请确认是否改变了默认对外规则入口、顺序、策略含义或公开模板行为；"
                        "若有，请同步更新 README.md、docs/usage-surge.md、docs/usage-mihomo.md 与两份公开模板。"
                    ),
                )
            ],
        )

    def test_style_doc_requires_agents_and_readme(self) -> None:
        changes = [
            check_change_guardrails.WorktreeChange(
                status="M",
                paths=("docs/rule-authoring-style.md",),
            )
        ]

        findings = check_change_guardrails.evaluate_guardrails(changes)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].level, "error")
        self.assertIn("AGENTS.md", findings[0].message)
        self.assertIn("README.md", findings[0].message)

    def test_build_tool_change_without_readme_emits_warning(self) -> None:
        changes = [
            check_change_guardrails.WorktreeChange(
                status="M",
                paths=("tools/check.ps1",),
            )
        ]

        findings = check_change_guardrails.evaluate_guardrails(changes)

        self.assertEqual(
            findings,
            [
                check_change_guardrails.GuardrailFinding(
                    level="warning",
                    message="本次涉及构建或检查脚本，请确认 README.md 的构建/验证说明是否也需要同步。",
                )
            ],
        )

    def test_partial_public_doc_bundle_emits_warning(self) -> None:
        changes = [
            check_change_guardrails.WorktreeChange(
                status="M",
                paths=("README.md",),
            ),
            check_change_guardrails.WorktreeChange(
                status="M",
                paths=("docs/usage-surge.md",),
            ),
        ]

        findings = check_change_guardrails.evaluate_guardrails(changes)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].level, "warning")
        self.assertIn("docs/usage-mihomo.md", findings[0].message)


class ChangeClassificationTests(unittest.TestCase):
    def test_classify_changes_returns_high_risk_categories(self) -> None:
        changes = [
            check_change_guardrails.WorktreeChange(
                status="M",
                paths=("AGENTS.md",),
            ),
            check_change_guardrails.WorktreeChange(
                status="M",
                paths=("tools/check.ps1",),
            ),
            check_change_guardrails.WorktreeChange(
                status="M",
                paths=("dist/build-report.json",),
            ),
        ]

        self.assertEqual(
            check_change_guardrails.classify_changes(changes),
            ["构建与检查脚本", "仓库约束", "构建产物"],
        )


if __name__ == "__main__":
    unittest.main()
