# Mihomo 使用说明

适用于：

- Clash Verge Rev
- Clash Meta for Android
- 其他兼容 Mihomo `rule-providers` 的客户端

## 推荐入口

- 完整公开参考模板：[`docs/examples/mihomo-public.yaml`](examples/mihomo-public.yaml)
- 规则产物入口：`dist/mihomo/classical/`
- 国内业务 DNS 清单有两层：公开模板继续使用小型精选 `dist/surge/dns/cn_dns_domains.list`；两份私有 Mihomo 性能配置使用 `dist/surge/dns/cn_performance_dns_domains.list`
- 代理组过滤方法论：[`docs/proxy-group-filter-methodology.md`](proxy-group-filter-methodology.md)
- Tun / DNS / 嗅探维护方法论：[`docs/mihomo-tun-dns-methodology.md`](mihomo-tun-dns-methodology.md)
- DNS 防泄漏方法论：[`docs/network-security/dns-leak-prevention.md`](network-security/dns-leak-prevention.md)

这个模板是基于本地长期使用的 Mihomo 配置整理出来的公开版，保留了多订阅聚合、区域自动切换、`rule-providers` 与完整规则顺序，但移除了真实机场地址和其他不适合公开仓库的私有信息。
重要边界：
对解析后的私人当前配置目录中的 `rulemesh-substore-mihomo-clash-verge.yaml` 与 `rulemesh-substore-mihomo-clash-meta.yaml` 两份私有 provider 配置，如果与本文或公开示例冲突，以 [docs/mihomo-tun-dns-methodology.md](mihomo-tun-dns-methodology.md) 里的“单一 DNS 真相”约束为准，不要把本文历史上的复杂 DNS 结构回灌到私有文件。


## 模板保留了什么

- `tun + sniffer + dns + proxy-providers + proxy-groups + rule-providers + rules` 的完整结构
- `geodata-mode: false` + `geox-url.mmdb` 显式固定到与 Surge 共用的本仓库 Release 镜像地址
- 多订阅聚合后的统一总开关与区域自动组
- `proxy-providers.*.proxy: DIRECT` 的订阅更新基线：它只控制 Mihomo 后台拉取机场订阅 URL，普通流量访问这些端点仍由后面的精确 `DOMAIN` / `IP-CIDR` 规则判断
- `reject`、`direct`、`proxy`、`region` 四类 RuleMesh `classical` 产物接入
- GitHub 继续采用“SSH 定向直连 + Core HTTPS 显式代理”拆分：`direct/github_ssh_direct.yaml` 只承接 `github.com:22` 与 `ssh.github.com:443`，`proxy/github_core_proxy.yaml` 则显式承接 GitHub 网页、`api.github.com`、Gist、Raw、静态资源与附件
- 公开参考模板保留 Mihomo 的 Tun、嗅探与 DNS 隔离思路，但两份私有 provider 配置不要直接照搬这里的历史复杂 DNS 分层。
- 两份 Mihomo 私有 provider 配置当前默认保持“单一 DNS 真相”版本：`ipv6: false`、`dns.ipv6: false`、`default-nameserver + nameserver + fake-ip-filter`。
- `proxy-providers.*.override.ip-version: dual` 只表示节点栈能力，不等于两份私有文件必须重新打开全局 IPv6 或恢复复杂 DNS 叠层。
- 默认启用 Tun 全量接管与域名嗅探，优先把 Mihomo 的实际体验拉到接近 Surge 的水位。
- `region/hk/hk_brokers.yaml` 专门承接复星证券/复星财富、致富证券、辉立证券与富途，默认用激进品牌关键词兜底并绑定 `🇭🇰 香港-自动选择`
- 激进 Personal 入口还包括 `region/hk/personal_priority_hk.yaml`、`region/hk/notion_hk.yaml` 与 `region/hk/hk_securities_aggressive.yaml`，分别覆盖指定高优先级域名、Notion 官方域名族，以及老虎证券公开入口、营销合规判区、静态资源等官方基础设施和港交所参与者网站快照；调用顺序必须先于广告拒绝、国内直连与广谱代理
- `direct/apple_direct.yaml` 与 `direct/outlook_direct.yaml` 分别用于 Apple 官方域名族和 Outlook 邮件数据面直连；`region/us/microsoft_store_us.yaml` 用于 Microsoft Store、许可、目录与下载交付端点美国分流。公开示例还显式让 `yikaiying.com` 直连
- `region/hk/alibaba_hk.yaml` 是可选的阿里系香港入口，默认公开模板不启用；专用设备配置可注册 provider 并在国内直连与阿里云 SSH 指定直连前绑定 `🇭🇰 香港-自动选择`
- `region/hk/wps_kdocs.yaml` 专门承接 WPS Office、金山文档、开放平台、云文档与资源分发连接，并绑定 `🇭🇰 香港-自动选择`
- `region/hk/global_media.yaml` 额外承接 X / Twitter 网页、短链与静态资源，以及 Polymarket 显式域名与激进关键词兜底，并默认绑定 `🇭🇰 香港-自动选择`
- `region/hk/google_hk.yaml` 统一承接 Google 全业务、Google AI 与官方完整公网地址空间，绑定 `🇭🇰 香港-自动选择` 并位于全部拒绝规则之前
- `region/us/ai_us.yaml` 统一承接 OpenAI / Claude / Copilot / Cursor / Grok / Windsurf / Augment 等非 Google 海外 AI 平台，并保留更激进的关键词兜底；客户端默认绑定 `🇺🇸 美国-自动选择`
- `direct/ai_cn_direct.yaml` 显式承接 Kimi / DeepSeek / 豆包 / 即梦 / Trae 中国大陆 / 元宝 / 混元 / 通义 / 千问 / 智谱 / MiniMax / 文心等国内 AI 入口；调用顺序固定为 `direct_ai_cn < direct_bytedance < hk_global_media < direct_cn`。两份 Mihomo 私有配置的普通目标网站继续默认使用海外 `nameserver`，实际启用且位于中国大陆通用兜底前的 `reject/`、`proxy/`、`region/` 集合必须先使用海外 DNS，随后仅 `rule-set:cn-performance-dns-domains` 可按已批准例外使用国内 DNS。
- 阿里云香港 SSH 继续走 `direct/alicloud_hk_ipv4_ssh22_direct.yaml`，调用层保留 `DIRECT,no-resolve`，该 provider 更新间隔使用 3600 秒；远程 provider 前必须先放仅限 TCP/22 的阿里注册大块与 `AS45102/AS134963/AS24429` 内联兜底
- AWS 香港区域入口已统一为 `region/hk/hk_aws_ipv4.yaml`
- 多地区链式 SOCKS5 端点产物仍发布为 `region/multi/chain_socks5_ipcidr.yaml`，但默认 Mihomo 模板不注册或调用它；普通 `RULE-SET` 分流不等价于代理节点拨号层的链式连接，只有配置并复测 `dialer-proxy` 后才能接入
- 阿里云香港 SSH 直连入口已统一为 `direct/alicloud_hk_ipv4_ssh22_direct.yaml`，入口内直接保留单调历史 `IP-CIDR` 与运行时 `IP-ASN` 的 `no-resolve + NETWORK,tcp + DST-PORT,22` 语义；阿里云控制面 `aliyuncs.com` 与出口探测 `check.myclientip.com` 仍通过单条 `DIRECT` 规则显式放行
- AdsPower 专项 `reject/direct/proxy` 规则集与 `proxy/gfw.yaml` 广谱代理规则的顺序关系
- Polygon 主网 RPC 专项 `proxy/polygon_rpc_proxy.yaml` 与 `proxy/gfw.yaml` 的顺序关系
- BSC 主网 RPC 专项 `proxy/bsc_rpc_proxy.yaml` 与 `proxy/gfw.yaml` 的顺序关系
- 海外 DNS 主 IPv4 端点专项 `proxy/overseas_dns_ipv4_proxy.yaml` 与 `proxy/gfw.yaml` 的顺序关系
- `direct/os_time_direct.yaml` 与其他普通直连规则的顺序关系
## 模板刻意移除了什么

- 真实机场订阅链接、供应商命名与 token
- `external-controller`、`secret` 等控制面参数
- 按局域网源 IP 的设备分流逻辑
- 私有 Surge 工作路由白名单特化；那份差异只属于本地 `rulemesh-substore-surge-work-whitelist.conf`
- 私有订阅域名同步块；这部分只在本地私有目录维护，并通过同步脚本写入两份 Mihomo 私有配置
- 1Password 重度用户专项入口；如需启用，请另行接入 `proxy/onepassword_proxy.yaml`

## 使用前只需要替换两处

1. 把模板里 `provider_a`、`provider_b`、`provider_c` 的 `url` 改成你自己的订阅地址。
2. 公开模板默认让最终兜底走总开关；两份私有性能优先配置则把 `MATCH` 指向现有全地区自动选择组，OpenAI / ChatGPT 仍由前置 `region/us/ai_us` 固定美国。

另请注意：

- Surge 公开模板里的 `use-local-host-item-for-proxy = false`、`hijack-dns = *:53` 与 `allow-wifi-access = false` 只属于 Surge 运行时参数，不要求 Mihomo 模板逐项镜像；Surge 不写 Mihomo / Stash 的 `dns-mode`，Mihomo 继续按 Tun / DNS 方法论独立维护。
- Clash Verge Rev 等支持 Tun 的客户端，建议同时开启 Tun 模式；这份模板默认按 Tun + 嗅探 + 分流 DNS 设计，关闭 Tun 会明显削弱体验。
- 如果你同时维护 Clash Verge Rev 与 Clash Meta for Android，本地私有目录建议拆成 `rulemesh-substore-mihomo-clash-verge.yaml` 与 `rulemesh-substore-mihomo-clash-meta.yaml` 两份；规则骨架可以保持一致，但节点域名解析策略应允许分别维护。
- 如果你把 `rulemesh-substore-mihomo-clash-verge.yaml` 当成 Clash Verge Rev 的日常主配置，建议在“订阅”页对这份本地配置右键“编辑信息”，把 `更新时间隔` 设为 `720` 分钟。
- 这项 `720` 分钟设置不会写回 YAML，而是保存在每台设备自己的 Clash Verge Rev profile 元数据里；因此同一份文件换到另一台设备后，也要重新手动设置一次。
- 这项 `720` 分钟设置不替代下方 `proxy-providers` / `rule-providers` 的 `interval`；YAML 里的 `interval` 仍是 Mihomo 内核层的下载间隔，Clash Verge Rev 的 `720` 只是额外的外层定时重载。
- `proxy-providers` 和 `rule-providers` 都有自己的 `proxy` 字段，但含义只限于“下载 / 更新这个 provider 时走哪个出站”。机场订阅属于 `proxy-providers`，默认写 `proxy: DIRECT`；GitHub 规则集属于 `rule-providers`，可以按需要继续写 `proxy: "🚀 节点选择"`。
- 对长期后台运行、电脑睡眠唤醒、偶发网络抖动这些场景，`720` 分钟外层定时重载可作为 provider 自动更新的保底保险；当前本地经验默认建议保留。
- 如果你把 `rulemesh-substore-mihomo-clash-verge.yaml` 当成 Clash Verge Rev 的单一真相，默认应关闭 Clash Verge Rev 的 `DNS 覆写`；否则运行时 `dns` 会被 AppData 下的 `dns_config.yaml` 覆盖。
- 如果你明确保留 Clash Verge Rev 的 `DNS 覆写`，就应把 `dns_config.yaml` 当成实际生效的 `dns` 配置入口，不要再假设源文件里的 `dns:` 会原样生效。
- 如果关闭 Clash Verge Rev 的 `DNS 覆写` 后出现“国内可访问、国外代理不通”，默认先确认桌面端私有文件是否被改离了“单一 DNS 真相”版本，而不是先回滚规则顺序。
- 对当前本地私有维护来说，Clash Verge Rev 在关闭 `DNS 覆写` 后，必须保持 `respect-rules: false`；普通目标网站默认走 `nameserver`，只增加“已启用高优先级规则集的海外 DNS 例外 + `rule-set:cn-performance-dns-domains` 国内 DNS”这一受限 `nameserver-policy` 结构。
- 如果出现“Clash Verge Rev 正常、Clash Meta for Android 不通”，默认先确认 Android 私有文件是否也被改离了这套简单基线，而不是先怀疑规则顺序。
- 对 Clash Meta for Android 的兼容性调整，默认也先保持“单一 DNS 真相”版本；只有用户明确确认且 Android 运行时复测证明必须特化时，才允许单独加例外。
- 这份模板不会把所有 `DIRECT` 交给国内 DNS；普通目标网站域名统一由海外 `nameserver` 解析，国内 DNS 只承担 `default-nameserver` bootstrap 与小型 `cn-dns-domains` 明确白名单。性能型产物是私有性能配置的明确选择，不是公开模板默认安全配置。

## 代理组过滤约定

- 本地私有 Mihomo 配置里，所有基于 provider 的代理组默认共用同一套排除条件：`剩余流量`、`套餐到期`、`距离下次重置`、`过滤掉`、`Expire Date`、`Traffic Reset` 这类状态/提示项按前缀匹配，`直接连接` 这类独立占位项按整行精确匹配，`联系我们` 与 `1.2 GB | 50 GB` 这类提示继续专项匹配，让手动切换、自动组和地区组尽量只展示真实节点。
- 这套过滤条件需要在所有相关代理组里保持完全一致；Mihomo 侧所有相关 `exclude-filter` 都必须与 Surge 语义对齐。
- 如果某个 provider 会给真实节点额外注入统一前缀，默认先检查是否存在“供应商名宽匹配误伤真实节点”的风险；详见 [docs/proxy-group-filter-methodology.md](proxy-group-filter-methodology.md)。

## Tun / DNS / 嗅探方法论

- Mihomo 的体验优化优先级，不是继续堆规则，而是先把 `tun`、`sniffer`、`dns` 这层运行时补齐。
- DNS 分流不按 `DIRECT` / `PROXY` 两分；普通目标网站域名默认走海外 `nameserver`。小型 `cn-dns-domains` 承接小米 / MIUI、和风天气、微信小程序、抖音专项、拼多多、小红书 CDN、知识星球与 `yikaiying.com` 等明确国内依赖，供公开模板使用；两份私有 Mihomo 性能配置改用自动合并中国直连域名主体的 `cn-performance-dns-domains`，但只能排在实际启用的高优先级海外 DNS 例外之后，绝不得泛化为所有直连域名。
- `localhost.weixin.qq.com` 的回环保护是 Surge `always-real-ip` 运行时语义；Mihomo 不新增同名仿制字段，也不为它改变 DNS 结构。
- 新增直连规则时，要先判断它是否仍属于普通目标网站域名；只有明确国内业务域名 / 国内域名后缀，才允许评估是否加入 `rules/dns/cn_dns_domains.list`。
- 对两份 Mihomo 私有 provider 配置来说，`default-nameserver` 只负责 `nameserver` 自身的 bootstrap；不要引入 `proxy-server-nameserver`、`fallback` 或已批准的高优先级海外例外与性能型国内清单之外的 DNS 字段。
- 如果未来确有 Clash Meta for Android 的定向兼容需求，也必须先保住“单一 DNS 真相”基线；只有用户明确确认且 Android 运行时复测证明必须例外时，才允许单独讨论特化。
- 当前 `dist/mihomo/classical/` 默认只发布 Mihomo 已确认支持的规则类型；像 `URL-REGEX` 这类 Surge 仍可使用、但 Mihomo classical 当前不支持的规则，会保留在源规则层和 Surge 产物中，但不会写入 Mihomo 产物。
- 这不是放弃该类规则；如果后续 Mihomo 官方版本已支持并经仓库验证通过，Mihomo 产物会同步恢复输出，不需要反向删改源规则。
- 详细维护边界、风险提示与检查清单见 [docs/mihomo-tun-dns-methodology.md](mihomo-tun-dns-methodology.md)。

## 私有订阅域名同步约定

- 真实订阅更新域名 / IP 只在解析后的私人当前配置目录中的 `private_subscription_direct.list` 维护，不写回公开模板
- 修改后运行同一目录中的 `sync_private_subscription_direct.ps1 -Target mihomo`，只同步两份 Mihomo 私有配置；只有用户明确要求两类客户端同时更新时才使用 `-Target all`。目录解析与可直接执行的 PowerShell 命令见 [docs/private-subscription-direct-sync.md](private-subscription-direct-sync.md)
- Mihomo 分支会把每个精确端点生成成普通 `DOMAIN` / `IP-CIDR` 节点选择规则，不附加 `PROCESS-NAME`，也不在这段规则里生成 `DIRECT`
- Mihomo 后台自动刷新机场订阅时，由对应 `proxy-providers.*.proxy: DIRECT` 显式控制；它与上一条“端点普通流量走节点选择”是两条独立路径
- 不要把 `proxy-providers.*.proxy` 与 `rule-providers.*.proxy` 混为一谈：前者是机场订阅节点清单更新，后者是 GitHub 规则集更新
- 这份共享源文件应只保留 Surge / Mihomo 都能直接复用的规则语法；当前只允许 `DOMAIN`、`DOMAIN-SUFFIX`、`IP-CIDR`、`IP-CIDR6`，并优先使用精确 `DOMAIN` / 主机网段
- 在两份 Mihomo 私有配置中，这组同步块都应继续放在 `proxy_gfw` 前
- 详细维护方式见 [docs/private-subscription-direct-sync.md](private-subscription-direct-sync.md)

## 规则顺序建议

1. Google 全业务香港规则
2. 拒绝规则
3. 其他区域精确规则；在 `hk_global_media` 前依次插入 `direct_ai_cn`、`direct_bytedance`
4. GitHub 仓库 SSH 定向直连
5. GitHub Core 节点选择规则
6. AdsPower 细分直连规则
7. AdsPower 细分节点选择规则
8. Polygon 主网 RPC 节点选择规则
9. BSC 主网 RPC 节点选择规则
10. 海外 DNS 主 IPv4 端点美国分流规则
11. 可选：1Password 核心连接节点选择规则
12. 其余直连规则
13. 代理优先规则
14. IP 规则
15. `MATCH`

注意：

- `region/hk/google_hk.yaml` 对应规则必须放在全部拒绝、`region/us/ai_us.yaml`、`direct_cn`、海外 DNS IP 美国分流与所有广谱规则前，并绑定 `🇭🇰 香港-自动选择`。
- Google Play、YouTube、Workspace、FCM、Gemini、DeepMind、Google 广告/统计域名与官方 `goog.json` 全部 IPv4 / IPv6 地址空间均由 `google_hk` 承接；完整地址空间故意包含 Google Cloud 客户地址。
- `region/us/ai_us.yaml` 只聚合非 Google 海外 AI 平台，不得重新加入 Gemini / AI Studio / NotebookLM / DeepMind；它继续绑定 `🇺🇸 美国-自动选择`。
- `DeepSeek`、`Trae` 中国大陆入口与其他国内 AI 不应并入 `region/us/ai_us.yaml`；它们应优先由 `direct_ai_cn` 承接，字节共享基础设施与中国大陆通用兜底再继续落到 `direct_bytedance`、`direct_cn`。
- `direct_ai_cn` 属于显式国内 AI 直连入口，顺序固定为 `direct_ai_cn < direct_bytedance < hk_global_media < direct_cn`；静态交集审计确认只纠正 `snssdk.com`，路由动作不直接推导 DNS 出口，两份 Mihomo 私有配置继续遵守“普通目标默认走海外 `nameserver`、高优先级已启用规则集先走海外 DNS、性能型国内清单后置”的分层基线。
- `region/hk/wps_kdocs.yaml` 必须放在 `direct_cn` 与 `MATCH` 前并绑定 `🇭🇰 香港-自动选择`；它不加入 `cn-dns-domains`，因此继续使用海外 `nameserver`，也不需要 `proxy-server-nameserver`。
- `region/hk/alibaba_hk.yaml` 启用后必须先于 `direct_ai_cn`、`direct_cn` 与阿里云 SSH 指定直连入口；Alibaba 主体覆盖域名和 IP 规则，XianYu 专项清单及 `goofish / xianyu / idlefish` 关键词补强闲鱼。设备专用配置可直接调用，通用共享配置则应额外评估源地址匹配是否能保留真实客户端地址。
- `region/hk/hk_brokers.yaml` 当前只承接复星证券/复星财富、致富证券、辉立证券与富途，应放在 `region/hk/global_media.yaml` 与 `proxy/gfw.yaml` 前，并绑定 `🇭🇰 香港-自动选择`。
- `region/hk/global_media.yaml` 当前还承接 `x.com`、`t.co`、`twimg.com` 与 `twitter.com` 等 X / Twitter 网页域名，以及 `polymarket.com` 与 `DOMAIN-KEYWORD,polymarket` 这组 Polymarket 香港兜底；默认应继续绑定 `🇭🇰 香港-自动选择`，不要再让它们回落到 `proxy/gfw.yaml` 或误挂到日本区域。
- 公开 `mihomo-public.yaml` 默认接入 `jp_domains` 规则提供器；当前用于让 `opinion.trade` 走 `🇯🇵 日本-自动选择`。
- `direct/github_ssh_direct.yaml` 必须放在 `proxy/github_core_proxy.yaml` 与 `proxy/gfw.yaml` 前，只给 `github.com:22` 与 `ssh.github.com:443` 直连，避免把 GitHub 网页误放直连。
- `proxy/github_core_proxy.yaml` 应放在 `proxy/gfw.yaml` 前，显式承接 GitHub 网页、`api.github.com`、Gist、Raw、静态资源与附件；这也会覆盖 `https://api.github.com/gists`、`https://api.github.com/users` 与 `https://gist.githubusercontent.com/...` 这类连接。
- `direct/alicloud_hk_ipv4_ssh22_direct.yaml` 应以 `RULE-SET,...,DIRECT,no-resolve` 调用；在它前面先放公开模板所示的 TCP/22 内联兜底，再与 `DOMAIN-SUFFIX,aliyuncs.com,DIRECT`、`DOMAIN,check.myclientip.com,DIRECT` 统一放在直连段；普通模板不恢复旧版阿里云广覆盖观察兜底。
- `direct/adspower_direct.yaml` 与 `proxy/adspower_proxy.yaml` 都应放在 `proxy/gfw.yaml` 前，确保 AdsPower 的细分直连与节点选择优先命中。
- `proxy/polygon_rpc_proxy.yaml` 应放在 `proxy/gfw.yaml` 前，确保 Polygon 主网 RPC 域名优先走 `🚀 节点选择`。
- `proxy/bsc_rpc_proxy.yaml` 应放在 `proxy/gfw.yaml` 前，确保 BSC 主网 RPC 域名优先走 `🚀 节点选择`。
- `proxy/overseas_dns_ipv4_proxy.yaml` 应放在 `proxy/gfw.yaml` 前，使 `1.1.1.1/32` 与 `9.9.9.9/32` 走 `🇺🇸 美国-自动选择`；Google `8.8.8.8` 已由更早的 `google_hk` 固定香港。
- 如果你是 1Password 重度用户，可额外接入 `proxy/onepassword_proxy.yaml`，并同样放在 `proxy/gfw.yaml` 前；这条规则由仓库每日自动抓取 1Password 官方支持页生成，默认只覆盖官方自有核心域名与更新/基础设施端点，详情见 [docs/onepassword-proxy-rules.md](onepassword-proxy-rules.md)。
- `reject/adspower_reject.yaml` 应和其他拒绝规则一起放在最前，先拦截隐私追踪与可安全阻断端点。
- `reject/adspower_reject.yaml` 当前只承载 Mihomo classical 已确认支持的 AdsPower 拒绝规则；源规则里为 Surge 保留的 `URL-REGEX` 条目不会进入这份 Mihomo 产物。
- `direct/os_time_direct.yaml` 建议放在其他普通 `direct/*.yaml` 前，优先保障 `time.windows.com`、`time.apple.com` 与 `time-macos.apple.com` 直连。
- 如果你希望默认禁用系统更新、升级时再临时放行，建议同时接入 `direct/os_time_direct.yaml`、`reject/os_update_reject.yaml`、`region/us/microsoft_us.yaml` 与 `region/us/macos_update_us.yaml`；平时由 `reject` 先拦截升级流量，系统时间同步仍由 `os_time_direct` 保持直连，放开拒绝入口后 Microsoft / macOS 更新流量统一走美国节点。
- `proxy/gfw.yaml` 建议放在国内直连规则之后，至少晚于 `LAN`、`direct_os_time`、`direct_ai_cn`、`direct_bytedance`、`direct_netease`、`direct_bilibili` 与 `direct_cn`，避免国内域名被广谱代理规则提前抢走；GitHub、AdsPower、RPC、海外 DNS 端点等精确代理入口仍应放在 `proxy/gfw.yaml` 前。
- Surge 私有工作路由白名单并不迁移到 Mihomo 模板；Mihomo 仍维持这里描述的公开/个人通用结构。

## 使用原则

- 客户端规则只引用 `dist/mihomo/classical/`；公开示例与工作白名单使用小型精选 `dist/surge/dns/cn_dns_domains.list`，Surge Personal 与两份 Mihomo 私有性能配置使用 `dist/surge/dns/cn_performance_dns_domains.list`
- `rules/` 是源规则层，不建议客户端直接引用
- 不要把 `classical` 产物误配成别的 `behavior`
- 不要再找旧的纯域名或纯 CIDR 产物目录；仓库已经统一走 `classical`
- GeoIP 数据库当前显式固定为 `mmdb`，并统一指向本仓库的 Release 镜像地址
- 不要手改 `dist/`，应先改 `rules/` 后重新构建
- 私有 Surge 工作路由白名单约定见 [docs/surge-work-cluster-whitelist.md](surge-work-cluster-whitelist.md)，但该约定不影响 Mihomo 模板与两份 Mihomo 私有配置。
- 私有订阅域名同步约定见 [docs/private-subscription-direct-sync.md](private-subscription-direct-sync.md)；该约定影响两份 Mihomo 私有配置，但不影响公开模板。
- 1Password 重度用户专项规则约定见 [docs/onepassword-proxy-rules.md](onepassword-proxy-rules.md)；公开模板默认不内置，需要时再显式接入。
- GeoIP 上游选择与维护边界见 [docs/geoip-upstream.md](geoip-upstream.md)。
- DNS 防泄漏与解析边界见 [docs/network-security/dns-leak-prevention.md](network-security/dns-leak-prevention.md)；任何 DNS、DoH、fake-ip、Tun 或 `proxy-server-nameserver` 调整后，都要做外部 DNS 泄漏验证。
