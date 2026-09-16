"""用脱敏配置验证官网、订阅专用域名和共用域名的不同用途。"""

from pathlib import Path
import hashlib
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/sync_private_subscription_direct.ps1"
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")
SURGE_NAMES = [
    "rulemesh-substore-surge-personal.conf",
    "rulemesh-substore-surge-personal-company.conf",
    "rulemesh-substore-surge-work-whitelist.conf",
]
MIHOMO_NAMES = [
    "rulemesh-substore-mihomo-flclash-desktop.yaml",
    "rulemesh-substore-mihomo-flclash-android.yaml",
]
SOURCE = """# 官网与订阅共用域名
DOMAIN,shared.example,SHARED
# 订阅专用域名
DOMAIN,subscription.example,SUBSCRIPTION
# 官网专用域名
DOMAIN,website.example,WEBSITE
DOMAIN,例子.example,WEBSITE
"""
SURGE = """# 注释里的 [Rule] 不是节标题。
[Proxy Group]
自动组 = select, DIRECT
[Rule]
RULE-SET,https://raw.githubusercontent.com/example/repo/main/proxy/onepassword_proxy.list,"自动组"
# >>> PRIVATE_SUBSCRIPTION_DIRECT_START
DOMAIN,old.example,DIRECT
# <<< PRIVATE_SUBSCRIPTION_DIRECT_END
FINAL,DIRECT
"""
MIHOMO = """proxy-providers:
  example:
    type: http
    url: https://shared.example/subscription
    proxy: DIRECT
rules:
  - RULE-SET,proxy_onepassword,自动组
  # >>> PRIVATE_SUBSCRIPTION_DIRECT_START
  - DOMAIN,old.example,DIRECT
  # <<< PRIVATE_SUBSCRIPTION_DIRECT_END
  - MATCH,DIRECT
"""


@unittest.skipUnless(POWERSHELL, "需要 PowerShell 执行实际同步器")
class PrivateSubscriptionSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        shutil.copyfile(SCRIPT, self.directory / SCRIPT.name)
        self.write("private_subscription_direct.list", SOURCE)
        for name in SURGE_NAMES:
            self.write(name, SURGE)
        for name in MIHOMO_NAMES:
            self.write(name, MIHOMO)

    def write(self, name, text):
        (self.directory / name).write_bytes(text.encode("utf-8"))

    def run_sync(self, target="all"):
        return subprocess.run(
            [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
             str(self.directory / SCRIPT.name), "-Target", target],
            capture_output=True, timeout=30,
        )

    def hashes(self):
        return {name: hashlib.sha256((self.directory / name).read_bytes()).digest()
                for name in SURGE_NAMES + MIHOMO_NAMES}

    def test_roles_preserve_browser_proxy_and_client_direct(self):
        result = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        for name in SURGE_NAMES:
            text = (self.directory / name).read_text("utf-8")
            for browser in ("Google Chrome", "Safari", "Microsoft Edge", "Firefox"):
                self.assertIn(f"AND,((PROCESS-NAME,{browser}),(DOMAIN,shared.example)),自动组", text)
            self.assertIn("DOMAIN,shared.example,DIRECT", text)
            self.assertIn("DOMAIN,subscription.example,DIRECT", text)
            self.assertIn('DOMAIN,website.example,"自动组"', text)
            self.assertIn('DOMAIN,xn--fsqu00a.example,"自动组"', text)
            self.assertFalse(any("AND," in line and
                                 ("subscription.example" in line or "website.example" in line)
                                 for line in text.splitlines()))
        for name in MIHOMO_NAMES:
            text = (self.directory / name).read_text("utf-8")
            self.assertIn("- DOMAIN,shared.example,自动组", text)
            self.assertIn("- DOMAIN,website.example,自动组", text)
            self.assertIn("- DOMAIN,subscription.example,DIRECT", text)
            self.assertIn("    proxy: DIRECT", text)
            self.assertNotIn("PROCESS-NAME", text)
        first = self.hashes()
        self.assertEqual(self.run_sync().returncode, 0)
        self.assertEqual(first, self.hashes())

    def test_explicit_target_preserves_other_client(self):
        for target, untouched in (("surge", MIHOMO_NAMES), ("mihomo", SURGE_NAMES)):
            before = self.hashes()
            self.assertEqual(self.run_sync(target).returncode, 0)
            after = self.hashes()
            self.assertTrue(all(before[name] == after[name] for name in untouched))

    def test_legacy_two_fields_keep_shared_semantics(self):
        self.write("private_subscription_direct.list", "DOMAIN,shared.example\nIP-CIDR,192.0.2.7\n")
        self.assertEqual(self.run_sync().returncode, 0)
        surge = (self.directory / SURGE_NAMES[0]).read_text("utf-8")
        self.assertIn("AND,((PROCESS-NAME,Google Chrome),(DOMAIN,shared.example)),自动组", surge)
        self.assertIn("IP-CIDR,192.0.2.7/32,DIRECT,no-resolve", surge)
        mihomo = (self.directory / MIHOMO_NAMES[0]).read_text("utf-8")
        self.assertIn("- IP-CIDR,192.0.2.7/32,自动组,no-resolve", mihomo)

    def test_bad_last_target_cannot_partially_update_earlier_files(self):
        bad = MIHOMO.replace("PRIVATE_SUBSCRIPTION_DIRECT_END", "BROKEN_END")
        self.write(MIHOMO_NAMES[-1], bad)
        before = self.hashes()
        self.assertNotEqual(self.run_sync().returncode, 0)
        self.assertEqual(before, self.hashes())

    def test_duplicate_marker_is_rejected_without_changes(self):
        self.write(SURGE_NAMES[-1], SURGE + "# >>> PRIVATE_SUBSCRIPTION_DIRECT_START\n")
        before = self.hashes()
        self.assertNotEqual(self.run_sync().returncode, 0)
        self.assertEqual(before, self.hashes())

    def test_invalid_or_duplicate_roles_fail_without_exposing_values(self):
        for source in (
            "DOMAIN,private-secret.example,UNKNOWN\n",
            "DOMAIN,例子.example,WEBSITE\nDOMAIN,xn--fsqu00a.example,SUBSCRIPTION\n",
        ):
            with self.subTest(source_type=source.count("\n")):
                self.write("private_subscription_direct.list", source)
                before = self.hashes()
                result = self.run_sync()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(before, self.hashes())
                self.assertNotIn(b"private-secret.example", result.stdout + result.stderr)

    def test_marker_outside_rules_section_is_rejected(self):
        self.write(SURGE_NAMES[0], SURGE.replace("[Rule]\n", "") + "[Rule]\nFINAL,DIRECT\n")
        before = self.hashes()
        self.assertNotEqual(self.run_sync().returncode, 0)
        self.assertEqual(before, self.hashes())


if __name__ == "__main__":
    unittest.main()
