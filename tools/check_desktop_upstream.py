"""Protect the desktop-only local upstream without restoring retired AdsPower rules."""
from __future__ import annotations
from pathlib import Path
import ipaddress
import re
import uuid

DESKTOP = "rulemesh-flclash-desktop.yaml"
MARKER = "# AdsPower desktop upstream: SOCKS5 7898"
PROVIDER = "666clouds"
NODE = "666clouds-relay"
BLOCKS = ("PROVIDER", "GROUP")
REMOVED = "AdsPower 已删除的域名、进程规则及专用 provider / DNS 资产不得恢复；仅允许桌面本机专用入口。"


def validate_upstream(document: dict) -> None:
    """Reuse the application's SOCKS port; a second listener would collide."""
    if type(document.get("socks-port")) is not int or document["socks-port"] != 7898:
        raise ValueError("桌面专用 SOCKS5 端口必须为 7898。")
    if document.get("allow-lan") is not False or document.get("bind-address") not in (None, "127.0.0.1"):
        raise ValueError("桌面专用入口必须仅供本机访问。")
    if document.get("listeners") or any(document.get(k) == 7898 for k in ("mixed-port", "port", "redir-port", "tproxy-port")):
        raise ValueError("不得创建冲突的重复 7898 监听器。")
    rules = document.get("rules", [])
    groups = {g["name"]: g for g in document.get("proxy-groups", []) if isinstance(g, dict) and "name" in g}
    if len(groups) != len(document.get("proxy-groups", [])) or not rules or rules[0] != "IN-PORT,7898," + PROVIDER:
        raise ValueError("桌面专用入站必须在首条固定交给 666clouds。")
    if sum(isinstance(r, str) and r.startswith("IN-PORT,") for r in rules) != 1:
        raise ValueError("桌面专用入站端口规则必须唯一。")
    if groups.get(PROVIDER) != {"name": PROVIDER, "type": "select", "hidden": True, "use": [PROVIDER]}:
        raise ValueError("666clouds 必须为隐藏的单 provider 固定组，无 DIRECT 或机场回退。")
    spec = document.get("proxy-providers", {}).get(PROVIDER, {})
    if set(spec) != {"type", "payload"} or spec["type"] != "inline" or not isinstance(spec["payload"], list) or len(spec["payload"]) != 1:
        raise ValueError("666clouds 必须是桌面本地单节点 inline provider。")
    node = spec["payload"][0]
    fields = {"name", "type", "server", "port", "uuid", "network", "tls", "servername", "client-fingerprint", "reality-opts", "udp"}
    if (not isinstance(node, dict) or set(node) != fields or node.get("name") != NODE
            or node.get("type") != "vless" or node.get("network") != "tcp" or node.get("tls") is not True
            or node.get("udp") is not True or node.get("client-fingerprint") != "chrome"
            or not isinstance(node.get("servername"), str) or not node["servername"]
            or type(node.get("port")) is not int or not 1 <= node["port"] <= 65535):
        raise ValueError("666clouds 必须保留经授权的 VLESS TCP Reality 结构。")
    # Parse identities without putting their values into an exception or diagnostic.
    try:
        ipaddress.ip_address(node["server"])
        uuid.UUID(node["uuid"])
    except (ValueError, TypeError, AttributeError):
        raise ValueError("666clouds 的地址或身份格式无效。") from None
    reality = node["reality-opts"]
    if (not isinstance(reality, dict) or set(reality) != {"public-key", "short-id"}
            or not isinstance(reality["public-key"], str) or not re.fullmatch(r"[\w-]{43}", reality["public-key"], re.ASCII)
            or not isinstance(reality["short-id"], str) or not re.fullmatch(r"(?:[0-9a-fA-F]{2}){1,8}", reality["short-id"])):
        raise ValueError("666clouds 的 Reality 参数格式无效。")
    for group in document.get("proxy-groups", []):
        if group["name"] == PROVIDER:
            continue
        if (PROVIDER in group.get("use", []) or any(n in group.get("proxies", []) for n in (PROVIDER, NODE))
                or any(group.get(k) for k in ("include-all", "include-all-proxies", "include-all-providers"))):
            raise ValueError("666clouds 不得混入普通业务菜单或机场自动组。")
    # Only this ingress rule may reference the private provider/group/node.
    other = {k: v for k, v in document.items() if k not in {"proxy-providers", "proxy-groups", "rules"}}
    other["providers"] = {k: v for k, v in document.get("proxy-providers", {}).items() if k != PROVIDER}
    other["groups"] = [g for g in document.get("proxy-groups", []) if g["name"] != PROVIDER]
    other["rules"] = rules[1:]
    if PROVIDER in str(other):
        raise ValueError("666clouds 只允许被桌面 7898 入站使用。")


def airport_providers(document: dict, path: Path) -> dict:
    """Exclude exactly the validated desktop local relay, never arbitrary non-HTTP providers."""
    providers = document.get("proxy-providers", {})
    if PROVIDER in providers:
        if path.name != DESKTOP:
            raise ValueError("666clouds 不得出现在其他客户端。")
        validate_upstream(document)
    return {name: spec for name, spec in providers.items() if name != PROVIDER}


def strip_relay_blocks(source: str) -> str:
    """Strip byte-stable marked desktop blocks before iOS section discovery."""
    import yaml
    expected = yaml.safe_load(source)
    del expected["proxy-providers"][PROVIDER]
    expected["proxy-groups"] = [g for g in expected["proxy-groups"] if g["name"] != PROVIDER]
    for kind in BLOCKS:
        start = "  # >>> RULEMESH_DESKTOP_666CLOUDS_" + kind
        end = "  # <<< RULEMESH_DESKTOP_666CLOUDS_" + kind
        if source.splitlines().count(start) != 1 or source.splitlines().count(end) != 1:
            raise ValueError("桌面专用中继标记必须唯一完整。")
        pattern = r"(?m)^" + re.escape(start) + r"\n[\s\S]*?^" + re.escape(end) + r"\n"
        source, count = re.subn(pattern, "", source)
        if count != 1:
            raise ValueError("桌面专用中继剥离失败。")
    # Fail closed if an edited marker swallowed unrelated settings or left a relay behind.
    if yaml.safe_load(source) != expected:
        raise ValueError("桌面中继标记范围改变了其他配置。")
    return source


def present(path: Path, lines: list[str]) -> bool:
    return path.name == DESKTOP and MARKER in lines


def check(path: Path, lines: list[str]) -> list[str]:
    active = "\n".join(line for line in lines if line.strip() and not line.lstrip().startswith(("#", ";", "//")))
    if MARKER not in lines and "adspower" not in active.lower() and PROVIDER not in active:
        return []
    if not present(path, lines):
        return [REMOVED]
    import yaml
    try:
        from check_private_subscriptions import load_yaml
        document = load_yaml("\n".join(lines))
        validate_upstream(document)
        if "adspower" in yaml.safe_dump(document, allow_unicode=True).lower():
            return [REMOVED]
    except (yaml.YAMLError, ValueError, TypeError, AttributeError, KeyError):
        return [REMOVED + " 专用入口结构校验失败。"]
    return []
