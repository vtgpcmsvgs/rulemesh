"""运行态核对必须识别混合传输、旧代理残留和不可解析的系统状态。"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from check_android_vpn_runtime import audit_connectivity, package_uid


class AndroidVpnRuntimeTests(unittest.TestCase):
    def row(self, transport="CELLULAR|VPN", proxy="", uid=10001, state="CONNECTED"):
        return (f"  NetworkAgentInfo{{network{{200}} ni{{VPN {state} extra: }} "
                f"lp{{{proxy}}} nc{{[ Transports: {transport} Capabilities: INTERNET "
                f"OwnerUid: {uid} ]}} }}")

    def test_cellular_wifi_and_standalone_vpn_are_recognized(self):
        for transport in ("CELLULAR|VPN", "WIFI|VPN", "VPN"):
            with self.subTest(transport=transport):
                self.assertTrue(audit_connectivity(self.row(transport), 10001)["passed"])

    def test_saved_switch_cannot_override_residual_runtime_proxy(self):
        result = audit_connectivity(self.row(proxy="HttpProxy: [127.0.0.1] 7890"), 10001)
        self.assertFalse(result["passed"])
        self.assertTrue(result["vpn_http_proxy_present"])

    def test_history_and_another_apps_vpn_do_not_pass(self):
        history = "09-14 21:00:00 old " + self.row()
        self.assertFalse(audit_connectivity(history, 10001)["passed"])
        self.assertFalse(audit_connectivity(self.row(uid=10002), 10001)["passed"])
        current = self.row() + "\n" + "history " + self.row(proxy="HttpProxy: old")
        self.assertTrue(audit_connectivity(current, 10001)["passed"])

    def test_disconnected_and_missing_vpn_fail(self):
        for raw in ("", self.row(state="DISCONNECTED"), self.row(transport="CELLULAR")):
            self.assertFalse(audit_connectivity(raw, 10001)["passed"])

    def test_missing_owner_or_network_state_cannot_pass(self):
        for raw in (self.row().replace("OwnerUid: 10001", ""),
                    self.row().replace("ni{VPN CONNECTED extra: }", "")):
            self.assertFalse(audit_connectivity(raw, 10001)["passed"])

    def test_duplicate_active_networks_fail_and_null_proxy_is_empty(self):
        self.assertFalse(audit_connectivity(self.row() + "\n" + self.row(), 10001)["passed"])
        self.assertTrue(audit_connectivity(self.row(proxy="HttpProxy: null"), 10001)["passed"])

    def test_package_uid_is_unique_and_never_matches_a_similar_package(self):
        self.assertEqual(package_uid("package:com.follow.clash uid:10001\n"), 10001)
        for raw in ("package:com.follow.clash.other uid:10001\n", "",
                    "package:com.follow.clash uid:10001\npackage:com.follow.clash uid:10002\n"):
            with self.assertRaises(ValueError):
                package_uid(raw)


if __name__ == "__main__":
    unittest.main()
