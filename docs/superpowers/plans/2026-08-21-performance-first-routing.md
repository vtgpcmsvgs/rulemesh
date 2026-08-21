# 性能优先分流实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将四份私有客户端配置从“全局美国优先”调整为“国内明确业务就近解析并直连、普通国际流量全地区择快、OpenAI 固定美国”。

**Architecture:** 公开仓库继续作为规则与 DNS 白名单源，私有仓库只编排客户端策略。Mihomo 仅为 `rule-set:cn-dns-domains` 恢复受限 `nameserver-policy`，其余域名继续使用海外业务 DNS；Surge 继续通过 `[Host] + DOMAIN-SET` 实现相同边界。通用兜底引用现有全地区自动组，不新增策略组。

**Tech Stack:** Python 3.14 `unittest`、PowerShell 5.1、RuleMesh 构建器、Surge profile、Mihomo YAML、官方 Mihomo Windows 运行时。

**Spec:** `docs/superpowers/specs/2026-08-21-performance-first-routing-design.md`

## Global Constraints

- OpenAI、ChatGPT 与 `region/us/ai_us` 固定美国出口。
- 工作白名单配置保持 `FINAL,REJECT`，不接入宽泛 `cn_direct`、`proxy/gfw` 或通用国际兜底。
- 国内 DNS 只允许处理 `cn_dns_domains` 明确登记的业务域名。
- 两份 Mihomo 保持顶层 `ipv6: false`、`dns.ipv6: false`、`use-hosts: false`、`use-system-hosts: false`、`respect-rules: false`。
- 两份 Mihomo 不增加 `proxy-server-nameserver`、`proxy-server-nameserver-policy`、`direct-nameserver` 或 `fallback`。
- 机场 provider 继续显式 `proxy: DIRECT`，测速地址继续为 `https://www.google.com/generate_204`。
- 私有文件逐文件保留现有 CRLF/LF；禁止整文件统一行尾。
- 所有检查输出在产生前脱敏，不回显订阅地址、密钥、节点名、策略名或证书参数。
- Windows 临时运行时使用任务专用目录，PowerShell 变量不得使用 `$HOME` / `$home`。

---

### Task 1: 放宽且收紧 Mihomo DNS 安全闸门

**Files:**
- Modify: `tests/test_check_dns_safety.py:223`
- Modify: `tools/check_dns_safety.py:20-43`
- Modify: `tools/check_dns_safety.py:375-433`

**Interfaces:**
- Consumes: `validate_path(path: Path) -> list[DnsSafetyFinding]`
- Produces: 私有 Mihomo 只接受 `rule-set:cn-dns-domains` 的 `nameserver-policy`；任何其他 policy key 仍失败。

- [ ] **Step 1: 写允许受限私有 DNS policy 的失败测试**

在 `DnsSafetyTests` 中加入：

```python
def test_private_mihomo_accepts_approved_cn_dns_policy(self) -> None:
    path = self.write_temp(
        "rulemesh-substore-mihomo-clash-verge.yaml",
        """ipv6: false
dns:
  enable: true
  ipv6: false
  use-hosts: false
  use-system-hosts: false
  respect-rules: false
  default-nameserver:
    - 223.5.5.5
  nameserver:
    - https://cloudflare-dns.com/dns-query
  nameserver-policy:
    "rule-set:cn-dns-domains":
      - https://dns.alidns.com/dns-query
      - https://doh.pub/dns-query
proxy-providers: {}
""",
    )

    self.assertEqual(check_dns_safety.validate_path(path), [])
```

- [ ] **Step 2: 写拒绝其他私有 DNS policy key 的测试**

加入 `test_private_mihomo_rejects_unapproved_nameserver_policy_key`，使用 `"+.example.com"` 加国内 DNS，并断言 finding 同时包含 `nameserver-policy` 与“仅允许”。

- [ ] **Step 3: 运行测试并确认 RED**

Run:

```powershell
& "$env:LocalAppData\Programs\Python\Python314\python.exe" -m unittest tests.test_check_dns_safety.DnsSafetyTests.test_private_mihomo_accepts_approved_cn_dns_policy tests.test_check_dns_safety.DnsSafetyTests.test_private_mihomo_rejects_unapproved_nameserver_policy_key -v
```

Expected: 第一个测试因 `nameserver-policy` 仍在私有禁用集合中而失败。

- [ ] **Step 4: 实现最小安全例外**

从 `MIHOMO_SINGLE_DNS_TRUTH_FORBIDDEN_KEYS` 移除 `nameserver-policy`。解析 policy key 时，对私有文件加入：

```python
if (
    single_dns_truth
    and current_nameserver_policy_key not in ALLOWED_DOMESTIC_NAMESERVER_POLICY_KEYS
):
    findings.append(
        DnsSafetyFinding(
            "error",
            path,
            index,
            "两份 Mihomo 私有配置的 nameserver-policy 仅允许 cn-dns-domains 国内业务白名单。",
            "删除其他 policy key；普通目标域名继续使用海外 nameserver。",
        )
    )
```

保持已有逻辑继续拒绝 policy 白名单外出现的国内 DNS，并继续禁止其他分层 DNS 字段。

- [ ] **Step 5: 运行 GREEN 与完整 DNS 安全测试**

Run:

```powershell
& "$env:LocalAppData\Programs\Python\Python314\python.exe" -m unittest tests.test_check_dns_safety -v
```

Expected: 全部通过，0 failure。

- [ ] **Step 6: 提交公开仓库闸门修改**

```powershell
git add tests/test_check_dns_safety.py tools/check_dns_safety.py
git commit -m "test: 允许受控国内 DNS 策略"
```

---

### Task 2: 为性能语义增加私有配置机械检查

**Files:**
- Create: `tools/check_private_performance.py`
- Create: `tests/test_check_private_performance.py`
- Modify: `tools/check.ps1`

**Interfaces:**
- Produces: `validate_profile(path: Path) -> list[PerformanceFinding]`
- Produces: CLI 对已登记私有仓库的四份文件执行脱敏检查；仓库不存在时明确 skip，存在时任何 finding 返回非零。

- [ ] **Step 1: 写合成配置失败测试**

测试至少覆盖以下可观察行为：

```python
def test_surge_personal_rejects_us_final(self) -> None:
    path = self.write_temp("rulemesh-substore-surge-personal.conf", surge_fixture(final="US"))
    self.assertTrue(any("通用 FINAL" in item.message for item in validate_profile(path)))

def test_surge_work_requires_exact_domestic_entries_and_reject_final(self) -> None:
    path = self.write_temp("rulemesh-substore-surge-work-whitelist.conf", work_fixture())
    messages = [item.message for item in validate_profile(path)]
    self.assertTrue(any("zsxq.com" in message for message in messages))
    self.assertTrue(any("yikaiying.com" in message for message in messages))

def test_mihomo_rejects_stale_health_and_us_match(self) -> None:
    path = self.write_temp("rulemesh-substore-mihomo-clash-verge.yaml", mihomo_fixture())
    messages = [item.message for item in validate_profile(path)]
    self.assertTrue(any("300" in message for message in messages))
    self.assertTrue(any("MATCH" in message for message in messages))
```

合成 fixture 使用虚构组名和 provider，不复制私有配置。

- [ ] **Step 2: 运行测试并确认 RED**

Run:

```powershell
& "$env:LocalAppData\Programs\Python\Python314\python.exe" -m unittest tests.test_check_private_performance -v
```

Expected: FAIL with `ModuleNotFoundError: check_private_performance`。

- [ ] **Step 3: 实现最小解析器**

解析器只读取：

- Surge `[Proxy Group]` 的组类型与区域角色、`[Rule]` 的 `FINAL` 和两个精确域名入口；
- Mihomo `proxy-providers` 的 `health-check.interval/lazy/url`、`proxy-groups` 的类型/区域角色/interval/lazy/tolerance、`rules` 的 `ai-us` 与 `MATCH` 目标；
- 不保留或输出 URL、provider 名、节点名、策略原名。

检查约束：

```text
Surge personal: FINAL -> 非美国 smart 自动组
Surge work: zsxq.com DIRECT + yikaiying.com DIRECT + FINAL REJECT
Mihomo: ai-us -> 美国组；MATCH -> 非美国全地区 url-test 组
Mihomo providers/url-test groups: interval 300, lazy false
Mihomo 美国组: tolerance 100
```

- [ ] **Step 4: 接入总检查并运行 GREEN**

在 `tools/check.ps1` 的 DNS 安全检查后调用该脚本。运行：

```powershell
& "$env:LocalAppData\Programs\Python\Python314\python.exe" -m unittest tests.test_check_private_performance -v
```

Expected: synthetic tests 全部通过；真实私有配置检查此时应失败，准确复现待修行为。

- [ ] **Step 5: 提交机械检查**

```powershell
git add tools/check_private_performance.py tests/test_check_private_performance.py tools/check.ps1
git commit -m "test: 守护性能优先私有配置"
```

---

### Task 3: 补齐国内 DNS 与直连源规则

**Files:**
- Modify: `tests/test_repo_invariants.py:235-270`
- Modify: `rules/dns/cn_dns_domains.list`
- Modify: `rules/direct/cn_direct.list:1-14`
- Rebuild: `dist/surge/dns/cn_dns_domains.list`
- Rebuild: `dist/surge/rules/direct/cn_direct.list`
- Rebuild: `dist/mihomo/classical/direct/cn_direct.yaml`

**Interfaces:**
- Produces: `.zsxq.com`、`.yikaiying.com` 的国内 DNS 调度；`yikaiying.com` 的跨客户端直连规则。

- [ ] **Step 1: 先改不变量测试**

把 DNS 清单期望数量从 `239` 改为 `241`，并在 `expected` 中加入：

```python
".yikaiying.com",
".zsxq.com",
```

另加：

```python
def test_yikaiying_keeps_explicit_cn_direct_fallback(self) -> None:
    source = (ROOT / "rules" / "direct" / "cn_direct.list").read_text(encoding="utf-8")
    self.assertEqual(source.count("DOMAIN-SUFFIX,yikaiying.com"), 1)
```

- [ ] **Step 2: 运行测试并确认 RED**

Run:

```powershell
& "$env:LocalAppData\Programs\Python\Python314\python.exe" -m unittest tests.test_repo_invariants.RepoInvariantTests.test_cn_dns_domains_keep_domestic_app_runtime_families tests.test_repo_invariants.RepoInvariantTests.test_yikaiying_keeps_explicit_cn_direct_fallback -v
```

Expected: 缺少两个 DNS 后缀与直连兜底而失败。

- [ ] **Step 3: 增加最小源规则**

在 `cn_dns_domains.list` 以中文小节加入：

```text
# 国内知识服务与明确自有站点
.zsxq.com
.yikaiying.com
```

在 `cn_direct.list` 的本地兜底段加入：

```text
DOMAIN-SUFFIX,yikaiying.com
```

不重复添加上游已经提供的 `zsxq.com`。

- [ ] **Step 4: 重建并运行 GREEN**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File tools/build_rules.ps1
& "$env:LocalAppData\Programs\Python\Python314\python.exe" -m unittest tests.test_repo_invariants.RepoInvariantTests.test_cn_dns_domains_keep_domestic_app_runtime_families tests.test_repo_invariants.RepoInvariantTests.test_yikaiying_keeps_explicit_cn_direct_fallback -v
```

Expected: 构建 0 warning，两个测试通过，生成产物包含对应规则。

- [ ] **Step 5: 提交规则与产物**

```powershell
git add rules/dns/cn_dns_domains.list rules/direct/cn_direct.list tests/test_repo_invariants.py dist/surge/dns/cn_dns_domains.list dist/surge/rules/direct/cn_direct.list dist/mihomo/classical/direct/cn_direct.yaml dist/build-report.json
git commit -m "feat: 优化国内站点解析与直连"
```

---

### Task 4: 更新公开维护边界与使用说明

**Files:**
- Modify: `AGENTS.md`
- Modify: `README.md:171-172,242,344-353`
- Modify: `docs/usage-surge.md:63-82`
- Modify: `docs/usage-mihomo.md:40,62,91-93,135`
- Modify: `docs/network-security/dns-leak-prevention.md:51-98`
- Modify: `docs/mihomo-tun-dns-methodology.md:69-119`
- Modify: `docs/surge-work-cluster-whitelist.md:24-60`

**Interfaces:**
- Produces: 新默认边界的中文维护说明；公开示例结构保持不变。

- [ ] **Step 1: 更新 AGENTS 与 README**

将“私有 Mihomo 永久禁止 nameserver-policy”改为：

```text
两份私有 Mihomo 仅允许经本次批准并完成运行时复测的 rule-set:cn-dns-domains nameserver-policy；
其他 nameserver-policy key 与 respect-rules、proxy-server-nameserver、direct-nameserver、fallback 继续禁止。
```

记录普通国际兜底走全地区自动选择、OpenAI 固定美国、工作白名单保持拒绝。

- [ ] **Step 2: 更新专项文档**

统一说明：

- `zsxq.com` 与 `yikaiying.com` 是本次确认的国内 DNS 性能例外；
- Mihomo 的 policy 只消费 `cn-dns-domains`，不从 `DIRECT` 动作推导 DNS；
- Surge 使用 `[Host]`，Mihomo 使用 `nameserver-policy`，两者语义不可互抄；
- Verge 与 Meta 统一 300 秒主动健康检查；
- 工作白名单只增加两个精确入口。

- [ ] **Step 3: 文档自审**

Run:

```powershell
rg -n -- '私有.*不恢复 nameserver-policy|私有.*单一海外.*nameserver|nameserver-policy.*回流' AGENTS.md README.md docs
```

Expected: 不再出现与已批准例外矛盾的旧说明；历史背景必须明确标注为旧基线。

- [ ] **Step 4: 提交文档**

```powershell
git add AGENTS.md README.md docs/usage-surge.md docs/usage-mihomo.md docs/network-security/dns-leak-prevention.md docs/mihomo-tun-dns-methodology.md docs/surge-work-cluster-whitelist.md
git commit -m "docs: 记录性能优先分流边界"
```

---

### Task 5: 修改四份私有配置并保留字节结构

**Files:**
- Modify: `C:/Users/zaife/Desktop/rulemesh-local/rulemesh-substore-surge-personal.conf:317`
- Modify: `C:/Users/zaife/Desktop/rulemesh-local/rulemesh-substore-surge-work-whitelist.conf:102-292`
- Modify: `C:/Users/zaife/Desktop/rulemesh-local/rulemesh-substore-mihomo-clash-verge.yaml:75-105,116-454,887`
- Modify: `C:/Users/zaife/Desktop/rulemesh-local/rulemesh-substore-mihomo-clash-meta.yaml:75-104,116-454,887`
- Modify: `C:/Users/zaife/Desktop/rulemesh-local/README.md`
- Modify: `C:/Users/zaife/Desktop/rulemesh-local/AGENTS.md`

**Interfaces:**
- Consumes: Task 1 DNS 例外与 Task 2 性能检查。
- Produces: 四份可审计的性能优先配置。

- [ ] **Step 1: 记录修改前字节与语义基线**

输出每个文件的 SHA-256、BOM、CRLF/LF 数量、角色化 FINAL/MATCH、健康检查分布；不得输出原始策略名或 URL。

- [ ] **Step 2: 运行真实私有配置检查并确认 RED**

Run:

```powershell
& "$env:LocalAppData\Programs\Python\Python314\python.exe" tools/check_private_performance.py
```

Expected: 报告美国通用兜底、工作白名单缺少两个入口、Verge 900 秒惰性检测。

- [ ] **Step 3: 修改 Surge personal 与 work**

- 从现有 `[Proxy Group]` 解析“全地区 smart 自动组”和“美国组”，把 personal 的 `FINAL` 从美国组替换为全地区组；不硬编码私密策略名。
- 在 work 的 `FINAL,REJECT` 前增加：

```text
DOMAIN-SUFFIX,zsxq.com,DIRECT
DOMAIN-SUFFIX,yikaiying.com,DIRECT
```

- 不改变 work 的最终拒绝或其他白名单入口。

- [ ] **Step 4: 修改两份 Mihomo DNS 与兜底**

在 `nameserver` 列表之后、`fake-ip-filter` 之前加入：

```yaml
  nameserver-policy:
    "rule-set:cn-dns-domains":
      - https://doh.pub/dns-query
      - https://dns.alidns.com/dns-query
```

从现有 `proxy-groups` 解析全地区自动组和美国组，将 `MATCH` 改为全地区自动组；`ai-us` 保持美国组。

- [ ] **Step 5: 修改健康检查**

- Verge 所有 8 个 provider 与所有 `url-test` 组：`interval: 300`、`lazy: false`。
- Meta 保持 `interval: 300`、`lazy: false`。
- 两份文件的美国 `url-test` 组：`tolerance: 100`。
- 不改变 provider 更新周期、provider `proxy: DIRECT`、User-Agent 或测速 URL。

- [ ] **Step 6: 更新私有 README 与 AGENTS**

用抽象角色说明性能优先默认，不写真实策略名：普通国际择快、OpenAI 美国、国内 DNS 白名单、工作配置最终拒绝。

- [ ] **Step 7: 验证 GREEN 与字节边界**

Run:

```powershell
& "$env:LocalAppData\Programs\Python\Python314\python.exe" tools/check_private_performance.py
& "$env:LocalAppData\Programs\Python\Python314\python.exe" tools/check_dns_safety.py
git -C C:\Users\zaife\Desktop\rulemesh-local diff --check
```

Expected: 两个检查均通过；未修改行不出现大面积行尾 diff；四份配置无 BOM。

---

### Task 6: 执行 Mihomo 官方运行时复测

**Files:**
- Temporary: 任务专用目录中的官方 Mihomo 可执行文件、最小 DNS 复测配置、端口隔离的两份私有配置副本
- No repository file changes unless a reproducible guardrail gap is found

**Interfaces:**
- Produces: 语法通过、运行态启动成功、国内白名单与普通国际对照域名走不同 DNS 路径的证据。

- [ ] **Step 1: 获取并校验官方运行时**

从 `MetaCubeX/mihomo` 官方 GitHub Release 获取 Windows amd64 资产与官方校验值，下载到 `New-Item` 创建的任务专用临时目录；记录版本与校验是否匹配，不输出私有数据。

- [ ] **Step 2: 执行两份私有配置语法测试**

每次使用独立临时 `-d` 目录：

```powershell
& $mihomoExe -t -d $taskDataDir -f $sanitizedRuntimeCopy
```

Expected: 两份配置均退出 0。输出先过滤订阅 URL、provider 名、节点名和控制器密钥。

- [ ] **Step 3: 启动最小 DNS 行为配置**

最小配置使用本地 `cn-dns-domains` provider、`redir-host`、独立 DNS 端口；`nameserver-policy` 与私有配置完全同构。使用 `Start-Process -WindowStyle Hidden` 启动并保留精确 PID。

- [ ] **Step 4: 验证解析边界**

- 查询 `zsxq.com`、`yikaiying.com`，确认命中 `cn-dns-domains` 国内解析路径。
- 查询 `chatgpt.com` 作为国际对照，确认不命中国内 DNS policy。
- 输出仅包含角色、样本数、平均耗时和集合是否匹配，不输出 IP 或原始日志。

- [ ] **Step 5: 清理临时运行时**

只终止记录的精确 PID，确认退出后删除已验证位于任务临时目录内的文件；不触碰用户主目录、客户端缓存或现有配置。

- [ ] **Step 6: 失败处理**

若语法或行为复测失败，立即从两份私有配置移除 `nameserver-policy`，保留其他性能改造，并回到根因分析；不得用静态检查代替运行时证据。

---

### Task 7: 全量验证、提交和推送双仓库

**Files:**
- Verify: 公开仓库全部改动
- Verify: 私有仓库全部改动

**Interfaces:**
- Produces: 两个远端 `main` 与本地一致，私有配置同步完成。

- [ ] **Step 1: 运行公开仓库完整验证**

```powershell
powershell -ExecutionPolicy Bypass -File tools/build_rules.ps1
powershell -ExecutionPolicy Bypass -File tools/check.ps1
git diff --check
```

Expected: 构建 0 warning；全部测试与检查通过；`dist/` 只有三条允许产物线。

- [ ] **Step 2: 执行全仓残留审计**

检查：旧的私有“禁止任何 nameserver-policy”说明、美国通用兜底、Verge 900 秒惰性健康检查、两个国内域名遗漏、废弃 dist 目录、BOM 与纯英文自写注释。未命中的 `rg` 退出码 1 按预期单独处理。

- [ ] **Step 3: 提交私有仓库**

```powershell
git -C C:\Users\zaife\Desktop\rulemesh-local add -- rulemesh-substore-surge-personal.conf rulemesh-substore-surge-work-whitelist.conf rulemesh-substore-mihomo-clash-verge.yaml rulemesh-substore-mihomo-clash-meta.yaml README.md AGENTS.md
git -C C:\Users\zaife\Desktop\rulemesh-local commit -m "feat: 切换为性能优先分流"
```

- [ ] **Step 4: 提交公开仓库剩余改动**

```powershell
git add -A
git commit -m "feat: 切换为性能优先分流"
```

- [ ] **Step 5: 推送私有仓库并确认同步**

```powershell
git -C C:\Users\zaife\Desktop\rulemesh-local push origin main
git -C C:\Users\zaife\Desktop\rulemesh-local fetch origin main
git -C C:\Users\zaife\Desktop\rulemesh-local rev-list --left-right --count 'HEAD...@{upstream}'
```

Expected: `0 0`，工作区干净。

- [ ] **Step 6: 推送公开仓库并确认同步**

```powershell
git push origin main
git fetch origin main
git rev-list --left-right --count 'HEAD...@{upstream}'
```

Expected: `0 0`，工作区干净。

- [ ] **Step 7: 最终交付**

报告同步状态、全仓检查、文档、验证、运行时限制、提交与推送状态；不回显任何私有值。

