from pathlib import Path
import base64
import os
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import check_performance_baseline as baseline
import check_private_dns_precedence as parser
import build_rules


class PerformanceBaselineTests(unittest.TestCase):
    def test_final_is_direct_except_work_whitelist(self):
        for client in ('surge', 'mihomo'):
            path, text = self.fixture(client)
            prefix = 'FINAL,' if client == 'surge' else '  - MATCH,'
            line = next(x for x in text.splitlines() if x.startswith(prefix))
            self.assertEqual(line.split(',')[1], 'DIRECT')
            for target in ('♻️ 自动选择', '🇺🇸 美国-自动选择', 'REJECT'):
                changed = text.replace(line, line.replace(',DIRECT', ',' + target))
                self.assertTrue(any('最终兜底' in error for error in baseline.check(path, changed.splitlines())))
            if client == 'surge':
                work = Path('work-whitelist.conf')
                self.assertTrue(any('最终兜底' in error for error in baseline.check(work, text.splitlines())))
                changed = text.replace(line, 'FINAL,REJECT')
                self.assertFalse(any('最终兜底' in error for error in baseline.check(work, changed.splitlines())))

    def fixture(self, client):
        path = ROOT / "docs/examples" / ("surge-public.conf" if client == "surge" else "mihomo-public.yaml")
        return path, path.read_text(encoding="utf-8")

    def test_public_templates_use_the_current_baseline(self):
        for client in ("surge", "mihomo"):
            path, text = self.fixture(client)
            with self.subTest(client=client):
                self.assertTrue(baseline.applies(text.splitlines()))
                self.assertEqual(baseline.check(path, text.splitlines()), [])

    def test_crypto_cannot_be_changed_to_performance_or_us_group(self):
        for client in ("surge", "mihomo"):
            path, text = self.fixture(client)
            prefix = "region/tw/crypto_tw.list," if client == "surge" else "RULE-SET,tw_crypto,"
            line = next(x for x in text.splitlines() if prefix in x)
            for target in ("♻️ 自动选择", "🇺🇸 美国-自动选择"):
                changed = text.replace(line, line.replace("🇨🇳 台湾-自动选择", target))
                with self.subTest(client=client, target=target):
                    self.assertTrue(any("crypto_tw" in error for error in baseline.check(path, changed.splitlines())))

    def test_ai_cannot_be_shadowed_by_google_ip_rules(self):
        for client in ("surge", "mihomo"):
            path, text = self.fixture(client)
            lines = text.splitlines()
            ai = next(i for i, x in enumerate(lines) if (x.startswith("RULE-SET,") and "/ai_us.list," in x) or x.startswith("  - RULE-SET,us_ai,"))
            google = next(i for i, x in enumerate(lines) if (x.startswith("RULE-SET,") and "/google_hk.list," in x) or x.startswith("  - RULE-SET,hk_google,"))
            lines[ai], lines[google] = lines[google], lines[ai]
            self.assertTrue(any("第一条" in error for error in baseline.check(path, lines)))

    def test_ai_dns_requires_explicit_us_outbound_and_node_bootstrap(self):
        path, text = self.fixture("mihomo")
        changed = text.replace("#🇺🇸 美国-自动选择", "")
        self.assertTrue(any("DoH" in error for error in baseline.check(path, changed.splitlines())))
        changed = text.replace("  proxy-server-nameserver:", "  ignored-node-dns:")
        self.assertTrue(any("bootstrap" in error for error in baseline.check(path, changed.splitlines())))

    def test_aws_calls_and_own_release_mirror_are_rejected(self):
        for client in ("surge", "mihomo"):
            path, text = self.fixture(client)
            changed = text + "\n# 测试注入的非注释调用\n  - RULE-SET,hk_aws_ipv4,DIRECT\n"
            self.assertTrue(any("AWS" in error for error in baseline.check(path, changed.splitlines())))
            changed = text.replace(baseline.GEOIP_URL, "https://github.com/vtgpcmsvgs/rulemesh/releases/download/geoip-country-mmdb/country.mmdb")
            self.assertTrue(any("Release" in error for error in baseline.check(path, changed.splitlines())))

    def test_multiple_groups_may_share_us_filter(self):
        path, text = self.fixture("surge")
        us_line = next(x for x in text.splitlines() if x.startswith("🇺🇸 美国-自动选择 ="))
        duplicate = us_line.replace("🇺🇸 美国-自动选择 =", "备用美国组 =", 1)
        text = text.replace("\n[Rule]\n", "\n" + duplicate + "\n[Rule]\n")
        self.assertEqual(baseline.check(path, text.splitlines()), [])

    def test_private_profiles_require_subscription_sync_markers(self):
        _, text = self.fixture("surge")
        errors = baseline.check(Path("rulemesh-substore-surge-personal.conf"), text.splitlines())
        self.assertTrue(any("同步块" in error for error in errors))

    def test_airport_manual_groups_are_not_rule_reachability_garbage(self):
        groups = [f'机场{i} = select, policy-path=https://example.com/{i}, hidden=0, policy-regex-filter=^机场{i}' for i in range(7)]
        owner = '手动入口 = select, ' + ', '.join(f'机场{i}' for i in range(7))
        lines = ['[Proxy Group]', owner, baseline.AIRPORT_START, *groups, baseline.AIRPORT_END, '[Rule]', 'FINAL,DIRECT']
        self.assertEqual(baseline.check_airport_groups(lines), [])
        for changed in (
            [line for line in lines if line != groups[0]],
            [line for line in lines if line != baseline.AIRPORT_START],
            [line for line in lines if line != owner],
            [line.replace('hidden=0', 'hidden=1') for line in lines],
            [line.replace(' = select, policy-path=', ' = smart, policy-path=') for line in lines],
        ):
            self.assertTrue(baseline.check_airport_groups(changed))

    def test_ai_dns_ruleset_must_keep_us_outbound_before_device_rules(self):
        path, text = self.fixture('surge')
        line = next(x for x in text.splitlines() if x.startswith('RULE-SET,' + baseline.AI_DNS_RULE + ','))
        self.assertTrue(baseline.check(path, text.replace(line, '').splitlines()))
        changed = text.replace(line, line.replace('🇺🇸 美国-自动选择', '♻️ 自动选择'))
        self.assertTrue(any('DoH' in error for error in baseline.check(path, changed.splitlines())))
        changed = text.replace(line, 'SRC-IP,192.0.2.1,"♻️ 自动选择"\n' + line)
        self.assertTrue(any('设备' in error for error in baseline.check(path, changed.splitlines())))
        source = ROOT / 'rules/region/us/ai_dns_us.list'
        self.assertEqual(build_rules.build_source(source).outputs['surge_rules'], ['DOMAIN,cloudflare-dns.com'])

    def test_aisi_ruleset_keeps_scope_and_apple_updates_are_already_covered(self):
        source = ROOT / 'rules/direct/aisi_direct.list'
        self.assertEqual(set(build_rules.build_source(source).outputs['surge_rules']), {
            'DOMAIN-SUFFIX,i4.cn', 'DOMAIN-SUFFIX,i5.cn', 'DOMAIN-KEYWORD,i4', 'DOMAIN-KEYWORD,aisi',
        })
        path, text = self.fixture('surge')
        active = [line for _, line in parser._active_surge_section(text.splitlines(), 'Rule')]
        aisi = next(i for i, line in enumerate(active) if '/aisi_direct.list,' in line)
        apple = next(i for i, line in enumerate(active) if '/apple_direct.list,' in line)
        reject = next(i for i, line in enumerate(active) if '/reject/' in line)
        self.assertLess(aisi, apple)
        self.assertLess(apple, reject)

    def test_private_sync_accepts_empty_surge_indent(self):
        script = Path(os.environ.get("USERPROFILE", "")) / "Desktop/rulemesh-local/sync_private_subscription_direct.ps1"
        powershell = shutil.which("powershell")
        if not powershell or not script.is_file():
            self.skipTest("仅在已登记私人脚本和 Windows PowerShell 可用时检查参数绑定")
        # 只加载纯格式化函数，用合成注释验证空字符串绑定；不执行脚本顶层同步。
        command = r'''
$ErrorActionPreference = 'Stop'
$taskScript = Join-Path $env:USERPROFILE 'Desktop\rulemesh-local\sync_private_subscription_direct.ps1'
$taskTokens = $null
$taskErrors = $null
$taskAst = [System.Management.Automation.Language.Parser]::ParseFile($taskScript, [ref]$taskTokens, [ref]$taskErrors)
$taskFunction = $taskAst.Find({ param($taskNode) $taskNode -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $taskNode.Name -eq 'Add-SourceEntries' }, $true)
if ($taskErrors.Count -ne 0 -or $null -eq $taskFunction) { throw 'Function parse failed' }
. ([scriptblock]::Create($taskFunction.Extent.Text))
$taskLines = [System.Collections.Generic.List[string]]::new()
$taskEntries = @([pscustomobject]@{ Type = 'comment'; Text = 'test' })
Add-SourceEntries -Lines $taskLines -Entries $taskEntries -Prefix '' -Style surge-direct -ProxyPolicy AUTO
if ($taskLines.Count -ne 1 -or $taskLines[0] -ne '# test') { throw 'Unexpected formatting' }
'''
        encoded = base64.b64encode(command.encode("utf-16-le")).decode("ascii")
        result = subprocess.run([powershell, "-NoProfile", "-EncodedCommand", encoded], capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, "私人同步脚本空缩进参数绑定失败")

    def test_domestic_and_regional_first_matches(self):
        path, text = self.fixture("surge")
        compiled = {}
        active = parser._active_surge_section(text.splitlines(), "Rule")
        rules = []
        for _, line in active:
            parts = [part.strip().strip('"') for part in line.split(",")]
            if len(parts) < 3 or parts[0] != "RULE-SET" or not parts[1].startswith(baseline.BASE):
                continue
            identifier = parts[1].removeprefix(baseline.BASE + "surge/rules/").removesuffix(".list")
            source = ROOT / "rules" / (identifier + ".list")
            if not source.exists():
                continue
            compiled[identifier] = build_rules.build_source(source).outputs["surge_rules"]
            rules.append((identifier, parts[2]))

        def matches(domain, rule):
            parts = rule.split(",")
            if len(parts) < 2:
                return False
            kind, value = parts[:2]
            return (kind == "DOMAIN" and domain == value) or (kind == "DOMAIN-SUFFIX" and (domain == value or domain.endswith("." + value))) or (kind == "DOMAIN-KEYWORD" and value in domain)

        cases = {
            "download.i4.cn": "DIRECT", "www.i5.cn": "DIRECT",
            "secure-appldnld.apple.com": "DIRECT", "updates.cdn-apple.com": "DIRECT",
            "cloudflare-dns.com": "🇺🇸 美国-自动选择",
            **{domain: "♻️ 自动选择" for domain in ("googleplay.com", "googleusercontent.com", "android.com", "gvt3.com", "xn--ngstr-lra8j.com")},
            "www.douyin.com": "DIRECT", "www.xiaohongshu.com": "DIRECT",
            "sns-webpic-qc.xhscdn.com": "DIRECT", "login.weixin.qq.com": "DIRECT",
            "servicewechat.com": "DIRECT", "chatgpt.com": "🇺🇸 美国-自动选择",
            "gemini.google.com": "🇺🇸 美国-自动选择", "notebooklm.google": "🇺🇸 美国-自动选择",
            "generativelanguage.googleapis.com": "🇺🇸 美国-自动选择",
            "www.binance.com": "🇨🇳 台湾-自动选择", "polymarket.com": "🇨🇳 台湾-自动选择",
            "opinion.trade": "🇯🇵 日本-自动选择", "futuhk.com": "🇭🇰 香港-自动选择",
            "www.google.com": "♻️ 自动选择", "www.youtube.com": "♻️ 自动选择",
        }
        for domain, expected in cases.items():
            with self.subTest(domain=domain):
                target = next((policy for identifier, policy in rules if any(matches(domain, rule) for rule in compiled[identifier])), None)
                self.assertEqual(target, expected)


if __name__ == "__main__":
    unittest.main()
