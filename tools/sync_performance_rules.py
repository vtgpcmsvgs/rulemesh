"""由完整直连表与精确代理表生成兜底 DIRECT 专用的小型冲突保护表。"""
from __future__ import annotations

from bisect import bisect_left
from pathlib import Path


def protective_rules(direct: list[str], proxy: list[str]) -> list[str]:
    """仅适用于末尾依次为直连表、域名代理表、DIRECT 的规则结构。"""
    exact: set[str] = set()
    suffix: set[str] = set()
    for rule in proxy:
        parts = rule.split(',')
        if len(parts) != 2 or parts[0] not in {'DOMAIN', 'DOMAIN-SUFFIX'}:
            raise ValueError('精简保护表只支持精确域名/后缀代理规则，禁止关键词或 IP 扩围。')
        if parts[0] == 'DOMAIN':
            exact.add(parts[1])
        else:
            suffix.add(parts[1])
    reversed_proxy = sorted('.'.join(d.split('.')[::-1]) for d in exact | suffix)
    result = []
    for rule in direct:
        parts = rule.split(',')
        kind, value = parts[:2]
        if kind not in {'DOMAIN', 'DOMAIN-SUFFIX'}:
            if kind not in {'IP-CIDR', 'IP-CIDR6', 'GEOIP'}:
                raise ValueError('完整直连表出现新语法，必须先验证精简推导。')
            result.append(rule)
            continue
        labels = value.split('.')
        overlaps = value in exact or any('.'.join(labels[i:]) in suffix for i in range(len(labels)))
        if kind == 'DOMAIN-SUFFIX':
            prefix = '.'.join(labels[::-1]) + '.'
            position = bisect_left(reversed_proxy, prefix)
            overlaps |= position < len(reversed_proxy) and reversed_proxy[position].startswith(prefix)
        if overlaps:
            result.append(rule)
    return result


def sync(root: Path, compile_source) -> int:
    direct = compile_source(root / 'direct/cn_direct.list').outputs['surge_rules']
    proxy = compile_source(root / 'proxy/gfw_precise.list').outputs['surge_rules']
    rules = protective_rules(direct, proxy)
    header = (
        '# 中国直连精简保护表：由完整 cn_direct 与 gfw_precise 自动推导，禁止手改。\n'
        '# 仅保留会被后续精确代理规则覆盖的国内域名，以及全部既有中国 IP/GEOIP 规则。\n'
        '# 调用顺序必须为本表、gfw_precise、FINAL/MATCH DIRECT，三者之间不得插入其他规则。\n'
        '# 不适用于工作白名单或其他最终策略；完整 cn_direct 与上游资产继续维护。\n'
    )
    path = root / 'direct/cn_direct_light.list'
    data = (header + '\n'.join(rules) + '\n').encode('utf-8')
    if not path.exists() or path.read_bytes() != data:
        temporary = path.with_suffix('.list.tmp')
        temporary.write_bytes(data)
        temporary.replace(path)
    return len(rules)
