# 性能型中国 DNS 架构重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Surge Personal 与两份 Mihomo 建立随中国直连上游自动更新的性能型国内 DNS 分类，同时保持所有海外/区域规则优先、OpenAI 固定美国，并保证工作白名单零变化。

**Architecture:** 保留现有 241 条小型 `cn_dns_domains` 给工作白名单，新增由 Loyalsoldier `direct.txt` 与人工白名单合并生成的 `cn_performance_dns_domains`。三个性能配置先让实际启用的 `reject/`、`proxy/`、`region/` 规则使用海外 DoH，再让性能型中国集合使用 DNSPod / AliDNS；独立检查器从真实规则顺序推导例外覆盖，避免两套手写清单再次漂移。

**Tech Stack:** Python 3.14、`unittest`、PowerShell、Surge Profile、Mihomo YAML、官方 Mihomo Windows amd64。

**Spec:** `docs/superpowers/specs/2026-08-21-cn-dns-architecture-refactor-design.md`

## Global Constraints

- `C:\Users\zaife\Desktop\rulemesh-local\rulemesh-substore-surge-work-whitelist.conf` 在本任务中必须保持 Git blob ID、文件内容、规则和 DNS 行为完全不变。
- 只修改 Surge Personal、Mihomo Clash Verge、Mihomo Clash Meta 三份性能配置；两份 Mihomo 的 DNS 结构必须一致。
- OpenAI / ChatGPT 的 `ai-us` 路由继续固定美国策略，且 `ai-us` 必须优先使用海外 DNS。
- 两份 Mihomo 保持 `ipv6: false`、`dns.ipv6: false`、`use-hosts: false`、`use-system-hosts: false`、`respect-rules: false`。
- 不得新增 `fallback`、`direct-nameserver`、`proxy-server-nameserver`、`proxy-server-nameserver-policy` 或 `direct-nameserver-follow-policy`。
- 机场 provider 保持 `proxy: DIRECT`，健康检查继续使用 HTTPS `https://www.google.com/generate_204`；不得修改订阅 URL、请求头、节点或私密策略名。
- 私有配置检查输出只能包含文件名、字段名、公开规则标识、计数和哈希，不得回显敏感值。
- Windows 构建统一使用 `tools/build_rules.ps1`；提交前运行 `tools/check.ps1`，构建 warning 必须为 0。
- 所有文件编辑使用 `apply_patch`；私人仓库保留未修改行的既有换行风格，新增或重写行使用 LF。

---

### Task 1: 生成独立的性能型中国 DNS 域名集合

**Files:**
- Modify: `tools/build_rules.py`
- Modify: `tests/test_build_rules.py`
- Create: `rules/dns/cn_performance_dns_domains.list`
- Modify: `tests/test_repo_invariants.py`
- Modify: `rules/upstream/sources.yaml`
- Modify: `rules/upstream/merge.yaml`
- Generate: `dist/surge/dns/cn_performance_dns_domains.list`
- Generate: `dist/build-report.json`

**Interfaces:**
- Consumes: `expand_source_lines(path: Path) -> list[SourceLine]`、`normalize_dns_domain_set_entry(raw: str) -> str`。
- Produces: `normalize_dns_source_entry(source_line: SourceLine) -> str`；`build_dns_domain_set_source(path)` 支持递归 `INCLUDE`，并输出稳定去重的域名列表。

- [ ] **Step 1: 写 DNS INCLUDE 的失败测试**

在 `tests/test_build_rules.py` 增加：

```python
def test_dns_domain_set_include_promotes_upstream_domains_to_suffix(self) -> None:
    upstream = self.rules_root / "upstream" / "loyalsoldier" / "direct.txt"
    upstream.parent.mkdir(parents=True, exist_ok=True)
    upstream.write_text("Example.COM\n", encoding="utf-8")
    curated = self.rules_root / "dns" / "cn_dns_domains.list"
    curated.parent.mkdir(parents=True, exist_ok=True)
    curated.write_text("exact.example\n.example.cn\n", encoding="utf-8")
    performance = self.rules_root / "dns" / "cn_performance_dns_domains.list"
    performance.write_text(
        "INCLUDE,upstream/loyalsoldier/direct.txt\n"
        "INCLUDE,dns/cn_dns_domains.list\n"
        ".example.com\n",
        encoding="utf-8",
    )

    with self.patch_repo_paths():
        result = build_rules.build_dns_domain_set_source(performance)

    self.assertEqual(
        result.outputs["surge_dns_domains"],
        [".example.com", "exact.example", ".example.cn"],
    )
```

再增加一个测试，让被 INCLUDE 的 IP 条目抛出 `BuildError`，且错误信息包含真实上游文件路径和行号。

- [ ] **Step 2: 运行目标测试，确认因 INCLUDE 尚未展开而失败**

```powershell
& "$env:LocalAppData\Programs\Python\Python314\python.exe" -m unittest tests.test_build_rules.BuildRulesTests.test_dns_domain_set_include_promotes_upstream_domains_to_suffix -v
```

Expected: FAIL；当前实现不会把上游普通域名转换成 `.example.com`。

- [ ] **Step 3: 实现最小 DNS INCLUDE 支持**

在 `tools/build_rules.py` 新增：

```python
def normalize_dns_source_entry(source_line: SourceLine) -> str:
    entry = normalize_dns_domain_set_entry(source_line.raw)
    relative = source_line.path.resolve().relative_to(RULES_ROOT.resolve())
    if relative.parts and relative.parts[0] == "upstream" and not entry.startswith("."):
        return normalize_domain_suffix(entry)
    return entry
```

把 `build_dns_domain_set_source()` 改为循环 `expand_source_lines(path)`；跳过 `source_line.raw` 的注释空行，错误位置使用真实 `source_line.path` 和 `source_line.line_no`，继续用 `ordered_unique(entries)`。

- [ ] **Step 4: 创建性能型源并登记语义**

`rules/dns/cn_performance_dns_domains.list` 使用中文头部并包含：

```text
INCLUDE,upstream/loyalsoldier/direct.txt
INCLUDE,dns/cn_dns_domains.list
```

在 `rules/upstream/sources.yaml`、`rules/upstream/merge.yaml` 登记：它只供性能配置使用，不替代工作白名单的小型清单。

- [ ] **Step 5: 写产物失败测试并转绿**

在 `tests/test_repo_invariants.py` 读取性能型产物，断言：

```python
self.assertGreaterEqual(len(domains), 100_000)
self.assertIn(".2mdn-cn.net", domains)
self.assertIn(".yikaiying.com", domains)
self.assertIn(".zsxq.com", domains)
```

同时断言有效条目不含逗号、斜杠或 IP 字面量。先运行并确认因产物不存在而 FAIL，再运行构建和目标测试：

```powershell
powershell -ExecutionPolicy Bypass -File tools/build_rules.ps1
& "$env:LocalAppData\Programs\Python\Python314\python.exe" -m unittest tests.test_build_rules tests.test_repo_invariants -v
```

Expected: PASS；构建报告出现两个 `dns-domain-set` 源，warning 为 0。

- [ ] **Step 6: 提交构建器与产物**

```powershell
git add tools/build_rules.py tests/test_build_rules.py tests/test_repo_invariants.py rules/dns/cn_performance_dns_domains.list rules/upstream/sources.yaml rules/upstream/merge.yaml dist/surge/dns/cn_performance_dns_domains.list dist/build-report.json
git commit -m "feat: 生成性能型中国 DNS 清单"
```

---

### Task 2: 允许受控的海外 DNS policy 例外

**Files:**
- Modify: `tools/check_dns_safety.py`
- Modify: `tests/test_check_dns_safety.py`

**Interfaces:**
- Produces: 任意 `nameserver-policy` key 可以使用纯海外 DNS；只有 `rule-set:cn-dns-domains` 与 `rule-set:cn-performance-dns-domains` 可以使用国内 DNS。

- [ ] **Step 1: 写三个失败测试**

增加：`test_mihomo_private_accepts_overseas_rule_set_policy`、`test_mihomo_private_rejects_domestic_dns_for_overseas_rule_set`、`test_mihomo_private_accepts_performance_cn_dns_policy`。fixture 使用私有 Mihomo 文件名、最低限度 `default-nameserver`、海外 `nameserver` 与 `proxy-providers: {}`。

- [ ] **Step 2: 运行并确认旧 key 白名单导致失败**

```powershell
& "$env:LocalAppData\Programs\Python\Python314\python.exe" -m unittest tests.test_check_dns_safety -v
```

Expected: 海外 `rule-set:us-ai` 和性能中国 key 的接受测试 FAIL。

- [ ] **Step 3: 最小修改安全检查器**

```python
ALLOWED_DOMESTIC_NAMESERVER_POLICY_KEYS = {
    "rule-set:cn-dns-domains",
    "rule-set:cn-performance-dns-domains",
}
```

删除“其他 policy key 一律报错”的分支；保留 `domestic_needles_in()`，使其他 key 仅在使用国内 DNS 时失败。同步更新错误文案。

- [ ] **Step 4: 运行 DNS 安全测试和全量单元测试**

```powershell
& "$env:LocalAppData\Programs\Python\Python314\python.exe" -m unittest tests.test_check_dns_safety -v
& "$env:LocalAppData\Programs\Python\Python314\python.exe" -m unittest discover -s tests -p "test_*.py"
```

Expected: PASS。

- [ ] **Step 5: 提交安全边界**

```powershell
git add tools/check_dns_safety.py tests/test_check_dns_safety.py
git commit -m "test: 允许海外 DNS 规则例外"
```

---

### Task 3: 新增三配置 DNS 优先级机械检查器

**Files:**
- Create: `tools/check_private_dns_precedence.py`
- Create: `tests/test_check_private_dns_precedence.py`
- Modify: `tools/check.ps1`

**Interfaces:**
- Produces: `validate_profile(path: Path, public_root: Path = ROOT) -> list[DnsPrecedenceFinding]`。
- Produces: `required_surge_exceptions(lines, public_root) -> list[str]` 与 `required_mihomo_exceptions(lines, public_root) -> list[str]`；只返回中国兜底前、公开产物含域名规则的 `reject/`、`proxy/`、`region/` 集合。

- [ ] **Step 1: 写 Surge 失败 fixture**

临时公开目录创建 `dist/surge/rules/region/us/ai_us.list`，内容为 `DOMAIN-SUFFIX,openai.com`。临时 Personal 配置包含该 RULE-SET、中国直连 RULE-SET、海外 `[Host]` 例外与性能型 DOMAIN-SET。分别断言：缺例外时失败；例外在性能集合之后时失败；例外在之前且使用 Cloudflare 时通过。

- [ ] **Step 2: 写 Mihomo 失败 fixture**

临时公开目录创建 `dist/mihomo/classical/region/us/ai_us.yaml`。临时 Mihomo 注册 `us_ai`、`cn_direct`、`cn-performance-dns-domains`，路由顺序为 `us_ai`、`cn_direct`、`MATCH`。分别断言：缺海外 policy 时失败；顺序颠倒时失败；顺序正确且海外 policy 数组与 `dns.nameserver` 完全相同时通过。

- [ ] **Step 3: 写工作白名单隔离失败 fixture**

```python
def test_work_profile_rejects_performance_dns_artifact(self) -> None:
    path = write_temp_work(
        "DOMAIN-SET:https://example/cn_performance_dns_domains.list = server:https://dns.alidns.com/dns-query"
    )
    findings = validate_profile(path, public_root)
    self.assertTrue(any("工作白名单" in item.message for item in findings))
```

- [ ] **Step 4: 运行新测试，确认模块尚不存在而失败**

```powershell
& "$env:LocalAppData\Programs\Python\Python314\python.exe" -m unittest tests.test_check_private_dns_precedence -v
```

Expected: ERROR/FAIL。

- [ ] **Step 5: 实现检查器**

检查器必须：

- 只解析 `[Host]`、`[Rule]`、`rule-providers`、`dns.nameserver`、`dns.nameserver-policy`、`rules`。
- 通过公开 URL 的 `reject/`、`proxy/`、`region/` 路径定位本地产物，不输出完整 URL。
- 读取本地产物判断是否含域名规则，纯 IP 集合不要求 DNS 例外。
- 要求每个高优先级域名集合的海外 DNS 例外出现在性能中国条目之前。
- 要求 Mihomo 海外 policy 数组与 `dns.nameserver` 完全相同，并要求 `ai-us` / `us_ai` 属于海外例外。
- 对工作白名单只检查“不含性能型产物”，不得要求新增规则。

- [ ] **Step 6: 接入总检查并确认真实配置先红**

在 `tools/check.ps1` 增加 `Invoke-PrivateDnsPrecedenceValidation`，放在 DNS safety 后、private performance 前。运行：

```powershell
& "$env:LocalAppData\Programs\Python\Python314\python.exe" tools/check_private_dns_precedence.py
```

Expected: FAIL；只报告三个性能配置尚未重构，不要求工作白名单改变。

- [ ] **Step 7: 提交检查器**

```powershell
git add tools/check_private_dns_precedence.py tests/test_check_private_dns_precedence.py tools/check.ps1
git commit -m "test: 守护 DNS 规则优先级"
```

---

### Task 4: 重构三份私有性能配置

**Files:**
- Modify: `C:\Users\zaife\Desktop\rulemesh-local\rulemesh-substore-surge-personal.conf`
- Modify: `C:\Users\zaife\Desktop\rulemesh-local\rulemesh-substore-mihomo-clash-verge.yaml`
- Modify: `C:\Users\zaife\Desktop\rulemesh-local\rulemesh-substore-mihomo-clash-meta.yaml`
- Must not modify: `C:\Users\zaife\Desktop\rulemesh-local\rulemesh-substore-surge-work-whitelist.conf`

**Interfaces:**
- Consumes: 新性能型产物与 Task 3 推导的高优先级集合。
- Produces: 三份通过 DNS safety、DNS precedence、private performance 的配置。

- [ ] **Step 1: 锁定工作白名单基线**

```powershell
git -C C:\Users\zaife\Desktop\rulemesh-local rev-parse "HEAD:rulemesh-substore-surge-work-whitelist.conf"
git -C C:\Users\zaife\Desktop\rulemesh-local hash-object rulemesh-substore-surge-work-whitelist.conf
```

两个值必须相同；摘要只保存在内存。

- [ ] **Step 2: 用 `apply_patch` 修改 Surge Personal**

- 在 `[Host]` 为检查器推导的域名型 `reject/`、`proxy/`、`region/` RULE-SET 补齐海外 DoH 映射，已有映射不重复。
- 所有海外例外排在性能型中国 DOMAIN-SET 之前。
- 把 Personal 的通用国内 DNS 引用改为 `cn_performance_dns_domains.list`。
- 不修改 `[Rule]`、代理组、节点、订阅或 MITM。

- [ ] **Step 3: 用 `apply_patch` 修改两份 Mihomo**

- 把旧 `cn-dns-domains` provider 替换为 `cn-performance-dns-domains`，指向新文本产物，保留 `type: http`、`behavior: domain`、`format: text` 和下载约定。
- 为每个高优先级域名 provider 增加 `rule-set:<provider-key>`，值逐项复制 `dns.nameserver` 海外 DoH 数组。
- 把国内 policy key 改为 `rule-set:cn-performance-dns-domains`，值保持 DNSPod / AliDNS。
- `us_ai` 海外例外必须位于性能中国 key 前；不修改路由、MATCH、机场 provider、节点或请求头。

- [ ] **Step 4: 运行三个检查器**

```powershell
& "$env:LocalAppData\Programs\Python\Python314\python.exe" tools/check_dns_safety.py
& "$env:LocalAppData\Programs\Python\Python314\python.exe" tools/check_private_dns_precedence.py
& "$env:LocalAppData\Programs\Python\Python314\python.exe" tools/check_private_performance.py
```

Expected: 全部 PASS。

- [ ] **Step 5: 确认工作白名单零变化**

```powershell
git -C C:\Users\zaife\Desktop\rulemesh-local diff --exit-code -- rulemesh-substore-surge-work-whitelist.conf
git -C C:\Users\zaife\Desktop\rulemesh-local diff --check
git -C C:\Users\zaife\Desktop\rulemesh-local status --short
```

Expected: 工作白名单退出 0；状态只出现三个性能配置。

---

### Task 5: 同步公开与私有维护文档

**Files:**
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `docs/usage-surge.md`
- Modify: `docs/usage-mihomo.md`
- Modify: `docs/network-security/dns-leak-prevention.md`
- Modify: `docs/mihomo-tun-dns-methodology.md`
- Modify: `C:\Users\zaife\Desktop\rulemesh-local\AGENTS.md`
- Modify: `C:\Users\zaife\Desktop\rulemesh-local\README.md`

**Interfaces:**
- Documents: 小型清单服务严格白名单；性能型清单服务 Personal/Mihomo；海外例外优先；工作白名单隔离。

- [ ] **Step 1: 更新公开文档**

明确两份 DNS 产物用途、性能型集合自动来源、海外规则优先、OpenAI 美国路由和 DNS、Mihomo 不恢复 fallback。公开示例继续使用保守小型清单，性能型产物是明确选择而非默认安全配置。

- [ ] **Step 2: 更新私有文档**

只写抽象行为，不写策略名、真实 URL 或私密字段：三份性能配置使用宽中国 DNS 集合；工作白名单继续使用小型集合且永久隔离。

- [ ] **Step 3: 构建、检查并提交公开文档**

```powershell
powershell -ExecutionPolicy Bypass -File tools/build_rules.ps1
git diff --check
git add AGENTS.md README.md docs/usage-surge.md docs/usage-mihomo.md docs/network-security/dns-leak-prevention.md docs/mihomo-tun-dns-methodology.md
git commit -m "docs: 说明性能型中国 DNS 边界"
```

Expected: 构建 0 warning，无 BOM 或行尾错误。

---

### Task 6: 官方 Mihomo 与 DNS 行为运行时复测

**Files:**
- Read only: 两份私有 Mihomo 配置
- Temporary only: 系统临时目录中的官方 Mihomo、最小测试配置和日志

**Interfaces:**
- Produces: 版本、官方 SHA-256 匹配、两份语法退出码、国内/海外 resolver 类别计数；不输出 IP 或私密日志。

- [ ] **Step 1: 获取官方稳定版和摘要**

通过 GitHub 官方 `releases/latest` 重定向和 `expanded_assets/<tag>` 获取标签、Windows amd64 ZIP 与 SHA-256；API 限流时不得把空值当版本。

- [ ] **Step 2: 单进程下载并校验**

在系统临时根创建 `rulemesh-mihomo-runtime-[0-9a-f]{32}`。长下载保留 session ID 并轮询，禁止第二写入者；摘要匹配后才解压和运行 `mihomo -v`。

- [ ] **Step 3: 两份真实配置隔离语法测试**

```powershell
& $mihomoExe -t -d $caseDir -f $privateConfig *> $privateLog
```

每份使用独立 `-d`；只输出代号和退出码，预期均为 0。

- [ ] **Step 4: 最小 DNS 行为测试**

使用公开域名和本地 rule-provider，通过仅绑定 `127.0.0.1` 的 `/dns/query` 验证：中国代表域名只出现国内 resolver，`chatgpt.com` 和一个区域重叠代表域名只出现海外 resolver。只输出答案数量和 resolver 类别计数。

- [ ] **Step 5: 停止精确 PID 并删除临时目录**

删除前验证目录位于系统临时根且名称严格匹配，确认无运行进程后删除；预期 `runtime_temp_removed=True`。

---

### Task 7: 全量验证、私有提交与双仓推送

**Files:**
- Verify: 整个公开仓库
- Commit: 私有三个配置、私有 `AGENTS.md`、私有 `README.md`

**Interfaces:**
- Produces: 两仓 clean、0 ahead / 0 behind，公开构建 0 warning，工作白名单 blob 不变。

- [ ] **Step 1: 运行公开全量验证**

```powershell
powershell -ExecutionPolicy Bypass -File tools/build_rules.ps1
powershell -ExecutionPolicy Bypass -File tools/check.ps1
git diff --check
```

Expected: 构建 0 warning；所有测试和三个检查器通过。

- [ ] **Step 2: 运行残留审计**

确认产物目录仍只有三条线；性能型产物不少于 10 万条且无 IP/复杂规则；三个性能配置引用新产物；工作白名单不引用；两份 Mihomo 禁止字段为 0，`us_ai` 海外例外存在；机场 provider 的 `proxy: DIRECT`、HTTPS health-check 和请求头计数与任务前一致。

- [ ] **Step 3: 再次确认工作白名单 blob 不变**

比较任务前保存的 HEAD blob、当前工作树 hash 与当前 HEAD blob，并执行：

```powershell
git -C C:\Users\zaife\Desktop\rulemesh-local diff --exit-code -- rulemesh-substore-surge-work-whitelist.conf
```

- [ ] **Step 4: 提交私有仓库**

```powershell
git add -- AGENTS.md README.md rulemesh-substore-surge-personal.conf rulemesh-substore-mihomo-clash-verge.yaml rulemesh-substore-mihomo-clash-meta.yaml
git commit -m "feat: 扩展性能型中国 DNS"
```

- [ ] **Step 5: 安全集成远端**

两仓分别 `git fetch origin` 并检查 `HEAD...@{upstream}`。远端前进时禁止强推；在 clean 工作区 rebase 到 `origin/main`，生成产物冲突通过源规则和标准构建重生，然后重新执行 Step 1–3。

- [ ] **Step 6: 推送并确认同步**

先私有后公开；每次推送后 fetch 并确认：

```text
ahead=0
behind=0
dirty=0
```

- [ ] **Step 7: 最终交付**

最终回复包含：三份配置变化、工作白名单零变化、OpenAI 美国约束、性能型集合规模、DNS 运行时证据、构建/测试、文档、双仓提交及 0/0 状态；不得回显私密值。
