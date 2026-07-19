from __future__ import annotations

import os
import plistlib
import signal
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "tools" / "install_surge_monitor_macos.sh"
LABEL = "com.rulemesh.surge-monitor"


class InstallSurgeMonitorMacosTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="rulemesh 安装测试 ")
        self.addCleanup(self.temp_dir.cleanup)
        temp_root = Path(self.temp_dir.name)

        self.repo_root = temp_root / "仓库 & '空格'"
        tools_dir = self.repo_root / "tools"
        tools_dir.mkdir(parents=True)
        self.installer = tools_dir / INSTALLER.name
        shutil.copy2(INSTALLER, self.installer)
        (tools_dir / "monitor_surge.py").write_text(
            "# 测试占位文件\n",
            encoding="utf-8",
        )
        dns_dir = self.repo_root / "rules" / "dns"
        dns_dir.mkdir(parents=True)
        (dns_dir / "cn_dns_domains.list").write_text(
            "# 测试清单\n.cn\n",
            encoding="utf-8",
        )

        self.home = temp_root / "用户 & 空格"
        self.home.mkdir()
        self.fake_bin = temp_root / "fake-bin"
        self.fake_bin.mkdir()
        self.launchctl_log = temp_root / "launchctl.log"
        self.launchctl_state = temp_root / "launchctl.state"
        self.plutil_log = temp_root / "plutil.log"
        self.write_fake_commands()

    @property
    def plist_path(self) -> Path:
        return self.home / "Library" / "LaunchAgents" / f"{LABEL}.plist"

    @property
    def state_dir(self) -> Path:
        return (
            self.home
            / "Library"
            / "Application Support"
            / "RuleMesh"
            / "surge-monitor"
        )

    def write_executable(self, name: str, content: str) -> None:
        path = self.fake_bin / name
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)

    def write_fake_commands(self) -> None:
        self.write_executable(
            "launchctl",
            "#!/bin/sh\n"
            "printf '%s\\n' \"$*\" >>\"$RULEMESH_TEST_LAUNCHCTL_LOG\"\n"
            "case \"$1\" in\n"
            "  print)\n"
            "    [ \"$(cat \"$RULEMESH_TEST_LAUNCHCTL_STATE\")\" = \"1\" ] || exit 1\n"
            "    printf '\\tstate = running\\n' ;;\n"
            "  bootout)\n"
            "    [ \"${RULEMESH_TEST_BOOTOUT_FAIL:-0}\" != \"1\" ] || exit 1\n"
            "    printf '0\\n' >\"$RULEMESH_TEST_LAUNCHCTL_STATE\" ;;\n"
            "  bootstrap)\n"
            "    [ \"${RULEMESH_TEST_BOOTSTRAP_FAIL:-0}\" != \"1\" ] || exit 1\n"
            "    printf '1\\n' >\"$RULEMESH_TEST_LAUNCHCTL_STATE\" ;;\n"
            "  *) exit 2 ;;\n"
            "esac\n",
        )
        self.write_executable(
            "plutil",
            "#!/bin/sh\n"
            "printf '%s\\n' \"$*\" >>\"$RULEMESH_TEST_PLUTIL_LOG\"\n"
            "if [ \"${RULEMESH_TEST_LINT_FAIL:-0}\" = \"1\" ]; then\n"
            "  printf '测试：plist 无效\\n' >&2\n"
            "  exit 1\n"
            "fi\n",
        )

    def installer_environment(
        self,
        *,
        loaded: bool = False,
        lint_fail: bool = False,
        bootout_fail: bool = False,
        bootstrap_fail: bool = False,
        health_wait_seconds: int = 0,
    ) -> dict[str, str]:
        self.launchctl_state.write_text("1\n" if loaded else "0\n", encoding="utf-8")
        env = os.environ.copy()
        env.update(
            {
                "HOME": str(self.home),
                "PATH": f"{self.fake_bin}:{env.get('PATH', '')}",
                "RULEMESH_TEST_LAUNCHCTL_LOG": str(self.launchctl_log),
                "RULEMESH_TEST_PLUTIL_LOG": str(self.plutil_log),
                "RULEMESH_TEST_LAUNCHCTL_STATE": str(self.launchctl_state),
                "RULEMESH_TEST_LINT_FAIL": "1" if lint_fail else "0",
                "RULEMESH_TEST_BOOTOUT_FAIL": "1" if bootout_fail else "0",
                "RULEMESH_TEST_BOOTSTRAP_FAIL": "1" if bootstrap_fail else "0",
                "RULEMESH_MONITOR_HEALTH_WAIT_SECONDS": str(health_wait_seconds),
            }
        )
        return env

    def run_installer(
        self,
        *args: str,
        loaded: bool = False,
        lint_fail: bool = False,
        bootout_fail: bool = False,
        bootstrap_fail: bool = False,
        script_path: Path | None = None,
        shell: str = "/bin/sh",
    ) -> subprocess.CompletedProcess[str]:
        env = self.installer_environment(
            loaded=loaded,
            lint_fail=lint_fail,
            bootout_fail=bootout_fail,
            bootstrap_fail=bootstrap_fail,
        )
        return subprocess.run(
            [shell, str(script_path or self.installer), *args],
            cwd=self.home,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def read_launchctl_calls(self) -> list[str]:
        if not self.launchctl_log.exists():
            return []
        return self.launchctl_log.read_text(encoding="utf-8").splitlines()

    def seed_existing_install(self) -> tuple[Path, Path]:
        self.plist_path.parent.mkdir(parents=True, exist_ok=True)
        self.plist_path.write_text("原有 plist\n", encoding="utf-8")
        monitor = self.state_dir / "runtime" / "tools" / "monitor_surge.py"
        dns_list = self.state_dir / "runtime" / "rules" / "dns" / "cn_dns_domains.list"
        monitor.parent.mkdir(parents=True, exist_ok=True)
        dns_list.parent.mkdir(parents=True, exist_ok=True)
        monitor.write_text("# 原有监控\n", encoding="utf-8")
        dns_list.write_text("# 原有清单\n", encoding="utf-8")
        return monitor, dns_list

    def test_install_writes_valid_plist_and_bootstraps_gui_domain(self) -> None:
        result = self.run_installer()

        self.assertEqual(result.returncode, 0, result.stderr)
        with self.plist_path.open("rb") as stream:
            plist = plistlib.load(stream)

        expected_runtime = self.state_dir / "runtime"
        expected_monitor = expected_runtime / "tools" / "monitor_surge.py"
        self.assertEqual(plist["Label"], LABEL)
        self.assertEqual(
            plist["ProgramArguments"],
            [
                "/usr/bin/python3",
                str(expected_monitor),
                "--config",
                str(self.state_dir / "config.json"),
                "daemon",
            ],
        )
        self.assertEqual(plist["WorkingDirectory"], str(expected_runtime))
        self.assertIs(plist["RunAtLoad"], True)
        self.assertEqual(plist["KeepAlive"], {"SuccessfulExit": False})
        self.assertGreaterEqual(plist["ThrottleInterval"], 10)
        self.assertEqual(
            plist["StandardOutPath"],
            str(self.state_dir / "monitor.stdout.log"),
        )
        self.assertEqual(
            plist["StandardErrorPath"],
            str(self.state_dir / "monitor.stderr.log"),
        )
        self.assertTrue(self.state_dir.is_dir())
        self.assertEqual(self.state_dir.stat().st_mode & 0o777, 0o700)
        self.assertEqual(
            (self.state_dir / "monitor.stdout.log").stat().st_mode & 0o777,
            0o600,
        )
        self.assertEqual(
            (self.state_dir / "monitor.stderr.log").stat().st_mode & 0o777,
            0o600,
        )
        self.assertEqual(
            expected_monitor.read_text(encoding="utf-8"),
            "# 测试占位文件\n",
        )
        self.assertEqual(
            (expected_runtime / "rules" / "dns" / "cn_dns_domains.list").read_text(
                encoding="utf-8"
            ),
            "# 测试清单\n.cn\n",
        )

        service_target = f"gui/{os.getuid()}/{LABEL}"
        self.assertEqual(
            self.read_launchctl_calls(),
            [
                f"print {service_target}",
                f"bootstrap gui/{os.getuid()} {self.plist_path}",
                f"print {service_target}",
            ],
        )
        self.assertIn("-lint", self.plutil_log.read_text(encoding="utf-8"))

    def test_install_resolves_symlink_to_absolute_repository_path(self) -> None:
        link_dir = Path(self.temp_dir.name) / "快捷方式"
        link_dir.mkdir()
        installer_link = link_dir / "安装监控.sh"
        installer_link.symlink_to(self.installer)

        result = self.run_installer(script_path=installer_link)

        self.assertEqual(result.returncode, 0, result.stderr)
        with self.plist_path.open("rb") as stream:
            plist = plistlib.load(stream)
        self.assertEqual(
            plist["ProgramArguments"][1],
            str(self.state_dir / "runtime" / "tools" / "monitor_surge.py"),
        )

    def test_install_is_compatible_with_zsh_function_argzero_behavior(self) -> None:
        result = self.run_installer(shell="/bin/zsh")

        self.assertEqual(result.returncode, 0, result.stderr)
        with self.plist_path.open("rb") as stream:
            plist = plistlib.load(stream)
        self.assertEqual(
            plist["ProgramArguments"][1],
            str(self.state_dir / "runtime" / "tools" / "monitor_surge.py"),
        )

    def test_reinstall_boots_out_only_exact_label_before_bootstrap(self) -> None:
        result = self.run_installer(loaded=True)

        self.assertEqual(result.returncode, 0, result.stderr)
        service_target = f"gui/{os.getuid()}/{LABEL}"
        self.assertEqual(
            self.read_launchctl_calls(),
            [
                f"print {service_target}",
                f"bootout {service_target}",
                f"bootstrap gui/{os.getuid()} {self.plist_path}",
                f"print {service_target}",
            ],
        )

    def test_lint_failure_preserves_existing_plist_and_skips_launchctl(self) -> None:
        self.plist_path.parent.mkdir(parents=True)
        self.plist_path.write_text("原有 plist\n", encoding="utf-8")

        result = self.run_installer(lint_fail=True)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("原有 plist 未被替换", result.stderr)
        self.assertEqual(
            self.plist_path.read_text(encoding="utf-8"),
            "原有 plist\n",
        )
        self.assertEqual(self.read_launchctl_calls(), [])
        self.assertEqual(
            list(self.plist_path.parent.glob(f".{LABEL}.plist.*")),
            [],
        )

    def test_python_preflight_failure_preserves_existing_service(self) -> None:
        monitor, dns_list = self.seed_existing_install()
        (self.repo_root / "tools" / "monitor_surge.py").write_text(
            "def broken(:\n",
            encoding="utf-8",
        )

        result = self.run_installer(loaded=True)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("语法预检", result.stderr)
        self.assertEqual(self.plist_path.read_text(encoding="utf-8"), "原有 plist\n")
        self.assertEqual(monitor.read_text(encoding="utf-8"), "# 原有监控\n")
        self.assertEqual(dns_list.read_text(encoding="utf-8"), "# 原有清单\n")
        self.assertEqual(self.read_launchctl_calls(), [])

    def test_bootstrap_failure_restores_existing_runtime_and_plist(self) -> None:
        monitor, dns_list = self.seed_existing_install()

        result = self.run_installer(loaded=True, bootstrap_fail=True)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("文件已恢复", result.stderr)
        self.assertEqual(self.plist_path.read_text(encoding="utf-8"), "原有 plist\n")
        self.assertEqual(monitor.read_text(encoding="utf-8"), "# 原有监控\n")
        self.assertEqual(dns_list.read_text(encoding="utf-8"), "# 原有清单\n")
        service_target = f"gui/{os.getuid()}/{LABEL}"
        self.assertEqual(
            self.read_launchctl_calls(),
            [
                f"print {service_target}",
                f"bootout {service_target}",
                f"bootstrap gui/{os.getuid()} {self.plist_path}",
                f"bootstrap gui/{os.getuid()} {self.plist_path}",
            ],
        )

    def test_new_install_bootstrap_failure_removes_staged_runtime_and_plist(self) -> None:
        result = self.run_installer(bootstrap_fail=True)

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.plist_path.exists())
        self.assertFalse(
            (self.state_dir / "runtime" / "tools" / "monitor_surge.py").exists()
        )
        self.assertFalse(
            (self.state_dir / "runtime" / "rules" / "dns" / "cn_dns_domains.list").exists()
        )

    def test_post_bootstrap_health_failure_restores_existing_install(self) -> None:
        monitor, dns_list = self.seed_existing_install()
        (self.repo_root / "tools" / "monitor_surge.py").write_text(
            "raise SystemExit(2)\n",
            encoding="utf-8",
        )

        result = self.run_installer(loaded=True)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("健康检查失败", result.stderr)
        self.assertEqual(self.plist_path.read_text(encoding="utf-8"), "原有 plist\n")
        self.assertEqual(monitor.read_text(encoding="utf-8"), "# 原有监控\n")
        self.assertEqual(dns_list.read_text(encoding="utf-8"), "# 原有清单\n")

    def test_signal_after_swap_restores_existing_install(self) -> None:
        monitor, dns_list = self.seed_existing_install()
        env = self.installer_environment(loaded=True, health_wait_seconds=2)
        process = subprocess.Popen(
            ["/bin/sh", str(self.installer)],
            cwd=self.home,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        service_target = f"gui/{os.getuid()}/{LABEL}"
        expected_bootstrap = f"bootstrap gui/{os.getuid()} {self.plist_path}"
        deadline = time.time() + 5
        while time.time() < deadline:
            if expected_bootstrap in self.read_launchctl_calls():
                break
            time.sleep(0.05)
        else:
            process.kill()
            self.fail("安装器未进入 bootstrap 后健康等待阶段")

        process.send_signal(signal.SIGTERM)
        _stdout, stderr = process.communicate(timeout=5)

        self.assertNotEqual(process.returncode, 0)
        self.assertIn("安装未提交", stderr)
        self.assertEqual(self.plist_path.read_text(encoding="utf-8"), "原有 plist\n")
        self.assertEqual(monitor.read_text(encoding="utf-8"), "# 原有监控\n")
        self.assertEqual(dns_list.read_text(encoding="utf-8"), "# 原有清单\n")
        self.assertEqual(self.launchctl_state.read_text(encoding="utf-8"), "1\n")
        self.assertGreaterEqual(
            self.read_launchctl_calls().count(f"bootstrap gui/{os.getuid()} {self.plist_path}"),
            2,
        )

    def test_uninstall_removes_only_plist_and_preserves_state(self) -> None:
        self.plist_path.parent.mkdir(parents=True)
        self.plist_path.write_text("测试 plist\n", encoding="utf-8")
        self.state_dir.mkdir(parents=True)
        history = self.state_dir / "history.jsonl"
        history.write_text("保留\n", encoding="utf-8")

        result = self.run_installer("--uninstall", loaded=True)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.plist_path.exists())
        self.assertEqual(history.read_text(encoding="utf-8"), "保留\n")
        service_target = f"gui/{os.getuid()}/{LABEL}"
        self.assertEqual(
            self.read_launchctl_calls(),
            [f"print {service_target}", f"bootout {service_target}"],
        )
        self.assertIn("状态和日志已保留", result.stdout)

    def test_uninstall_bootout_failure_preserves_plist_and_state(self) -> None:
        self.plist_path.parent.mkdir(parents=True)
        self.plist_path.write_text("测试 plist\n", encoding="utf-8")
        self.state_dir.mkdir(parents=True)
        history = self.state_dir / "history.jsonl"
        history.write_text("保留\n", encoding="utf-8")

        result = self.run_installer(
            "--uninstall",
            loaded=True,
            bootout_fail=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("plist 未删除", result.stderr)
        self.assertTrue(self.plist_path.exists())
        self.assertTrue(history.exists())


if __name__ == "__main__":
    unittest.main()
