from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REGISTRATION_PATH = "private-repository.json"
DOCUMENTATION_PATH = "docs/private-repository-bootstrap.md"
EXPECTED_KEYS = {
    "schema_version",
    "repository",
    "clone_url",
    "visibility",
    "default_branch",
    "windows_checkout",
    "current_config_candidates",
    "documentation",
}
EXPECTED_VALUES: dict[str, Any] = {
    "schema_version": 1,
    "repository": "vtgpcmsvgs/rulemesh-local",
    "clone_url": "https://github.com/vtgpcmsvgs/rulemesh-local.git",
    "visibility": "private",
    "default_branch": "main",
    "windows_checkout": r"%USERPROFILE%\Desktop\rulemesh-local",
    "current_config_candidates": ["current", "."],
    "documentation": DOCUMENTATION_PATH,
}
REQUIRED_REFERENCES = {
    "AGENTS.md": (
        "private-repository.json",
        "vtgpcmsvgs/rulemesh-local",
        "本机不存在",
    ),
    "README.md": (
        "private-repository.json",
        "docs/private-repository-bootstrap.md",
        "vtgpcmsvgs/rulemesh-local",
    ),
    DOCUMENTATION_PATH: (
        "private-repository.json",
        "vtgpcmsvgs/rulemesh-local",
        "gh repo clone",
        "origin/main...main",
    ),
}
FIXED_CURRENT_LITERAL = r"%USERPROFILE%\Desktop\rulemesh-local\current"


def validate_registration(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    manifest_path = root / REGISTRATION_PATH
    if not manifest_path.is_file():
        return [f"缺少私人仓库登记文件：{REGISTRATION_PATH}"]

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"无法读取私人仓库登记文件：{exc}"]

    if not isinstance(manifest, dict):
        return ["私人仓库登记文件顶层必须是 JSON 对象。"]

    actual_keys = set(manifest)
    missing_keys = sorted(EXPECTED_KEYS - actual_keys)
    unknown_keys = sorted(actual_keys - EXPECTED_KEYS)
    if missing_keys:
        errors.append(f"私人仓库登记缺少字段：{', '.join(missing_keys)}")
    if unknown_keys:
        errors.append(f"私人仓库登记包含未允许字段：{', '.join(unknown_keys)}")

    for key, expected in EXPECTED_VALUES.items():
        if key in manifest and manifest[key] != expected:
            errors.append(f"私人仓库登记字段 {key} 与预期不一致。")

    for relative_path, needles in REQUIRED_REFERENCES.items():
        path = root / relative_path
        if not path.is_file():
            errors.append(f"缺少私人仓库发现说明：{relative_path}")
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"无法读取 {relative_path}：{exc}")
            continue
        missing = [needle for needle in needles if needle not in content]
        if missing:
            errors.append(
                f"{relative_path} 缺少私人仓库发现关键字：{', '.join(missing)}"
            )

    documentation_paths = [root / "AGENTS.md", root / "README.md"]
    docs_root = root / "docs"
    if docs_root.is_dir():
        documentation_paths.extend(
            path for path in docs_root.rglob("*") if path.is_file()
        )
    for path in documentation_paths:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            continue
        relative_path = path.relative_to(root).as_posix()
        for line_number, line in enumerate(lines, start=1):
            if FIXED_CURRENT_LITERAL not in line:
                continue
            is_resolver_rule = (
                relative_path == "AGENTS.md"
                and "优先使用" in line
                and "仓库根目录" in line
            )
            if not is_resolver_rule:
                errors.append(
                    f"{relative_path}:{line_number} 把 current 写成固定路径；"
                    "应改为解析后的私人当前配置目录。"
                )

    return errors


def main() -> int:
    errors = validate_registration()
    if errors:
        for error in errors:
            print(f"[private-repository] error: {error}", file=sys.stderr)
        print("[private-repository] 私人仓库登记检查失败。", file=sys.stderr)
        return 1

    print("[private-repository] 私人仓库登记与跨机器发现说明检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
