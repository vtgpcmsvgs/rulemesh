"""Protect the desktop-only local upstream without restoring retired AdsPower rules."""
from __future__ import annotations

from pathlib import Path

NAME = "adspower-upstream"
DESKTOP = "rulemesh-flclash-desktop.yaml"
REMOVED = "AdsPower 已删除的域名、进程规则及专用 provider / DNS 资产不得恢复；仅允许桌面本机专用入口。"


def validate_listener(document: dict) -> None:
    """Fail closed: a loopback SOCKS5 listener uses the actual general auto group."""
    listeners = document.get("listeners")
    if not isinstance(listeners, list) or len(listeners) != 1:
        raise ValueError("桌面专用入口必须唯一。")
    item = listeners[0]
    if not isinstance(item, dict) or set(item) != {"name", "type", "listen", "port", "proxy"}:
        raise ValueError("桌面专用入口字段不符合已审核结构。")
    if (item["name"] != NAME or item["type"] != "socks" or item["listen"] != "127.0.0.1"
            or type(item["port"]) is not int or item["port"] != 7898):
        raise ValueError("桌面专用入口必须仅监听本机 SOCKS5 7898。")
    targets = [r.split(",")[2] for r in document.get("rules", [])
               if isinstance(r, str) and r.startswith("RULE-SET,proxy_gfw,") and len(r.split(",")) == 3]
    groups = {g["name"]: g for g in document.get("proxy-groups", []) if isinstance(g, dict) and "name" in g}
    if len(targets) != 1 or item["proxy"] != targets[0] or targets[0] not in groups:
        raise ValueError("桌面专用入口必须引用实际通用代理规则使用的自动组。")
    group = groups[targets[0]]
    if (group.get("type") != "url-test" or not isinstance(group.get("use"), list) or not group["use"]
            or group.get("proxies") or any(group.get(key) for key in ("include-all", "include-all-proxies", "include-all-providers"))):
        raise ValueError("桌面专用入口必须使用纯机场 provider 自动组，不允许 DIRECT 或内联回退。")


def check(path: Path, lines: list[str]) -> list[str]:
    active = "\n".join(line for line in lines if line.strip() and not line.lstrip().startswith(("#", ";", "//")))
    if "adspower" not in active.lower():
        return []
    if path.name != DESKTOP:
        return [REMOVED]
    import yaml
    try:
        document = yaml.safe_load("\n".join(lines))
        validate_listener(document)
        other = {key: value for key, value in document.items() if key != "listeners"}
        if "adspower" in yaml.safe_dump(other, allow_unicode=True).lower():
            return [REMOVED]
    except (yaml.YAMLError, ValueError, TypeError, AttributeError, KeyError):
        return [REMOVED + " 专用入口结构校验失败。"]
    return []
