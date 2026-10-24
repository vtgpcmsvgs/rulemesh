"""只读核对 Android 实际 VPN，避免把保存的开关误当成已经生效。"""
from pathlib import Path
from html.parser import HTMLParser
import argparse
import json
import re
import shlex
import subprocess
from urllib.parse import urlsplit

PACKAGE = "com.follow.clash"
CHATGPT_TLS_COMMAND = (
    'curl --noproxy "*" --connect-timeout 3 --max-time 5 '
    '--silent --show-error --head --output /dev/null '
    '--write-out "\\nRM_CHATGPT_TLS %{http_code} %{ssl_verify_result} %{time_appconnect}\\n" '
    'https://android.chat.openai.com/'
)
GOOGLE_SEARCH_COMMAND = (
    'curl --noproxy "*" --connect-timeout 4 --max-time 12 '
    '--silent --show-error --location --max-redirs 5 --compressed '
    '--proto =https --proto-redir =https '
    '--user-agent "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/142.0.0.0 Mobile Safari/537.36" '
    '--write-out "\\nRM_GOOGLE_SEARCH %{http_code} %{ssl_verify_result} '
    '%{time_appconnect} %{num_redirects} %{url_effective}\\n" '
    'https://www.google.com/'
)


class _GoogleSearchForm(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_search_form = False
        self.present = False

    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        if tag == "form":
            try:
                action = urlsplit(fields.get("action") or "")
                self.in_search_form = action.path == "/search" and action.hostname in {None, "google.com", "www.google.com"}
            except ValueError:
                self.in_search_form = False
        if self.in_search_form and fields.get("name") == "q" and (
                tag == "textarea" or tag == "input" and (fields.get("type") or "text").lower() in {"text", "search"}):
            self.present = True

    def handle_endtag(self, tag):
        if tag == "form":
            self.in_search_form = False


def audit_google_search(raw: str, command_exit_code: int = 0, *, expected_path: str | None = None) -> dict:
    """移动 UA 跟随跳转并要求真实搜索表单；正文/完整 URL 仅在内存中解析。"""
    markers = list(re.finditer(
        r"^RM_GOOGLE_SEARCH (\d{3}) (\d+) (\d+(?:\.\d+)?) (\d+) (\S+)\s*$", raw, re.M))
    status, verification, handshake, redirects, final_host = None, None, 0.0, None, None
    https = search = False
    path_matches = expected_path is None
    if len(markers) == 1:
        marker = markers[0]
        status, verification = int(marker[1]), int(marker[2])
        handshake, redirects = float(marker[3]), int(marker[4])
        try:
            url = urlsplit(marker[5])
            final_host, https = url.hostname, url.scheme == "https"
            path_matches = expected_path is None or url.path == expected_path
        except ValueError:
            pass
        body = raw[:marker.start()]
        form = _GoogleSearchForm()
        form.feed(body)
        search = form.present
    curl_errors = re.findall(r"curl: \((\d+)\)", raw)
    passed = (command_exit_code == 0 and len(markers) == 1 and not curl_errors
              and status == 200 and verification == 0 and handshake > 0 and https
              and final_host in {"google.com", "www.google.com"} and search and path_matches)
    # 只输出固定主机角色，恶意/未知跳转中的主机也不得未经脱敏直接输出。
    role = "google_com" if final_host in {"google.com", "www.google.com"} else (
        "google_cn" if final_host and (final_host == "google.cn" or final_host.endswith(".google.cn")) else "other_or_unknown")
    return {"http_status": status, "certificate_verify_result": verification,
            "tls_handshake_completed": handshake > 0, "redirect_count": redirects,
            "final_host_role": role, "search_form_present": search,
            "expected_path_matched": path_matches,
            "curl_error_code": int(curl_errors[-1]) if curl_errors else None,
            "command_exit_code": command_exit_code, "passed": bool(passed)}


def audit_chatgpt_tls(raw: str, command_exit_code: int = 0) -> dict:
    """只证明手机到主接口完成受信 TLS；403 不等于账号或业务验收。"""
    matches = re.findall(r"^RM_CHATGPT_TLS (\d{3}) (\d+) (\d+(?:\.\d+)?)\s*$", raw, re.M)
    curl_errors = re.findall(r"curl: \((\d+)\)", raw)
    status, verification, handshake = None, None, 0.0
    if len(matches) == 1:
        status, verification = int(matches[0][0]), int(matches[0][1])
        handshake = float(matches[0][2])
    return {
        "http_status": status,
        "certificate_verify_result": verification,
        "tls_handshake_completed": handshake > 0,
        "curl_error_code": int(curl_errors[-1]) if curl_errors else None,
        "command_exit_code": command_exit_code,
        # 超时也可能打印 verify_result=0；必须同时确认握手及真实 HTTP 响应。
        "passed": command_exit_code == 0 and len(matches) == 1 and not curl_errors
        and status is not None and 200 <= status <= 599
        and verification == 0 and handshake > 0,
    }


def package_uid(raw: str) -> int:
    matches = re.findall(rf"^package:{re.escape(PACKAGE)} uid:(\d+)\s*$", raw, re.M)
    if len(matches) != 1:
        raise ValueError("无法唯一确认 FlClash 的系统归属。")
    return int(matches[0])


def audit_connectivity(raw: str, owner_uid: int) -> dict:
    found = []
    unparsed = False
    for line in raw.splitlines():
        # 历史日志可能引用旧代理；只读取当前 NetworkAgentInfo 条目。
        if not line.lstrip().startswith("NetworkAgentInfo{"):
            continue
        transport = re.search(r"\bTransports:\s*([A-Z]+(?:\|[A-Z]+)*)", line)
        if not transport or "VPN" not in transport.group(1).split("|"):
            continue
        owner = re.search(r"\bOwnerUid:\s*(\d+)\b", line)
        if owner is None:
            unparsed = True
            continue
        if int(owner.group(1)) != owner_uid:
            continue
        network_info = re.search(r"\bni\{([^}]*)\}", line)
        if network_info is None:
            unparsed = True
            continue
        if not re.search(r"\bCONNECTED\b", network_info.group(1)):
            continue
        proxy = re.search(r"\bHttpProxy:\s*([^}]+)", line)
        has_proxy = bool(proxy and not re.match(r"(?:null|\[\])(?:\s|$)", proxy.group(1)))
        found.append(has_proxy)
    result = {
        "active_flclash_vpn_count": len(found),
        "vpn_http_proxy_present": any(found),
        "unparsed_vpn_entry": unparsed,
        "passed": len(found) == 1 and not any(found) and not unparsed,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", required=True, type=Path, help="已授权 USB 设备使用的 adb.exe 路径")
    parser.add_argument("--chatgpt-tls", action="store_true", help="另用手机 curl 核对 ChatGPT 主接口受信 TLS；不代表应用页面或消息成功")
    parser.add_argument("--google-search", action="store_true", help="用移动 UA 跟随 Google 普通入口跳转并核对搜索表单；不改变浏览器 Cookie")
    args = parser.parse_args()
    if not args.adb.is_file():
        parser.error("ADB 文件不存在。")

    def run_shell(*command: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [str(args.adb), "-d", "shell", *command], capture_output=True, timeout=15,
        )

    def read(*command: str) -> str:
        result = run_shell(*command)
        if result.returncode:
            raise RuntimeError("ADB 读取失败；请核对唯一 USB 设备及系统授权。")
        return result.stdout.decode("utf-8", errors="replace")

    try:
        owner = package_uid(read("pm", "list", "packages", "-U", PACKAGE))
        # 原始系统输出只在内存中解析；不打印地址、设备标识或 UID。
        result = audit_connectivity(read("dumpsys", "connectivity"), owner)
        if args.chatgpt_tls:
            # 原始 curl 错误、地址与响应头均不输出，不发送账号凭据或消息。
            probe = run_shell("sh", "-c", shlex.quote(CHATGPT_TLS_COMMAND))
            result["chatgpt_tls"] = audit_chatgpt_tls(
                (probe.stdout + probe.stderr).decode("utf-8", errors="replace"),
                command_exit_code=probe.returncode,
            )
            result["passed"] = result["passed"] and result["chatgpt_tls"]["passed"]
        if args.google_search:
            probe = run_shell("sh", "-c", shlex.quote(GOOGLE_SEARCH_COMMAND))
            result["google_search"] = audit_google_search(
                (probe.stdout + probe.stderr).decode("utf-8", errors="replace"), probe.returncode)
            result["passed"] = result["passed"] and result["google_search"]["passed"]
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"passed": False, "error_type": type(error).__name__}))
        return 1
    print(json.dumps(result))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
