"""只读核对 Android 实际 VPN，避免把保存的开关误当成已经生效。"""
from pathlib import Path
import argparse
import json
import re
import shlex
import subprocess

PACKAGE = "com.follow.clash"
CHATGPT_TLS_COMMAND = (
    'curl --noproxy "*" --connect-timeout 3 --max-time 5 '
    '--silent --show-error --head --output /dev/null '
    '--write-out "\\nRM_CHATGPT_TLS %{http_code} %{ssl_verify_result} %{time_appconnect}\\n" '
    'https://android.chat.openai.com/'
)


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
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"passed": False, "error_type": type(error).__name__}))
        return 1
    print(json.dumps(result))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
