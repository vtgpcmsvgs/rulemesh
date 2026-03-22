import sys
import tempfile
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
