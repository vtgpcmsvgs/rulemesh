"""设备验收子进程。仅供 check_task_acceptance.py 捕获私有 IPC，不直接保存原始输出。"""
from __future__ import annotations

from datetime import datetime, timezone
import base64
import json
import ipaddress
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
from urllib.parse import quote, urlsplit
import uuid

# Windows embeddable Python 的 ._pth 隔离模式不自动添加脚本目录。
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_android_vpn_runtime import GOOGLE_SEARCH_COMMAND, audit_connectivity, audit_google_search, package_uid
from check_android_us_chain import EXITS, FRONT, FRONT_GROUPS, HK_EXITS, HK_REGION, REGION, US_EXITS


class AdbTransport:
    def __init__(self, path):
        self.path = str(Path(path).resolve())
        if not Path(self.path).is_file():
            raise ValueError('ADB file missing')

    def shell(self, command, deadline_seconds=25):
        # 脚本从 stdin 发送，控制器密钥不会进入主机进程命令行或日志。
        result = subprocess.run([self.path, '-d', 'shell', 'sh'], input=command.encode(), capture_output=True, timeout=deadline_seconds)
        if result.returncode:
            raise RuntimeError('ADB command failed')
        return result.stdout.decode('utf-8', 'replace')

    def http(self, port, path, secret=''):
        limit = 16 if '/delay?' in path else 20 if path.startswith('/dns/query?') else 10
        raw, code = shell_result(self, 'curl --noproxy "*" --fail --silent --show-error --max-time ' + str(limit) + ' '
                                 '-H ' + shlex.quote('Authorization: Bearer ' + secret) + ' ' +
                                 shlex.quote(f'http://127.0.0.1:{port}{path}'))
        if code:
            raise RuntimeError('Controller request failed')
        return json.loads(raw)

    def change(self, port, path, secret, method, data):
        command = ('curl --noproxy "*" --fail --silent --show-error --max-time 10 -X ' + method +
                   ' -H ' + shlex.quote('Authorization: Bearer ' + secret) +
                   ' -H "Content-Type: application/json" --data ' + shlex.quote(json.dumps(data or {})) +
                   ' --write-out "\\nRM_HTTP %{http_code}\\n" ' + shlex.quote(f'http://127.0.0.1:{port}{path}'))
        raw, code = shell_result(self, command)
        if code or re.findall(r'(?m)^RM_HTTP (\d+)$', raw) != ['204']:
            raise RuntimeError('Controller selection failed')

    def close(self):
        pass


def shell_result(device, command):
    raw = device.shell(command + '; printf "\\nRM_ACCEPT_EXIT=%s\\n" "$?"', deadline_seconds=30)
    markers = list(re.finditer(r'(?m)^RM_ACCEPT_EXIT=(\d+)\s*$', raw))
    if len(markers) != 1:
        raise RuntimeError('Incomplete device command')
    return raw[:markers[0].start()], int(markers[0][1])


def open_device(settings):
    if settings.get('adb'):
        return AdbTransport(settings['adb'])
    from android_usb_transport import UsbAdb
    for attempt in range(3):
        device = None
        try:
            device = UsbAdb(settings['usb_api_directory'])
            device.connect()
            return device
        except Exception:
            if device:
                device.close()
            if attempt == 2:
                raise
            time.sleep(1)


def change(device, controller, method, group, data=None):
    path = '/proxies/' + quote(group, safe='')
    if isinstance(device, AdbTransport):
        return device.change(controller['port'], path, controller['secret'], method, data)
    body = json.dumps(data).encode() if data else b''
    request = (method + ' ' + path + ' HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer ' + controller['secret'] +
               '\r\nContent-Type: application/json\r\nContent-Length: ' + str(len(body)) + '\r\nConnection: close\r\n\r\n').encode() + body
    response = device.exchange('tcp:' + str(controller['port']), request, deadline_seconds=15)
    if int(response.split(b' ', 2)[1]) != 204:
        raise RuntimeError('Controller selection failed')


def provider_health(providers, expected, now=None):
    now = now or datetime.now(timezone.utc)
    summaries = []
    for name in expected:
        body = providers.get(name, {})
        nodes = body.get('proxies', [])
        interval = expected[name]
        fresh = 0
        for node in nodes:
            try:
                latest = node.get('history', [])[-1]
                age = (now - datetime.fromisoformat(latest['time'].replace('Z', '+00:00'))).total_seconds()
                fresh += node.get('alive') is True and 0 <= age <= interval and latest.get('delay', 0) > 0
            except (KeyError, IndexError, ValueError, TypeError):
                pass
        summaries.append({'provider': name, 'nodes': len(nodes), 'recent_alive': fresh,
                          'state': 'passed' if nodes and fresh else 'unknown'})
    return summaries


def dns_evidence(before, after, group, required_leaf=None):
    old = {c.get('id'): c.get('download', 0) for c in before}
    return any(c.get('metadata', {}).get('host') in {'dns.google', 'cloudflare-dns.com'}
               and group in c.get('chains', []) and 'DIRECT' not in c.get('chains', [])
               and (required_leaf is None or required_leaf in c.get('chains', []))
               and c.get('download', 0) > old.get(c.get('id'), 0) for c in after)


def public_address(value):
    try:
        address = ipaddress.ip_address(value)
        return str(address) if address.is_global else None
    except (ValueError, TypeError):
        return None


def front_runtime(proxies):
    """界面可见的地区前置须在运行内核中存在；不输出真实机场节点名。"""
    front = proxies.get(FRONT, {})
    forbidden = {FRONT, REGION, HK_REGION, *EXITS, 'DIRECT', 'AI', 'Google', 'Microsoft'}
    return {
        'front_region_selector': front.get('type') == 'Selector',
        'front_six_regions_exact': front.get('all') == list(FRONT_GROUPS),
        'front_active_region_known': front.get('now') in FRONT_GROUPS,
        'front_regions_airport_only': all(
            proxies.get(name, {}).get('type') == 'URLTest'
            and bool(proxies[name].get('all'))
            and not (set(proxies[name]['all']) & forbidden)
            for name in FRONT_GROUPS),
    }


def quarantine_runtime(providers, quarantine):
    """在实际 provider 列表核对已排除节点，空响应不能充当删除成功。"""
    return (bool(quarantine) and all(name in providers and providers[name].get('proxies')
            and not ({node.get('name') for node in providers[name]['proxies']} & set(blocked))
            for name, blocked in quarantine.items()))


def trace_evidence(raw, previous, name, hostname="chatgpt.com", required_groups=("AI",)):
    """快连接结束后会消失；仅使用请求进行中的新返回字节作为链路证据。"""
    observed = False
    for encoded in re.findall(r'(?m)^RM_CONN ([A-Za-z0-9+/=]+)$', raw):
        try:
            snapshot = json.loads(base64.b64decode(encoded, validate=True))
        except (ValueError, TypeError):
            continue
        observed |= any(c.get('metadata', {}).get('host') == hostname
                        and set(required_groups).issubset(c.get('chains', []))
                        and 'DIRECT' not in c.get('chains', []) and name in c.get('chains', [])
                        and c.get('download', 0) > previous.get(c.get('id'), 0)
                        for c in snapshot.get('connections', []))
    codes = re.findall(r'(?m)^RM_TRACE_CODE=(\d+)\s*$', raw)
    if len(codes) != 1:
        raise RuntimeError('Incomplete trace result')
    return int(codes[0]), observed


def trace_probe(device, controller, previous, name, url="https://chatgpt.com/cdn-cgi/trace", required_groups=("AI",)):
    # 在手机内并行观察、在单个 USB shell 会话内顺序交付；不落盘原始连接或出口 IP。
    query = ('curl --noproxy "*" --silent --max-time 2 -H ' +
             shlex.quote('Authorization: Bearer ' + controller['secret']) + ' ' +
             shlex.quote('http://127.0.0.1:' + str(controller['port']) + '/connections'))
    command = ('( for n in ' + ' '.join(str(n) for n in range(20)) + '; do printf "RM_CONN "; ' + query +
               ' | base64 | tr -d "\\n"; printf "\\n"; sleep 0.3; done ) & monitor=$!; '
               'trace=$(curl --noproxy "*" --fail --silent --show-error --connect-timeout 10 --max-time 20 '
               '--limit-rate 64 ' + shlex.quote(url) + '); trace_code=$?; wait "$monitor"; '
               'printf "RM_TRACE_CODE=%s\\n" "$trace_code"; printf "%s\\n" "$trace"')
    raw, shell_code = shell_result(device, command)
    if shell_code:
        raise RuntimeError('Trace collection failed')
    code, observed = trace_evidence(raw, previous, name, urlsplit(url).hostname, required_groups)
    return raw, code, observed


TRACE_TARGETS = {
    'US': ('https://chatgpt.com/cdn-cgi/trace', 'https://claude.ai/cdn-cgi/trace',
           'https://www.perplexity.ai/cdn-cgi/trace', 'https://www.cursor.com/cdn-cgi/trace'),
    'HK': ('https://www.notion.so/cdn-cgi/trace', 'https://www.notion.com/cdn-cgi/trace'),
}


def exit_evidence(raw, code, observed, name, expected):
    """信任用户登记的 IP 集合，不把登记本身当作实际观测；端口到美国 IP 的顺序未获确认。"""
    region = 'US' if name in US_EXITS else 'HK'
    fields = dict(re.findall(r'(?m)^([a-z_]+)=(.*)$', raw))
    address = public_address(fields.get('ip'))
    names = US_EXITS if region == 'US' else HK_EXITS
    allowed = {expected['exit_identities'][n] for n in names}
    identity_matches = address is not None and address in allowed and fields.get('loc') == region
    return {'exit': EXITS.index(name) + 1, 'region': region, '_ip': address,
            'observed_region': fields.get('loc'), 'business_chain_observed': observed,
            'identity_matches': identity_matches, 'request_exit': code,
            'passed': code == 0 and identity_matches and observed}


def selection_snapshot(proxies):
    # LoadBalance 无 now/fixed，也不实现 SelectAble。只读观测，不 PUT/DELETE 负载均衡组。
    return {name: {key: proxies.get(name, {}).get(key) for key in ('type', 'all', 'now', 'fixed')}
            for name in (REGION, HK_REGION, FRONT, 'AI', 'Google')}


def regional_probes(device, controller, get, expected):
    rows = {name: {'exit': EXITS.index(name) + 1, 'region': 'US' if name in US_EXITS else 'HK',
                   'passed': False, 'state': 'not_observed'} for name in EXITS}
    # 采用实际 AI / Notion 业务路径观测自然哈希分配；不能为验收修改路由或伪造选中状态。
    for region, targets in TRACE_TARGETS.items():
        names = US_EXITS if region == 'US' else HK_EXITS
        required = ('AI', REGION) if region == 'US' else (HK_REGION,)
        for url in targets:
            if all(rows[name]['passed'] for name in names):
                break
            previous = {c.get('id'): c.get('download', 0) for c in get('/connections').get('connections', [])}
            try:
                raw, code, _ = trace_probe(device, controller, previous, names[0], url, required)
                for name in names:
                    _, observed = trace_evidence(raw, previous, name, urlsplit(url).hostname, required)
                    candidate = exit_evidence(raw, code, observed, name, expected)
                    if not rows[name]['passed'] and (observed or not rows[name].get('business_chain_observed')):
                        rows[name] = candidate
            except Exception as error:
                for name in names:
                    if not rows[name]['passed']:
                        rows[name]['error_type'] = type(error).__name__
    return list(rows.values())


def collect(settings, expected):
    device = open_device(settings)
    result = {'state': 'unknown', 'passed': False, 'regional_exits': []}
    controller = settings['controller']
    if type(controller.get('port')) is not int or not 1024 <= controller['port'] <= 65535 or not isinstance(controller.get('secret'), str) or any(c in controller['secret'] for c in '\r\n'):
        device.close()
        raise ValueError('Explicit controller invalid')
    def get(path):
        return device.http(controller['port'], path, controller['secret'])
    try:
        result['stage'] = 'vpn_and_runtime'
        uid = package_uid(device.shell('pm list packages -U com.follow.clash'))
        result['vpn'] = audit_connectivity(device.shell('dumpsys connectivity'), uid)
        config = get('/configs')
        proxies = get('/proxies')['proxies']
        rules = get('/rules')['rules']
        hk = expected['google_hk']
        result['runtime'] = {
            'mode_rule': config.get('mode') == 'rule', 'process_always': config.get('find-process-mode') == 'always',
            'lan_disabled': config.get('allow-lan') is False,
            'google_hk': proxies.get('Google', {}).get('now') == hk,
            'hk_single_exit_no_fallback': proxies.get(hk, {}).get('type') == 'LoadBalance',
            **front_runtime(proxies),
            'us_load_balance_candidates': proxies.get(REGION, {}).get('all') == list(US_EXITS)
                and proxies.get(REGION, {}).get('type') == 'LoadBalance',
            'hk_fixed_candidate': proxies.get(HK_REGION, {}).get('type') == 'LoadBalance'
                and proxies.get(HK_REGION, {}).get('all') == list(HK_EXITS),
            'ai_uses_us_chain': proxies.get('AI', {}).get('now') == REGION,
            'google_rule': sum(r.get('type') == 'RuleSet' and r.get('payload') == 'hk_google' and r.get('proxy') == 'Google' for r in rules) == 1,
            'ai_rule': sum(r.get('type') == 'RuleSet' and r.get('payload') == 'us_ai' and r.get('proxy') == 'AI' for r in rules) == 1,
        }
        provider_data = get('/providers/proxies')['providers']
        result['providers'] = provider_health(provider_data, expected['providers'])
        result['runtime']['confirmed_bad_nodes_provider_excluded'] = quarantine_runtime(provider_data, expected['quarantine'])
        result['google'] = []
        result['stage'] = 'mobile_google'
        for path in ('/',):
            command = GOOGLE_SEARCH_COMMAND.removesuffix('https://www.google.com/') + shlex.quote('https://www.google.com' + path)
            command = command.replace('--connect-timeout 4 --max-time 12', '--connect-timeout 10 --max-time 20')
            for attempt in range(2):
                raw, code = shell_result(device, command)
                audit = audit_google_search(raw, code, expected_path='/')
                # 仅冷连接超时可短重试，跳转、验证码和其他业务失败不能被抹掉。
                if not (code == 28 and audit['http_status'] == 0 and not audit['tls_handshake_completed']):
                    break
            audit['attempts'] = attempt + 1
            result['google'].append(audit)
        # Google 搜索的原始 HTML 可能只有启用 JS 的页面；通过真实 Chrome 执行 JS 后验收。
        from android_chrome_probe import probe
        result['stage'] = 'chrome'
        result['chrome'] = probe(device)
        result['stage'] = 'dns'
        before = get('/connections').get('connections', [])
        statuses = []
        for domain in ('google.com', 'chatgpt.com'):
            # 唯一查询名绕过本地缓存；已登记主机再单独核对成功解析。
            get('/dns/query?name=rm-' + uuid.uuid4().hex + '.' + domain + '&type=A')
            statuses.append(get('/dns/query?name=' + domain + '&type=A').get('Status') == 0)
        after = get('/connections').get('connections', [])
        result['dns'] = {'queries_succeeded': all(statuses), 'google_hk_doh_observed': dns_evidence(before, after, 'Google', hk),
                         'ai_us_doh_observed': dns_evidence(before, after, 'AI', REGION)}
        result['stage'] = 'regional_exits'
        saved = selection_snapshot(proxies)
        result['regional_exits'] = regional_probes(device, controller, get, expected)
        result['selection_restored'] = selection_snapshot(get('/proxies')['proxies']) == saved
        checks = [result['vpn']['passed'], all(result['runtime'].values()), all(r['state'] == 'passed' for r in result['providers']),
                  all(r['passed'] for r in result['google']), result['chrome']['passed'], result['chrome']['cache_restored'], all(result['dns'].values()),
                  len(result['regional_exits']) == len(EXITS) and all(r['passed'] for r in result['regional_exits']), result['selection_restored']]
        result['passed'] = all(checks)
        result['state'] = 'passed' if result['passed'] else 'failed_or_unconfirmed'
        result['stage'] = 'complete'
    except Exception as error:
        result['error_type'] = type(error).__name__
    finally:
        device.close()
    return result


def main():
    # 内部 worker 通过 stdin 接收配置，stdout 只供父进程捕获，不能直接作为日志运行。
    if sys.argv[1:] != ['--worker']:
        print(json.dumps({'passed': False, 'state': 'use_check_task_acceptance_entrypoint'}))
        return 1
    try:
        payload = json.load(sys.stdin)
        result = collect(payload['settings'], payload['expected'])
    except Exception as error:
        result = {'passed': False, 'state': 'unknown', 'error_type': type(error).__name__, 'regional_exits': []}
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
