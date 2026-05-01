from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_RULE_GROUP_PREFIXES = (
    "rules/reject/",
    "rules/direct/",
    "rules/proxy/",
    "rules/region/",
)
SOURCE_RULE_METADATA_FILES = (
    "rules/upstream/sources.yaml",
    "rules/upstream/merge.yaml",
)
PUBLIC_DOC_BUNDLE = (
    "README.md",
    "docs/usage-surge.md",
    "docs/usage-mihomo.md",
    "docs/examples/surge-public.conf",
    "docs/examples/mihomo-public.yaml",
)
BUILD_TOOL_PATHS = (
    "tools/build_rules.ps1",
    "tools/build_rules.py",
    "tools/check.ps1",
    "tools/check_change_guardrails.py",
)
STYLE_DOC_PATH = "docs/rule-authoring-style.md"
WORKFLOW_PREFIX = ".github/workflows/"


@dataclass(frozen=True)
class WorktreeChange:
    status: str
    paths: tuple[str, ...]


@dataclass(frozen=True)
class GuardrailFinding:
    level: str
    message: str


def run_git_lines(*args: str) -> list[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return [line for line in completed.stdout.splitlines() if line.strip()]


def parse_name_status_line(line: str) -> WorktreeChange:
    parts = line.split("\t")
    status = parts[0]
    if status.startswith("R"):
        if len(parts) != 3:
            raise ValueError(f"无法解析 rename 变更：{line}")
        return WorktreeChange(status="R", paths=(parts[1], parts[2]))
    if len(parts) != 2:
        raise ValueError(f"无法解析变更行：{line}")
    return WorktreeChange(status=status, paths=(parts[1],))


def collect_worktree_changes() -> list[WorktreeChange]:
    changes: list[WorktreeChange] = []

    tracked_lines = run_git_lines("diff", "--name-status", "--find-renames", "HEAD", "--")
    changes.extend(parse_name_status_line(line) for line in tracked_lines)

    for path in run_git_lines("ls-files", "--others", "--exclude-standard"):
        changes.append(WorktreeChange(status="??", paths=(path,)))

    return changes


def is_source_rule_path(path: str) -> bool:
    return path.endswith(".list") and path.startswith(SOURCE_RULE_GROUP_PREFIXES)


def is_structural_rule_change(change: WorktreeChange) -> bool:
    if change.status not in {"A", "D", "R", "??"}:
        return False
    return any(is_source_rule_path(path) for path in change.paths)


def collect_changed_paths(changes: list[WorktreeChange]) -> set[str]:
    changed: set[str] = set()
    for change in changes:
        changed.update(change.paths)
    return changed


def classify_changes(changes: list[WorktreeChange]) -> list[str]:
    changed_paths = collect_changed_paths(changes)
    categories: list[str] = []

    if any(is_source_rule_path(path) for path in changed_paths):
        categories.append("源规则")
    if any(path in SOURCE_RULE_METADATA_FILES for path in changed_paths):
        categories.append("上游登记")
    if any(path in PUBLIC_DOC_BUNDLE for path in changed_paths):
        categories.append("公开说明/模板")
    if any(path in BUILD_TOOL_PATHS for path in changed_paths):
        categories.append("构建与检查脚本")
    if STYLE_DOC_PATH in changed_paths:
        categories.append("规则编排文档")
    if "AGENTS.md" in changed_paths:
        categories.append("仓库约束")
    if any(path.startswith(WORKFLOW_PREFIX) for path in changed_paths):
        categories.append("CI 工作流")
    if any(path.startswith("dist/") for path in changed_paths):
        categories.append("构建产物")

    return categories


def evaluate_guardrails(changes: list[WorktreeChange]) -> list[GuardrailFinding]:
    findings: list[GuardrailFinding] = []
    changed_paths = collect_changed_paths(changes)

    if any(is_structural_rule_change(change) for change in changes):
        missing = [
            path for path in SOURCE_RULE_METADATA_FILES if path not in changed_paths
        ]
        if missing:
            findings.append(
                GuardrailFinding(
                    level="error",
                    message=(
                        "本次包含 rules/{reject,direct,proxy,region}/ 下 .list 的新增、删除或重命名，"
                        f"必须同步更新 {', '.join(missing)}。"
                    ),
                )
            )

    if STYLE_DOC_PATH in changed_paths:
        missing = [path for path in ("AGENTS.md", "README.md") if path not in changed_paths]
        if missing:
            findings.append(
                GuardrailFinding(
                    level="error",
                    message=(
                        f"修改 {STYLE_DOC_PATH} 时，必须同步更新 {', '.join(missing)}，"
                        "避免规则编排约定只停留在单份文档。"
                    ),
                )
            )

    if any(is_source_rule_path(path) for path in changed_paths):
        public_docs_changed = {path for path in PUBLIC_DOC_BUNDLE if path in changed_paths}
        if not public_docs_changed:
            findings.append(
                GuardrailFinding(
                    level="warning",
                    message=(
                        "本次涉及源规则，请确认是否改变了默认对外规则入口、顺序、策略含义或公开模板行为；"
                        "若有，请同步更新 README.md、docs/usage-surge.md、docs/usage-mihomo.md 与两份公开模板。"
                    ),
                )
            )

    if any(path in BUILD_TOOL_PATHS for path in changed_paths) and "README.md" not in changed_paths:
        findings.append(
            GuardrailFinding(
                level="warning",
                message=(
                    "本次涉及构建或检查脚本，请确认 README.md 的构建/验证说明是否也需要同步。"
                ),
            )
        )

    public_bundle_changed = [path for path in PUBLIC_DOC_BUNDLE if path in changed_paths]
    non_readme_public_changes = [path for path in public_bundle_changed if path != "README.md"]
    if non_readme_public_changes and len(public_bundle_changed) < len(PUBLIC_DOC_BUNDLE):
        missing = [path for path in PUBLIC_DOC_BUNDLE if path not in changed_paths]
        findings.append(
            GuardrailFinding(
                level="warning",
                message=(
                    "本次只修改了部分公开说明或模板；请确认以下文件是否也需要联动："
                    f"{', '.join(missing)}。"
                ),
            )
        )

    return findings


def main() -> int:
    try:
        changes = collect_worktree_changes()
    except FileNotFoundError:
        print("[guardrails] 未找到 git，跳过变更联动检查。")
        return 0
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else str(exc)
        print(f"[guardrails] 读取 git 变更失败：{stderr}", file=sys.stderr)
        return 1

    if not changes:
        print("[guardrails] 当前工作区无本地变更。")
        return 0

    categories = classify_changes(changes)
    if categories:
        print(f"[guardrails] 变更分类：{', '.join(categories)}")
    else:
        print("[guardrails] 变更分类：未命中已知高风险类别")

    findings = evaluate_guardrails(changes)
    for finding in findings:
        print(f"[guardrails] {finding.level}: {finding.message}")

    errors = [finding for finding in findings if finding.level == "error"]
    if errors:
        print("[guardrails] 变更联动检查失败。", file=sys.stderr)
        return 1

    print("[guardrails] 变更联动检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
