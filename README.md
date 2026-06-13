# RuleMesh

这个仓库现在按“一份源规则，多端产物输出”的思路维护：

- `rules/` 是源规则层，只放你自己审阅后的规则素材与维护元数据
- `dist/` 是构建产物层，客户端只引用这里
- `Surge` 使用 `dist/surge/rules/`
- `Surge` 与 Mihomo 的国内业务域名 DNS 白名单共用 `dist/surge/dns/`
- `Clash Verge Rev` 与 `Clash Meta for Android` 使用 `dist/mihomo/classical/`

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
  check_dns_safety.py
```

说明：

- `rules/` 下参与构建的源规则文件统一使用 `.list` 命名
- `rules/dns/` 用于维护 DNS 专用域名清单；当前 `cn_dns_domains.list` 生成 `dist/surge/dns/cn_dns_domains.list`
- `rules/app/` 用于维护单一应用的主清单；例如 `rules/app/adspower.txt` 会在构建前自动派生到 `rules/reject/`、`rules/direct/` 与 `rules/proxy/`
- 例如 `rules/region/us/google_us.list` 会生成 `dist/surge/rules/region/us/google_us.list` 与 `dist/mihomo/classical/region/us/google_us.yaml`
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
这个脚本现在还会额外校验 Surge 配置里的测速 URL 约定，防止把必须保持 `http://` 的字段误改成 `https://`；同时执行 `tools/check_dns_safety.py`，检查 Surge / Mihomo 配置是否把普通目标网站域名泄漏到国内 DNS。

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
- 通用上游、Chainlist、1Password、AWS、阿里云等 upstream 抓取失败会统一聚合告警；如果工作流其他步骤失败，还会再发一条不依赖仓库 checkout 的工作流级失败兜底告警
- 支持手动触发
- [`.github/workflows/build-dist.yml`](.github/workflows/build-dist.yml) 不再自动拉上游或自动修复提交；如果网页端直接编辑 `main` 却漏提 `dist/`，工作流会明确报错提醒补齐

## 客户端如何使用

请只引用 `dist/`，不要直接引用：

- `rules/`
- 第三方原始规则库 URL
- `rules/upstream/` 下的登记文件

接入示例见：

- [docs/usage-surge.md](docs/usage-surge.md)
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

补充约定：

- 2026-05-07 下线的两类激进拒绝入口不再作为默认规则维护，也不要回写到公开模板或私有配置
- AdsPower 专项规则统一维护在 `rules/app/adspower.txt`
- 客户端应显式接入 `reject/adspower_reject`、`direct/adspower_direct` 与 `proxy/adspower_proxy`，不要再退回单条 `DOMAIN-KEYWORD,adspower` 兜底
- GitHub Core 代理专项规则统一维护在 `rules/proxy/github_core_proxy.list`
- 客户端应显式接入 `direct/github_ssh_direct` 与 `proxy/github_core_proxy`，并都放在 `proxy/gfw` 前；前者只承接 `github.com:22` 与 `ssh.github.com:443`，后者显式承接 GitHub 网页、`api.github.com`、Gist、Raw、静态资源与附件
- Polygon 主网 RPC 专项规则统一维护在 `rules/proxy/polygon_rpc_proxy.list`
- BSC 主网 RPC 专项规则统一维护在 `rules/proxy/bsc_rpc_proxy.list`
- 两者上游快照由 `tools/sync_upstream_rules.py` 每日从 Chainlist 的 `rpcs.json` 抓取并累计更新，避免日常波动导致既有覆盖面回撤
- 客户端应显式接入 `proxy/polygon_rpc_proxy` 与 `proxy/bsc_rpc_proxy`，并放在 `proxy/gfw` 前，让 `🚀 节点选择` 先命中这些 RPC 域名
- 海外 DNS 主 IPv4 端点专项规则统一维护在 `rules/proxy/overseas_dns_ipv4_proxy.list`
- 客户端应显式接入 `proxy/overseas_dns_ipv4_proxy`，并放在 `proxy/gfw` 前；Surge 侧继续按 `RULE-SET,...,"🇺🇸 美国-自动选择",no-resolve` 接入，让美国地区策略先命中 `1.1.1.1/32`、`8.8.8.8/32` 与 `9.9.9.9/32`
- AWS 香港区域规则入口已统一命名为 `region/hk/hk_aws_ipv4`，与东京、大阪、首尔、台北保持同类命名
- 自维护多地区链式 SOCKS5 端点入口已统一命名为 `region/multi/chain_socks5_ipcidr`，不再继续挂在 `region/jp/` 或默认绑定日本策略组
- 阿里云香港 SSH 直连入口已统一命名为 `direct/alicloud_hk_ipv4_ssh22_direct`；`rules/upstream/alicloud/hk_ipv4.txt` 继续保留纯 IPv4 快照，而公开入口文件直接保留 `SSH TCP/22` 最终语义，不要求客户端额外拼接端口条件
- Surge 与 Mihomo 当前统一把 GeoIP mmdb 显式固定到你自己的仓库 Release 镜像：`vtgpcmsvgs/rulemesh/releases/download/geoip-country-mmdb/country.mmdb`
- 对应上游登记与维护约定见 `rules/upstream/geodata/metacubex_country_mmdb.yaml` 与 [docs/geoip-upstream.md](docs/geoip-upstream.md)
- Surge 的 `internet-test-url`、`proxy-test-url`、代理 `test-url=` 与 `smart / fallback / load-balance` 的 `url=` 统一保持 `http://`；不要因为 `policy-path`、GeoIP 或其他下载入口使用 `https://` 就顺手改成 `https://`。
- 当前公开模板与本地私有 Surge 配置默认采用 `http://www.baidu.com`、`http://www.google.com/generate_204` 与 `http://www.gstatic.com/generate_204` 这组三段式测速 URL；它们不是唯一答案，但继续作为本仓库的轻量稳定基线。
- `rules/region/hk/global_media.list` 额外承接 `x.com`、`t.co`、`twimg.com` 与 `twitter.com` 等 X / Twitter 网页域名，以及 `polymarket.com` 与 `DOMAIN-KEYWORD,polymarket` 这组 Polymarket 香港兜底，默认绑定 `🇭🇰 香港-自动选择`，减少回落到通用 `proxy/gfw` 或误挂到日本策略的超时与地区限制
- 1Password 核心连接专项规则统一维护在 `rules/proxy/onepassword_proxy.list`
- 上游快照由 `tools/sync_upstream_rules.py` 每日抓取 1Password 官方《ports and domains》支持页，保守收敛到核心一方域名与更新/基础设施端点
- 如需启用，请显式接入 `proxy/onepassword_proxy` 并放在 `proxy/gfw` 前；公开模板默认不内置这条重度用户特化入口
- 操作系统时间同步专项规则统一维护在 `rules/direct/os_time_direct.list`
- 客户端应显式接入 `direct/os_time_direct`，并放在其他普通 `direct/*` 前，默认保持 `DIRECT`
- 如果你采用“默认禁更，升级时手动临时放行”的习惯，建议同时接入 `direct/os_time_direct`、`reject/os_update_reject`、`region/us/microsoft_us` 与 `region/us/macos_update_us`；其中 `os_time_direct` 负责系统时间同步直连，其余入口必须放在 `reject` 之后并绑定美国策略
- 国内业务域名 DNS 白名单统一维护在 `rules/dns/cn_dns_domains.list`，并生成 `dist/surge/dns/cn_dns_domains.list`；该清单只放明确国内业务域名 / 国内域名后缀，不放代理节点 server 域名、订阅入口域名、IP 或复杂规则

其中 Surge 当前建议明确区分两种使用版本：

- 软路由集群版
  - 只在本地私有环境维护，用于工作电脑集群接入软路由 Surge。
  - 允许包含按局域网源 IP 的设备分流、私有 `policy-path`、`[MITM]` 与证书参数。
- 其中私有 `rulemesh-substore-surge-work-whitelist.conf` 当前采用工作电脑白名单模式：只保留明确列出的放行入口，未列入白名单的流量统一 `REJECT`。
- 这份工作白名单默认不额外开放局域网代理入口；旁路由已接管流量，工作文件不承担 LAN 代理服务。
- 其中只有设备分流继续按局域网源 IP 约束，并按指定 AWS 区域 / 多地区链式 SOCKS5 IP 段定向到对应工作机亚洲出口组；区域精确、GitHub SSH、GitHub Raw 自举入口、GitHub Core 代理入口、GitHub 观察兜底、私有订阅域名同步块、1Password 核心连接、AdsPower、Polygon 主网 RPC、BSC 主网 RPC、海外 DNS 主 IPv4 端点、代理节点 bootstrap DNS 直连例外、海外加密 DNS 显式入口与指定直连不再额外限制源 IP。
- 在该白名单里，`direct/os_time_direct` 属于系统时间同步直连入口，`region/us/microsoft_us` 与 `region/us/macos_update_us` 属于允许保留的系统类美国分流入口。
- 白名单专属的单个直连域名例外（例如 `smtp.163.com`）默认直接维护在“指定直连”入口，不为单条规则额外拆分公开 `rules/` 文件。
- 白名单专属的单个拒绝域名，或只用于阻断浏览器扩展更新链路的拒绝规则，也默认直接维护在白名单的“拒绝规则”入口，不为单条规则额外拆分公开 `rules/` 文件。
- 其中 `proxy/onepassword_proxy`、`proxy/polygon_rpc_proxy`、`proxy/bsc_rpc_proxy`、`proxy/overseas_dns_ipv4_proxy`，代理节点 bootstrap DNS 直连例外 `dns.alidns.com` / `doh.pub`，以及 DoH / DoH3 / DoQ、`cloudflare-dns.com`、`dns.google`、`dns.quad9.net` 都是允许保留的白名单入口；bootstrap DNS 走 `DIRECT`，海外加密 DNS 端点走美国出口。
  - 其中 GitHub SSH 后先进入 GitHub Raw 自举入口，再显式放行 `proxy/github_core_proxy`，并保留一条 `DOMAIN-KEYWORD,github,REJECT` 广覆盖观察兜底，用于发现 SSH / GitHub Core 之外的漏网之鱼；AdsPower 细分规则后也保留一条 `DOMAIN-KEYWORD,adspower,REJECT` 广覆盖观察兜底。
  - 阿里云香港 SSH、`aliyuncs.com` 与 `check.myclientip.com` 统一收敛到“指定直连”段显式放行；其后额外保留一条阿里云广覆盖 `REJECT` 观察兜底，用于发现上游阿里云规则的漏网之鱼。
  - 私有订阅域名统一在 `%USERPROFILE%\Desktop\rulemesh-local\current\private_subscription_direct.list` 维护，并通过脚本同步到本地四份私有配置中的“Chrome 访问节点选择例外 + 订阅更新直连”规则块，不回写公开模板。
  - 其中 `raw.githubusercontent.com` 作为规则产物下载自举入口，但不再使用 `server:system`；普通目标网站的全局 DNS 仍保持海外 DNS，不再回退到 `system + 国内 DNS`。
  - 工作白名单模式下，广覆盖观察规则统一只允许使用 `REJECT`；不要对 `DIRECT` 或 `PROXY` 规则使用 `extended-matching`，否则会把可伪造的 Host / SNI 纳入放行判断，扩大绕过白名单的攻击面。
  - 原单独 `IP 规则` 段已删除，避免与设备分流重复。
  - 其中 AdsPower 在精细规则后允许额外保留一条广覆盖观察兜底，用于发现细分规则漏网之鱼。
  - 这份工作路由白名单与两个 `personal` 配置永久有意不一致，后续维护不要按“统一模板”思路把它改回去。
  - 维护约定见 [docs/surge-work-cluster-whitelist.md](docs/surge-work-cluster-whitelist.md)。
- 个人终端版
  - 对应仓库里的公开参考模板 [`docs/examples/surge-public.conf`](docs/examples/surge-public.conf)。
  - 保留通用的 `General + Proxy Group + Rule` 结构，但移除设备分流、私有订阅地址与 `[MITM]`。
  - 不继承上述工作路由白名单约束，继续按个人/公开模板的通用结构维护。

其中两份公开参考模板已经做过脱敏处理，适合直接上传到公开仓库给他人参考：

- `docs/examples/surge-public.conf`
  - 对应 Surge 的“个人终端版”
  - 保留完整 `General + Host + Proxy Group + Rule` 结构
  - 已移除设备分流、私有订阅地址与 `[MITM]`
- 默认保持 `allow-wifi-access = false`，不把个人终端直接暴露给局域网其他设备
- Surge profile 不写 `dns-mode = fake-ip`；Fake IP 由 Surge Enhanced Mode / VIF 运行时提供，Mac 端加载 profile 后需要在 Surge 里启用 Enhanced Mode
- Surge `skip-proxy` 不再包含 Apple `17.0.0.0/8`，避免 macOS 更新流量绕过 `reject/os_update_reject` 与 `region/us/macos_update_us`
- 默认启用 `use-local-host-item-for-proxy = false`、`hijack-dns = *:53`、海外 `encrypted-dns-server`、`encrypted-dns-follow-outbound-mode = true` 与 `test-timeout = 3` 这组运行时参数
- 默认关闭 `ipv6 = false`，并注释 `ipv6-vif = auto`；如需 IPv6，应先完成 DNS 泄漏、WebRTC 与出口一致性测试
- 默认同时接入 `direct/os_time_direct`，并配套接入 `reject/os_update_reject`、`region/us/microsoft_us` 与 `region/us/macos_update_us`；前者负责系统时间同步，后两者在放开拒绝规则后统一走美国节点
- 默认接入 AdsPower 专项 `reject/direct/proxy` 规则集，并保持在 `proxy/gfw` 前完成细分控制
- 默认接入 Polygon 主网 RPC 专项 `proxy/polygon_rpc_proxy` 规则，并保持在 `proxy/gfw` 前优先命中
- 默认接入 BSC 主网 RPC 专项 `proxy/bsc_rpc_proxy` 规则，并保持在 `proxy/gfw` 前优先命中
- 默认接入海外 DNS 主 IPv4 端点专项 `proxy/overseas_dns_ipv4_proxy` 规则，并保持在 `proxy/gfw` 前优先命中；命中后统一走 `🇺🇸 美国-自动选择`
- 默认在 `github_ssh_direct` 后先保留 `DOMAIN,raw.githubusercontent.com,"🚀 节点选择"` 自举入口，再接入 `proxy/github_core_proxy`；同时继续保留 `raw.githubusercontent.com = server:https://cloudflare-dns.com/dns-query` 这一条规则产物下载解析例外，但它不是代理节点 bootstrap，不能替代 `proxy-node-domains` 的 AliDNS 解析
- Surge `[Host]` 中的 `proxy-node-domains` 必须使用生产设备可直接访问的 Sub-Store 分享文件 URL，形如 `https://<你的 Sub-Store 后端或反代域名>/share/file/proxy-node-domains`；不要把未经同网络验证的 `/api/file/` 链接直接写进生产配置
- `proxy-node-domains` 返回内容必须过滤 IP，并按一行一个域名输出；逗号分隔的一整行不符合 Surge `DOMAIN-SET` 预期
- 这类 Surge 运行时参数不要求 Mihomo 公开模板逐项镜像；Mihomo 继续按各自的 Tun / DNS 语义单独维护
- 默认接入 `direct/alicloud_hk_ipv4_ssh22_direct`，并在直连段显式保留 `DOMAIN-SUFFIX,aliyuncs.com` 与 `DOMAIN,check.myclientip.com`
- 默认让 X / Twitter 网页、短链与静态资源，以及 Polymarket 相关域名优先命中 `region/hk/global_media`，避免落回通用 `proxy/gfw`
- 默认接入 `region/jp/domains_to_jp` 入口；当前用于让 `opinion.trade` 走 `🇯🇵 日本-自动选择`
  - 刻意不承载私有工作路由白名单结构，避免把本地工作特化误当成公开模板默认值
- `docs/examples/mihomo-public.yaml`
  - 保留完整 `tun + sniffer + dns + proxy-providers + proxy-groups + rule-providers + rules` 结构
  - 已移除真实机场订阅链接、供应商命名与控制面参数
  - `proxy-providers.*.proxy` 默认显式写 `DIRECT`，只控制 Mihomo 后台更新机场订阅 URL；浏览器访问机场官网 / 面板仍由 `rules` 里的进程与域名规则控制
- 默认同时接入 `direct/os_time_direct`，并配套接入 `reject/os_update_reject`、`region/us/microsoft_us` 与 `region/us/macos_update_us`；前者负责系统时间同步，后两者在放开拒绝规则后统一走美国节点
- 默认接入 AdsPower 专项 `reject/direct/proxy` 规则集，并保持在 `proxy/gfw` 前完成细分控制
- 默认接入 Polygon 主网 RPC 专项 `proxy/polygon_rpc_proxy` 规则，并保持在 `proxy/gfw` 前优先命中
- 默认接入 BSC 主网 RPC 专项 `proxy/bsc_rpc_proxy` 规则，并保持在 `proxy/gfw` 前优先命中
- 默认接入海外 DNS 主 IPv4 端点专项 `proxy/overseas_dns_ipv4_proxy` 规则，并保持在 `proxy/gfw` 前优先命中；命中后统一走 `🇺🇸 美国-自动选择`
- 默认接入 `direct_alicloud_hk_ipv4_ssh22`，并在直连段显式保留 `DOMAIN-SUFFIX,aliyuncs.com` 与 `DOMAIN,check.myclientip.com`
- 默认让 X / Twitter 网页、短链与静态资源，以及 Polymarket 相关域名优先命中 `region/hk/global_media`，避免落回通用 `proxy/gfw`
- 默认接入 `jp_domains` 规则提供器；当前用于让 `opinion.trade` 走 `🇯🇵 日本-自动选择`
  - 对两份 Mihomo 私有 provider 配置，当前默认保持 `ipv6: false` 与 `dns.ipv6: false`，优先先把 IPv4、fake-ip 与 DNS 链路做稳；不要因为 Surge 或某次临时实验可用，就把双栈重新开成默认基线
  - 默认采用 Tun 全量接管、域名嗅探与 DNS 隔离；两份 Mihomo 私有文件当前保持“单一 DNS 真相”版本，普通目标网站域名只走 `nameserver`，不要再默认引入 `proxy-server-nameserver`、`nameserver-policy`、`fallback` 这类多层 DNS 叠加
  - 同样不承载私有 Surge 工作路由白名单特化

## 当前设计原则

- 源规则尽量保持小而清晰，优先你自己的审阅结果
- 规则类上游只作为参考素材，不直接暴露给客户端
- GeoIP 数据库属于运行时依赖，当前作为显式例外统一固定到“MetaCubeX upstream + 本仓库 Release 镜像分发”
- 统一输出显式规则行，不再生成额外的客户端专用精简产物
- 域名规则、CIDR 规则与大多数关键词规则都通过 `RULE-SET` / `behavior: classical` 接入
- 单一应用如果同时涉及 `reject`、`direct`、`proxy` 多种动作，优先使用 `rules/app/*.txt` 主清单统一维护，再派生到现有四类源规则
- AdsPower 专项规则应先命中 `reject/adspower_reject`、`direct/adspower_direct`、`proxy/adspower_proxy`，再落到 `proxy/gfw`
- Polygon 主网 RPC 专项规则应先命中 `proxy/polygon_rpc_proxy`，再落到 `proxy/gfw`
- BSC 主网 RPC 专项规则应先命中 `proxy/bsc_rpc_proxy`，再落到 `proxy/gfw`
- 海外 DNS 主 IPv4 端点专项规则应先命中 `proxy/overseas_dns_ipv4_proxy` 并走美国地区策略，再落到 `proxy/gfw`
- GitHub 相关访问应先命中 `direct/github_ssh_direct` 与 `proxy/github_core_proxy`，再落到 `proxy/gfw`
- X / Twitter 网页、短链与静态资源，以及 Polymarket 相关域名应先命中 `region/hk/global_media`，再落到 `proxy/gfw`
- 1Password 核心连接专项规则如启用，应先命中 `proxy/onepassword_proxy`，再落到 `proxy/gfw`
- 操作系统时间同步专项规则应先命中 `direct/os_time_direct`，再落到其他普通 `direct/*`
- Google 通用服务、海外 AI、Microsoft 与 macOS 更新专项入口应先命中 `region/us/*`，其中 Microsoft / macOS 更新仍必须排在 `reject/os_update_reject` 之后，避免默认禁更逻辑失效
- DNS 信任边界优先于连通性微调：普通目标网站域名默认不得交给国内 DNS；国内 DNS 只作为 DNS 服务器域名 bootstrap、代理节点 `server` 域名 bootstrap，以及 `cn_dns_domains` 专用国内业务域名白名单的受限例外；详细约束见 [docs/network-security/dns-leak-prevention.md](docs/network-security/dns-leak-prevention.md)
- 同一套路由骨架不等于同一个客户端运行时；`Surge`、`Clash Verge Rev`、`Clash Meta for Android` 在 DNS 启动链上允许存在实现差异
- 本地同时维护 Clash Verge Rev 与 Clash Meta for Android 时，允许拆成两份 Mihomo 私有配置；规则骨架尽量共享，节点域名解析策略允许分别维护
- Surge 私有工作路由白名单与本地其他私有配置永久允许结构不一致，维护时不要互相回抄

## 源规则编排约定

- 中大型源规则文件默认按“同平台 / 同服务聚合展示 + 上游优先 + 本地兜底”维护，不再把显式域名和关键词兜底简单堆成两大坨
- 文件头必须先写清楚：这份规则负责什么、不负责什么、与相邻规则文件的边界是什么、客户端顺序上应放在哪里
- 同一小节内部默认顺序是：小节注释、`INCLUDE,upstream/...`、显式域名 / 网段、`DOMAIN-KEYWORD` 兜底
- IP 类源规则可以只写 `IP-CIDR`、`IP-CIDR6`、`GEOIP`、`IP-ASN`、`ASN` 主体；构建产物会自动补 `no-resolve`，客户端调用纯 IP 规则集时仍建议在 `RULE-SET` 层保留 `no-resolve`
- 像 `ai_us`、`ai_cn_direct`、`bytedance_direct`、`google_us`、`crypto_tw` 这类多平台或多服务混合文件，优先按平台或服务分组
- 像 `cn_direct`、`telegram` 这类入口型或通用基础兜底文件，可以保持“上游主体 + 本地最高优先级兜底”的简单结构，但仍要把边界写清楚
- 如果本次修改只影响注释、分组与顺序，且构建后确认 `dist/` 内容不变，允许最终只提交源文件；但仍然必须完整执行构建和检查
- 详细规则见 [docs/rule-authoring-style.md](docs/rule-authoring-style.md)

## Google 路由强约束

- Google 通用服务（含 Google Play / YouTube / FCM）主维护在 `rules/region/us/google_us.list`；Google Play 下载 CDN 与重定向域也应在这里显式兜底，避免被后面的通用 direct/gfw 抢先接管
- `Gemini` / `AI Studio` / `NotebookLM` 允许在 `rules/region/us/ai_us.list` 保留 AI 视角交叉兜底，但客户端顺序仍必须让 `google_us` 排在 `ai_us` 前
- 客户端应接入 `dist/surge/rules/region/us/google_us.list` 或 `dist/mihomo/classical/region/us/google_us.yaml`
- Google 规则必须绑定 `US-AUTO`（或等价美国策略组），不再提供 `proxy/google` 双入口
- 规则顺序必须先放 Google US 规则，再放 `region/us/ai_us` 与 `region/hk/global_media` 等广谱区域规则；Google 通用服务与海外 AI 入口都统一命中美国策略
- 新增或调整 Google 规则时，先改该源文件，再执行构建同步 `dist/`

## AI 路由约定

- `rules/region/us/ai_us.list` 当前按“第三方上游聚合 + 本地激进兜底”维护，但定位已收敛为“海外 AI 平台入口”，统一承接 `OpenAI`、`Claude`、`Gemini`、`Copilot`、`Cursor`、`Grok`、`Windsurf`、`Augment` 等海外 AI 平台，并统一绑定美国地区策略
- `rules/direct/ai_cn_direct.list` 新增为“国内 AI 显式直连入口”，优先承接 `Kimi / Moonshot`、`DeepSeek`、`豆包`、`即梦`、`Trae 中国大陆入口`、`元宝`、`混元`、`通义 / 千问`、`智谱 / ChatGLM`、`MiniMax / 海螺`、`文心` 等国内 AI 平台
- `Trae` 只在 `ai_us` 中保留明确海外入口；`DeepSeek`、`Trae` 中国大陆入口与其他国内 AI 不应并入 `ai_us`，而应优先落到 `direct/ai_cn_direct`，共享基础设施再继续落到 `direct/bytedance_direct`、`direct/cn_direct`
- 上游主体优先引用 `blackmatrix7/ios_rule_script`、`SkywalkerJi/Clash-Rules` 与 `Accademia/Additional_Rule_For_Clash` 的快照；其中 `Trae` 只参考第三方上游，不再直接整包并入，避免把国内入口误送到海外 AI 代理策略
- 客户端顺序继续保持 `google_us` 在前、`ai_us` 在后；国内 AI 侧则让 `direct/ai_cn_direct` 排在 `direct/bytedance_direct`、`direct/cn_direct` 前，确保显式国内入口优先命中
- 私有 `rulemesh-substore-surge-work-whitelist.conf` 不会自动并入这组新的国内 AI 放行入口；工作白名单仍需继续按“只放行明确白名单入口，其余统一 REJECT”的原则单独评估

## 上游维护方式

当前仓库只先落两类维护元数据：

- `rules/upstream/sources.yaml`
  - 记录每个主要源文件建议参考哪些上游
- `rules/upstream/merge.yaml`
  - 记录未来如何把上游素材并回本仓库源规则
- `rules/upstream/geodata/metacubex_country_mmdb.yaml`
  - 记录 Surge 与 Mihomo 共用的 GeoIP mmdb 上游选择与下载入口

这几类文件当前都不参与规则构建，只负责把维护策略写清楚，避免后续继续依赖口头约定。

## 本地私有配置

仓库提供 [`.rulemesh.local.example.json`](.rulemesh.local.example.json) 作为本地私有配置模板。复制为 `.rulemesh.local.json` 后，可给 `tools/sync_upstream_rules.py` 提供本地告警与阿里云上游鉴权配置；当前支持：

- `upstream_alert.feishu_webhook_url`
- `upstream_alert.feishu_secret`
- `alicloud.access_key_id`
- `alicloud.access_key_secret`
- `alicloud.security_token`

约定如下：

- `.rulemesh.local.json` 只用于本地私有环境，已经被 `.gitignore` 忽略，不应提交到公开仓库
- 缺少本地配置时，不影响本地构建与手工同步主流程，只会跳过本地 Feishu 告警发送；但 GitHub Actions 的每日 upstream 工作流会要求 webhook secrets 可用
- 真实 Webhook、密钥、私有订阅地址、MITM 参数与本地长期使用配置应继续保留在公开仓库外部，例如 `%USERPROFILE%\Desktop\rulemesh-local\current`
- 私有订阅域名同步块当前也统一保留在 `%USERPROFILE%\Desktop\rulemesh-local\current` 中：使用 `private_subscription_direct.list` 作为单一源文件，再通过 `sync_private_subscription_direct.ps1` 同步到四份本地私有配置中的“Chrome 访问节点选择例外 + 订阅更新直连”规则块
- 两份 Mihomo 私有配置里的机场 `proxy-providers` 默认必须保留 `proxy: DIRECT`，用于让后台订阅 URL 更新直连；这和 `rule-providers` 拉 GitHub 规则集时可使用 `proxy: "🚀 节点选择"` 是两条不同链路
- 四份本地私有配置里，所有基于 `policy-path` / provider 的代理组默认共用同一套排除条件：`剩余流量`、`套餐到期`、`距离下次重置`、`过滤掉`、`Expire Date`、`Traffic Reset` 这类状态/提示项按前缀匹配，`直接连接` 这类独立占位项按整行精确匹配，`联系我们` 与 `1.2 GB | 50 GB` 这类提示继续专项匹配
- 如果某个 provider 会给真实节点名追加统一前缀，不要把供应商名或独立占位项写成宽匹配，否则可能误伤真实节点
- 详细背景、禁止事项与改动前检查清单见 [docs/proxy-group-filter-methodology.md](docs/proxy-group-filter-methodology.md)
- 如果本地同时维护 Clash Verge Rev 与 Clash Meta for Android，建议分别维护 `rulemesh-substore-mihomo-clash-verge.yaml` 与 `rulemesh-substore-mihomo-clash-meta.yaml`
- 四份私有配置不是同一套 DNS 方法论：两份 Surge 私有配置允许继续保留 Surge 自己可用的复杂 DNS 版本；两份 Mihomo 私有配置默认不允许照搬这套结构
- 对 `rulemesh-substore-mihomo-clash-verge.yaml` 与 `rulemesh-substore-mihomo-clash-meta.yaml`，默认保持“单一 DNS 真相”版本：`ipv6: false`、`use-hosts: false`、`use-system-hosts: false`，`dns:` 里只保留 `default-nameserver`、`nameserver`、`fake-ip-filter` 等最小必需字段
- 未经用户明确确认与运行时复测，不要在两份 Mihomo 私有文件里恢复 `respect-rules: true`、`nameserver-policy`、`proxy-server-nameserver`、`proxy-server-nameserver-policy`、`direct-nameserver`、`fallback`
- Mihomo 私有文件里的 provider `health-check.url` 与 `url-test` 组测速 URL 统一使用 HTTPS `https://www.google.com/generate_204`，不要改回 HTTP
- 如果把 `rulemesh-substore-mihomo-clash-verge.yaml` 当成 Clash Verge Rev 的日常主配置，建议在客户端“订阅”页对这份本地配置右键“编辑信息”，把 `更新时间隔` 设为 `720` 分钟，作为默认维护基线
- 这项 `720` 分钟设置不写回 YAML，而是保存在每台设备自己的 Clash Verge Rev profile 元数据里；换设备后需要重新设置一次
- 这项 `720` 分钟设置不替代 YAML 里的 `proxy-providers` / `rule-providers` 自身 `interval`；后者仍负责 Mihomo 内核层的下载间隔，前者只是额外的外层定时重载保险，用于降低长期后台运行、睡眠唤醒后 provider 偶发不刷新的概率
- 如果把 `rulemesh-substore-mihomo-clash-verge.yaml` 当成 Clash Verge Rev 的唯一权威配置，默认应关闭 Clash Verge Rev 的 `DNS 覆写`；否则运行时 `dns` 会被 AppData 下的 `dns_config.yaml` 覆盖
- 如果明确保留 Clash Verge Rev 的 `DNS 覆写`，则应把 `dns_config.yaml` 视为实际生效的 `dns` 单一真相，而不是继续假设源文件里的 `dns:` 会原样生效
- 如果关闭 Clash Verge Rev 的 `DNS 覆写` 后出现“国内可访问、国外代理不通”，默认先确认桌面端私有文件是否被改离了“单一 DNS 真相”版本，而不是先回滚规则顺序或怀疑节点本身
- 如果某个 provider 在 Clash Verge Rev 私有链路里整批测速失败，但把同一订阅直接导入客户端又正常，默认先按 [docs/mihomo-tun-dns-methodology.md](docs/mihomo-tun-dns-methodology.md) 对比运行时 `dns:`，优先排查 DNS 链差异，不要先把问题归因到节点本身
- 如果两份 Mihomo 私有文件里再次出现 `nameserver-policy`、`proxy-server-nameserver`、`fallback` 或 `respect-rules: true` 回流，默认按 DNS 回归处理，优先恢复到“单一 DNS 真相”版本，而不是继续在复杂分层上叠补丁
- 对 Clash Meta for Android 的兼容性调整，默认也先保持“单一 DNS 真相”版本；只有在用户明确确认且 Android 运行时复测证明必须特化时，才允许为 Android 单独增加例外
- 这组私有订阅域名同步规则只记录在本地目录与私有文档约定中，不回写公开 `rules/`、`dist/` 或公开模板
- 详细维护方式见 [docs/private-subscription-direct-sync.md](docs/private-subscription-direct-sync.md)
- 若私有配置结构发生变化，必须同步更新 `.rulemesh.local.example.json` 与相关文档，但只能提交脱敏占位值

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
