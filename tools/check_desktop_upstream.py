"""Protect the desktop-only local upstream without restoring retired AdsPower rules."""
from __future__ import annotations
from pathlib import Path

DESKTOP = "rulemesh-flclash-desktop.yaml"
MARKER = "# AdsPower desktop upstream: SOCKS5 7898"
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
    targets = [r.split(",")[2] for r in rules
               if isinstance(r, str) and r.startswith("RULE-SET,proxy_gfw,") and len(r.split(",")) == 3]
    groups = {g["name"]: g for g in document.get("proxy-groups", []) if isinstance(g, dict) and "name" in g}
    if len(targets) != 1 or targets[0] not in groups or not rules or rules[0] != "IN-PORT,7898," + targets[0]:
        raise ValueError("桌面专用入站必须在首条按端口交给实际通用机场自动组。")
    if sum(isinstance(r, str) and r.startswith("IN-PORT,") for r in rules) != 1:
        raise ValueError("桌面专用入站端口规则必须唯一。")
    group = groups[targets[0]]
    if (group.get("type") != "url-test" or not isinstance(group.get("use"), list) or not group["use"]
            or group.get("proxies") or any(group.get(key) for key in ("include-all", "include-all-proxies", "include-all-providers"))):
        raise ValueError("桌面专用入口必须使用纯机场 provider 自动组，不允许 DIRECT 或内联回退。")


def present(path: Path, lines: list[str]) -> bool:
    return path.name == DESKTOP and MARKER in lines


def check(path: Path, lines: list[str]) -> list[str]:
    active = "\n".join(line for line in lines if line.strip() and not line.lstrip().startswith(("#", ";", "//")))
    if MARKER not in lines and "adspower" not in active.lower():
        return []
    if not present(path, lines):
        return [REMOVED]
    import yaml
    try:
        document = yaml.safe_load("\n".join(lines))
        validate_upstream(document)
        if "adspower" in yaml.safe_dump(document, allow_unicode=True).lower():
            return [REMOVED]
    except (yaml.YAMLError, ValueError, TypeError, AttributeError, KeyError):
        return [REMOVED + " 专用入口结构校验失败。"]
    return []
