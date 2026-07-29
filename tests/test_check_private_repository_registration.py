import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import check_private_repository_registration  # noqa: E402


class PrivateRepositoryRegistrationTests(unittest.TestCase):
    def create_valid_tree(self, root: Path) -> None:
        manifest = dict(check_private_repository_registration.EXPECTED_VALUES)
        (root / "private-repository.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (root / "docs").mkdir()
        references = check_private_repository_registration.REQUIRED_REFERENCES
        for relative_path, needles in references.items():
            path = root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n".join(needles) + "\n", encoding="utf-8")

    def test_valid_registration_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.create_valid_tree(root)

            self.assertEqual(
                check_private_repository_registration.validate_registration(root),
                [],
            )

    def test_unknown_manifest_field_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.create_valid_tree(root)
            path = root / "private-repository.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["token"] = "不允许在公开登记中保存凭据"
            path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            errors = check_private_repository_registration.validate_registration(root)

            self.assertTrue(any("未允许字段" in error for error in errors))

    def test_missing_document_reference_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.create_valid_tree(root)
            (root / "README.md").write_text(
                "private-repository.json\n",
                encoding="utf-8",
            )

            errors = check_private_repository_registration.validate_registration(root)

            self.assertTrue(any("README.md" in error for error in errors))

    def test_fixed_current_path_outside_resolver_rule_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.create_valid_tree(root)
            path = root / "docs" / "legacy.md"
            path.write_text(
                "%USERPROFILE%\\Desktop\\rulemesh-local\\current\\config.yaml\n",
                encoding="utf-8",
            )

            errors = check_private_repository_registration.validate_registration(root)

            self.assertTrue(any("current 写成固定路径" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
