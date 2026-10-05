"""从私人桌面配置派生 Clash Mi iOS 配置；只输出状态，不输出私有内容。

使用标准库，避免本机 Python 未安装 PyYAML 时无法维护配置。
仅支持仓库现有的块式 YAML；重复顶层键和不符合预期的锚点直接拒绝。
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import tempfile

SOURCE_NAME = "rulemesh-substore-mihomo-flclash-desktop.yaml"
TARGET_NAME = "rulemesh-substore-mihomo-clashmi-ios.yaml"
ROOT = Path(__file__).resolve().parents[1]
RULE_BASE = "https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/"
HEADER = """# Clash Mi iOS 专用配置；由桌面配置派生，请勿单独修改业务规则。
# RuleMesh 性能基线：2026-09-09
# iOS 不识别应用进程；VPN/TUN 由 Clash Mi 的 TUN 覆写管理。
# 导入后关闭 DNS、规则和代理组覆写；TUN 覆写与启用保持打开。
# 默认国内双 DoH，AI 独立美国解析；测速周期 600 秒。
# 维护与实机验收：公开仓库 docs/clashmi-ios.md。
"""


def derive(source: str, repo_root: Path = ROOT) -> str:
    """保留业务数据及规则顺序，仅变更明确列出的客户端字段。"""
    if source.startswith("\ufeff"):
        raise ValueError("源配置含 BOM。")
    source = source.replace("\r\n", "\n")
    anchors = list(re.finditer(r"(?m)^([a-zA-Z][\w-]*):", source))
    names = [match[1] for match in anchors]
    if len(names) != len(set(names)):
        raise ValueError("源配置存在重复顶层键。")
    required = {"find-process-mode", "tun", "dns", "proxy-providers", "proxy-groups", "rule-providers", "rules"}
    if not required <= set(names):
        raise ValueError("源配置缺少必要顶层字段。")
    sections = {}
    for index, match in enumerate(anchors):
        end = anchors[index + 1].start() if index + 1 < len(anchors) else len(source)
        sections[match[1]] = source[match.start():end]
    if not re.fullmatch(r"find-process-mode: strict\s*", sections["find-process-mode"]):
        raise ValueError("桌面进程设置已变化，需要重新审核 iOS 派生。")
    if re.search(r"(?m)^\s*-\s*.*PROCESS-(?:NAME|PATH)", sections["rules"]):
        raise ValueError("桌面新增进程规则，需要先审核 iOS 的目的地替代规则。")
    sections["find-process-mode"] = "find-process-mode: off\n"
    del sections["tun"]
    sections["dns"], count = re.subn(r"(?m)^  listen:[^\n]*\n", "", sections["dns"])
    if count != 1:
        raise ValueError("DNS listen 锚点不唯一，需要重新审核。")
    for name in ("proxy-providers", "proxy-groups"):
        indent = "      " if name == "proxy-providers" else "    "
        sections[name], count = re.subn(r"(?m)^" + indent + r"interval: 300[ \t]*$", indent + "interval: 600", sections[name])
        if not count:
            raise ValueError("桌面测速周期锚点不存在，需要重新审核。")
    # Clash Mi 官方 FAQ 明确 iOS 不支持 ASN 数据库；保留已构建的精确网段，
    # 仅移除阿里云 TCP/22 的运行时 ASN 兜底，其他业务入口不能静默丢弃。
    rule_lines = sections["rules"].splitlines(keepends=True)
    for line in rule_lines:
        if "IP-ASN," in line and not re.fullmatch(r"  - AND,\(\(IP-ASN,\d+,no-resolve\),\(NETWORK,tcp\),\(DST-PORT,22\)\),DIRECT\n?", line):
            raise ValueError("存在未经审核的 ASN 规则。")
    sections["rules"] = "".join(line for line in rule_lines if "IP-ASN," not in line)
    providers = sections["rule-providers"]
    blocks = list(re.finditer(r"(?m)^  ([\w-]+):[ \t]*\n", providers))
    for index in reversed(range(len(blocks))):
        match = blocks[index]
        end = blocks[index + 1].start() if index + 1 < len(blocks) else len(providers)
        block = providers[match.start():end]
        urls = re.findall(r"(?m)^    url: (.+)$", block)
        if not urls:
            continue
        url = urls[0].strip("\"'")
        if not url.startswith(RULE_BASE + "dist/mihomo/classical/"):
            raise ValueError("发现未登记的规则上游，需要审核 iOS 兼容性。")
        local = (repo_root / url.removeprefix(RULE_BASE)).resolve()
        if not local.is_relative_to((repo_root / "dist/mihomo/classical").resolve()):
            raise ValueError("规则路径超出构建目录。")
        payload = [json.loads(line[4:]) for line in local.read_text(encoding="utf-8").splitlines() if line.startswith('  - "')]
        if not payload:
            raise ValueError("构建规则为空或格式不受支持。")
        if not any("IP-ASN," in rule for rule in payload):
            continue
        if local.name != "alicloud_hk_ipv4_ssh22_direct.yaml":
            raise ValueError("其他规则集新增 ASN，需要先审核。")
        supported = [rule for rule in payload if "IP-ASN," not in rule]
        if not supported:
            raise ValueError("阿里云 SSH 精确网段不可为空。")
        inline = f"  {match[1]}:\n    type: inline\n    behavior: classical\n    payload:\n"
        inline += "".join("      - " + json.dumps(rule, ensure_ascii=False) + "\n" for rule in supported)
        providers = providers[:match.start()] + inline + providers[end:]
    sections["rule-providers"] = providers
    # 标记可能位于文件头或正文，统一去重后保留一次，避免重复触发检查。
    body = "".join(sections.values())
    markers = list(dict.fromkeys(line for line in source.splitlines() if line.startswith("# RuleMesh ")))
    for marker in markers:
        body = re.sub(r"(?m)^" + re.escape(marker) + r"\n", "", body)
    extra_markers = "".join(marker + "\n" for marker in markers if marker not in HEADER.splitlines())
    return HEADER + extra_markers + "\n" + body.rstrip() + "\n"


def default_root() -> Path:
    root = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop" / "rulemesh-local"
    return root / "current" if (root / "current").is_dir() else root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-root", type=Path, default=default_root())
    parser.add_argument("--check", action="store_true", help="只检查已存在的 iOS 配置是否与桌面派生结果一致")
    args = parser.parse_args()
    source = args.private_root / SOURCE_NAME
    target = args.private_root / TARGET_NAME
    if args.check and not target.exists():
        print("[clashmi] 未配置 iOS 派生文件，跳过。")
        return 0
    try:
        expected = derive(source.read_text(encoding="utf-8")).encode("utf-8")
        if args.check:
            if target.read_bytes() != expected:
                print("[clashmi] iOS 配置与桌面派生结果不一致；重新运行派生器后复核。")
                return 1
        elif not target.exists() or target.read_bytes() != expected:
            with tempfile.NamedTemporaryFile(dir=args.private_root, prefix=".clashmi-", delete=False) as temp:
                temporary = Path(temp.name)
                temp.write(expected)
            try:
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
    except (OSError, ValueError):
        # 私有配置解析异常不回显源行、订阅地址或异常中的路径细节。
        print("[clashmi] 派生失败：检查文件存在性、权限、BOM、唯一字段及桌面进程/测速锚点。")
        return 1
    print("[clashmi] iOS 派生一致性检查通过。" if args.check else "[clashmi] iOS 专用配置已生成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
