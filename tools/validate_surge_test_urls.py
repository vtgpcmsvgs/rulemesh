from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_SURGE_TEMPLATE = ROOT / "docs" / "examples" / "surge-public.conf"
LOCAL_CURRENT_ROOT = Path.home() / "Desktop" / "rulemesh-local" / "current"
URL_BASED_GROUP_TYPES = frozenset({"url-test", "fallback", "load-balance", "smart"})

GENERAL_TEST_URL_PATTERN = re.compile(
    r"^\s*(internet-test-url|proxy-test-url)\s*=\s*(?P<url>[^,\s]+)",
    re.IGNORECASE,
)
POLICY_GROUP_PATTERN = re.compile(r"^\s*[^=\r\n]+\s*=\s*(?P<type>[A-Za-z-]+)\b")
URL_PARAMETER_PATTERN = re.compile(r"(?:^|,)\s*url\s*=\s*(?P<url>[^,\s]+)", re.IGNORECASE)
TEST_URL_PARAMETER_PATTERN = re.compile(
    r"(?:^|,)\s*test-url\s*=\s*(?P<url>[^,\s]+)",
    re.IGNORECASE,
)


def read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("utf-8", b"", 0, 1, f"Cannot decode file: {path}")


def is_comment_or_blank(raw: str) -> bool:
    stripped = raw.strip()
    return not stripped or stripped.startswith(("#", ";", "//"))


def normalize_url_token(token: str) -> str:
    return token.strip().strip('"').strip("'")


def is_http_url(token: str) -> bool:
    return normalize_url_token(token).lower().startswith("http://")


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def validate_surge_profile(path: Path) -> list[str]:
    findings: list[str] = []
    content = read_text(path)

    for line_no, raw in enumerate(content.splitlines(), start=1):
        if is_comment_or_blank(raw):
            continue

        general_match = GENERAL_TEST_URL_PATTERN.match(raw)
        if general_match and not is_http_url(general_match.group("url")):
            key = general_match.group(1)
            findings.append(
                f"{display_path(path)}:{line_no} {key} must stay on http://"
            )

        test_url_match = TEST_URL_PARAMETER_PATTERN.search(raw)
        if test_url_match and not is_http_url(test_url_match.group("url")):
            findings.append(
                f"{display_path(path)}:{line_no} test-url must stay on http://"
            )

        group_match = POLICY_GROUP_PATTERN.match(raw)
        if not group_match:
            continue

        group_type = group_match.group("type").lower()
        if group_type not in URL_BASED_GROUP_TYPES:
            continue

        url_match = URL_PARAMETER_PATTERN.search(raw)
        if url_match and not is_http_url(url_match.group("url")):
            findings.append(
                f"{display_path(path)}:{line_no} {group_type} group url must stay on http://"
            )

    return findings


def collect_default_paths() -> list[Path]:
    paths: list[Path] = []
    if PUBLIC_SURGE_TEMPLATE.exists():
        paths.append(PUBLIC_SURGE_TEMPLATE)

    if LOCAL_CURRENT_ROOT.exists():
        paths.extend(sorted(path for path in LOCAL_CURRENT_ROOT.glob("*.conf") if path.is_file()))

    return paths


def main() -> int:
    paths = collect_default_paths()
    if not paths:
        print("[validate_surge_test_urls] no Surge profile files found")
        return 0

    findings: list[str] = []
    for path in paths:
        findings.extend(validate_surge_profile(path))

    if findings:
        for finding in findings:
            print(f"[validate_surge_test_urls] {finding}", file=sys.stderr)
        return 1

    print(f"[validate_surge_test_urls] checked {len(paths)} Surge profile files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
