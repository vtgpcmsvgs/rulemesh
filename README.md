# RuleMesh

这个仓库现在按“一份源规则，多端产物输出”的思路维护：

- `rules/` 是源规则层，只放你自己审阅后的规则素材与维护元数据
- `dist/` 是构建产物层，客户端只引用这里
- `Surge` 使用 `dist/surge/rules/`
- `Clash Verge Rev` 与 `Clash Meta for Android` 使用 `dist/mihomo/classical/`

这样做的目标是把“怎么维护规则”与“客户端怎么接入规则”分开，避免客户端继续直接引用第三方规则上游仓库，也避免源规则和客户端格式绑死。GeoIP 数据库属于客户端运行时依赖，是当前保留的显式外部上游例外。

## 目录说明

```text
rules/
  app/         # 应用级主清单（构建前自动派生）
  reject/      # 拒绝类源规则
  direct/      # 直连类源规则
  proxy/       # 代理类源规则
  region/      # 区域策略类源规则
  upstream/    # 上游来源登记与未来合并模板

dist/
  surge/
    rules/     # Surge RULE-SET 使用的显式规则产物
  mihomo/
    classical/ # Mihomo 的 behavior: classical 使用的显式规则产物

tools/
  build_rules.ps1
  build_rules.py
```

说明：

- `rules/` 下参与构建的源规则文件统一使用 `.list` 命名
- `rules/app/` 用于维护单一应用的主清单；例如 `rules/app/adspower.txt` 会在构建前自动派生到 `rules/reject/`、`rules/direct/` 与 `rules/proxy/`
- 例如 `rules/region/tw/google_tw.list` 会生成 `dist/surge/rules/region/tw/google_tw.list` 与 `dist/mihomo/classical/region/tw/google_tw.yaml`
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

这个脚本会串行执行构建、单元测试、`dist/` 目录结构校验、`dist/build-report.json` warning 校验，并在最后输出 `git status --short`。

CI 或其他非 Windows 环境如果已经确认本机 `python` 可用，也可以直接执行：

```bash
python tools/build_rules.py
```

构建脚本会：

- 先把 `rules/app/adspower.txt` 自动派生到 `rules/reject/adspower_reject.list`、`rules/direct/adspower_direct.list` 与 `rules/proxy/adspower_proxy.list`
- 从 `rules/` 读取源规则
- 自动生成 `dist/surge/rules/` 与 `dist/mihomo/classical/`
- 将纯域名规则规范化成显式规则行，例如 `.example.com` 会输出成 `DOMAIN-SUFFIX,example.com`
- 尝试识别 `domain-only`、`ipcidr-only`、`classical/mixed`
- 强制校验 `rules/{reject,direct,proxy,region}/` 中的自写注释为中文；若出现纯英文注释会直接失败
- 对不能安全转换到目标客户端格式的行输出 warning，而不是静默吞掉
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
- [docs/mihomo-tun-dns-methodology.md](docs/mihomo-tun-dns-methodology.md)
- [docs/geoip-upstream.md](docs/geoip-upstream.md)
- [docs/surge-work-cluster-whitelist.md](docs/surge-work-cluster-whitelist.md)
- [docs/private-subscription-direct-sync.md](docs/private-subscription-direct-sync.md)
- [docs/aws-region-rules.md](docs/aws-region-rules.md)
- [docs/alicloud-direct-rules.md](docs/alicloud-direct-rules.md)
- [docs/github-ssh-direct-rules.md](docs/github-ssh-direct-rules.md)
- [docs/onepassword-proxy-rules.md](docs/onepassword-proxy-rules.md)

补充约定：

- 浏览器明文 HTTP 拦截统一维护在 `rules/reject/plain_http_reject.list`
- 客户端请直接引用 `dist/surge/rules/reject/plain_http_reject.list` 或 `dist/mihomo/classical/reject/plain_http_reject.yaml`
- 不要在本地配置里重复手写同一组 `PROCESS-NAME + PORT 80` 拦截规则
- AdsPower 专项规则统一维护在 `rules/app/adspower.txt`
- 客户端应显式接入 `reject/adspower_reject`、`direct/adspower_direct` 与 `proxy/adspower_proxy`，不要再退回单条 `DOMAIN-KEYWORD,adspower` 兜底
- Polygon 主网 RPC 专项规则统一维护在 `rules/proxy/polygon_rpc_proxy.list`
- BSC 主网 RPC 专项规则统一维护在 `rules/proxy/bsc_rpc_proxy.list`
- 两者上游快照由 `tools/sync_upstream_rules.py` 每日从 Chainlist 的 `rpcs.json` 抓取并累计更新，避免日常波动导致既有覆盖面回撤
- 客户端应显式接入 `proxy/polygon_rpc_proxy` 与 `proxy/bsc_rpc_proxy`，并放在 `proxy/gfw` 前，让 `🚀 节点选择` 先命中这些 RPC 域名
- Google Public DNS 主 IPv4 端点专项规则统一维护在 `rules/proxy/google_public_dns_ipv4_proxy.list`
- 客户端应显式接入 `proxy/google_public_dns_ipv4_proxy`，并放在 `proxy/gfw` 前，让 `🚀 节点选择` 先命中 `8.8.8.8/32`
- AWS 香港区域规则入口已统一命名为 `region/hk/hk_aws_ipv4`，与东京、大阪、首尔、台北保持同类命名
- 阿里云香港 SSH 直连入口已统一命名为 `direct/alicloud_hk_ipv4_ssh22_direct`；`rules/upstream/alicloud/hk_ipv4.txt` 继续保留纯 IPv4 快照，而公开入口文件直接保留 `SSH TCP/22` 最终语义，不要求客户端额外拼接端口条件
- Surge 与 Mihomo 当前统一把 GeoIP mmdb 显式固定到你自己的仓库 Release 镜像：`vtgpcmsvgs/rulemesh/releases/download/geoip-country-mmdb/country.mmdb`
- 对应上游登记与维护约定见 `rules/upstream/geodata/metacubex_country_mmdb.yaml` 与 [docs/geoip-upstream.md](docs/geoip-upstream.md)
- `rules/region/hk/global_media.list` 额外承接 `x.com`、`t.co`、`twimg.com` 与 `twitter.com` 等 X / Twitter 网页域名，默认绑定 `🇭🇰 香港-自动选择`，减少回落到通用 `proxy/gfw` 的页面超时
- 1Password 核心连接专项规则统一维护在 `rules/proxy/onepassword_proxy.list`
- 上游快照由 `tools/sync_upstream_rules.py` 每日抓取 1Password 官方《ports and domains》支持页，保守收敛到核心一方域名与更新/基础设施端点
- 如需启用，请显式接入 `proxy/onepassword_proxy` 并放在 `proxy/gfw` 前；公开模板默认不内置这条重度用户特化入口
- 操作系统时间同步专项规则统一维护在 `rules/direct/os_time_direct.list`
- 客户端应显式接入 `direct/os_time_direct`，并放在其他普通 `direct/*` 前，默认保持 `DIRECT`
- 如果你采用“默认禁更，升级时手动临时放行”的习惯，建议同时接入 `direct/os_time_direct`、`reject/os_update_reject`、`direct/microsoft_direct` 与 `direct/macos_update_direct`；其中 `os_time_direct` 负责系统时间同步直连，其余入口用于升级窗口

其中 Surge 当前建议明确区分两种使用版本：

- 软路由集群版
  - 只在本地私有环境维护，用于工作电脑集群接入软路由 Surge。
  - 允许包含按局域网源 IP 的设备分流、私有 `policy-path`、`[MITM]` 与证书参数。
  - 其中私有 `rulemesh-substore-surge-work-whitelist.conf` 当前采用工作电脑白名单模式：只保留明确列出的放行入口，未列入白名单的流量统一 `REJECT`。
- 其中只有设备分流继续按局域网源 IP 约束，并按指定 AWS 区域 / 日本 SOCKS5 IP 段定向到对应工作机亚洲出口组；区域精确、GitHub SSH、GitHub Raw 下载入口、GitHub 观察兜底、私有订阅更新直连、1Password 核心连接、AdsPower、Polygon 主网 RPC、BSC 主网 RPC、Google Public DNS 主 IPv4 端点、Cloudflare DNS 与指定直连不再额外限制源 IP。
- 在该白名单里，`direct/os_time_direct`、`direct/microsoft_direct` 与 `direct/macos_update_direct` 都属于允许保留的系统类直连入口。
- 白名单专属的单个直连域名例外（例如 `smtp.163.com`）默认直接维护在“指定直连”入口，不为单条规则额外拆分公开 `rules/` 文件。
- 白名单专属的单个拒绝域名，或只用于阻断浏览器扩展更新链路的拒绝规则，也默认直接维护在白名单的“拒绝规则”入口，不为单条规则额外拆分公开 `rules/` 文件。
- 其中 `proxy/onepassword_proxy`、`proxy/polygon_rpc_proxy`、`proxy/bsc_rpc_proxy`、`proxy/google_public_dns_ipv4_proxy` 与 `DOMAIN-SUFFIX,cloudflare-dns.com` 都是允许保留的节点选择入口，用于白名单模式下显式放行指定代理端点。
  - 其中 GitHub SSH 后直接进入 GitHub Raw 下载入口，并保留一条 `DOMAIN-KEYWORD,github,REJECT` 广覆盖观察兜底，用于发现 SSH / Raw 之外的漏网之鱼；AdsPower 细分规则后也保留一条 `DOMAIN-KEYWORD,adspower,REJECT` 广覆盖观察兜底。
  - 阿里云香港 SSH、`aliyuncs.com` 与 `check.myclientip.com` 统一收敛到“指定直连”段显式放行；其后额外保留一条阿里云广覆盖 `REJECT` 观察兜底，用于发现上游阿里云规则的漏网之鱼。
  - 私有订阅更新直连统一在 `%USERPROFILE%\Desktop\rulemesh-local\current\private_subscription_direct.list` 维护，并通过脚本同步到本地三份私有配置，不回写公开模板。
  - 其中 `raw.githubusercontent.com` 额外绑定 `server:system`，同时 `dns-server` 保留 `system + 公共 DNS`，用于降低 GitHub Raw 外部资源偶发超时。
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
- 默认同时接入 `direct/os_time_direct`，并配套接入 `reject/os_update_reject`、`direct/microsoft_direct` 与 `direct/macos_update_direct`；前者负责系统时间同步，后两者便于临时放开 Windows / macOS 系统升级直连
- 默认接入 AdsPower 专项 `reject/direct/proxy` 规则集，并保持在 `proxy/gfw` 前完成细分控制
- 默认接入 Polygon 主网 RPC 专项 `proxy/polygon_rpc_proxy` 规则，并保持在 `proxy/gfw` 前优先命中
- 默认接入 BSC 主网 RPC 专项 `proxy/bsc_rpc_proxy` 规则，并保持在 `proxy/gfw` 前优先命中
- 默认接入 Google Public DNS 主 IPv4 端点专项 `proxy/google_public_dns_ipv4_proxy` 规则，并保持在 `proxy/gfw` 前优先命中
- 默认保留 `dns-server = system + 公共 DNS` 与 `raw.githubusercontent.com = server:system` 这组 GitHub Raw 解析兜底
- 默认接入 `direct/alicloud_hk_ipv4_ssh22_direct`，并在直连段显式保留 `DOMAIN-SUFFIX,aliyuncs.com` 与 `DOMAIN,check.myclientip.com`
- 默认让 X / Twitter 网页、短链与静态资源优先命中 `region/hk/global_media`，避免落回通用 `proxy/gfw`
  - 刻意不承载私有工作路由白名单结构，避免把本地工作特化误当成公开模板默认值
- `docs/examples/mihomo-public.yaml`
  - 保留完整 `tun + sniffer + dns + proxy-providers + proxy-groups + rule-providers + rules` 结构
  - 已移除真实机场订阅链接、供应商命名与控制面参数
- 默认同时接入 `direct/os_time_direct`，并配套接入 `reject/os_update_reject`、`direct/microsoft_direct` 与 `direct/macos_update_direct`；前者负责系统时间同步，后两者便于临时放开 Windows / macOS 系统升级直连
- 默认接入 AdsPower 专项 `reject/direct/proxy` 规则集，并保持在 `proxy/gfw` 前完成细分控制
- 默认接入 Polygon 主网 RPC 专项 `proxy/polygon_rpc_proxy` 规则，并保持在 `proxy/gfw` 前优先命中
- 默认接入 BSC 主网 RPC 专项 `proxy/bsc_rpc_proxy` 规则，并保持在 `proxy/gfw` 前优先命中
- 默认接入 Google Public DNS 主 IPv4 端点专项 `proxy/google_public_dns_ipv4_proxy` 规则，并保持在 `proxy/gfw` 前优先命中
- 默认接入 `direct_alicloud_hk_ipv4_ssh22`，并在直连段显式保留 `DOMAIN-SUFFIX,aliyuncs.com` 与 `DOMAIN,check.myclientip.com`
- 默认让 X / Twitter 网页、短链与静态资源优先命中 `region/hk/global_media`，避免落回通用 `proxy/gfw`
  - 默认采用 Tun 全量接管、域名嗅探与分流 DNS；国际域名默认优先国外加密 DNS，明确的国内直连域名集单独走国内加密 DNS
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
- Google Public DNS 主 IPv4 端点专项规则应先命中 `proxy/google_public_dns_ipv4_proxy`，再落到 `proxy/gfw`
- X / Twitter 网页、短链与静态资源应先命中 `region/hk/global_media`，再落到 `proxy/gfw`
- 1Password 核心连接专项规则如启用，应先命中 `proxy/onepassword_proxy`，再落到 `proxy/gfw`
- 操作系统时间同步专项规则应先命中 `direct/os_time_direct`，再落到其他普通 `direct/*`
- 同一套路由骨架不等于同一个客户端运行时；`Surge`、`Clash Verge Rev`、`Clash Meta for Android` 在 DNS 启动链上允许存在实现差异
- 本地同时维护 Clash Verge Rev 与 Clash Meta for Android 时，允许拆成两份 Mihomo 私有配置；规则骨架尽量共享，节点域名解析策略允许分别维护
- Surge 私有工作路由白名单与本地其他私有配置永久允许结构不一致，维护时不要互相回抄

## Google 路由强约束

- Google 相关（含 Google Play / Gemini / YouTube / FCM）只在 `rules/region/tw/google_tw.list` 维护
- 客户端应接入 `dist/surge/rules/region/tw/google_tw.list` 或 `dist/mihomo/classical/region/tw/google_tw.yaml`
- Google 规则必须绑定 `TW-AUTO`（或等价台湾策略组），不再提供 `proxy/google` 双入口
- 规则顺序必须先放 Google TW 规则，再放 `region/hk/global_media` 等广谱区域规则，确保优先命中台湾策略
- 新增或调整 Google 规则时，先改该源文件，再执行构建同步 `dist/`

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
- 私有订阅更新直连当前也统一保留在 `%USERPROFILE%\Desktop\rulemesh-local\current` 中：使用 `private_subscription_direct.list` 作为单一源文件，再通过 `sync_private_subscription_direct.ps1` 同步到四份本地私有配置
- 如果本地同时维护 Clash Verge Rev 与 Clash Meta for Android，建议分别维护 `rulemesh-substore-mihomo-clash-verge.yaml` 与 `rulemesh-substore-mihomo-clash-meta.yaml`
- 对 Clash Meta for Android 的兼容性调整，默认优先收敛到节点域名解析这一层；只有在移动网络下直连国外 DoH 不稳定时，才在 Android 专用文件里把 `proxy-server-nameserver` 定向到国内可直连加密 DNS
- 这组私有订阅直连规则只记录在本地目录与私有文档约定中，不回写公开 `rules/`、`dist/` 或公开模板
- 详细维护方式见 [docs/private-subscription-direct-sync.md](docs/private-subscription-direct-sync.md)
- 若私有配置结构发生变化，必须同步更新 `.rulemesh.local.example.json` 与相关文档，但只能提交脱敏占位值

## 维护建议

- 优先改 `rules/`，不要直接手改 `dist/`
- 新增规则前，先想清楚它是 `reject`、`direct`、`proxy` 还是 `region`
- 遇到单一应用同时涉及多种动作时，优先维护 `rules/app/*.txt` 主清单，再由构建前同步派生到现有分类
- 新增、删除或重命名 `rules/{reject,direct,proxy,region}/` 下的 `.list` 源规则文件时，同步更新 `rules/upstream/sources.yaml` 与 `rules/upstream/merge.yaml`
- 新增或调整默认对外使用的规则入口、顺序、策略含义时，同步更新 `README.md`、`docs/usage-surge.md`、`docs/usage-mihomo.md` 与两份公开模板
- 新增或调整 Mihomo 默认的 Tun、嗅探、DNS 分流、安全边界或性能取舍时，同步更新 `docs/mihomo-tun-dns-methodology.md`
- 如果一个源文件开始变得很大，优先补 `sources.yaml` 与 `merge.yaml`，再考虑引入更多上游素材
- 提交前优先运行 `powershell -ExecutionPolicy Bypass -File tools/check.ps1`
- 提交前看一眼 `dist/build-report.json` 的 warnings，特别是 Mihomo 不支持的规则类型
- 自写注释、生成说明、文档说明默认统一写中文，不要再放英文占位注释

## 规则方法论：上游优先 + 本地兜底

本仓库统一采用“上游优先精准匹配 + 本地规则兜底覆盖”的编排方式：

- 先写 `INCLUDE,upstream/...`，优先命中第三方持续维护的精细规则。
- 再写本地兜底规则，优先使用 `DOMAIN-KEYWORD` 与 `DOMAIN-SUFFIX` 提升覆盖韧性。
- 兜底规则只补“高频且长期稳定”的关键词/后缀，避免把本地规则膨胀成上游镜像。
- 当某类规则暂无可靠上游时，可先保留手写规则；一旦有稳定上游，再迁移到“上游优先”结构。
- 目标是同时兼顾：上游的精准全面 + 本地兜底的抗失效能力。
