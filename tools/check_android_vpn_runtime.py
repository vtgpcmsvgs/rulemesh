"""只读核对 Android 实际 VPN，避免把保存的开关误当成已经生效。"""
from pathlib import Path
import argparse
import json
import re
import subprocess

PACKAGE = "com.follow.clash"


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
    args = parser.parse_args()
    if not args.adb.is_file():
        parser.error("ADB 文件不存在。")

    def read(*command: str) -> str:
        result = subprocess.run(
            [str(args.adb), "-d", "shell", *command], capture_output=True, timeout=15,
        )
        if result.returncode:
            raise RuntimeError("ADB 读取失败；请核对唯一 USB 设备及系统授权。")
        return result.stdout.decode("utf-8", errors="replace")

    try:
        owner = package_uid(read("pm", "list", "packages", "-U", PACKAGE))
        # 原始系统输出只在内存中解析；不打印地址、设备标识或 UID。
        result = audit_connectivity(read("dumpsys", "connectivity"), owner)
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"passed": False, "error_type": type(error).__name__}))
        return 1
    print(json.dumps(result))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
