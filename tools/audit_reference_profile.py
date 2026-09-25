"""只输出第三方配置的白名单统计；禁止回显 DNS、节点、hosts 或解析错误原文。"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path


SERVICES = ("Google", "YouTube", "AI", "Telegram", "Crypto", "Microsoft", "Apple")
PROTOCOLS = {"anytls", "ss", "ssr", "vmess", "vless", "trojan", "hysteria2", "tuic", "socks5", "http"}
GROUP_TYPES = {"select", "url-test", "fallback", "load-balance", "smart"}


def summarize(data: dict) -> dict:
    """字段和值都做白名单过滤；DNS 中也可能存在凭证，不能整节输出。"""
    nodes = [n for n in data.get("proxies", []) if isinstance(n, dict)]
    groups = [g for g in data.get("proxy-groups", []) if isinstance(g, dict)]
    dns = data.get("dns", {})
    result = {
        "nodes": len(nodes),
        "protocol_counts": dict(Counter(n.get("type") if n.get("type") in PROTOCOLS else "other" for n in nodes)),
        "group_types": dict(Counter(g.get("type") if g.get("type") in GROUP_TYPES else "other" for g in groups)),
        "rules": len(data.get("rules", [])),
        "dns": {
            "nameserver_count": len(dns.get("nameserver", [])),
            "bootstrap_count": len(dns.get("proxy-server-nameserver", [])),
            "policy_count": len(dns.get("nameserver-policy", {})),
            "fake_ip_explicit": dns.get("enhanced-mode") == "fake-ip",
            "fake_ip_filter_count": len(dns.get("fake-ip-filter", [])),
        },
        "services": {s: sum(g.get("name") == s for g in groups) for s in SERVICES},
    }
    for key in ("udp", "tfo", "skip-cert-verify"):
        result[key + "_enabled_nodes"] = sum(n.get(key) is True for n in nodes)
    for key in ("idle-session-check-interval", "idle-session-timeout", "min-idle-session"):
        result[key] = dict(Counter(str(n[key]) for n in nodes if type(n.get(key)) is int and 0 <= n[key] <= 86400))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    args = parser.parse_args()
    try:
        import yaml
    except ImportError:
        print("请在任务专用依赖目录安装 PyYAML 并设置 PYTHONPATH；不要假设系统或捆绑 Python 已安装。")
        return 1
    try:
        data = yaml.safe_load(args.profile.read_text("utf-8-sig"))
        result = summarize(data)
    except Exception:
        print("参考配置读取或解析失败；为保护私人内容，不输出异常原文。")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
