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
    print(json.dumps({'checked': len(paths), 'findings': [f for f in findings if f['errors']]}, ensure_ascii=False))
    return int(any(f['errors'] for f in findings))


if __name__ == '__main__':
    raise SystemExit(main())
