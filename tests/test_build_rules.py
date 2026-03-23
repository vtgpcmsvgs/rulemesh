import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import build_rules  # noqa: E402


class DetectNonChineseCommentTests(unittest.TestCase):
    def test_detects_english_sentence(self) -> None:
        self.assertEqual(
            build_rules.detect_non_chinese_comment("# Alibaba Cloud Hong Kong SSH direct rules."),
            "Alibaba Cloud Hong Kong SSH direct rules.",
        )

    def test_detects_single_word_english_header(self) -> None:
        self.assertEqual(
            build_rules.detect_non_chinese_comment("# TODO"),
            "TODO",
        )

    def test_ignores_chinese_comment(self) -> None:
        self.assertIsNone(
            build_rules.detect_non_chinese_comment("# 阿里云香港 SSH TCP/22 直连规则。")
        )

    def test_ignores_url_reference(self) -> None:
        self.assertIsNone(
            build_rules.detect_non_chinese_comment(
                "# - https://github.com/privacy-protection-tools/anti-AD"
            )
        )

    def test_ignores_commented_rule(self) -> None:
        self.assertIsNone(
            build_rules.detect_non_chinese_comment("# DOMAIN,api.mini.wps.cn")
        )


class FindNonChineseCommentLinesTests(unittest.TestCase):
    def test_finds_only_english_comment_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "sample.list"
            path.write_text(
                "# 中文说明\n"
                "# English section title\n"
                "DOMAIN,example.com\n"
                "# DOMAIN,commented.example.com\n",
                encoding="utf-8",
            )

            self.assertEqual(
                build_rules.find_non_chinese_comment_lines(path),
                [(2, "English section title")],
            )


class TempRepoBuildRulesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.repo_root = Path(self.temp_dir.name)
        self.rules_root = self.repo_root / "rules"
        self.dist_root = self.repo_root / "dist"
        (self.rules_root / "direct").mkdir(parents=True, exist_ok=True)

    def patch_repo_paths(self):
        return patch.multiple(
            build_rules,
            ROOT=self.repo_root,
            RULES_ROOT=self.rules_root,
            DIST_ROOT=self.dist_root,
        )

    def test_utf8_bom_plain_rule_does_not_produce_warning(self) -> None:
        path = self.rules_root / "direct" / "bom.list"
        path.write_text("example.com\n", encoding="utf-8-sig")

        with self.patch_repo_paths():
            result = build_rules.build_source(path)

        self.assertEqual(result.outputs["surge_rules"], ["DOMAIN,example.com"])
        self.assertEqual(result.outputs["mihomo_classical"], ["DOMAIN,example.com"])
        self.assertEqual(result.warnings, [])

    def test_build_source_normalizes_target_specific_aliases(self) -> None:
        path = self.rules_root / "direct" / "ports.list"
        path.write_text(
            "DST-PORT,80\n"
            "AND,((PROCESS-NAME,chrome.exe),(DST-PORT,80))\n"
            "DEST-PORT,443\n"
            "AND,((PROCESS-NAME,firefox.exe),(DEST-PORT,443))\n",
            encoding="utf-8",
        )

        with self.patch_repo_paths():
            result = build_rules.build_source(path)

        self.assertEqual(
            result.outputs["surge_rules"],
            [
                "DEST-PORT,80",
                "AND,((PROCESS-NAME,chrome.exe),(DEST-PORT,80))",
                "DEST-PORT,443",
                "AND,((PROCESS-NAME,firefox.exe),(DEST-PORT,443))",
            ],
        )
        self.assertEqual(
            result.outputs["mihomo_classical"],
            [
                "DST-PORT,80",
                "AND,((PROCESS-NAME,chrome.exe),(DST-PORT,80))",
                "DST-PORT,443",
                "AND,((PROCESS-NAME,firefox.exe),(DST-PORT,443))",
            ],
        )
        self.assertEqual(result.warnings, [])

    def test_build_source_normalizes_src_ip_aliases_for_targets(self) -> None:
        path = self.rules_root / "direct" / "src_ip.list"
        path.write_text(
            "SRC-IP,198.51.100.0/24\n"
            "AND,((PROCESS-NAME,chrome.exe),(SRC-IP,198.51.100.0/24))\n"
            "SRC-IP-CIDR,203.0.113.0/24\n"
            "AND,((PROCESS-NAME,firefox.exe),(SRC-IP-CIDR,203.0.113.0/24))\n",
            encoding="utf-8",
        )

        with self.patch_repo_paths():
            result = build_rules.build_source(path)

        self.assertEqual(
            result.outputs["surge_rules"],
            [
                "SRC-IP,198.51.100.0/24",
                "AND,((PROCESS-NAME,chrome.exe),(SRC-IP,198.51.100.0/24))",
                "SRC-IP,203.0.113.0/24",
                "AND,((PROCESS-NAME,firefox.exe),(SRC-IP,203.0.113.0/24))",
            ],
        )
        self.assertEqual(
            result.outputs["mihomo_classical"],
            [
                "SRC-IP-CIDR,198.51.100.0/24",
                "AND,((PROCESS-NAME,chrome.exe),(SRC-IP-CIDR,198.51.100.0/24))",
                "SRC-IP-CIDR,203.0.113.0/24",
                "AND,((PROCESS-NAME,firefox.exe),(SRC-IP-CIDR,203.0.113.0/24))",
            ],
        )
        self.assertEqual(result.warnings, [])

    def test_include_cycle_raises_build_error(self) -> None:
        path_a = self.rules_root / "direct" / "a.list"
        path_b = self.rules_root / "direct" / "b.list"
        path_a.write_text("INCLUDE,direct/b.list\n", encoding="utf-8")
        path_b.write_text("INCLUDE,direct/a.list\n", encoding="utf-8")

        with self.patch_repo_paths():
            with self.assertRaises(build_rules.BuildError) as context:
                build_rules.expand_source_lines(path_a)

        self.assertIn("INCLUDE 循环引用", str(context.exception))

    def test_unsupported_mihomo_rule_emits_warning(self) -> None:
        parsed = build_rules.parse_line("PROTOCOL,ICMP")

        self.assertEqual(parsed.surge_rule, "PROTOCOL,ICMP")
        self.assertIsNone(parsed.mihomo_classical)
        self.assertEqual(
            parsed.warnings,
            ["mihomo does not support PROTOCOL,ICMP; kept only in Surge rules"],
        )


if __name__ == "__main__":
    unittest.main()
