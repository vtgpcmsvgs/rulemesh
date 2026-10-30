"""拒绝被上传表达式或编码文本替代的私有配置；诊断不含文件正文。"""
from pathlib import Path
import json
import re
from check_private_dns_precedence import PRIVATE_PROFILE_NAMES, default_paths, ROOT


def check(path: Path, raw: bytes) -> list[str]:
    if raw.startswith(b'\xef\xbb\xbf'):
        return ["配置不得含 UTF-8 BOM。"]
    try:
        lines = raw.decode('utf-8').splitlines()
    except UnicodeDecodeError:
        return ["配置必须是有效 UTF-8 文本。"]
    required = ("General", "Proxy Group", "Rule") if path.suffix == '.conf' else (
        "dns", "proxy-providers", "proxy-groups", "rule-providers", "rules")
    headers = [m[1] for line in lines if (m := re.fullmatch(r'\[([^\]]+)\]\s*', line))] if path.suffix == '.conf' else [
        m[1] for line in lines if (m := re.match(r'^([\w-]+):', line))]
    if any(headers.count(key) != 1 for key in required):
        return ["配置主体缺失或节重复；禁止提交上传表达式、Base64 或截断内容。"]
    return []


def main() -> int:
    paths = [p for p in default_paths(ROOT) if p.name in PRIVATE_PROFILE_NAMES]
    findings = [{'profile': p.name, 'errors': check(p, p.read_bytes())} for p in paths]
    findings.extend(check_chain_consistency({p.name: p.read_text(encoding='utf-8').splitlines() for p in paths}))
    print(json.dumps({'checked': len(paths), 'findings': [f for f in findings if f['errors']]}, ensure_ascii=False))
    return int(any(f['errors'] for f in findings))


def check_chain_consistency(profiles):
    """六客户端必须共用同一份落地身份和认证；比较只在内存中进行。"""
    import check_android_us_chain as chain
    from check_private_subscriptions import load_yaml
    if not any(chain.present(lines) for lines in profiles.values()):
        return []
    try:
        assert set(profiles) == chain.PROFILES
        identities = []
        for name, lines in profiles.items():
            assert chain.present(lines) and not chain.check(Path(name), lines)
            if name.endswith('.conf'):
                node = chain.surge_definitions(lines, 'Proxy')[chain.EXITS[0]]
                options = dict(p.split('=', 1) for p in node[3:])
                identities.append((node[1], int(node[2]), options['username'], options['password']))
            else:
                node = load_yaml('\n'.join(lines))['proxies'][0]
                identities.append(tuple(node[k] for k in ('server', 'port', 'username', 'password')))
        assert len(set(identities)) == 1
    except Exception:
        return [{'profile': 'private-us-chain', 'errors': ['六份私人配置的美国落地登记、认证或完整性不一致；详情已隐藏。']}]
    return []


if __name__ == '__main__':
    raise SystemExit(main())
