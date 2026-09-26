"""防止正则词边界被 YAML 解码成退格，诊断不泄露标量内容。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from check_yaml_controls import check


class YamlControlTests(unittest.TestCase):
    def test_rejects_decoded_controls(self):
        for value in (r'filter: "\bus\b"', r'filter: "\x08"', r'filter: "\u0008"', 'filter: "\x08"'):
            self.assertTrue(check(value))

    def test_accepts_literal_word_boundaries(self):
        self.assertEqual(check(r'filter: "\\bus\\b"'), [])
        self.assertEqual(check("filter: '\\bus\\b'"), [])

    def test_private_value_not_in_diagnostic(self):
        self.assertNotIn('SECRET', str(check(r'filter: "SECRET\b"')))

    def test_baseline_cannot_bypass_guard(self):
        import tempfile
        from check_dns_safety import validate_path
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'profile.yaml'
            path.write_text('# RuleMesh 性能基线：2026-09-09\nfilter: "SECRET\\b"\n', encoding='utf-8')
            result = validate_path(path)
            self.assertTrue(result)
            self.assertIn('控制字符', result[0].message)
            self.assertNotIn('SECRET', str(result))
