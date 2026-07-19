from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import datetime as dt
import fcntl
import hashlib
import hmac
import ipaddress
import json
import os
import re
import signal
import sqlite3
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Optional, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / ".rulemesh.local.json"
DEFAULT_STATE_DIR = Path.home() / "Library" / "Application Support" / "RuleMesh" / "surge-monitor"
DEFAULT_SURGE_CLI = Path("/Applications/Surge.app/Contents/Applications/surge-cli")
CN_DNS_DOMAINS_PATH = ROOT / "rules" / "dns" / "cn_dns_domains.list"
REQUEST_DETAIL_RETENTION_HOURS = 36
REQUEST_SEEN_RETENTION_SECONDS = 3600
DEFAULT_MAX_DATABASE_MB = 256

DOMESTIC_DNS_NEEDLES = (
    "223.5.5.5",
    "223.6.6.6",
    "119.29.29.29",
    "119.28.28.28",
    "114.114.114.114",
    "dns.alidns.com",
    "doh.pub",
)
OVERSEAS_DNS_NEEDLES = (
    "1.1.1.1",
    "8.8.8.8",
    "9.9.9.9",
    "cloudflare-dns.com",
    "dns.google",
    "dns.quad9.net",
)
BUILTIN_POLICIES = {"DIRECT", "REJECT", "REJECT-TINYGIF", "REJECT-DROP"}
GOOGLE_FOCUS_SUFFIXES = (
    "google.com",
    "googleapis.com",
    "gstatic.com",
    "googleusercontent.com",
)
OPENAI_FOCUS_SUFFIXES = (
    "chatgpt.com",
    "openai.com",
    "oaistatic.com",
    "oaiusercontent.com",
)

DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": True,
    "surge_cli_path": str(DEFAULT_SURGE_CLI),
    "state_dir": "",
    "request_poll_seconds": 20,
    "snapshot_seconds": 300,
    "probe_seconds": 900,
    "retention_days": 14,
    "max_database_mb": DEFAULT_MAX_DATABASE_MB,
    "probes": [
        {
            "name": "baidu",
            "category": "domestic",
            "url": "https://www.baidu.com/",
            "accepted_status": [200, 301, 302, 403],
        },
        {
            "name": "qq",
            "category": "domestic",
            "url": "https://www.qq.com/",
            "accepted_status": [200, 301, 302, 403],
        },
        {
            "name": "google",
            "category": "google",
            "url": "https://www.google.com/generate_204",
            "accepted_status": [204],
        },
        {
            "name": "chatgpt",
            "category": "openai",
            "url": "https://chatgpt.com/",
            "accepted_status": [200, 301, 302, 307, 308, 403, 429],
        },
    ],
    "thresholds": {
        "minimum_samples": 5,
        "minimum_failures": 3,
        "failure_ratio": 0.2,
        "final_hit_count": 5,
        "dns_slow_ms": 1000,
        "connect_slow_ms": 3000,
        "total_slow_ms": 10000,
    },
    "privacy": {
        "store_final_hostnames": True,
        "store_url_paths_queries": False,
        "store_device_names_addresses": False,
    },
}


class MonitorError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def utc_now() -> float:
    return time.time()


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = dict(base)
    for key, value in override.items():
        current = result.get(key)
        if isinstance(current, Mapping) and isinstance(value, Mapping):
            result[key] = deep_merge(current, value)
        else:
            result[key] = value
    return result


def _require_int(config: Mapping[str, Any], key: str, minimum: int) -> int:
    value = config.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise MonitorError("invalid_config_" + key)
    return value


def load_config(path: Optional[Path]) -> dict[str, Any]:
    override: Mapping[str, Any] = {}
    if path and path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MonitorError("invalid_config_json") from exc
        if not isinstance(payload, Mapping):
            raise MonitorError("invalid_config_root")
        section = payload.get("surge_monitor", payload)
        if not isinstance(section, Mapping):
            raise MonitorError("invalid_config_section")
        override = section

    config = deep_merge(DEFAULT_CONFIG, override)
    if not isinstance(config.get("enabled"), bool):
        raise MonitorError("invalid_config_enabled")
    _require_int(config, "request_poll_seconds", 5)
    _require_int(config, "snapshot_seconds", 60)
    _require_int(config, "probe_seconds", 300)
    _require_int(config, "retention_days", 1)
    _require_int(config, "max_database_mb", 32)

    privacy = config.get("privacy")
    if not isinstance(privacy, Mapping):
        raise MonitorError("invalid_config_privacy")
    # 这两条是硬边界，不允许通过本地配置放宽。
    if privacy.get("store_url_paths_queries") is not False:
        raise MonitorError("privacy_url_storage_forbidden")
    if privacy.get("store_device_names_addresses") is not False:
        raise MonitorError("privacy_device_storage_forbidden")
    if not isinstance(privacy.get("store_final_hostnames"), bool):
        raise MonitorError("invalid_config_store_final_hostnames")

    thresholds = config.get("thresholds")
    if not isinstance(thresholds, Mapping):
        raise MonitorError("invalid_config_thresholds")
    for key in (
        "minimum_samples",
        "minimum_failures",
        "final_hit_count",
        "dns_slow_ms",
        "connect_slow_ms",
        "total_slow_ms",
    ):
        _require_int(thresholds, key, 1)
    ratio = thresholds.get("failure_ratio")
    if not isinstance(ratio, (int, float)) or isinstance(ratio, bool) or not 0 < float(ratio) <= 1:
        raise MonitorError("invalid_config_failure_ratio")

    probes = config.get("probes")
    if not isinstance(probes, list) or not probes:
        raise MonitorError("invalid_config_probes")
    normalized_probes = []
    seen_names = set()
    for item in probes:
        if not isinstance(item, Mapping):
            raise MonitorError("invalid_config_probe")
        name = str(item.get("name", "")).strip().lower()
        category = str(item.get("category", "")).strip().lower()
        url = str(item.get("url", "")).strip()
        accepted = item.get("accepted_status")
        parsed = urllib.parse.urlsplit(url)
        if (
            not name
            or name in seen_names
            or category not in {"domestic", "google", "openai"}
            or parsed.scheme != "https"
            or not parsed.hostname
            or not isinstance(accepted, list)
            or not accepted
            or any(isinstance(code, bool) or not isinstance(code, int) for code in accepted)
        ):
            raise MonitorError("invalid_config_probe")
        seen_names.add(name)
        normalized_probes.append(
            {
                "name": name,
                "category": category,
                "url": url,
                "accepted_status": accepted,
            }
        )
    config["probes"] = normalized_probes

    raw_state_dir = str(config.get("state_dir", "")).strip()
    state_dir = Path(raw_state_dir).expanduser() if raw_state_dir else DEFAULT_STATE_DIR
    resolved_state_dir = state_dir.resolve()
    protected_paths = {
        Path("/"),
        Path("/tmp"),
        Path("/private"),
        Path("/private/tmp"),
        Path("/var"),
        Path("/private/var"),
        Path.home().resolve(),
        (Path.home() / "Desktop").resolve(),
        (Path.home() / "Documents").resolve(),
        (Path.home() / "Downloads").resolve(),
        (Path.home() / "Library").resolve(),
        ROOT.resolve(),
        *[path.resolve() for path in DEFAULT_STATE_DIR.parents],
    }
    if (
        resolved_state_dir in protected_paths
        or not (
            resolved_state_dir.name == "surge-monitor"
            or resolved_state_dir.name.startswith("surge-monitor-")
        )
    ):
        raise MonitorError("unsafe_state_dir")
    config["state_dir"] = str(resolved_state_dir)
    config["surge_cli_path"] = str(Path(str(config["surge_cli_path"])).expanduser())
    return config


def ensure_private_dir(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
        os.chmod(path, 0o700)
    except OSError as exc:
        raise MonitorError("state_dir_unavailable") from exc


def load_or_create_secret(state_dir: Path) -> bytes:
    secret_path = state_dir / "identity.key"
    if secret_path.exists():
        try:
            secret = secret_path.read_bytes()
            os.chmod(secret_path, 0o600)
        except OSError as exc:
            raise MonitorError("identity_key_unavailable") from exc
        if len(secret) < 32:
            raise MonitorError("identity_key_invalid")
        return secret
    secret = os.urandom(32)
    try:
        fd = os.open(str(secret_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, secret)
        finally:
            os.close(fd)
    except OSError as exc:
        raise MonitorError("identity_key_unavailable") from exc
    return secret


def stable_id(secret: bytes, namespace: str, value: str, length: int = 10) -> str:
    digest = hmac.new(secret, (namespace + "\0" + value).encode("utf-8"), hashlib.sha256).hexdigest()
    return digest[:length]


def normalize_hostname(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    candidate = value.strip()
    if not candidate:
        return ""
    if "://" in candidate:
        candidate = urllib.parse.urlsplit(candidate).hostname or ""
    else:
        if candidate.startswith("[") and "]" in candidate:
            candidate = candidate[1 : candidate.index("]")]
        elif candidate.count(":") == 1:
            host, port = candidate.rsplit(":", 1)
            if port.isdigit():
                candidate = host
    candidate = candidate.rstrip(".").lower()
    try:
        ipaddress.ip_address(candidate)
        return candidate
    except ValueError:
        pass
    try:
        candidate = candidate.encode("idna").decode("ascii")
    except UnicodeError:
        return ""
    if len(candidate) > 253 or not re.fullmatch(r"[a-z0-9._-]+", candidate):
        return ""
    return candidate


def parse_domain_suffixes(path: Path) -> tuple[str, ...]:
    if not path.exists():
        return ("cn",)
    suffixes = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip().lower()
        if not line or line.startswith("#"):
            continue
        suffix = normalize_hostname(line.lstrip("."))
        if suffix:
            suffixes.append(suffix)
    return tuple(sorted(set(suffixes), key=lambda item: (-len(item), item)))


def host_matches(host: str, suffixes: Iterable[str]) -> bool:
    return any(host == suffix or host.endswith("." + suffix) for suffix in suffixes)


def probe_host_categories(config: Mapping[str, Any]) -> dict[str, str]:
    result = {}
    for probe in config["probes"]:
        host = normalize_hostname(urllib.parse.urlsplit(probe["url"]).hostname)
        if host:
            result[host] = str(probe["category"])
    return result


def classify_host(
    host: str,
    probe_hosts: Mapping[str, str],
    cn_suffixes: Sequence[str],
    rule: Any = None,
) -> str:
    if not host:
        return "other"
    for focus_host, category in probe_hosts.items():
        if host == focus_host or host.endswith("." + focus_host):
            return category
    if host_matches(host, GOOGLE_FOCUS_SUFFIXES):
        return "google"
    if host_matches(host, OPENAI_FOCUS_SUFFIXES):
        return "openai"
    if host_matches(host, cn_suffixes):
        return "domestic"
    rule_text = str(rule or "").lower()
    if "google_us" in rule_text:
        return "google"
    if "ai_us" in rule_text:
        return "us_platform"
    return "other"


def privacy_host(
    host: str,
    category: str,
    is_final: bool,
    store_final_hostnames: bool,
    secret: bytes,
) -> tuple[str, str]:
    if not host:
        return "__unknown__", "other"
    try:
        ipaddress.ip_address(host)
        return "ip#" + stable_id(secret, "ip", host), "ip"
    except ValueError:
        pass
    if category != "other":
        return host, category
    if is_final and store_final_hostnames:
        return host, "final_candidate"
    return "__other__", "other"


def classify_rule(value: Any) -> tuple[str, bool]:
    if not isinstance(value, str):
        return "UNKNOWN", False
    text = value.strip().upper()
    if not text:
        return "UNKNOWN", False
    for rule_type in (
        "FINAL",
        "RULE-SET",
        "DOMAIN-SET",
        "DOMAIN-SUFFIX",
        "DOMAIN-KEYWORD",
        "DOMAIN",
        "GEOIP",
        "IP-CIDR6",
        "IP-CIDR",
        "IP-ASN",
        "PROCESS-NAME",
        "AND",
        "OR",
        "NOT",
        "PROTOCOL",
    ):
        if text == rule_type or text.startswith(rule_type + ",") or text.startswith(rule_type + " "):
            return rule_type, rule_type == "FINAL"
    token = re.split(r"[ ,]", text, maxsplit=1)[0]
    return token[:32] if token else "UNKNOWN", False


def anonymize_policy(value: Any, secret: bytes) -> str:
    if not isinstance(value, str) or not value.strip():
        return "UNKNOWN"
    policy = value.strip()
    if policy.upper() in BUILTIN_POLICIES:
        return policy.upper()
    return "policy#" + stable_id(secret, "policy", policy)


def classify_error(notes: Any, failed: bool, rejected: bool) -> str:
    if rejected:
        return "rejected"
    if not failed:
        return "none"
    if isinstance(notes, list):
        text = " ".join(str(item) for item in notes)
    else:
        text = str(notes or "")
    lowered = text.lower()
    if re.search(r"dns|resolve|resolver|name server|no upstream", lowered):
        return "dns"
    if re.search(r"no route|unreachable|network is down", lowered):
        return "no_route"
    if re.search(r"timeout|timed out", lowered):
        return "timeout"
    if re.search(r"refused", lowered):
        return "refused"
    if re.search(r"tls|ssl|certificate|handshake", lowered):
        return "tls"
    if re.search(r"reset|closed|eof|broken pipe", lowered):
        return "reset"
    return "other"


def timing_ms(records: Any, name_pattern: str) -> Optional[float]:
    if not isinstance(records, list):
        return None
    regex = re.compile(name_pattern, re.IGNORECASE)
    for item in records:
        if not isinstance(item, Mapping) or not regex.search(str(item.get("name", ""))):
            continue
        value = item.get("durationInMillisecond")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return max(0.0, float(value))
        value = item.get("duration")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return max(0.0, float(value) * 1000.0)
    return None


def total_duration_ms(item: Mapping[str, Any]) -> Optional[float]:
    start = item.get("startDate")
    end = item.get("completedDate")
    if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
        return None
    value = float(end) - float(start)
    if value < 0 or value > 86400:
        return None
    return value * 1000.0


def connect_database(state_dir: Path, readonly: bool = False) -> sqlite3.Connection:
    database_path = state_dir / "monitor.sqlite3"
    if readonly:
        if not database_path.is_file():
            raise MonitorError("monitor_state_missing")
        try:
            connection = sqlite3.connect(database_path.as_uri() + "?mode=ro", uri=True, timeout=10)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only=ON")
            connection.execute("PRAGMA busy_timeout=5000")
            return connection
        except sqlite3.Error as exc:
            raise MonitorError("database_unavailable") from exc
    try:
        connection = sqlite3.connect(str(database_path), timeout=10)
    except sqlite3.Error as exc:
        raise MonitorError("database_unavailable") from exc
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute("PRAGMA secure_delete=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        connection.executescript(
            """
        CREATE TABLE IF NOT EXISTS requests (
            request_key TEXT PRIMARY KEY,
            started_at REAL NOT NULL,
            observed_at REAL NOT NULL,
            host_key TEXT NOT NULL,
            host_public_id TEXT NOT NULL,
            host_scope TEXT NOT NULL,
            client_id TEXT NOT NULL,
            policy_id TEXT NOT NULL,
            original_policy_id TEXT NOT NULL,
            rule_type TEXT NOT NULL,
            is_final INTEGER NOT NULL,
            is_direct INTEGER NOT NULL,
            failed INTEGER NOT NULL,
            rejected INTEGER NOT NULL,
            completed INTEGER NOT NULL,
            error_category TEXT NOT NULL,
            total_ms REAL,
            dns_ms REAL,
            connect_ms REAL
        );
        CREATE INDEX IF NOT EXISTS requests_started_idx ON requests(started_at);
        CREATE INDEX IF NOT EXISTS requests_scope_idx ON requests(host_scope, started_at);

        CREATE TABLE IF NOT EXISTS request_seen (
            request_key TEXT PRIMARY KEY,
            last_seen REAL NOT NULL,
            finalized INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS request_seen_time_idx ON request_seen(last_seen);

        CREATE TABLE IF NOT EXISTS probes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sampled_at REAL NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            host_key TEXT NOT NULL,
            reachable INTEGER NOT NULL,
            healthy INTEGER NOT NULL,
            error_category TEXT NOT NULL,
            http_code INTEGER NOT NULL,
            dns_ms REAL,
            connect_ms REAL,
            tls_ms REAL,
            total_ms REAL,
            remote_id TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS probes_time_idx ON probes(sampled_at);

        CREATE TABLE IF NOT EXISTS dns_samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sampled_at REAL NOT NULL,
            host_key TEXT NOT NULL,
            server_class TEXT NOT NULL,
            success INTEGER NOT NULL,
            error_category TEXT NOT NULL,
            time_ms REAL,
            answer_count INTEGER NOT NULL,
            answer_id TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS dns_samples_time_idx ON dns_samples(sampled_at);

        CREATE TABLE IF NOT EXISTS profile_audits (
            sampled_at REAL NOT NULL,
            profile_id TEXT NOT NULL,
            code TEXT NOT NULL,
            ok INTEGER NOT NULL,
            PRIMARY KEY (sampled_at, code)
        );
        CREATE INDEX IF NOT EXISTS profile_audits_time_idx ON profile_audits(sampled_at);

        CREATE TABLE IF NOT EXISTS runtime_events (
            event_id TEXT PRIMARY KEY,
            sampled_at REAL NOT NULL,
            category TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS health_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sampled_at REAL NOT NULL,
            component TEXT NOT NULL,
            ok INTEGER NOT NULL,
            code TEXT NOT NULL,
            count_value INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS health_events_time_idx ON health_events(sampled_at);

        CREATE TABLE IF NOT EXISTS recommendations (
            recommendation_id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            subject_id TEXT NOT NULL,
            first_seen REAL NOT NULL,
            last_seen REAL NOT NULL,
            status TEXT NOT NULL,
            evidence_json TEXT NOT NULL
        );
        """
        )
        privacy_vacuum_required = False
        request_columns = {
            str(row["name"])
            for row in connection.execute("PRAGMA table_info(requests)").fetchall()
        }
        if "request_key" not in request_columns:
            connection.executescript(
                """
                ALTER TABLE requests RENAME TO requests_legacy;
                CREATE TABLE requests (
                    request_key TEXT PRIMARY KEY,
                    started_at REAL NOT NULL,
                    observed_at REAL NOT NULL,
                    host_key TEXT NOT NULL,
                    host_public_id TEXT NOT NULL,
                    host_scope TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    policy_id TEXT NOT NULL,
                    original_policy_id TEXT NOT NULL,
                    rule_type TEXT NOT NULL,
                    is_final INTEGER NOT NULL,
                    is_direct INTEGER NOT NULL,
                    failed INTEGER NOT NULL,
                    rejected INTEGER NOT NULL,
                    completed INTEGER NOT NULL,
                    error_category TEXT NOT NULL,
                    total_ms REAL,
                    dns_ms REAL,
                    connect_ms REAL
                );
                DROP TABLE requests_legacy;
                CREATE INDEX requests_started_idx ON requests(started_at);
                CREATE INDEX requests_scope_idx ON requests(host_scope, started_at);
                """
            )
            privacy_vacuum_required = True
        transitional_rows = connection.execute(
            """
            SELECT COUNT(*) FROM requests
            WHERE request_key LIKE 'legacy:%' OR request_key LIKE 'migrated:%'
            """
        ).fetchone()[0]
        if int(transitional_rows or 0):
            connection.execute(
                """
                DELETE FROM requests
                WHERE request_key LIKE 'legacy:%' OR request_key LIKE 'migrated:%'
                """
            )
            privacy_vacuum_required = True
        connection.execute(
            """
            UPDATE requests
            SET request_key = 'migrated:' || lower(hex(randomblob(16)))
            WHERE request_key LIKE 'legacy:%'
            """
        )
        connection.execute(
            """
            UPDATE recommendations SET status = 'pending_investigation_approval'
            WHERE status IN ('pending', 'pending_approval')
            """
        )
        connection.commit()
        if privacy_vacuum_required:
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            connection.execute("VACUUM")
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        os.chmod(database_path, 0o600)
    except (OSError, sqlite3.Error) as exc:
        connection.close()
        raise MonitorError("database_unavailable") from exc
    return connection


def record_health(
    connection: sqlite3.Connection,
    component: str,
    ok: bool,
    code: str,
    count_value: int = 0,
    sampled_at: Optional[float] = None,
) -> None:
    connection.execute(
        "INSERT INTO health_events(sampled_at, component, ok, code, count_value) VALUES (?, ?, ?, ?, ?)",
        (sampled_at or utc_now(), component, int(ok), code[:64], int(count_value)),
    )


def run_surge_cli(config: Mapping[str, Any], arguments: Sequence[str], timeout: int = 15) -> Any:
    executable = Path(str(config["surge_cli_path"]))
    if not executable.is_file() or not os.access(str(executable), os.X_OK):
        raise MonitorError("surge_cli_unavailable")
    try:
        completed = subprocess.run(
            [str(executable), "--raw", *arguments],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise MonitorError("surge_cli_timeout") from exc
    except OSError as exc:
        raise MonitorError("surge_cli_exec_error") from exc
    if completed.returncode != 0:
        raise MonitorError("surge_cli_exit_" + str(completed.returncode))
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise MonitorError("surge_cli_invalid_json") from exc
    if payload is None:
        raise MonitorError("surge_cli_empty")
    return payload


def collect_requests(
    connection: sqlite3.Connection,
    config: Mapping[str, Any],
    secret: bytes,
    cn_suffixes: Sequence[str],
    now: Optional[float] = None,
    payload: Any = None,
) -> int:
    sampled_at = now or utc_now()
    if payload is None:
        payload = run_surge_cli(config, ["dump", "request"])
    if not isinstance(payload, Mapping) or not isinstance(payload.get("recent-requests"), list):
        raise MonitorError("request_schema_invalid")

    recent = payload["recent-requests"]
    if storage_backpressure(connection):
        record_health(connection, "request", True, "storage_backpressure", len(recent), sampled_at)
        connection.commit()
        return 0
    previous_request_health = connection.execute(
        "SELECT MAX(sampled_at) AS value FROM health_events WHERE component = 'request'"
    ).fetchone()["value"]
    probe_hosts = probe_host_categories(config)
    privacy = config["privacy"]
    rows = []
    seen_rows = []
    request_keys = []
    for item in recent:
        if not isinstance(item, Mapping):
            continue
        request_id = item.get("id")
        if isinstance(request_id, str) and request_id.isdigit():
            request_id = int(request_id)
        if isinstance(request_id, bool) or not isinstance(request_id, int):
            continue
        started = item.get("startDate")
        started_at = float(started) if isinstance(started, (int, float)) else sampled_at
        if started_at > sampled_at + 86400 or started_at < 946684800:
            started_at = sampled_at
        request_material = "{}\0{}\0{:.6f}".format(
            item.get("engineIdentifier") or "default",
            request_id,
            started_at,
        )
        request_key = stable_id(secret, "request", request_material, 32)
        request_keys.append(request_key)
        rule_type, is_final = classify_rule(item.get("rule"))
        failed = bool(item.get("failed"))
        rejected = bool(item.get("rejected"))
        completed = bool(item.get("completed"))
        seen_rows.append((request_key, sampled_at, int(completed or failed or rejected)))
        raw_host = normalize_hostname(item.get("remoteHost"))
        category = classify_host(raw_host, probe_hosts, cn_suffixes, item.get("rule"))
        host_key, host_scope = privacy_host(
            raw_host,
            category,
            is_final and (failed or rejected),
            bool(privacy.get("store_final_hostnames", True)),
            secret,
        )
        should_store = category != "other" or host_scope == "final_candidate"
        if not should_store:
            continue
        host_public_id = "host#" + stable_id(secret, "host-public", raw_host or host_key, 12)
        client_value = str(item.get("deviceName") or item.get("sourceAddress") or item.get("local") or "unknown")
        client_id = "client#" + stable_id(secret, "client", client_value)
        policy_id = anonymize_policy(item.get("policyName"), secret)
        original_policy_id = anonymize_policy(item.get("originalPolicyName"), secret)
        rows.append(
            (
                request_key,
                started_at,
                sampled_at,
                host_key,
                host_public_id,
                host_scope,
                client_id,
                policy_id,
                original_policy_id,
                rule_type,
                int(is_final),
                int(policy_id == "DIRECT" or original_policy_id == "DIRECT"),
                int(failed),
                int(rejected),
                int(completed),
                classify_error(item.get("notes"), failed, rejected),
                total_duration_ms(item),
                timing_ms(item.get("timingRecords"), r"dns"),
                timing_ms(item.get("timingRecords"), r"tcp|connect"),
            )
        )

    unique_keys = sorted(set(request_keys))
    existing_seen = set()
    if unique_keys:
        placeholders = ",".join("?" for _ in unique_keys)
        existing_seen = {
            str(row["request_key"])
            for row in connection.execute(
                "SELECT request_key FROM request_seen WHERE request_key IN (" + placeholders + ")",
                unique_keys,
            )
        }
    previous_seen_at = connection.execute(
        "SELECT MAX(last_seen) AS value FROM request_seen"
    ).fetchone()["value"]
    connection.executemany(
        """
        INSERT INTO request_seen(request_key, last_seen, finalized) VALUES (?, ?, ?)
        ON CONFLICT(request_key) DO UPDATE SET
            last_seen = excluded.last_seen,
            finalized = MAX(request_seen.finalized, excluded.finalized)
        """,
        seen_rows,
    )

    detail_keys = sorted({str(row[0]) for row in rows})
    existing_details = set()
    if detail_keys:
        placeholders = ",".join("?" for _ in detail_keys)
        existing_details = {
            str(row["request_key"])
            for row in connection.execute(
                "SELECT request_key FROM requests WHERE request_key IN (" + placeholders + ")",
                detail_keys,
            )
        }
    connection.executemany(
        """
        INSERT INTO requests(
            request_key, started_at, observed_at, host_key, host_public_id,
            host_scope, client_id,
            policy_id, original_policy_id, rule_type, is_final, is_direct,
            failed, rejected, completed, error_category, total_ms, dns_ms, connect_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(request_key) DO UPDATE SET
            observed_at = excluded.observed_at,
            host_key = excluded.host_key,
            host_public_id = excluded.host_public_id,
            host_scope = excluded.host_scope,
            client_id = excluded.client_id,
            policy_id = excluded.policy_id,
            original_policy_id = excluded.original_policy_id,
            rule_type = excluded.rule_type,
            is_final = excluded.is_final,
            is_direct = excluded.is_direct,
            failed = MAX(requests.failed, excluded.failed),
            rejected = MAX(requests.rejected, excluded.rejected),
            completed = MAX(requests.completed, excluded.completed),
            error_category = CASE
                WHEN excluded.failed = 1 OR excluded.rejected = 1
                THEN excluded.error_category ELSE requests.error_category END,
            total_ms = COALESCE(excluded.total_ms, requests.total_ms),
            dns_ms = COALESCE(excluded.dns_ms, requests.dns_ms),
            connect_ms = COALESCE(excluded.connect_ms, requests.connect_ms)
        """,
        rows,
    )
    inserted = len(set(detail_keys) - existing_details)

    buffer_saturated = (
        len(unique_keys) >= 200
        and previous_seen_at is not None
        and not existing_seen
    )
    record_health(connection, "request", True, "ok", len(unique_keys), sampled_at)
    monitor_interrupted = previous_request_health is not None and (
        sampled_at - float(previous_request_health)
        > max(120, int(config["request_poll_seconds"]) * 4)
    )
    if monitor_interrupted:
        record_health(connection, "coverage", False, "monitor_gap", 1, sampled_at)
    elif buffer_saturated:
        record_health(connection, "coverage", False, "request_gap", 1, sampled_at)
    connection.commit()
    return inserted


def _profile_sections(profile: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = ""
    for raw_line in profile.splitlines():
        line = raw_line.strip()
        match = re.fullmatch(r"\[([^]]+)\]", line)
        if match:
            current = match.group(1).lower()
            sections.setdefault(current, [])
            continue
        if current and line and not line.startswith(("#", ";")):
            sections[current].append(line)
    return sections


def _profile_setting(lines: Sequence[str], key: str) -> str:
    pattern = re.compile(r"^" + re.escape(key) + r"\s*=\s*(.*?)\s*$", re.IGNORECASE)
    for line in lines:
        match = pattern.match(line)
        if match:
            return match.group(1)
    return ""


def audit_profile(profile: str) -> dict[str, bool]:
    sections = _profile_sections(profile)
    general = sections.get("general", [])
    host = sections.get("host", [])
    rules = sections.get("rule", [])
    dns_server = _profile_setting(general, "dns-server").lower()
    encrypted_dns = _profile_setting(general, "encrypted-dns-server").lower()
    use_local = _profile_setting(general, "use-local-host-item-for-proxy").lower()
    hijack = _profile_setting(general, "hijack-dns").lower()
    follow = _profile_setting(general, "encrypted-dns-follow-outbound-mode").lower()
    host_text = "\n".join(host).lower()
    global_resolvers = [
        value.strip()
        for setting in (dns_server, encrypted_dns)
        for value in setting.split(",")
        if value.strip()
    ]
    cn_dns_lines = [line.lower() for line in host if "cn_dns_domains" in line.lower()]
    proxy_node_lines = [line.lower() for line in host if "proxy-node-domains" in line.lower()]
    final_lines = [line for line in rules if line.upper().startswith("FINAL,")]
    final_last = bool(rules) and rules[-1].upper().startswith("FINAL,")
    return {
        "global_dns_excludes_domestic": not any(
            needle in dns_server or needle in encrypted_dns for needle in DOMESTIC_DNS_NEEDLES
        ),
        "overseas_dns_present": any(
            needle in dns_server or needle in encrypted_dns for needle in OVERSEAS_DNS_NEEDLES
        ),
        "global_dns_matches_known_overseas": bool(global_resolvers)
        and all(any(needle in resolver for needle in OVERSEAS_DNS_NEEDLES) for resolver in global_resolvers),
        "use_local_host_for_proxy_false": use_local == "false",
        "hijack_all_dns": "*:53" in hijack,
        "encrypted_dns_follows_outbound": follow == "true",
        "cn_dns_domain_set_present": "domain-set:" in host_text and "cn_dns_domains" in host_text,
        "cn_dns_domain_set_uses_domestic": bool(cn_dns_lines)
        and all(any(needle in line for needle in DOMESTIC_DNS_NEEDLES) for line in cn_dns_lines),
        "proxy_node_domain_set_present": "domain-set:" in host_text and "proxy-node-domains" in host_text,
        "proxy_node_domain_set_uses_domestic": bool(proxy_node_lines)
        and all(any(needle in line for needle in DOMESTIC_DNS_NEEDLES) for line in proxy_node_lines),
        "final_rule_present": bool(final_lines),
        "final_rule_is_last": final_last,
    }


def collect_profile_audit(
    connection: sqlite3.Connection,
    config: Mapping[str, Any],
    now: Optional[float] = None,
    payload: Any = None,
) -> dict[str, bool]:
    sampled_at = now or utc_now()
    if payload is None:
        payload = run_surge_cli(config, ["dump", "profile", "effective"])
    if not isinstance(payload, Mapping) or not isinstance(payload.get("profile"), str):
        raise MonitorError("profile_schema_invalid")
    profile = payload["profile"]
    profile_id = hashlib.sha256(profile.encode("utf-8")).hexdigest()[:16]
    results = audit_profile(profile)
    connection.executemany(
        "INSERT OR REPLACE INTO profile_audits(sampled_at, profile_id, code, ok) VALUES (?, ?, ?, ?)",
        [(sampled_at, profile_id, code, int(ok)) for code, ok in results.items()],
    )
    record_health(connection, "profile", True, "ok", len(results), sampled_at)
    connection.commit()
    return results


def classify_dns_server(value: Any) -> str:
    text = str(value or "").lower()
    if any(needle in text for needle in DOMESTIC_DNS_NEEDLES):
        return "domestic"
    if any(needle in text for needle in OVERSEAS_DNS_NEEDLES):
        return "overseas"
    if "system" in text:
        return "system"
    if "local" in text or not text:
        return "local_or_unknown"
    return "other"


def collect_dns(
    connection: sqlite3.Connection,
    config: Mapping[str, Any],
    secret: bytes,
    cn_suffixes: Sequence[str],
    now: Optional[float] = None,
    payload: Any = None,
) -> int:
    sampled_at = now or utc_now()
    if payload is None:
        payload = run_surge_cli(config, ["dump", "dns"])
    if not isinstance(payload, Mapping) or not isinstance(payload.get("dnsCache"), list):
        raise MonitorError("dns_schema_invalid")
    if storage_backpressure(connection):
        record_health(connection, "dns", True, "storage_backpressure", 0, sampled_at)
        connection.commit()
        return 0
    probe_hosts = probe_host_categories(config)
    recent_candidate_hosts = {
        str(row["host_key"])
        for row in connection.execute(
            """
            SELECT DISTINCT host_key FROM requests
            WHERE started_at >= ?
              AND host_scope IN ('domestic', 'google', 'openai', 'us_platform', 'final_candidate')
              AND (failed = 1 OR is_final = 1)
              AND host_key NOT LIKE '__%'
            """,
            (sampled_at - 86400,),
        )
    }
    rows = []
    for item in payload["dnsCache"]:
        if not isinstance(item, Mapping):
            continue
        host = normalize_hostname(item.get("domain"))
        is_probe_host = any(
            host == focus_host or host.endswith("." + focus_host)
            for focus_host in probe_hosts
        )
        if not is_probe_host and host not in recent_candidate_hosts:
            continue
        data = item.get("data") if isinstance(item.get("data"), list) else []
        logs = item.get("logs") if isinstance(item.get("logs"), list) else []
        success = bool(data)
        error = classify_error(logs, not success, False)
        time_cost = item.get("timeCost")
        time_ms = float(time_cost) * 1000 if isinstance(time_cost, (int, float)) else None
        answer_material = "\0".join(sorted(str(value) for value in data))
        answer_id = stable_id(secret, "dns-answer", answer_material) if answer_material else "none"
        rows.append(
            (
                sampled_at,
                host,
                classify_dns_server(item.get("server")),
                int(success),
                error,
                time_ms,
                len(data),
                answer_id,
            )
        )
    connection.executemany(
        """
        INSERT INTO dns_samples(
            sampled_at, host_key, server_class, success, error_category,
            time_ms, answer_count, answer_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    record_health(connection, "dns", True, "ok", len(rows), sampled_at)
    connection.commit()
    return len(rows)


def classify_event(item: Mapping[str, Any]) -> str:
    text = (str(item.get("type", "")) + " " + str(item.get("content", ""))).lower()
    if "dns" in text:
        return "dns"
    if any(term in text for term in ("network", "interface", "route", "wifi")):
        return "network"
    if any(term in text for term in ("proxy", "policy", "connection")):
        return "proxy"
    if any(term in text for term in ("profile", "reload", "module")):
        return "profile"
    if "dhcp" in text:
        return "dhcp"
    if any(term in text for term in ("error", "fail", "warning")):
        return "error"
    return "other"


def collect_events(
    connection: sqlite3.Connection,
    config: Mapping[str, Any],
    secret: bytes,
    now: Optional[float] = None,
    payload: Any = None,
) -> int:
    sampled_at = now or utc_now()
    if payload is None:
        payload = run_surge_cli(config, ["dump", "event"])
    if not isinstance(payload, Mapping) or not isinstance(payload.get("events"), list):
        raise MonitorError("event_schema_invalid")
    if storage_backpressure(connection):
        record_health(connection, "event", True, "storage_backpressure", 0, sampled_at)
        connection.commit()
        return 0
    rows = []
    for item in payload["events"]:
        if not isinstance(item, Mapping):
            continue
        identifier = str(item.get("identifier") or "")
        date = item.get("date")
        material = identifier + "\0" + str(date) + "\0" + str(item.get("type", ""))
        rows.append((stable_id(secret, "event", material, 20), sampled_at, classify_event(item)))
    before = connection.total_changes
    connection.executemany(
        "INSERT OR IGNORE INTO runtime_events(event_id, sampled_at, category) VALUES (?, ?, ?)", rows
    )
    inserted = connection.total_changes - before
    record_health(connection, "event", True, "ok", inserted, sampled_at)
    connection.commit()
    return inserted


def _float_or_none(value: str) -> Optional[float]:
    try:
        return max(0.0, float(value) * 1000.0)
    except (TypeError, ValueError):
        return None


def probe_error(returncode: int, stderr: str, http_code: int, healthy: bool) -> str:
    if returncode == 0 and healthy:
        return "none"
    text = stderr.lower()
    if "resolve" in text or returncode in {5, 6}:
        return "dns"
    if "timed out" in text or returncode == 28:
        return "timeout"
    if "refused" in text or returncode == 7:
        return "refused"
    if "ssl" in text or "certificate" in text or returncode in {35, 51, 58, 60}:
        return "tls"
    if returncode == 0 and http_code >= 500:
        return "http_5xx"
    if returncode == 0:
        return "unexpected_status"
    return "other"


def run_probe(probe: Mapping[str, Any], secret: bytes, timeout: int = 20) -> dict[str, Any]:
    format_string = "%{http_code}\t%{time_namelookup}\t%{time_connect}\t%{time_appconnect}\t%{time_total}\t%{remote_ip}"
    command = [
        "/usr/bin/curl",
        "-4",
        "--silent",
        "--show-error",
        "--output",
        "/dev/null",
        "--connect-timeout",
        "8",
        "--max-time",
        "15",
        "--user-agent",
        "RuleMesh-Surge-Monitor/1.0",
        "--write-out",
        format_string,
        str(probe["url"]),
    ]
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "reachable": False,
            "healthy": False,
            "error_category": "timeout",
            "http_code": 0,
            "dns_ms": None,
            "connect_ms": None,
            "tls_ms": None,
            "total_ms": None,
            "remote_id": "none",
        }
    fields = completed.stdout.strip().split("\t")
    while len(fields) < 6:
        fields.append("")
    try:
        http_code = int(fields[0])
    except ValueError:
        http_code = 0
    reachable = completed.returncode == 0 and http_code > 0
    healthy = reachable and http_code in set(int(value) for value in probe["accepted_status"])
    remote_id = "none"
    if fields[5]:
        remote_id = "remote#" + stable_id(secret, "remote", fields[5])
    return {
        "reachable": reachable,
        "healthy": healthy,
        "error_category": probe_error(completed.returncode, completed.stderr, http_code, healthy),
        "http_code": http_code,
        "dns_ms": _float_or_none(fields[1]),
        "connect_ms": _float_or_none(fields[2]),
        "tls_ms": _float_or_none(fields[3]),
        "total_ms": _float_or_none(fields[4]),
        "remote_id": remote_id,
    }


def collect_probes(
    connection: sqlite3.Connection,
    config: Mapping[str, Any],
    secret: bytes,
    now: Optional[float] = None,
    runner: Any = run_probe,
) -> int:
    sampled_at = now or utc_now()
    rows = []
    probes = list(config["probes"])
    if storage_backpressure(connection):
        record_health(connection, "probe", True, "storage_backpressure", 0, sampled_at)
        connection.commit()
        return 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(probes))) as executor:
        results = list(executor.map(lambda probe: runner(probe, secret), probes))
    for probe, result in zip(probes, results):
        host = normalize_hostname(urllib.parse.urlsplit(probe["url"]).hostname)
        rows.append(
            (
                sampled_at,
                probe["name"],
                probe["category"],
                host,
                int(bool(result["reachable"])),
                int(bool(result["healthy"])),
                str(result["error_category"]),
                int(result["http_code"]),
                result["dns_ms"],
                result["connect_ms"],
                result["tls_ms"],
                result["total_ms"],
                str(result["remote_id"]),
            )
        )
    connection.executemany(
        """
        INSERT INTO probes(
            sampled_at, name, category, host_key, reachable, healthy,
            error_category, http_code, dns_ms, connect_ms, tls_ms, total_ms, remote_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    failures = sum(1 for row in rows if not row[5])
    record_health(connection, "probe", failures == 0, "ok" if failures == 0 else "probe_failure", failures, sampled_at)
    connection.commit()
    return len(rows)


def collect_snapshot(
    connection: sqlite3.Connection,
    config: Mapping[str, Any],
    secret: bytes,
    cn_suffixes: Sequence[str],
    now: Optional[float] = None,
) -> None:
    sampled_at = now or utc_now()
    collectors = (
        ("profile", lambda: collect_profile_audit(connection, config, sampled_at)),
        ("dns", lambda: collect_dns(connection, config, secret, cn_suffixes, sampled_at)),
        ("event", lambda: collect_events(connection, config, secret, sampled_at)),
    )
    for component, collector in collectors:
        try:
            collector()
        except (MonitorError, sqlite3.Error) as exc:
            code = exc.code if isinstance(exc, MonitorError) else "database_error"
            try:
                record_health(connection, component, False, code, 0, sampled_at)
                connection.commit()
            except sqlite3.Error:
                connection.rollback()
    analyze(connection, config, hours=24, now=sampled_at, persist=True)


def database_size_bytes(connection: sqlite3.Connection) -> int:
    database_path = ""
    for row in connection.execute("PRAGMA database_list"):
        if str(row[1]) == "main":
            database_path = str(row[2] or "")
            break
    if not database_path:
        page_count = int(connection.execute("PRAGMA page_count").fetchone()[0])
        page_size = int(connection.execute("PRAGMA page_size").fetchone()[0])
        return page_count * page_size
    total = 0
    for suffix in ("", "-wal", "-shm"):
        try:
            total += Path(database_path + suffix).stat().st_size
        except OSError:
            pass
    return total


def storage_backpressure(connection: sqlite3.Connection) -> bool:
    row = connection.execute(
        """
        SELECT ok, code FROM health_events
        WHERE component = 'storage' ORDER BY sampled_at DESC LIMIT 1
        """
    ).fetchone()
    return bool(row is not None and not bool(row["ok"]) and row["code"] == "budget_exceeded")


def _cap_table_rows(
    connection: sqlite3.Connection,
    table: str,
    order_column: str,
    maximum_rows: int,
) -> None:
    connection.execute(
        "DELETE FROM {0} WHERE rowid NOT IN "
        "(SELECT rowid FROM {0} ORDER BY {1} DESC LIMIT ?)".format(table, order_column),
        (maximum_rows,),
    )


def _vacuum_database(connection: sqlite3.Connection) -> None:
    connection.commit()
    connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    connection.execute("VACUUM")
    connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")


def purge_old_data(
    connection: sqlite3.Connection,
    retention_days: int,
    now: Optional[float] = None,
    max_database_mb: int = DEFAULT_MAX_DATABASE_MB,
) -> None:
    current = now or utc_now()
    cutoff = current - retention_days * 86400
    connection.execute(
        "DELETE FROM requests WHERE started_at < ?",
        (current - REQUEST_DETAIL_RETENTION_HOURS * 3600,),
    )
    connection.execute(
        "DELETE FROM requests WHERE host_scope = 'other' OR (host_scope = 'final_candidate' AND failed = 0 AND rejected = 0)"
    )
    connection.execute(
        "DELETE FROM request_seen WHERE last_seen < ?",
        (current - REQUEST_SEEN_RETENTION_SECONDS,),
    )
    for table, column in (
        ("probes", "sampled_at"),
        ("dns_samples", "sampled_at"),
        ("profile_audits", "sampled_at"),
        ("runtime_events", "sampled_at"),
        ("health_events", "sampled_at"),
        ("recommendations", "last_seen"),
    ):
        connection.execute("DELETE FROM " + table + " WHERE " + column + " < ?", (cutoff,))
    connection.commit()

    limit_bytes = max_database_mb * 1024 * 1024
    size_before = database_size_bytes(connection)
    if size_before <= limit_bytes:
        record_health(
            connection,
            "storage",
            True,
            "ok",
            (size_before + 1024 * 1024 - 1) // (1024 * 1024),
            current,
        )
        connection.commit()
        return

    # 超限时优先牺牲成功明细和旧去重键，再逐级限制高基数表。
    connection.execute(
        "DELETE FROM requests WHERE failed = 0 AND rejected = 0 AND started_at < ?",
        (current - 6 * 3600,),
    )
    connection.execute(
        "DELETE FROM request_seen WHERE last_seen < ?",
        (current - 600,),
    )
    try:
        _vacuum_database(connection)
    except sqlite3.Error:
        connection.rollback()

    target_bytes = int(limit_bytes * 0.9)
    phases = (
        {
            "requests": 50000,
            "request_seen": 100000,
            "dns_samples": 100000,
            "probes": 20000,
            "profile_audits": 10000,
            "runtime_events": 20000,
            "health_events": 20000,
            "recommendations": 2000,
        },
        {
            "requests": 10000,
            "request_seen": 25000,
            "dns_samples": 25000,
            "probes": 5000,
            "profile_audits": 2000,
            "runtime_events": 5000,
            "health_events": 5000,
            "recommendations": 500,
        },
        {
            "requests": 2000,
            "request_seen": 5000,
            "dns_samples": 5000,
            "probes": 1000,
            "profile_audits": 500,
            "runtime_events": 1000,
            "health_events": 1000,
            "recommendations": 200,
        },
        {
            "requests": 200,
            "request_seen": 500,
            "dns_samples": 500,
            "probes": 200,
            "profile_audits": 120,
            "runtime_events": 200,
            "health_events": 500,
            "recommendations": 100,
        },
    )
    order_columns = {
        "requests": "started_at",
        "request_seen": "last_seen",
        "dns_samples": "sampled_at",
        "probes": "sampled_at",
        "profile_audits": "sampled_at",
        "runtime_events": "sampled_at",
        "health_events": "sampled_at",
        "recommendations": "last_seen",
    }
    for caps in phases:
        if database_size_bytes(connection) <= target_bytes:
            break
        for table, maximum_rows in caps.items():
            _cap_table_rows(connection, table, order_columns[table], maximum_rows)
        try:
            _vacuum_database(connection)
        except sqlite3.Error:
            connection.rollback()
            break
    size_after = database_size_bytes(connection)
    record_health(
        connection,
        "storage",
        False,
        "budget_compacted" if size_after <= limit_bytes else "budget_exceeded",
        (size_after + 1024 * 1024 - 1) // (1024 * 1024),
        current,
    )
    connection.commit()


def recommendation_id(kind: str, subject: str) -> str:
    digest = hashlib.sha256((kind + "\0" + subject).encode("utf-8")).hexdigest()[:8].upper()
    return "RM-INV-" + kind + "-" + digest


def _recommendation(
    kind: str,
    subject: str,
    title: str,
    evidence: Mapping[str, Any],
    proposal: str,
    risk: str,
) -> dict[str, Any]:
    return {
        "recommendation_id": recommendation_id(kind, subject),
        "kind": kind,
        "status": "pending_investigation_approval",
        "subject": subject,
        "title": title,
        "diagnosis": title,
        "evidence": dict(evidence),
        "proposal": proposal,
        "risk": risk,
        "rollback": "该 ID 只授权只读调查，不产生配置变更，因此无需回滚。",
        "validation": "只读调查必须补齐目标归属、实际规则命中、策略路径、IP 出口和 DNS 出口证据，之后另行生成不可变的 RM-EXEC 变更方案。",
    }


def public_recommendation(item: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in item.items() if key != "subject"}


def profile_window_info(
    connection: sqlite3.Connection, requested_cutoff: float
) -> tuple[float, int, Optional[float]]:
    rows = connection.execute(
        """
        SELECT sampled_at, MIN(profile_id) AS profile_id
        FROM profile_audits
        WHERE sampled_at >= ?
        GROUP BY sampled_at
        ORDER BY sampled_at
        """,
        (requested_cutoff,),
    ).fetchall()
    previous: Optional[str] = None
    changes = 0
    last_change: Optional[float] = None
    for row in rows:
        profile_id = str(row["profile_id"])
        if previous is not None and profile_id != previous:
            changes += 1
            last_change = float(row["sampled_at"])
        previous = profile_id
    latest_gap = connection.execute(
        """
        SELECT MAX(sampled_at) AS value FROM health_events
        WHERE sampled_at >= ? AND (
            (component = 'coverage' AND code IN ('request_gap', 'monitor_gap'))
            OR (component IN ('request', 'profile', 'dns', 'event') AND ok = 0)
            OR (component = 'probe' AND code = 'probe_exec_error')
        )
        """,
        (requested_cutoff,),
    ).fetchone()["value"]
    effective_cutoff = max(
        requested_cutoff,
        last_change or requested_cutoff,
        float(latest_gap) if latest_gap is not None else requested_cutoff,
    )
    return effective_cutoff, changes, last_change


def summarize_group_evidence(entries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    samples = sum(int(item.get("samples") or 0) for item in entries)
    failures = sum(int(item.get("failures") or 0) for item in entries)
    result: dict[str, Any] = {
        "targets": sorted({str(item.get("target")) for item in entries})[:5],
        "target_count": len({str(item.get("target")) for item in entries}),
        "samples": samples,
        "failures": failures,
        "rejected": sum(int(item.get("rejected") or 0) for item in entries),
        "failure_ratio": round(failures / samples, 3) if samples else 0.0,
        "final_hits": sum(int(item.get("final_hits") or 0) for item in entries),
        "dns_failures": sum(int(item.get("dns_failures") or 0) for item in entries),
        "slow_dns_samples": sum(int(item.get("slow_dns_samples") or 0) for item in entries),
        "slow_path_samples": sum(int(item.get("slow_path_samples") or 0) for item in entries),
        "policy": str(entries[0].get("policy", "UNKNOWN")) if entries else "UNKNOWN",
    }
    for field in ("avg_dns_ms", "avg_connect_ms", "avg_total_ms"):
        weighted = [
            (float(item[field]), int(item.get("samples") or 0))
            for item in entries
            if item.get(field) is not None
        ]
        weight = sum(value[1] for value in weighted)
        result[field] = (
            round(sum(value * count for value, count in weighted) / weight, 1)
            if weight
            else None
        )
    maxima = [float(item["max_total_ms"]) for item in entries if item.get("max_total_ms") is not None]
    result["max_total_ms"] = round(max(maxima), 1) if maxima else None
    dns_samples = sum(int(item.get("dns_samples") or 0) for item in entries)
    if dns_samples:
        result["dns_samples"] = dns_samples
        result["dns_sample_failures"] = sum(
            int(item.get("dns_sample_failures") or 0) for item in entries
        )
        server_classes = {
            value
            for item in entries
            for value in str(item.get("dns_server_classes") or "").split(",")
            if value
        }
        result["dns_server_classes"] = ",".join(sorted(server_classes)) or "unknown"
    return result


def analyze(
    connection: sqlite3.Connection,
    config: Mapping[str, Any],
    hours: int = 24,
    now: Optional[float] = None,
    persist: bool = True,
) -> list[dict[str, Any]]:
    sampled_at = now or utc_now()
    requested_cutoff = sampled_at - hours * 3600
    cutoff, _profile_changes, _last_profile_change = profile_window_info(
        connection, requested_cutoff
    )
    thresholds = config["thresholds"]
    min_samples = int(thresholds["minimum_samples"])
    min_failures = int(thresholds["minimum_failures"])
    failure_ratio = float(thresholds["failure_ratio"])
    final_hit_count = int(thresholds["final_hit_count"])
    dns_slow_ms = int(thresholds["dns_slow_ms"])
    connect_slow_ms = int(thresholds["connect_slow_ms"])
    total_slow_ms = int(thresholds["total_slow_ms"])
    recommendations: list[dict[str, Any]] = []
    us_path_groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    cn_path_groups: dict[str, list[dict[str, Any]]] = {}

    latest_profile_time = connection.execute(
        "SELECT MAX(sampled_at) AS value FROM profile_audits"
    ).fetchone()["value"]
    if latest_profile_time is not None:
        failed_codes = [
            row["code"]
            for row in connection.execute(
                "SELECT code FROM profile_audits WHERE sampled_at = ? AND ok = 0 ORDER BY code",
                (latest_profile_time,),
            )
        ]
        safety_codes = failed_codes
        if safety_codes:
            recommendations.append(
                _recommendation(
                    "DNS-SAFETY",
                    ",".join(safety_codes),
                    "Surge DNS / 配置 / 规则基础边界出现回归",
                    {"failed_checks": safety_codes},
                    "先只读核对生效 profile 与仓库 DNS 安全检查，再生成最小修复 diff；未经批准不重载配置。",
                    "高：错误修改 DNS 可能造成泄漏或代理节点无法解析。",
                )
            )

    host_rows = connection.execute(
        """
        SELECT host_key, MIN(host_public_id) AS host_public_id, host_scope, policy_id,
               COUNT(*) AS samples,
               SUM(CASE WHEN failed = 1 OR rejected = 1 THEN 1 ELSE 0 END) AS failures,
               SUM(rejected) AS rejected,
               SUM(is_final) AS final_hits,
               SUM(CASE WHEN error_category = 'dns' THEN 1 ELSE 0 END) AS dns_failures,
               AVG(dns_ms) AS avg_dns_ms,
               AVG(connect_ms) AS avg_connect_ms,
               AVG(total_ms) AS avg_total_ms,
               MAX(total_ms) AS max_total_ms,
               SUM(CASE WHEN dns_ms >= ? THEN 1 ELSE 0 END) AS slow_dns_samples,
               SUM(CASE WHEN connect_ms >= ? OR total_ms >= ? THEN 1 ELSE 0 END) AS slow_path_samples
        FROM requests
        WHERE started_at >= ?
          AND host_scope IN ('domestic', 'google', 'openai', 'us_platform', 'final_candidate')
        GROUP BY host_key, host_scope, policy_id
        """,
        (dns_slow_ms, connect_slow_ms, total_slow_ms, cutoff),
    ).fetchall()
    for row in host_rows:
        samples = int(row["samples"] or 0)
        failures = int(row["failures"] or 0)
        final_hits = int(row["final_hits"] or 0)
        ratio = failures / samples if samples else 0.0
        failure_trigger = failures >= min_failures and ratio >= failure_ratio
        slow_dns_samples = int(row["slow_dns_samples"] or 0)
        slow_path_samples = int(row["slow_path_samples"] or 0)
        slow_trigger = slow_dns_samples >= min_failures or slow_path_samples >= min_failures
        if samples < min_samples or not (failure_trigger or slow_trigger):
            continue
        host = str(row["host_key"])
        scope = str(row["host_scope"])
        display_host = host
        if scope == "final_candidate":
            display_host = "域名#" + str(row["host_public_id"]).removeprefix("host#")
        evidence = {
            "target": display_host,
            "samples": samples,
            "failures": failures,
            "rejected": int(row["rejected"] or 0),
            "failure_ratio": round(ratio, 3),
            "final_hits": final_hits,
            "dns_failures": int(row["dns_failures"] or 0),
            "avg_dns_ms": round(float(row["avg_dns_ms"]), 1) if row["avg_dns_ms"] is not None else None,
            "avg_connect_ms": round(float(row["avg_connect_ms"]), 1)
            if row["avg_connect_ms"] is not None
            else None,
            "avg_total_ms": round(float(row["avg_total_ms"]), 1)
            if row["avg_total_ms"] is not None
            else None,
            "max_total_ms": round(float(row["max_total_ms"]), 1)
            if row["max_total_ms"] is not None
            else None,
            "slow_dns_samples": slow_dns_samples,
            "slow_path_samples": slow_path_samples,
            "policy": str(row["policy_id"]),
        }
        dns_context = connection.execute(
            """
            SELECT COUNT(*) AS samples,
                   SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) AS failures,
                   AVG(time_ms) AS avg_ms,
                   GROUP_CONCAT(DISTINCT server_class) AS server_classes
            FROM dns_samples WHERE sampled_at >= ? AND host_key = ?
            """,
            (cutoff, host),
        ).fetchone()
        if int(dns_context["samples"] or 0):
            evidence.update(
                {
                    "dns_samples": int(dns_context["samples"]),
                    "dns_sample_failures": int(dns_context["failures"] or 0),
                    "dns_sample_avg_ms": round(float(dns_context["avg_ms"]), 1)
                    if dns_context["avg_ms"] is not None
                    else None,
                    "dns_server_classes": str(dns_context["server_classes"] or "unknown"),
                }
            )
        if scope == "domestic" and final_hits >= final_hit_count and failure_trigger:
            recommendations.append(
                _recommendation(
                    "CN-FINAL",
                    host,
                    "国内目标频繁落入 FINAL 并失败",
                    evidence,
                    "核对该域名在 direct 规则与 cn_dns_domains 两条轴上的覆盖；确认归属后再补源规则、重建并复测 DNS 出口。",
                    "中：误判归属会把应代理的目标错误直连，或把普通目标交给国内 DNS。",
                )
            )
        elif scope == "domestic" and (
            int(row["dns_failures"] or 0) >= min_failures
            or slow_dns_samples >= min_failures
        ):
            recommendations.append(
                _recommendation(
                    "CN-DNS",
                    host,
                    "国内目标存在持续 DNS 失败或高延迟",
                    evidence,
                    "核对该目标是否命中 cn_dns_domains、实际解析服务器类别与 DIRECT 规则；只为确认的国内业务补白名单。",
                    "高：不得把全局 DNS 改为国内解析器。",
                )
            )
        elif scope in {"google", "openai", "us_platform"}:
            us_path_groups.setdefault((scope, str(row["policy_id"])), []).append(evidence)
        elif scope == "domestic":
            cn_path_groups.setdefault(str(row["policy_id"]), []).append(evidence)
        elif scope == "final_candidate" and final_hits >= final_hit_count:
            recommendations.append(
                _recommendation(
                    "FINAL-FAIL",
                    str(row["host_public_id"]),
                    "未分类目标落入 FINAL 后持续失败",
                    evidence,
                    "先人工确认目标归属与所需出口，再决定补 direct/proxy/region 规则；监控不会据域名自动改规则。",
                    "中：目标归属未知，自动分流风险不可接受。",
                )
            )

    for (scope, policy_id), entries in sorted(us_path_groups.items()):
        recommendations.append(
            _recommendation(
                "US-PATH",
                scope + ":" + policy_id,
                "Google/ChatGPT 等美国平台路径出现持续抖动",
                summarize_group_evidence(entries),
                "先对匿名策略 ID 对应的美国节点做定向测试并关联事件；证据确认后，再评估专用 Smart Group、fallback 或剔除不稳定节点。",
                "中：调整策略组可能改变出口 IP，一些平台会触发登录或风控验证。",
            )
        )
    for policy_id, entries in sorted(cn_path_groups.items()):
        recommendations.append(
            _recommendation(
                "CN-PATH",
                "domestic:" + policy_id,
                "国内目标直连路径持续失败或缓慢",
                summarize_group_evidence(entries),
                "只读关联相同窗口的 DNS 类别、规则命中与 TCP / 总耗时，确认是站点、直连出口还是规则顺序问题。",
                "低：当前 ID 只授权调查，不改变路由或 DNS。",
            )
        )

    probe_rows = connection.execute(
        """
        SELECT name, category, host_key, COUNT(*) AS samples,
               SUM(CASE WHEN healthy = 0 THEN 1 ELSE 0 END) AS failures,
               AVG(connect_ms) AS avg_connect_ms,
               AVG(total_ms) AS avg_total_ms,
               SUM(CASE WHEN connect_ms >= ? OR total_ms >= ? THEN 1 ELSE 0 END) AS slow_samples
        FROM probes WHERE sampled_at >= ?
        GROUP BY name, category, host_key
        """,
        (connect_slow_ms, total_slow_ms, cutoff),
    ).fetchall()
    for row in probe_rows:
        samples = int(row["samples"] or 0)
        failures = int(row["failures"] or 0)
        ratio = failures / samples if samples else 0.0
        failure_trigger = failures >= min_failures and ratio >= failure_ratio
        slow_samples = int(row["slow_samples"] or 0)
        if samples < min_samples or not (
            failure_trigger or slow_samples >= min_failures
        ):
            continue
        category = str(row["category"])
        evidence = {
            "probe": str(row["name"]),
            "samples": samples,
            "failures": failures,
            "failure_ratio": round(ratio, 3),
            "avg_connect_ms": round(float(row["avg_connect_ms"]), 1)
            if row["avg_connect_ms"] is not None
            else None,
            "avg_total_ms": round(float(row["avg_total_ms"]), 1)
            if row["avg_total_ms"] is not None
            else None,
            "slow_samples": slow_samples,
        }
        dns_context = connection.execute(
            """
            SELECT COUNT(*) AS samples,
                   SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) AS failures,
                   GROUP_CONCAT(DISTINCT server_class) AS server_classes
            FROM dns_samples WHERE sampled_at >= ? AND host_key = ?
            """,
            (cutoff, str(row["host_key"])),
        ).fetchone()
        if int(dns_context["samples"] or 0):
            evidence.update(
                {
                    "dns_samples": int(dns_context["samples"]),
                    "dns_sample_failures": int(dns_context["failures"] or 0),
                    "dns_server_classes": str(dns_context["server_classes"] or "unknown"),
                }
            )
        if category == "domestic":
            kind = "CN-PROBE"
            title = "国内主动探测持续失败或连接缓慢"
            proposal = "关联同窗口的规则命中、DNS 服务器类别与 FINAL 计数，确认是解析、直连路径还是漏匹配后再拟方案。"
            risk = "低：当前只建议进一步只读诊断。"
        else:
            kind = "US-PROBE"
            title = "Google/ChatGPT 主动探测持续失败或连接缓慢"
            proposal = "关联美国策略匿名 ID、TCP 建连阶段和 Surge 事件；确认节点抖动后再提交 Smart Group/fallback 调整方案。"
            risk = "中：后续策略调整可能改变平台看到的出口 IP。"
        recommendations.append(
            _recommendation(kind, str(row["name"]), title, evidence, proposal, risk)
        )

    gap = connection.execute(
        """
        SELECT COALESCE(SUM(count_value), 0) AS saturated_windows
        FROM health_events
        WHERE sampled_at >= ? AND component = 'coverage' AND code = 'request_gap'
        """,
        (cutoff,),
    ).fetchone()["saturated_windows"]
    request_count = connection.execute(
        "SELECT COUNT(*) AS value FROM requests WHERE started_at >= ?", (cutoff,)
    ).fetchone()["value"]
    if int(gap or 0) >= 3:
        recommendations.append(
            _recommendation(
                "COVERAGE",
                "request-poll",
                "请求采样窗口存在明显缺口",
                {"captured": int(request_count or 0), "saturated_windows": int(gap)},
                "把 request_poll_seconds 从当前值小幅下调，并观察 CPU/日志开销；不改 Surge 配置。",
                "低：仅调整本地采集频率。",
            )
        )

    unique: dict[str, dict[str, Any]] = {}
    for item in recommendations:
        unique[item["recommendation_id"]] = item
    results = list(unique.values())
    if persist:
        for item in results:
            evidence_json = json.dumps(public_recommendation(item), ensure_ascii=False, sort_keys=True)
            connection.execute(
                """
                INSERT INTO recommendations(
                    recommendation_id, kind, subject_id, first_seen, last_seen, status, evidence_json
                ) VALUES (?, ?, ?, ?, ?, 'pending_investigation_approval', ?)
                ON CONFLICT(recommendation_id) DO UPDATE SET
                    last_seen = excluded.last_seen,
                    evidence_json = excluded.evidence_json
                """,
                (
                    item["recommendation_id"],
                    item["kind"],
                    hashlib.sha256(str(item["subject"]).encode("utf-8")).hexdigest()[:16],
                    sampled_at,
                    sampled_at,
                    evidence_json,
                ),
            )
        connection.commit()
    return sorted(results, key=lambda item: item["recommendation_id"])


def local_time_text(timestamp: float) -> str:
    return dt.datetime.fromtimestamp(timestamp).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def data_quality(
    connection: sqlite3.Connection,
    config: Mapping[str, Any],
    now: Optional[float] = None,
) -> dict[str, Any]:
    sampled_at = now or utc_now()
    request_age = max(120, int(config["request_poll_seconds"]) * 4)
    snapshot_age = max(1200, int(config["snapshot_seconds"]) * 4)
    probe_age = max(3600, int(config["probe_seconds"]) * 3)
    specifications = (
        ("request", request_age, True),
        ("profile", snapshot_age, True),
        ("dns", snapshot_age, True),
        ("event", snapshot_age, True),
        ("probe", probe_age, False),
    )
    issues: list[str] = []
    latest: dict[str, Any] = {}
    latest_sample_times: dict[str, float] = {}
    for component, maximum_age, require_ok in specifications:
        row = connection.execute(
            """
            SELECT sampled_at, ok, code, count_value
            FROM health_events WHERE component = ? ORDER BY sampled_at DESC LIMIT 1
            """,
            (component,),
        ).fetchone()
        if row is None:
            issues.append(component + ":no_sample")
            latest[component] = None
            continue
        age_seconds = max(0, int(sampled_at - float(row["sampled_at"])))
        latest_sample_times[component] = float(row["sampled_at"])
        code = str(row["code"])
        latest[component] = {
            "age_seconds": age_seconds,
            "ok": bool(row["ok"]),
            "code": code,
        }
        if age_seconds > maximum_age:
            issues.append(component + ":stale")
        elif (require_ok and not bool(row["ok"])) or (
            component == "probe" and code == "probe_exec_error"
        ):
            issues.append(component + ":" + code)

    latest_gap = connection.execute(
        """
        SELECT sampled_at, component, code
        FROM health_events
        WHERE sampled_at >= ? AND (
            (component = 'coverage' AND code IN ('request_gap', 'monitor_gap'))
            OR (component IN ('request', 'profile', 'dns', 'event') AND ok = 0)
            OR (component = 'probe' AND code = 'probe_exec_error')
        )
        ORDER BY sampled_at DESC LIMIT 1
        """,
        (sampled_at - 86400,),
    ).fetchone()
    if latest_gap is not None:
        gap_time = float(latest_gap["sampled_at"])
        gap_component = str(latest_gap["component"])
        gap_code = str(latest_gap["code"])
        recovery_reason = gap_code if gap_component == "coverage" else gap_component + "_" + gap_code
        recovery_seconds = max(0, int(sampled_at - gap_time))
        required_recovery = max(
            int(config["request_poll_seconds"]) * 5,
            int(config["snapshot_seconds"]),
            min(int(config["probe_seconds"]), 900),
        )
        all_components_newer = all(
            latest_sample_times.get(component, 0) > gap_time
            for component, _maximum_age, _require_ok in specifications
        )
        latest["coverage"] = {
            "code": recovery_reason,
            "recovery_seconds": recovery_seconds,
            "required_recovery_seconds": required_recovery,
        }
        if recovery_seconds < required_recovery or not all_components_newer:
            issues.append("coverage:recovering_after_" + recovery_reason)

    storage_issue = connection.execute(
        """
        SELECT code FROM health_events
        WHERE sampled_at >= ? AND component = 'storage' AND ok = 0
        ORDER BY sampled_at DESC LIMIT 1
        """,
        (sampled_at - 86400,),
    ).fetchone()
    if storage_issue is not None:
        issues.append("storage:" + str(storage_issue["code"]))

    return {
        "status": "healthy" if not issues else "degraded",
        "ok": not issues,
        "issues": sorted(set(issues)),
        "latest": latest,
    }


def quality_recommendation(quality: Mapping[str, Any]) -> dict[str, Any]:
    issues = [str(value) for value in quality.get("issues", [])]
    return _recommendation(
        "COLLECTOR",
        ",".join(issues) or "unknown",
        "本地监控采集质量不足，暂停网络优化判断",
        {"quality": str(quality.get("status", "degraded")), "issues": issues},
        "只读核对 LaunchAgent 状态、运行副本版本、最近采集时间与有界错误日志；恢复连续新鲜样本后再生成网络建议。",
        "低：该调查不操作 Surge，也不改变规则、DNS 或策略组。",
    )


def report_markdown(
    connection: sqlite3.Connection,
    config: Mapping[str, Any],
    hours: int,
    now: Optional[float] = None,
) -> str:
    sampled_at = now or utc_now()
    requested_cutoff = sampled_at - hours * 3600
    cutoff, profile_changes, _last_profile_change = profile_window_info(
        connection, requested_cutoff
    )
    request_summary = connection.execute(
        """
        SELECT COUNT(*) AS samples, SUM(failed) AS failures, SUM(rejected) AS rejected,
               SUM(is_final) AS final_hits, COUNT(DISTINCT client_id) AS clients
        FROM requests WHERE started_at >= ?
        """,
        (cutoff,),
    ).fetchone()
    probe_summary = connection.execute(
        """
        SELECT COUNT(*) AS samples, SUM(CASE WHEN healthy = 0 THEN 1 ELSE 0 END) AS failures
        FROM probes WHERE sampled_at >= ?
        """,
        (cutoff,),
    ).fetchone()
    dns_summary = connection.execute(
        """
        SELECT COUNT(*) AS samples, SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) AS failures,
               AVG(time_ms) AS avg_ms
        FROM dns_samples WHERE sampled_at >= ?
        """,
        (cutoff,),
    ).fetchone()
    latest_profile = connection.execute(
        "SELECT MAX(sampled_at) AS value FROM profile_audits"
    ).fetchone()["value"]
    profile_failed = 0
    profile_id = "尚无样本"
    if latest_profile is not None:
        row = connection.execute(
            """
            SELECT MIN(profile_id) AS profile_id, SUM(CASE WHEN ok = 0 THEN 1 ELSE 0 END) AS failures
            FROM profile_audits WHERE sampled_at = ?
            """,
            (latest_profile,),
        ).fetchone()
        profile_id = str(row["profile_id"] or "未知")
        profile_failed = int(row["failures"] or 0)
    quality = data_quality(connection, config, sampled_at)
    recommendations = (
        analyze(connection, config, hours, sampled_at, persist=False)
        if bool(quality["ok"])
        else [quality_recommendation(quality)]
    )

    lines = [
        "# RuleMesh Surge 本地监控日报",
        "",
        "- 统计窗口：最近 {} 小时（截至 {}）".format(hours, local_time_text(sampled_at)),
        "- 有效分析起点：{}；窗口内配置指纹变化：{} 次".format(
            local_time_text(cutoff), profile_changes
        ),
        "- 关注请求明细（最多保留 36 小时）：{} 条；失败 {} 条；拒绝 {} 条；FINAL 命中 {} 条；匿名客户端 {} 个".format(
            int(request_summary["samples"] or 0),
            int(request_summary["failures"] or 0),
            int(request_summary["rejected"] or 0),
            int(request_summary["final_hits"] or 0),
            int(request_summary["clients"] or 0),
        ),
        "- 主动探测：{} 次；未达健康条件 {} 次".format(
            int(probe_summary["samples"] or 0), int(probe_summary["failures"] or 0)
        ),
        "- 关注 DNS 样本：{} 条；失败 {} 条；平均耗时 {} ms".format(
            int(dns_summary["samples"] or 0),
            int(dns_summary["failures"] or 0),
            "{:.1f}".format(float(dns_summary["avg_ms"])) if dns_summary["avg_ms"] is not None else "无",
        ),
        "- 生效配置指纹：{}；安全审计未通过项：{}".format(profile_id, profile_failed),
        "- 采集质量：{}；问题：{}".format(
            quality["status"], "、".join(quality["issues"]) if quality["issues"] else "无"
        ),
        "",
        "## 待批准只读调查",
        "",
    ]
    if not recommendations:
        lines.append("当前没有达到阈值的优化建议；监控未修改任何 Surge 或仓库配置。")
        return "\n".join(lines) + "\n"
    for item in recommendations:
        evidence = item["evidence"]
        evidence_text = "；".join("{}={}".format(key, value) for key, value in evidence.items())
        lines.extend(
            [
                "### {} · {}".format(item["recommendation_id"], item["title"]),
                "",
                "- 状态：" + str(item["status"]),
                "- 证据：" + evidence_text,
                "- 诊断：" + item["diagnosis"],
                "- 调查方案：" + item["proposal"],
                "- 风险：" + item["risk"],
                "- 回滚：" + item["rollback"],
                "- 验证：" + item["validation"],
                "- 授权：如同意开展独立只读深挖，请回复 `批准调查 {}`；该 ID 不授权任何配置变更。".format(
                    item["recommendation_id"]
                ),
                "- 执行边界：只有后续列明精确文件 / 规则 / 策略、diff、风险、回滚与复测的 `RM-EXEC-*` 再次获批后，才允许执行。",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def status_payload(connection: sqlite3.Connection, config: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "enabled": bool(config["enabled"]),
        "state_dir": str(config["state_dir"]),
        "retention_days": int(config["retention_days"]),
        "max_database_mb": int(config["max_database_mb"]),
        "quality": data_quality(connection, config),
    }
    for component in ("request", "profile", "dns", "event", "probe", "storage"):
        row = connection.execute(
            """
            SELECT sampled_at, ok, code, count_value
            FROM health_events WHERE component = ? ORDER BY sampled_at DESC LIMIT 1
            """,
            (component,),
        ).fetchone()
        result[component] = (
            {
                "sampled_at": local_time_text(float(row["sampled_at"])),
                "ok": bool(row["ok"]),
                "code": str(row["code"]),
                "count": int(row["count_value"]),
            }
            if row
            else None
        )
    return result


def collect_once(
    connection: sqlite3.Connection,
    config: Mapping[str, Any],
    secret: bytes,
    include_probe: bool = True,
) -> bool:
    cn_suffixes = parse_domain_suffixes(CN_DNS_DOMAINS_PATH)
    success = True
    try:
        collect_requests(connection, config, secret, cn_suffixes)
    except (MonitorError, sqlite3.Error) as exc:
        code = exc.code if isinstance(exc, MonitorError) else "database_error"
        try:
            record_health(connection, "request", False, code)
            connection.commit()
        except sqlite3.Error:
            connection.rollback()
        success = False
    collect_snapshot(connection, config, secret, cn_suffixes)
    if include_probe:
        try:
            collect_probes(connection, config, secret)
        except (MonitorError, OSError, sqlite3.Error):
            try:
                record_health(connection, "probe", False, "probe_exec_error")
                connection.commit()
            except sqlite3.Error:
                connection.rollback()
            success = False
    analyze(connection, config, hours=24, persist=True)
    purge_old_data(
        connection,
        int(config["retention_days"]),
        max_database_mb=int(config["max_database_mb"]),
    )
    return success


@contextlib.contextmanager
def daemon_lock(state_dir: Path) -> Iterator[None]:
    lock_path = state_dir / "daemon.lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        os.chmod(lock_path, 0o600)
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise MonitorError("daemon_already_running") from exc
        yield


def truncate_log_if_needed(path: Path, maximum_bytes: int = 1024 * 1024) -> None:
    try:
        if path.is_file() and path.stat().st_size > maximum_bytes:
            with path.open("r+b") as stream:
                stream.truncate(0)
    except OSError:
        pass


def run_daemon(connection: sqlite3.Connection, config: Mapping[str, Any], secret: bytes) -> int:
    if not bool(config["enabled"]):
        return 0
    state_dir = Path(str(config["state_dir"]))
    cn_suffixes = parse_domain_suffixes(CN_DNS_DOMAINS_PATH)
    stop = False

    def request_stop(_signum: int, _frame: Any) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    request_interval = int(config["request_poll_seconds"])
    snapshot_interval = int(config["snapshot_seconds"])
    probe_interval = int(config["probe_seconds"])
    next_request = 0.0
    next_snapshot = 0.0
    next_probe = utc_now() + min(30, request_interval)
    next_purge = 0.0

    with daemon_lock(state_dir):
        while not stop:
            now = utc_now()
            if now >= next_request:
                try:
                    collect_requests(connection, config, secret, cn_suffixes, now)
                except (MonitorError, sqlite3.Error) as exc:
                    code = exc.code if isinstance(exc, MonitorError) else "database_error"
                    try:
                        record_health(connection, "request", False, code, 0, now)
                        connection.commit()
                    except sqlite3.Error:
                        connection.rollback()
                next_request = now + request_interval
            if now >= next_snapshot:
                try:
                    collect_snapshot(connection, config, secret, cn_suffixes, now)
                except sqlite3.Error:
                    connection.rollback()
                next_snapshot = now + snapshot_interval
            if now >= next_probe:
                try:
                    collect_probes(connection, config, secret, now)
                except (MonitorError, OSError, sqlite3.Error):
                    try:
                        record_health(connection, "probe", False, "probe_exec_error", 0, now)
                        connection.commit()
                    except sqlite3.Error:
                        connection.rollback()
                next_probe = now + probe_interval
            if now >= next_purge:
                try:
                    purge_old_data(
                        connection,
                        int(config["retention_days"]),
                        now,
                        int(config["max_database_mb"]),
                    )
                except sqlite3.Error:
                    connection.rollback()
                truncate_log_if_needed(state_dir / "monitor.stderr.log")
                if state_dir != DEFAULT_STATE_DIR:
                    truncate_log_if_needed(DEFAULT_STATE_DIR / "monitor.stderr.log")
                next_purge = now + min(3600, snapshot_interval)
            wake_at = min(next_request, next_snapshot, next_probe, next_purge)
            time.sleep(max(0.2, min(1.0, wake_at - utc_now())))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Surge 本地只读监控与脱敏建议生成器")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="本地 JSON 配置；默认读取仓库 .rulemesh.local.json",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("daemon", help="运行 7×24 采集守护进程")
    collect_parser = subparsers.add_parser("collect", help="立即完成一次采集")
    collect_parser.add_argument("--no-probe", action="store_true", help="本次不执行主动 HTTPS 探测")
    report_parser = subparsers.add_parser("report", help="输出脱敏监控报告")
    report_parser.add_argument("--hours", type=int, default=24, help="报告时间窗口，默认 24 小时")
    report_parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    subparsers.add_parser("status", help="输出各采集器最近状态")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "daemon":
        truncate_log_if_needed(DEFAULT_STATE_DIR / "monitor.stderr.log")
    try:
        config = load_config(args.config)
        state_dir = Path(str(config["state_dir"]))
        if args.command == "daemon":
            truncate_log_if_needed(state_dir / "monitor.stderr.log")
        if not bool(config["enabled"]):
            if args.command == "status":
                print(
                    json.dumps(
                        {
                            "enabled": False,
                            "state_dir": str(state_dir),
                            "request": None,
                            "profile": None,
                            "dns": None,
                            "event": None,
                            "probe": None,
                        },
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    )
                )
                return 0
            if args.command in {"daemon", "collect"}:
                return 0
            raise MonitorError("monitor_disabled")
        readonly = args.command in {"report", "status"}
        if readonly:
            connection = connect_database(state_dir, readonly=True)
            secret = b""
        else:
            ensure_private_dir(state_dir)
            secret = load_or_create_secret(state_dir)
            connection = connect_database(state_dir)
        try:
            if args.command == "daemon":
                return run_daemon(connection, config, secret)
            if args.command == "collect":
                return 0 if collect_once(connection, config, secret, not args.no_probe) else 1
            if args.command == "report":
                if args.hours < 1 or args.hours > int(config["retention_days"]) * 24:
                    raise MonitorError("invalid_report_hours")
                if args.format == "json":
                    sampled_at = utc_now()
                    quality = data_quality(connection, config, sampled_at)
                    recommendations = (
                        analyze(
                            connection,
                            config,
                            args.hours,
                            sampled_at,
                            persist=False,
                        )
                        if bool(quality["ok"])
                        else [quality_recommendation(quality)]
                    )
                    payload = {
                        "generated_at": local_time_text(sampled_at),
                        "hours": args.hours,
                        "quality": quality,
                        "recommendations": [
                            public_recommendation(item)
                            for item in recommendations
                        ],
                    }
                    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
                else:
                    print(report_markdown(connection, config, args.hours), end="")
                return 0
            if args.command == "status":
                print(json.dumps(status_payload(connection, config), ensure_ascii=False, indent=2, sort_keys=True))
                return 0
        finally:
            connection.close()
    except MonitorError as exc:
        print("[surge-monitor] {}".format(exc.code), file=sys.stderr)
        return 2
    except sqlite3.Error:
        print("[surge-monitor] database_error", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
