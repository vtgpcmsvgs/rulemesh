# RuleMesh

这个仓库现在按“一份源规则，多端产物输出”的思路维护：

- `rules/` 是源规则层，只放你自己审阅后的规则素材与维护元数据
- `dist/` 是构建产物层，客户端只引用这里
- `Surge` 使用 `dist/surge/rules/`
- `Surge` 与 Mihomo 的国内业务域名 DNS 清单共用 `dist/surge/dns/`；其中小型精选清单服务严格白名单，性能型清单服务已明确启用的个人性能配置
- `FlClash 桌面端` 与 `FlClash 安卓端` 使用 `dist/mihomo/classical/`

这样做的目标是把“怎么维护规则”与“客户端怎么接入规则”分开，避免客户端继续直接引用第三方规则上游仓库，也避免源规则和客户端格式绑死。GeoIP 数据库属于客户端运行时依赖，是当前保留的显式外部上游例外。

## 目录说明

```text
rules/
  app/         # 应用级主清单（构建前自动派生）
  dns/         # DNS 专用域名清单源文件
  reject/      # 拒绝类源规则
  direct/      # 直连类源规则
  proxy/       # 代理类源规则
  region/      # 区域策略类源规则
  upstream/    # 上游来源登记与未来合并模板

dist/
  surge/
    dns/       # Surge [Host] 与 Mihomo 相关 DNS 维护输入清单
    rules/     # Surge RULE-SET 使用的显式规则产物
  mihomo/
    classical/ # Mihomo 的 behavior: classical 使用的显式规则产物

tools/
  build_rules.ps1
  build_rules.py
  check.ps1
  check_change_guardrails.py
  check_private_repository_registration.py
  check_dns_safety.py

private-repository.json # 私人配置仓库的机器可读发现登记
```

说明：

- `rules/` 下参与构建的源规则文件统一使用 `.list` 命名
- `rules/dns/` 用于维护 DNS 专用域名清单；`cn_dns_domains.list` 生成小型精选 `dist/surge/dns/cn_dns_domains.list`，`cn_performance_dns_domains.list` 自动合并中国直连域名主体与前者，生成性能型 `dist/surge/dns/cn_performance_dns_domains.list`
- `rules/app/` 用于维护单一应用的主清单；例如 `rules/app/adspower.txt` 会在构建前自动派生到 `rules/reject/`、`rules/direct/` 与 `rules/proxy/`
- 例如 `rules/region/hk/google_hk.list` 会生成 `dist/surge/rules/region/hk/google_hk.list` 与 `dist/mihomo/classical/region/hk/google_hk.yaml`
- `dist/build-report.json` 会记录每个源文件被识别为 `domain-only`、`ipcidr-only` 或 `classical/mixed`，以及构建警告
- 这些分类结果只用于维护诊断，不再对应额外的 `domainset` / `domain` / `ipcidr` 产物目录

## 如何构建

Windows 本地与 Codex 会话统一优先使用包装脚本：

```bash
powershell -ExecutionPolicy Bypass -File tools/build_rules.ps1
```

日常开发自检可直接运行：

```bash
powershell -ExecutionPolicy Bypass -File tools/check.ps1
```

这个脚本会串行执行构建、变更联动闸门、单元测试、`dist/` 目录结构校验、`dist/build-report.json` warning 校验，并在最后输出 `git status --short`。
其中 `tools/check_change_guardrails.py` 会先按“源规则 / 上游登记 / 公开说明模板 / 构建与检查脚本”等类别总结当前工作区变更；对于当前已明确的强关联项，会直接失败，例如：

- `rules/{reject,direct,proxy,region}/` 下 `.list` 源规则文件新增、删除或重命名，但没有同步修改 `rules/upstream/sources.yaml` 与 `rules/upstream/merge.yaml`
- `docs/rule-authoring-style.md` 已修改，但没有同步更新 `AGENTS.md` 与 `README.md`

其余暂时还不适合机械化硬判定的联动项，会以显式提醒输出，逼着维护者在提交前再看一眼，而不是只靠记忆。
这个脚本现在还会执行 `tools/check_private_repository_registration.py`，确保私人配置仓库的远程标识、本地路径、恢复文档和 Codex 约定没有失联；并校验 Surge 配置里的测速 URL 约定，防止把必须保持 `http://` 的字段误改成 `https://`，同时执行 `tools/check_dns_safety.py`，检查 Surge / Mihomo 配置是否把普通目标网站域名泄漏到国内 DNS。

CI 或其他非 Windows 环境如果已经确认本机 `python` 可用，也可以直接执行：

```bash
python tools/build_rules.py
```

构建脚本会：

- 先把 `rules/app/adspower.txt` 自动派生到 `rules/reject/adspower_reject.list`、`rules/direct/adspower_direct.list` 与 `rules/proxy/adspower_proxy.list`
- 从 `rules/` 读取源规则
- 自动生成 `dist/surge/rules/`、`dist/surge/dns/` 与 `dist/mihomo/classical/`
- 将纯域名规则规范化成显式规则行，例如 `.example.com` 会输出成 `DOMAIN-SUFFIX,example.com`
- 对 `IP-CIDR`、`IP-CIDR6`、`GEOIP`、`IP-ASN`、`ASN` 这类 IP 判断规则自动补 `no-resolve`，避免客户端为了判断 IP 类规则提前触发本地 DNS
- 尝试识别 `domain-only`、`ipcidr-only`、`classical/mixed`
- 强制校验 `rules/{reject,direct,proxy,region}/` 中的自写注释为中文；若出现纯英文注释会直接失败
- 对不能安全转换到目标客户端格式的行输出 warning，而不是静默吞掉
- 对当前 Mihomo classical 明确不支持、但 Surge 仍需要保留的规则类型，源规则层继续保留，Surge 产物照常输出，Mihomo 产物按当前兼容矩阵选择性跳过；当前已落地的例子是 `URL-REGEX`
- 这种“对 Mihomo 选择性跳过”只代表当前版本能力边界，不代表永久删语义；如果后续 Mihomo 官方版本已支持并经仓库验证通过，应同步恢复 Mihomo 产物输出，而不是继续保留特判
- 保证重复执行结果一致

## 如何发布

最小发布流程：

1. 修改 `rules/app/` 主清单或 `rules/` 源规则
2. 运行 `powershell -ExecutionPolicy Bypass -File tools/build_rules.ps1`
3. 检查 `dist/` 与 `dist/build-report.json`
4. 提交 `rules/`、`dist/`、文档与 CI 改动

仓库已新增最小 GitHub Actions 工作流：

- push 到 `main` 时会运行单元测试、重建 `dist/`，并校验已提交的 `rules/upstream` 与 `dist/` 是否和仓库源码一致
- `pull request` 到 `main` 时会校验单元测试、构建流程，以及 `rules/upstream` 与 `dist/` 是否已经提交最新结果
- 每天 `09:30 Asia/Shanghai` 的上游同步、重建与自动回写由 [`.github/workflows/sync-upstream-rules.yml`](.github/workflows/sync-upstream-rules.yml) 单独负责
- 这条每日上游工作流会在 `checkout` 前先发送一次 Feishu webhook 健康检查；只要 webhook 缺失、失效或发送失败，工作流会直接失败
- 通用上游、Chainlist、1Password、AWS、阿里云等 upstream 抓取失败会统一聚合告警并让同步步骤失败，避免残缺快照继续构建或提交；如果工作流其他步骤失败，还会再发一条不依赖仓库 checkout 的工作流级失败兜底告警
- 支持手动触发
- [`.github/workflows/build-dist.yml`](.github/workflows/build-dist.yml) 不再自动拉上游或自动修复提交；如果网页端直接编辑 `main` 却漏提 `dist/`，工作流会明确报错提醒补齐

## 客户端如何使用

请只引用 `dist/`，不要直接引用：

- `rules/`
- 第三方原始规则库 URL
- `rules/upstream/` 下的登记文件

接入示例见：

- [docs/usage-surge.md](docs/usage-surge.md)
- [docs/surge-local-monitoring.md](docs/surge-local-monitoring.md)
- [docs/usage-mihomo.md](docs/usage-mihomo.md)
- [docs/examples/surge-public.conf](docs/examples/surge-public.conf)
- [docs/examples/mihomo-public.yaml](docs/examples/mihomo-public.yaml)
- [docs/network-security/dns-leak-prevention.md](docs/network-security/dns-leak-prevention.md)
- [docs/mihomo-tun-dns-methodology.md](docs/mihomo-tun-dns-methodology.md)
- [docs/geoip-upstream.md](docs/geoip-upstream.md)
- [docs/surge-work-cluster-whitelist.md](docs/surge-work-cluster-whitelist.md)
- [docs/private-subscription-direct-sync.md](docs/private-subscription-direct-sync.md)
- [docs/aws-region-rules.md](docs/aws-region-rules.md)
- [docs/alicloud-direct-rules.md](docs/alicloud-direct-rules.md)
- [docs/github-ssh-direct-rules.md](docs/github-ssh-direct-rules.md)
- [docs/github-core-proxy-rules.md](docs/github-core-proxy-rules.md)
- [docs/onepassword-proxy-rules.md](docs/onepassword-proxy-rules.md)
- [docs/rule-authoring-style.md](docs/rule-authoring-style.md)

## 当前默认配置

用户已批准 [2026-09-09 性能基线](docs/performance-baseline.md)，适用于七份公开/私有配置：

- 海外 AI（含 Gemini、AI Studio、NotebookLM）固定美国，第一条规则优先匹配；国内 AI、抖音、小红书、微信直连。
- Crypto、Polymarket、Polygon/BSC RPC 固定台湾；`opinion.trade` 保留日本访问例外，香港券商与 Personal 证券入口保留香港。明确地区要求优先于测速结果。
- 命中前置规则的其余海外代理业务使用全地区自动组；未命中规则的 FINAL/MATCH 按 2026-09-12 用户要求使用 DIRECT，仅工作白名单保持 REJECT，不再按国家标签限制候选节点；套餐占位项继续过滤。前置 DIRECT/REJECT 行为继续保留。
- Google 的 google_hk 兼容路径和完整官方 IP 地址空间保留，普通 Google 服务自动择优；AI、国内精选及地区必需规则都在它前面。
- 国内默认双 DoH，AI 单独通过美国解析；Mihomo 开启 TCP 并发，保留 ARC、fake-ip，桌面 300 秒、安卓 600 秒主动测速。默认国内 DNS 后不再重复加载十万条 DNS 专用清单。
- AWS IP 和链式 SOCKS5 的源规则、快照与构建产物保留；当前配置不再注册或调用。
- GeoIP 直接使用 [MetaCubeX country.mmdb](https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/country.mmdb)，停止本仓库二次 Release 发布。未定制的公共资源优先活跃上游，自定义规则继续引用 dist。

当前维护边界：

- 工作白名单保持最终 `FINAL,REJECT` 和既有设备条件，只补充微信、小红书精选直连，不增加 cn_direct / gfw 广谱放行；Personal 专项入口不得复制进去。
- 家庭和公司两份 Surge Personal 只允许用途说明与 MITM 不同，路由与 DNS 同步；两份 Mihomo 的 provider 和地区策略同步。
- GitHub SSH 精确直连先于 Core / gfw；Raw 自举入口与海外 Host 解析独立保留。工作文件已有 GitHub 观察规则保留；AdsPower 观察规则已按用户要求停用。
- Outlook 邮件、精确共享认证与资源直连，不放宽 Microsoft 根域。WPS、Notion、Microsoft Store 等普通代理自动择优，香港证券保留香港。
- 阿里云 SSH 仅 TCP/22 的内联兜底必须先于远程规则；阿里控制面与出口探测精确直连保留。已登记设备的阿里业务条件仍保留源地址，普通代理策略改为自动组。
- AdsPower 保留主清单与 reject/direct/proxy 产物，当前配置不再调用；Polygon、BSC 和可选 1Password 等上游持续更新，不直接替换掉本地定制规则。
- Surge 测速保留 HTTP，Mihomo 保留 HTTPS；Surge 不写 dns-mode 或 proxy-server-nameserver。传统 DNS 接管、节点 bootstrap、IPv4 基线与微信本机回环例外继续保留。
- 私有订阅下载后台 DIRECT 与普通端点自动代理是不同连接；同步脚本按明确 Target 执行，且必须保留同步块起止标记。
- 2026-05-07 下线的激进拒绝入口不恢复；本地只读监控仍使用 RM-INV / RM-EXEC 两阶段授权，不自动修改配置。

构建、静态检查和原生语法检查分别执行。静态检查已通过不等于生产运行态生效；历史 v1.19.25 查询未命中模拟 resolver，当前 DNS 路由运行时仍未确认时必须明确说明，不宣称未经测量的性能提升。

详细接入与规则顺序以两份 [客户端使用说明](docs/usage-surge.md)、[Mihomo 使用说明](docs/usage-mihomo.md) 和当前模板为准。GitHub 主体定制规则坚持源文件审阅、构建输出与联动检查；公开日志禁止包含私有订阅、设备、证书或策略细节。

## 源规则编排约定

- 中大型源规则文件默认按“同平台 / 同服务聚合展示 + 上游优先 + 本地兜底”维护，不再把显式域名和关键词兜底简单堆成两大坨
- 文件头必须先写清楚：这份规则负责什么、不负责什么、与相邻规则文件的边界是什么、客户端顺序上应放在哪里
- 同一小节内部默认顺序是：小节注释、`INCLUDE,upstream/...`、显式域名 / 网段、`DOMAIN-KEYWORD` 兜底
- IP 类源规则可以只写 `IP-CIDR`、`IP-CIDR6`、`GEOIP`、`IP-ASN`、`ASN` 主体；构建产物会自动补 `no-resolve`，客户端调用纯 IP 规则集时仍建议在 `RULE-SET` 层保留 `no-resolve`
- 像 `ai_us`、`ai_cn_direct`、`bytedance_direct`、`google_hk`、`crypto_tw` 这类多平台或多服务混合文件，优先按平台或服务分组
- 像 `cn_direct`、`telegram` 这类入口型或通用基础兜底文件，可以保持“上游主体 + 本地最高优先级兜底”的简单结构，但仍要把边界写清楚
- 任务中一旦出现错误、用户纠正、错误假设、验证失败或回滚，必须在同一任务内自动完成“现象—根因—修复—防复发”复盘；可机械验证的经验优先落到测试或检查脚本，其余写入最窄的维护文档，并同步 `AGENTS.md` 与规则编排文档
- 私有配置排障时，脱敏必须发生在命令输出之前；不得先打印完整私有行再依赖最终回复隐藏，优先只输出字段名、计数、哈希或已替换敏感值的片段
- 如果本次修改只影响注释、分组与顺序，且构建后确认 `dist/` 内容不变，允许最终只提交源文件；但仍然必须完整执行构建和检查
- 详细规则见 [docs/rule-authoring-style.md](docs/rule-authoring-style.md)

## Google 与 AI 路由边界

Google 通用业务仍维护在 google_hk 兼容入口，完整同步 Google / FCM / YouTube 和官方 goog.json 地址空间；不扣除 GCP 客户地址。Google AI 专项 INCLUDE 与关键词已移入 ai_us，必须前置美国出口，避免被通用 IP 规则抢先覆盖。

ai_us 同时承接 OpenAI、Claude、Copilot、Cursor、Grok、Windsurf、Augment 等海外平台；国内 AI、Trae 中国大陆入口继续由 ai_cn_direct / bytedance_direct 直连。工作白名单不因通用模板变更自动加入国内 AI 入口。详细顺序以性能基线和模板为准。

## 上游维护方式

当前仓库只先落两类维护元数据：

- `rules/upstream/sources.yaml`
  - 记录每个主要源文件建议参考哪些上游
- `rules/upstream/merge.yaml`
  - 记录未来如何把上游素材并回本仓库源规则
- `rules/upstream/geodata/metacubex_country_mmdb.yaml`
  - 记录 Surge 与 Mihomo 共用的 GeoIP mmdb 上游选择与下载入口

这几类文件当前都不参与规则构建，只负责把维护策略写清楚，避免后续继续依赖口头约定。

## 私人配置仓库发现与恢复

真实客户端配置的最终数据源是 GitHub 私人仓库 [`vtgpcmsvgs/rulemesh-local`](https://github.com/vtgpcmsvgs/rulemesh-local)，Windows 默认工作副本位于 `%USERPROFILE%\Desktop\rulemesh-local`。根目录 [`private-repository.json`](private-repository.json) 是这项对应关系的机器可读登记。

同一 GitHub 账号已经登录，并不意味着另一台机器已经克隆该仓库，也不意味着新的 Codex 会话自动知道本地目录对应关系。若本机不存在 `rulemesh-local`，应先读取登记文件，通过 GitHub 确认私人仓库可访问，再克隆到登记路径；不得直接断言配置不存在或创建新的空仓库。完整恢复、校验与脱敏边界见 [docs/private-repository-bootstrap.md](docs/private-repository-bootstrap.md)。

## 本地私有配置

仓库提供 [`.rulemesh.local.example.json`](.rulemesh.local.example.json) 作为本地私有配置模板。复制为 `.rulemesh.local.json` 后，可给 `tools/sync_upstream_rules.py` 提供本地告警与阿里云上游鉴权配置；当前支持：

- `upstream_alert.feishu_webhook_url`
- `upstream_alert.feishu_secret`
- `alicloud.access_key_id`
- `alicloud.access_key_secret`
- `alicloud.security_token`
- `surge_monitor`：Surge 7×24 本地监控的脱敏运行参数、公共轻量探测目标与固定隐私边界；匿名化随机盐由运行时在本机自动生成，不写入配置样例
- `surge_monitor.notifications.feishu`：可选的本机飞书日报提醒；真实 Webhook / 签名密钥只写入状态目录私有配置，公开样例保持空值

约定如下：

- `.rulemesh.local.json` 只用于本地私有环境，已经被 `.gitignore` 忽略，不应提交到公开仓库
- 缺少本地配置时，不影响本地构建与手工同步主流程，只会跳过本地 Feishu 告警发送；但 GitHub Actions 的每日 upstream 工作流会要求 webhook secrets 可用
- 真实 Webhook、密钥、私有订阅地址、MITM 参数与本地长期使用配置应继续保留在公开仓库外部的私人 `rulemesh-local` 仓库中
- 私有订阅端点同步块统一保留在解析后的私人当前配置目录中：使用 `private_subscription_direct.list` 作为单一源文件，运行 `sync_private_subscription_direct.ps1` 时显式选择 `-Target surge`、`-Target mihomo` 或 `-Target all`；不要在用户明确排除某一客户端时顺带更新它。目录解析见 [docs/private-repository-bootstrap.md](docs/private-repository-bootstrap.md)
- 两份 Mihomo 私有配置里的机场 `proxy-providers` 默认必须保留 `proxy: DIRECT`，用于让后台订阅 URL 更新直连；订阅端点的普通流量由 Mihomo `rules` 中的精确 `DOMAIN` / `IP-CIDR` 规则交给节点选择。这和 `rule-providers` 拉 GitHub 规则集时可使用 `proxy: "🚀 节点选择"` 是三条彼此独立的链路
- 检查机场 provider 是否过期、流量耗尽或仍有存活节点时，统一按 [私有订阅端点同步约定](docs/private-subscription-direct-sync.md#mihomo-provider-有效性极速审计) 的 30 秒目标 / 60 秒硬上限只读路径执行：并发无代理探测直属订阅 URL，再通过实际已配置的 Mihomo 控制器单次读取运行态汇总。FlClash 默认私有 IPC 不是 HTTP 控制器；控制器未启用时报告运行态未知。分别报告端点、配额、有效期与近期健康历史；默认不强制 health-check、不启动隔离核心，也不依据旧缓存下结论
- 四份本地私有配置里，所有基于 `policy-path` / provider 的代理组默认共用同一套排除条件：`剩余流量`、`套餐到期`、`距离下次重置`、`过滤掉`、`Expire Date`、`Traffic Reset` 这类状态/提示项按前缀匹配，`直接连接` 这类独立占位项按整行精确匹配，`联系我们` 与 `1.2 GB | 50 GB` 这类提示继续专项匹配
- 如果某个 provider 会给真实节点名追加统一前缀，不要把供应商名或独立占位项写成宽匹配，否则可能误伤真实节点
- 详细背景、禁止事项与改动前检查清单见 [docs/proxy-group-filter-methodology.md](docs/proxy-group-filter-methodology.md)
- 如果本地同时维护 FlClash 桌面端 与 FlClash 安卓端，建议分别维护 `rulemesh-substore-mihomo-flclash-desktop.yaml` 与 `rulemesh-substore-mihomo-flclash-android.yaml`
- 五份私有配置共享业务策略基线，但保留 Surge / Mihomo 自身的 DNS 与运行时语义，工作白名单也保持独立。
- 两份 Mihomo 私有配置使用默认国内双 DoH、AI 专用美国 DoH 与独立节点 bootstrap；IPv4、关闭 hosts 混入和 respect-rules 的约束继续保留。
- 旧版 2026-08-21 分层镜像 DNS 已由 2026-09-09 性能基线取代；不得按历史说明删除新版 AI 专用 policy 或必需的节点 bootstrap。
- Mihomo 私有文件里的 provider `health-check.url` 与 `url-test` 组测速 URL 统一使用 HTTPS `https://www.google.com/generate_204`，不要改回 HTTP
- 如果某个 provider 在 FlClash 桌面端 私有链路里整批测速失败，但把同一订阅直接导入客户端又正常，默认先按 [docs/mihomo-tun-dns-methodology.md](docs/mihomo-tun-dns-methodology.md) 对比运行时 `dns:`，优先排查 DNS 链差异，不要先把问题归因到节点本身
- 如果两份 Mihomo 私有文件里出现高优先级海外例外与 `rule-set:cn-performance-dns-domains` 之外的 `nameserver-policy`、`proxy-server-nameserver`、`fallback` 或 `respect-rules: true`，默认按 DNS 回归处理；已批准的分层例外不应被误删
- 对 FlClash 安卓端 的兼容性调整，默认也先保持“单一 DNS 真相”版本；只有在用户明确确认且 Android 运行时复测证明必须特化时，才允许为 Android 单独增加例外
- 这组私有订阅域名同步规则只记录在本地目录与私有文档约定中，不回写公开 `rules/`、`dist/` 或公开模板
- 详细维护方式见 [docs/private-subscription-direct-sync.md](docs/private-subscription-direct-sync.md)
- 若私有配置结构发生变化，必须同步更新 `.rulemesh.local.example.json` 与相关文档，但只能提交脱敏占位值

## Surge 7×24 本地监控

长期承担 DHCP 与旁路由流量接管的 Surge Mac，可使用 [docs/surge-local-monitoring.md](docs/surge-local-monitoring.md) 中的本地监控闭环。该机制由 macOS `launchd` 启动，与 Surge 的交互只通过自带 `surge-cli` 读取请求、DNS、规则、策略与有效配置摘要；它不要求打开 HTTP API，也不启用 MITM。

默认每 20 秒读取请求增量、每 5 分钟检查 DNS 与配置摘要、每 15 分钟执行轻量主动探测；全量 HMAC 去重键约保留 1 小时，关注请求明细保留 36 小时，探测、DNS 摘要、配置 / 健康审计与建议索引保留 14 天，数据库预算默认 256 MiB。独立的 Codex automation 每日 `09:00 Asia/Shanghai` 从已安装的运行副本读取脱敏报告并把完整建议留在 Scheduled；可选飞书提醒由本地守护进程在 `09:05` 独立发送，只包含采集质量和待查看项数量，它不是 Scheduled 成功完成的回执。落盘主机名只限国内分类目标、Google / ChatGPT 受控依赖、配置中的主动探测主机及其子域、明确命中 `google_hk` / `ai_us` 的受控平台目标与失败 `FINAL` 候选；其余只保存匿名客户端与策略 ID、规则类型、错误类别、计时，以及去重和关联所需的不可逆摘要。不得保存 URL 路径或查询、设备名或 IP、headers、body、原始 profile 或完整 CLI 输出。

请求类慢路径建议只依据 DNS / TCP 建连计时和明确失败触发；完整请求持续时间可能包含长轮询、流式传输或下载，仅作为调查上下文。固定轻量 HTTPS 主动探测仍保留端到端总耗时判断。

监控和日报只负责提出 `RM-INV-*` 调查建议；用户只能在对应 Scheduled 任务中回复 `批准调查 RM-INV-*` 来授权只读深挖，飞书回复不计入审批。调查形成精确 diff、风险、回滚与复测步骤后，必须另行生成 `RM-EXEC-*` 并获得第二次明确批准，才允许执行 `set`、`reload`、`flush dns`、`switch-profile`、配置编辑或策略切换。采集缺失、失败或过期时，日报暂停网络优化判断；获批后的变更仍要同时复测规则命中、IP 出口与 DNS 出口。

## 维护建议

- 动手前先把本次改动归类到“源规则 / 上游登记 / 公开说明模板 / 构建与检查脚本 / 私有同步项”；高风险联动没想清前，不要直接编辑
- 优先改 `rules/`，不要直接手改 `dist/`
- 新增规则前，先想清楚它是 `reject`、`direct`、`proxy` 还是 `region`
- 遇到单一应用同时涉及多种动作时，优先维护 `rules/app/*.txt` 主清单，再由构建前同步派生到现有分类
- 新增、删除或重命名 `rules/{reject,direct,proxy,region}/` 下的 `.list` 源规则文件时，同步更新 `rules/upstream/sources.yaml` 与 `rules/upstream/merge.yaml`
- 新增或调整默认对外使用的规则入口、顺序、策略含义时，同步更新 `README.md`、`docs/usage-surge.md`、`docs/usage-mihomo.md` 与两份公开模板
- 新增或调整 Mihomo 默认的 Tun、嗅探、DNS 分流、安全边界或性能取舍时，同步更新 `docs/mihomo-tun-dns-methodology.md`
- 新增或调整 Surge / Mihomo / Sub-Store / DoH / fake-ip / Tun / 透明代理相关配置时，同步检查 DNS 泄漏风险，并按需更新 [docs/network-security/dns-leak-prevention.md](docs/network-security/dns-leak-prevention.md)
- 新增、删除或调整“某类规则在 Mihomo 侧是否保留 / 跳过”的兼容映射时，同步更新 `README.md`、`docs/usage-mihomo.md` 与 `docs/mihomo-tun-dns-methodology.md`
- 如果本次修改改变了源规则的编排方式、分组风格、文件边界或维护习惯，同步更新 `AGENTS.md`、`README.md` 与 `docs/rule-authoring-style.md`
- 如果一个源文件开始变得很大，优先补 `sources.yaml` 与 `merge.yaml`，再考虑引入更多上游素材
- 提交前优先运行 `powershell -ExecutionPolicy Bypass -File tools/check.ps1`
- `tools/check.ps1` 现在会先执行 `tools/check_change_guardrails.py` 与 `tools/check_dns_safety.py`：少数确定性的强关联项和 DNS 高风险配置会直接失败，其余高风险联动会以提醒形式输出，默认不能忽略
- 提交前看一眼 `dist/build-report.json` 的 warnings，特别是 Mihomo 不支持的规则类型
- 只有实际执行过构建、检查、`git status` 等动作，最终结论里才算“已验证”；不要把推断写成已完成
- 自写注释、生成说明、文档说明默认统一写中文，不要再放英文占位注释

## 规则方法论：上游优先 + 本地兜底

本仓库统一采用“上游优先精准匹配 + 本地规则兜底覆盖”的编排方式：

- 先写 `INCLUDE,upstream/...`，优先命中第三方持续维护的精细规则。
- 再写本地兜底规则，优先使用 `DOMAIN-KEYWORD` 与 `DOMAIN-SUFFIX` 提升覆盖韧性。
- 兜底规则只补“高频且长期稳定”的关键词/后缀，避免把本地规则膨胀成上游镜像。
- 当某类规则暂无可靠上游时，可先保留手写规则；一旦有稳定上游，再迁移到“上游优先”结构。
- 目标是同时兼顾：上游的精准全面 + 本地兜底的抗失效能力。

机场策略与配置精简：三份私人 Surge 的七个机场手动组分别保留并接回选择入口，不按规则引用数量删除。Personal 爱思入口集中为 `direct/aisi_direct`；Apple 更新和 Google Play 复用既有规则集；Surge AI DNS 的美国出口集中为 `region/us/ai_dns_us`。Mihomo 保持已有组与 DNS 代理参数，不扩大业务范围。设备地址及订阅端点继续只在私人仓库维护，详见 [性能基线](docs/performance-baseline.md)。

2026-09-12：`direct/ips5_direct` 以 DIRECT 覆盖 `ips5.vip` 主域及全部子域，位于 AI 之后、Google 广谱与拒绝之前，使用默认国内双 DoH；工作白名单仅增加该服务。AdsPower 停用范围、资产与定时任务处理见[规则停用与恢复](docs/rule-deactivation.md)。

2026-09-12 FlClash 迁移与优化以 [客户端性能基线](docs/flclash-performance.md) 为准：桌面和安卓使用新文件名；通用末尾改为 cn_direct_light → gfw_precise → DIRECT，完整规则资产保留。工作白名单不接入新兜底，机场手动组保留。桌面 300 秒、安卓 600 秒，备用地区按需检测；以最终生成配置核对界面覆写。
