# Aggressive Personal Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为两份 Surge Personal 配置实现 Notion / 香港证券香港出口、Apple / Outlook 直连、Microsoft Store / 其余 Microsoft 美国出口，并安全拆分家庭与公司 MITM。

**Architecture:** 新增互不污染工作白名单的 Personal 专用公开规则集，并由统一构建产出 Surge 与 Mihomo 格式；港交所网站域名通过现有上游同步器生成受阈值保护的快照。两份私有 Surge 配置共用相同规则序列，只在角色注释和 MITM 上不同，公开检查器同时识别两个 Personal 文件。

**Tech Stack:** Python 3.14、`unittest`、Windows PowerShell 5.1、Surge 規則、Git

**Spec:** `docs/superpowers/specs/2026-08-21-aggressive-personal-routing-design.md`

## Global Constraints

- 不得编辑或间接扩张 `rulemesh-substore-surge-work-whitelist.conf` 的行为。
- 公司 MITM 只进入私有仓库，任何输出只允许字段名、长度或不可逆摘要。
- 新增源规则必须同步 `rules/upstream/sources.yaml` 与 `rules/upstream/merge.yaml`。
- 公开源文件和文档使用中文，UTF-8 无 BOM；构建只能使用 `tools/build_rules.ps1`。
- 两份 Mihomo 私有配置不接入本次 Personal 激进规则。
- OpenAI / ChatGPT 继续固定美国出口。

---

### Task 1: 锁定公开规则内容与顺序

**Files:**
- Create: `rules/region/hk/personal_priority_hk.list`
- Create: `rules/region/hk/notion_hk.list`
- Create: `rules/region/hk/hk_securities_aggressive.list`
- Create: `rules/direct/apple_direct.list`
- Create: `rules/direct/outlook_direct.list`
- Create: `rules/region/us/microsoft_store_us.list`
- Modify: `rules/upstream/sources.yaml`
- Modify: `rules/upstream/merge.yaml`
- Test: `tests/test_repo_invariants.py`

**Interfaces:**
- Consumes: `rules/upstream/hkex/sehk_participant_websites.list` 生成的 `DOMAIN-SUFFIX` 快照。
- Produces: 六个稳定规则标识，供两份 Personal 配置与公开使用说明引用。

- [ ] **Step 1: 写规则内容与边界的失败测试**

```python
def test_aggressive_personal_rule_sources_keep_required_boundaries(self) -> None:
    self.assertIn("DOMAIN-KEYWORD,notion", notion)
    self.assertIn("INCLUDE,upstream/hkex/sehk_participant_websites.list", brokers)
    self.assertIn("DOMAIN-SUFFIX,apple.com", apple)
    self.assertIn("DOMAIN-KEYWORD,outlook", outlook)
    self.assertIn("DOMAIN-SUFFIX,delivery.mp.microsoft.com", store)
    self.assertNotIn("DOMAIN-KEYWORD,tiger\n", brokers)
```

- [ ] **Step 2: 运行目标测试并确认因文件不存在而失败**

Run: `& "$env:LocalAppData\Programs\Python\Python314\python.exe" -m unittest tests.test_repo_invariants.RepoInvariantTests.test_aggressive_personal_rule_sources_keep_required_boundaries -v`

Expected: `FAIL` 或 `ERROR`，明确指向新增规则文件不存在。

- [ ] **Step 3: 创建最小源规则与上游登记**

```text
# Notion 香港区域策略规则：官方域名优先，品牌关键词兜底。
DOMAIN-SUFFIX,notion.com
DOMAIN-SUFFIX,notion.site
DOMAIN-SUFFIX,notionusercontent.com
DOMAIN-SUFFIX,notion-static.com
DOMAIN-SUFFIX,notion.so
DOMAIN-KEYWORD,notion
```

Apple、Outlook、Store 与 Personal 优先规则按设计文档逐项列出；证券激进规则仅包含 HKEX 快照 INCLUDE、老虎证券明确后缀及 `itiger` / `tigerbrokers` / `upfintech` 等低误伤关键词。

- [ ] **Step 4: 重跑目标测试确认通过**

Run: `& "$env:LocalAppData\Programs\Python\Python314\python.exe" -m unittest tests.test_repo_invariants.RepoInvariantTests.test_aggressive_personal_rule_sources_keep_required_boundaries -v`

Expected: `OK`。

### Task 2: 港交所参与者网站同步器

**Files:**
- Modify: `tools/sync_upstream_rules.py`
- Modify: `tests/test_sync_upstream_rules.py`
- Create: `rules/upstream/hkex/sehk_participant_websites.list`

**Interfaces:**
- Produces: `normalize_hkex_website_host(value: str) -> str | None`、`extract_hkex_participant_page(html_text: str) -> HkexParticipantPage`、`build_hkex_participant_snapshot_text(pages: list[HkexParticipantPage]) -> str`、`sync_hkex_participant_websites(failures: list[UpstreamFailure]) -> tuple[int, int]`。
- Consumes: 现有 `fetch_text`、`write_if_changed`、`record_failure` 与 `SYNC_TASKS`。

- [ ] **Step 1: 写 URL 规范化、页面解析、阈值拒绝与任务登记失败测试**

```python
def test_hkex_page_parser_extracts_only_public_http_hosts(self) -> None:
    page = sync_upstream_rules.extract_hkex_participant_page(HKEX_FIXTURE)
    self.assertEqual(page.hosts, ("laglobal.com.hk", "sec.abci.com.hk"))

def test_hkex_snapshot_rejects_truncated_results(self) -> None:
    with self.assertRaisesRegex(ValueError, "参与者记录数"):
        sync_upstream_rules.build_hkex_participant_snapshot_text([small_page])
```

- [ ] **Step 2: 运行 HKEX 测试并确认缺少接口而失败**

Run: `& "$env:LocalAppData\Programs\Python\Python314\python.exe" -m unittest tests.test_sync_upstream_rules.HkexParticipantHelpersTests -v`

Expected: `ERROR`，缺少 HKEX 接口。

- [ ] **Step 3: 实现受限并发抓取、解析与原子快照**

```python
@dataclass(frozen=True)
class HkexParticipantPage:
    page: int
    total_pages: int
    total_records: int
    website_entries: int
    hosts: tuple[str, ...]
```

抓取首页后按官方总页数生成任务，最多八并发；任何页失败、页码不连续、记录数低于 500 或唯一网站主机低于安全阈值时拒绝写入。

- [ ] **Step 4: 重跑 HKEX 测试确认通过**

Run: `& "$env:LocalAppData\Programs\Python\Python314\python.exe" -m unittest tests.test_sync_upstream_rules.HkexParticipantHelpersTests tests.test_sync_upstream_rules.SyncTaskRegistryTests -v`

Expected: `OK`。

- [ ] **Step 5: 运行目标同步并生成当前官方快照**

Run: `& "$env:LocalAppData\Programs\Python\Python314\python.exe" -c "import sys; sys.path.insert(0, 'tools'); import sync_upstream_rules as s; failures=[]; print(s.sync_hkex_participant_websites(failures)); raise SystemExit(bool(failures))"`

Expected: 更新 `rules/upstream/hkex/sehk_participant_websites.list`，失败列表为空；不得打印完整域名列表。

### Task 3: 双 Personal 文件识别与安全检查

**Files:**
- Modify: `tools/check_dns_safety.py`
- Modify: `tools/check_private_dns_precedence.py`
- Modify: `tools/check_private_performance.py`
- Modify: `tests/test_check_dns_safety.py`
- Modify: `tests/test_check_private_dns_precedence.py`
- Modify: `tests/test_check_private_performance.py`
- Modify: `tests/test_validate_surge_test_urls.py`

**Interfaces:**
- Produces: `SURGE_PERSONAL_NAMES` 或等价不可变集合，包含家庭与公司两个文件名。
- Consumes: 私有仓库解析后的实际目录，不读取或输出 MITM 值。

- [ ] **Step 1: 写公司 Personal 文件应被发现、验证并采用相同顺序的失败测试**

```python
def test_company_surge_personal_is_registered(self) -> None:
    self.assertIn("rulemesh-substore-surge-personal-company.conf", PRIVATE_PROFILE_NAMES)
```

- [ ] **Step 2: 运行相关测试并确认公司文件名缺失导致失败**

Run: `& "$env:LocalAppData\Programs\Python\Python314\python.exe" -m unittest tests.test_check_dns_safety tests.test_check_private_dns_precedence tests.test_check_private_performance tests.test_validate_surge_test_urls -v`

Expected: 至少一项断言因公司文件未登记而失败。

- [ ] **Step 3: 把单一 Personal 常量改为双文件集合**

```python
SURGE_PERSONAL_NAMES = {
    "rulemesh-substore-surge-personal.conf",
    "rulemesh-substore-surge-personal-company.conf",
}
```

所有 Personal 专属验证改为 `path.name in SURGE_PERSONAL_NAMES`，不得影响工作白名单与 Mihomo 分支。

- [ ] **Step 4: 重跑相关测试确认通过**

Run: `& "$env:LocalAppData\Programs\Python\Python314\python.exe" -m unittest tests.test_check_dns_safety tests.test_check_private_dns_precedence tests.test_check_private_performance tests.test_validate_surge_test_urls -v`

Expected: `OK`。

### Task 4: 拆分私有配置并接入激进规则

**Files:**
- Modify: `C:/Users/zaife/Desktop/rulemesh-local/rulemesh-substore-surge-personal.conf`
- Create: `C:/Users/zaife/Desktop/rulemesh-local/rulemesh-substore-surge-personal-company.conf`
- Modify: `C:/Users/zaife/Desktop/rulemesh-local/sync_private_subscription_direct.ps1`
- Modify: `C:/Users/zaife/Desktop/rulemesh-local/README.md`
- Modify: `C:/Users/zaife/Desktop/rulemesh-local/AGENTS.md`

**Interfaces:**
- Consumes: Task 1 产生的六个公开规则 URL，以及私有 `MITM.txt` 中与用户批准证书摘要匹配的两字段块。
- Produces: 两份除角色和 MITM 外规范化一致的 Surge Personal 配置。

- [ ] **Step 1: 写私有配置结构、顺序和等价性失败检查**

使用脱敏 PowerShell 检查：公司文件存在；六个规则入口均存在；Apple 在更新拒绝前、Store 在 Outlook 前、Outlook 在 Microsoft 前；规范化移除角色注释与 MITM 后两文件 SHA-256 相同；工作白名单 SHA-256 仍为基线值。

- [ ] **Step 2: 运行检查并确认公司文件缺失导致失败**

Run: 脱敏 PowerShell 检查脚本。

Expected: `COMPANY_EXISTS=false` 或等价失败，不输出 MITM 值。

- [ ] **Step 3: 机械复制家庭配置并安全替换公司 MITM**

从家庭文件复制完整配置；从 `MITM.txt` 选择与用户批准证书前后锚点及摘要一致的 `[MITM]` 块；只替换公司文件的角色注释和 MITM。然后在两份文件按设计顺序插入规则 URL，并让私有订阅同步脚本的 Surge 目标同时更新两份 Personal 与工作白名单。

- [ ] **Step 4: 重跑脱敏检查确认通过**

Expected: 两份配置结构等价、MITM 摘要不同、规则顺序正确、工作白名单哈希不变。

### Task 5: 文档、构建、全量验证与发布

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/usage-surge.md`
- Modify: `docs/usage-mihomo.md`
- Modify: `docs/examples/surge-public.conf`
- Modify: `docs/examples/mihomo-public.yaml`
- Rebuild: `dist/surge/rules/**`
- Rebuild: `dist/mihomo/classical/**`
- Rebuild: `dist/build-report.json`

**Interfaces:**
- Consumes: Tasks 1-4 的稳定规则标识与验证结果。
- Produces: 可发布文档、构建产物以及本地和远端一致的两个仓库。

- [ ] **Step 1: 更新公开说明、示例顺序与 PowerShell 5.1 摘要兼容约束**

公开示例把新增规则标为 Personal 激进组合；不得让工作白名单接入新规则。`AGENTS.md` 记录 Windows PowerShell 5.1 使用 `SHA256.Create()`，避免使用不存在的静态 `HashData`。

- [ ] **Step 2: 构建并运行全量检查**

Run: `powershell -ExecutionPolicy Bypass -File tools/build_rules.ps1`

Run: `powershell -ExecutionPolicy Bypass -File tools/check.ps1`

Run: `git diff --check`

Expected: 构建 0 warning、全量检查退出 0、无空白错误，`dist/` 仅保留三条批准产物线。

- [ ] **Step 3: 运行私有检查并审计敏感值**

确认公开仓库不存在公司 MITM 摘要对应值或证书片段；私有文件只输出字段计数和摘要；`git diff --check` 通过。

- [ ] **Step 4: 提交并推送公开仓库**

```powershell
git add -- rules tools tests docs README.md AGENTS.md dist
git commit -m "feat: add aggressive personal routing"
git push origin main
```

- [ ] **Step 5: 提交并推送私有仓库**

```powershell
git add -- rulemesh-substore-surge-personal.conf rulemesh-substore-surge-personal-company.conf sync_private_subscription_direct.ps1 README.md AGENTS.md
git commit -m "feat: split personal surge profiles"
git push origin main
```

- [ ] **Step 6: 最终远端一致性检查**

两个仓库分别执行 `git fetch origin`、`git rev-list --left-right --count "HEAD...@{upstream}"` 与 `git status --porcelain`；预期均为 `0 0` 且工作区为空。

