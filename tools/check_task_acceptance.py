"""任务收尾入口：完整仓库检查、订阅闸门、安卓业务/DNS 与五个美国出口。"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

import check_android_us_chain as chain
from check_private_subscriptions import default_directory, load_yaml, PROFILE_NAMES

ROOT = Path(__file__).resolve().parents[1]


def fingerprint(directory):
    return {name: hashlib.sha256((directory / name).read_bytes()).hexdigest() for name in PROFILE_NAMES}


def overall(report):
    """缺项、未知、恢复失败都不能通过；禁止复用旧设备证据替代本次采集。"""
    device = report.get('android', {})
    exits = device.get('us_exits', [])
    return (report.get('baseline', {}).get('passed') is True and report.get('source_unchanged') is True
            and device.get('passed') is True and device.get('selection_restored') is True
            and device.get('distinct_us_exit_count') == 5
            and len(exits) == 5 and {r.get('exit') for r in exits} == set(range(1, 6))
            and report.get('exit_identity_policy') == 'user-provided-trusted'
            and all(r.get('passed') is True for r in exits))


def validate_settings(settings):
    if not isinstance(settings, dict) or settings.get('exit_identity_policy') != 'user-provided-trusted':
        raise ValueError('Explicit user-provided exit policy required')
    if bool(settings.get('adb')) == bool(settings.get('usb_api_directory')):
        raise ValueError('Select exactly one authorized device transport')
    if not Path(settings.get('device_python', sys.executable)).is_file():
        raise ValueError('Device Python missing')
    return settings


def run(settings, directory, *, baseline_runner=subprocess.run, worker_runner=subprocess.run):
    settings = validate_settings(settings)
    began = time.monotonic()
    source = fingerprint(directory)
    document = load_yaml((directory / chain.PROFILE).read_text('utf-8'))
    report = {'schema_version': 1, 'run_id': uuid.uuid4().hex, 'started_at': datetime.now(timezone.utc).isoformat(),
              'baseline': {'passed': False}, 'android': {'state': 'not_run', 'passed': False}, 'source_sha256': source,
              'exit_identity_policy': 'user-provided-trusted', 'purity_check': 'not_requested'}
    print('[acceptance] build, offline regressions and mandatory online subscription gate', flush=True)
    try:
        completed = baseline_runner(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(ROOT / 'tools/check.ps1')],
                                   cwd=ROOT, capture_output=True, timeout=600)
        raw = (completed.stdout + completed.stderr).decode('utf-8', 'replace')
        count = re.search(r'Ran (\d+) tests', raw)
        report['baseline'] = {'passed': completed.returncode == 0 and '[check] all checks passed' in raw,
                              'test_count': int(count[1]) if count else None,
                              'subscription_gate_passed': '"subscription_downloads_passed": true' in raw}
        report['baseline']['passed'] &= report['baseline']['subscription_gate_passed']
        # 不依赖打印完整日志；基线失败时原入口可重跑诊断，报告不回显私人内容。
        if not report['baseline']['passed']:
            return report
        if chain.validate((directory / chain.PROFILE).read_text('utf-8').splitlines()):
            raise ValueError('Approved Android five-exit chain required')
        print('[acceptance] collect fresh Android VPN, Google, DNS and five US exits; restore selection afterward', flush=True)
        expected = {'google_hk': document['proxy-groups'][0].get('name'),
                    'providers': {name: body['health-check']['interval'] for name, body in document['proxy-providers'].items()}}
        google = next(g for g in document['proxy-groups'] if g['name'] == 'Google')
        expected['google_hk'] = google['proxies'][0]
        expected['quarantine'] = {}
        for entry in document[chain.QUARANTINE]['nodes']:
            expected['quarantine'].setdefault(entry['provider'], []).append(entry['name'])
        payload = json.dumps({'settings': settings, 'expected': expected}, ensure_ascii=True)
        worker = worker_runner([settings.get('device_python', sys.executable), '-B', str(ROOT / 'tools/collect_android_acceptance.py'), '--worker'],
                               input=payload.encode('utf-8'), capture_output=True, timeout=420)
        if worker.returncode:
            raise RuntimeError('Device collector failed')
        device = json.loads(worker.stdout)
        report['android'] = device
        # 用户明确要求信任指定五出口；不发送出口 IP 到风险数据库。
        addresses = {row.pop('_ip', None) for row in device.get('us_exits', [])}
        report['android']['distinct_us_exit_count'] = len(addresses - {None})
        report['android']['passed'] &= len(addresses - {None}) == 5
        report['source_unchanged'] = fingerprint(directory) == source
    except Exception as error:
        report['error_type'] = type(error).__name__
    finally:
        # 出口 IP 只允许留在内存，连错误路径也不能写入最终报告。
        for row in report.get('android', {}).get('us_exits', []):
            row.pop('_ip', None)
        report['duration_seconds'] = round(time.monotonic() - began, 1)
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        report['passed'] = bool(overall(report))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings', required=True, type=Path, help='公开仓库外的私人本机设置 JSON')
    parser.add_argument('--private-root', type=Path)
    parser.add_argument('--output', type=Path, help='保存脱敏验收报告；不接受历史报告作为输入')
    args = parser.parse_args()
    try:
        if args.settings.resolve().is_relative_to(ROOT):
            raise ValueError('Private settings must stay outside public repository')
        settings = json.loads(args.settings.read_text('utf-8'))
        report = run(settings, args.private_root or default_directory())
    except Exception as error:
        report = {'passed': False, 'state': 'unknown', 'error_type': type(error).__name__}
    if args.output:
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
