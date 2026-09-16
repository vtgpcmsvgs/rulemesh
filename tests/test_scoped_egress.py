"""防止 AI 子串误伤、DNS 前置遮蔽与有业务依据的地区要求漂移。"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_rules
import check_common_routes as common
import check_performance_baseline as baseline


class ScopedEgressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ai = build_rules.build_source(ROOT / 'rules/region/us/ai_us.list').outputs['surge_rules']

    def ai_matches(self, domain):
        return any(common.matches(rule, domain, 'browser') for rule in self.ai)

    def test_ai_never_uses_substring_wildcard_shared_ip_or_asn(self):
        self.assertTrue(self.ai)
        self.assertEqual({r.split(',')[0] for r in self.ai}, {'DOMAIN', 'DOMAIN-SUFFIX'})
        for domain in ('auth0.com', 'sentry.io', 'stripe.com', 'intercom.io', 'workos.com',
                       'byteoversea.com', 'algolia.net', 'segment.io', 'apis.google.com'):
            self.assertFalse(self.ai_matches('unrelated.' + domain), domain)

    def test_domestic_and_similar_names_do_not_become_us_ai(self):
        for domain in ('gxairlines.com', 'jxairport.com', 'auxair.com', 'poemlife.com',
                       'poemschina.com', 'likepoems.com', 'sunon-china.com', 'ngrok.cc',
                       'openailab.com', 'gemini530.net', 'kkcursor.com', 'rcolab.com',
                       'cybertogether.net', 'sunorensolar.com', 'procetpoeinjector.com'):
            for candidate in (domain, 'www.' + domain):
                self.assertFalse(self.ai_matches(candidate), candidate)
        for word in ('xai', 'poe', 'suno', 'openai', 'gemini', 'cursor', 'augment', 'together', 'claude'):
            self.assertFalse(self.ai_matches(word + '.example.org'), word)

    def test_real_ai_products_and_tenant_dependencies_keep_us(self):
        for domain in ('chatgpt.com', 'auth.openai.com', 'cdn.oaistatic.com', 'files.oaiusercontent.com',
                       'gemini.google.com', 'aistudio.google.com', 'notebooklm.google',
                       'generativelanguage.googleapis.com', 'claude.ai', 'claude.com', 'api.anthropic.com',
                       'api.x.ai', 'grok.com', 'api.githubcopilot.com', 'copilot.microsoft.com',
                       'cursor.com', 'cursor.sh', 'codeium.com', 'augmentcode.com', 'trae.ai',
                       'perplexity.ai', 'poe.com', 'openrouter.ai', 'suno.com', 'suno.ai',
                       'openai-api.arkoselabs.com', 'xai.chronosphere.io'):
            self.assertTrue(self.ai_matches(domain), domain)
        self.assertFalse(self.ai_matches('openai.com.example.org'))
        self.assertFalse(self.ai_matches('notopenai.com'))

    def fixture(self, client):
        path = ROOT / 'docs/examples' / ('surge-public.conf' if client == 'surge' else 'mihomo-public.yaml')
        return path, path.read_text('utf-8')

    def test_wps_hk_and_store_us_cannot_fall_back_to_auto(self):
        for client in ('surge', 'mihomo'):
            path, text = self.fixture(client)
            for suffix, alias in [('wps_kdocs', 'hk_wps_kdocs'), ('microsoft_store_us', 'us_microsoft_store')]:
                line = next(s for s in text.splitlines() if (s.startswith('RULE-SET,') and '/' + suffix + '.list,' in s) or s.startswith('  - RULE-SET,' + alias + ','))
                changed = text.replace(line, line.rsplit(',', 1)[0] + ',"♻️ 自动选择"')
                self.assertTrue(any('地区出口' in e for e in baseline.check(path, changed.splitlines())))

    def test_domestic_protection_cannot_be_shadowed(self):
        path, text = self.fixture('surge')
        marker = 'RULE-SET,' + baseline.BASE + 'surge/rules/direct/cn_services_direct.list,DIRECT'
        for inserted in ('SRC-IP,192.0.2.1,"♻️ 自动选择"', 'PROTOCOL,DOH,"♻️ 自动选择"'):
            changed = text.replace(marker, inserted + '\n' + marker)
            self.assertTrue(any('国内 DNS' in e for e in baseline.check(path, changed.splitlines())))
        changed = text.replace('\n[Host]\n', '\n[Host]\n*i4* = server:https://cloudflare-dns.com/dns-query\n')
        self.assertTrue(any('海外 Host' in e for e in baseline.check(path, changed.splitlines())))

    def test_domestic_services_are_small_and_explicit(self):
        rules = build_rules.build_source(ROOT / 'rules/direct/cn_services_direct.list').outputs['surge_rules']
        for domain in ('dns.alidns.com', 'doh.pub', 'sm2.doh.pub', 'dns.pub', 'doh.360.cn', 'www.h3c.com'):
            self.assertTrue(any(common.matches(rule, domain, 'browser') for rule in rules), domain)
        for domain in ('www.360.cn', 'alibaba.com', 'example.cn', 'doh.pub.example.com'):
            self.assertFalse(any(common.matches(rule, domain, 'browser') for rule in rules), domain)


if __name__ == '__main__':
    unittest.main()
