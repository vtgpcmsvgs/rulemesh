"""在业务基线之前拒绝 YAML 原文及双引号转义产生的控制字符。"""
import re


def check(text: str) -> list[tuple[int, str]]:
    findings = []
    for number, line in enumerate(text.split('\n'), 1):
        if any(ord(c) < 32 and c not in '\r\t' or 0x7F <= ord(c) <= 0x9F and ord(c) != 0x85 for c in line):
            findings.append((number, 'YAML 原文含控制字符。'))
        # 仅检查双引号标量；成对反斜杠代表正则文本，不是 YAML 转义。
        for match in re.finditer(r'"(?:[^"\\]|\\.)*"', line):
            scalar = match.group()
            for escaped in re.finditer(r'\\(?:x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}|.)', scalar):
                token = escaped.group()[1:]
                code = int(token[1:], 16) if token[:1] in {'x', 'u', 'U'} and len(token) > 1 else None
                if token in {'0', 'a', 'b', 'v', 'f', 'e'} or code is not None and (code < 32 and code not in {9, 10, 13} or 0x7F <= code <= 0x9F and code != 0x85):
                    findings.append((number, 'YAML 双引号转义会生成控制字符；正则反斜杠应双写或使用单引号。'))
                    break
    return findings
