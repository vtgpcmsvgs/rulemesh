"""运行态核对必须识别混合传输、旧代理残留和不可解析的系统状态。"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from check_android_vpn_runtime import audit_chatgpt_tls, audit_connectivity, package_uid, audit_google_search


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

    def test_trusted_tls_with_forbidden_http_is_transport_evidence_only(self):
        result = audit_chatgpt_tls("RM_CHATGPT_TLS 403 0 0.633475\n")
        self.assertTrue(result["passed"])
        self.assertEqual(result["http_status"], 403)

    def test_zero_verify_result_without_a_handshake_cannot_pass(self):
        for raw in ("RM_CHATGPT_TLS 000 0 0.000000\n",
                    "curl: (28) timeout\nRM_CHATGPT_TLS 000 0 0.000000\n",
                    "curl: (35) TLS connect error\nRM_CHATGPT_TLS 000 1 0.000000\n",
                    "RM_CHATGPT_TLS 403 20 0.600000\n",
                    "curl: (28) timeout\nRM_CHATGPT_TLS 200 0 0.600000\n"):
            with self.subTest(raw=raw):
                self.assertFalse(audit_chatgpt_tls(raw)["passed"])

    def test_missing_malformed_or_duplicate_tls_evidence_fails(self):
        for raw in ("", "curl: not found", "RM_CHATGPT_TLS bad\n",
                    "RM_CHATGPT_TLS 200 0 0.5\n" * 2):
            self.assertFalse(audit_chatgpt_tls(raw)["passed"])

    def test_failed_command_cannot_be_hidden_by_a_valid_http_marker(self):
        result = audit_chatgpt_tls("RM_CHATGPT_TLS 200 0 0.5\n", command_exit_code=28)
        self.assertFalse(result["passed"])
        self.assertEqual(result["command_exit_code"], 28)

    def test_google_mobile_redirect_requires_com_search_and_trusted_tls(self):
        body = '<html><form action="/search"><textarea name="q"></textarea></form></html>\n'
        good = body + 'RM_GOOGLE_SEARCH 200 0 0.5 1 https://www.google.com/\n'
        self.assertTrue(audit_google_search(good)["passed"])
        for raw in (good.replace('www.google.com/', 'www.google.cn/m'),
                    good.replace('www.google.com/', 'www.google.com.evil.invalid/'),
                    good.replace('https:', 'http:'), good.replace('200 0', '404 0'),
                    good.replace('200 0', '200 20'), good.replace('0.5', '0.0'),
                    good.replace(body, ''), good + good, '', 'curl: (28) timeout\n' + good):
            with self.subTest(raw=raw):
                self.assertFalse(audit_google_search(raw)["passed"])
        self.assertFalse(audit_google_search(good, 28)["passed"])

    def test_google_challenge_hidden_query_or_script_is_not_a_search_form(self):
        marker = '\nRM_GOOGLE_SEARCH 200 0 0.5 0 https://www.google.com/\n'
        for body in ('<form action="/search"><input type="hidden" name="q"></form>',
                     '<form action="/search"><input data-name="q"></form>',
                     '<script>let s=\'<form action="/search"><textarea name="q"></textarea></form>\'</script>',
                     '<form action="/sorry/"><textarea name="q"></textarea></form>',
                     '<form action="https://private.invalid/search"><input name="q"></form>'):
            self.assertFalse(audit_google_search(body + marker)["passed"])

    def test_google_probe_redacts_unknown_url_and_query(self):
        raw = '<input name="q">\nRM_GOOGLE_SEARCH 200 0 0.5 1 https://private.invalid/?token=secret\n'
        result = audit_google_search(raw)
        self.assertEqual(result["final_host_role"], 'other_or_unknown')
        self.assertNotIn('private.invalid', str(result))
        self.assertNotIn('secret', str(result))

    def test_real_search_cannot_be_satisfied_by_a_homepage_redirect(self):
        body = '<form action="/search"><textarea name="q"></textarea></form>\n'
        home = body + 'RM_GOOGLE_SEARCH 200 0 0.5 0 https://www.google.com/\n'
        self.assertTrue(audit_google_search(home, expected_path='/')['passed'])
        self.assertFalse(audit_google_search(home, expected_path='/search')['passed'])
        search = home.replace('https://www.google.com/', 'https://www.google.com/search?q=fixture')
        self.assertTrue(audit_google_search(search, expected_path='/search')['passed'])


if __name__ == "__main__":
    unittest.main()
