# Surge 使用说明

## 推荐入口

- 个人终端版公开参考模板：[`docs/examples/surge-public.conf`](examples/surge-public.conf)
- 规则产物入口：`dist/surge/rules/`
- 国内业务域名 DNS 清单入口：`dist/surge/dns/cn_dns_domains.list`
- 代理组过滤方法论：[`docs/proxy-group-filter-methodology.md`](proxy-group-filter-methodology.md)
- DNS 防泄漏方法论：[`docs/network-security/dns-leak-prevention.md`](network-security/dns-leak-prevention.md)

这个模板是基于本地长期使用的 Surge 配置整理出来的公开版，保留了总开关、区域自动切换、拒绝规则、直连规则与 IP 规则的完整结构，但移除了不适合公开仓库的个人化部分。

> 重要边界：Surge 可以继续保留当前 `[Host] + 海外全局 DNS + 国内 bootstrap 例外` 的复杂 DNS 方案；[docs/mihomo-tun-dns-methodology.md](mihomo-tun-dns-methodology.md) 里针对两份 Mihomo 私有 provider 配置的“单一 DNS 真相”红线，不适用于 Surge，也不要反向把 Surge 这套复杂 DNS 抄回 Mihomo 私有配置。

## 版本划分

- 软路由集群版
  - 用于工作电脑集群接入软路由 Surge。
  - 可保留 `SRC-IP` 设备分流、私有订阅地址与完整 `[MITM]`。
  - 默认不额外开放局域网代理入口；旁路由已接管流量，工作白名单不承担 LAN 代理服务。
  - 这类内容不适合入公开仓库，建议只在本地私有目录维护。
- 其中私有 `rulemesh-substore-surge-work-whitelist.conf` 当前使用工作电脑白名单模式，并与两个 `personal` 配置永久有意不一致。
- 维护这份白名单文件时请同时参考 [docs/surge-work-cluster-whitelist.md](surge-work-cluster-whitelist.md)。
- 若只新增某个白名单专属的单个直连域名，默认直接维护在 2.10“指定直连”入口，不为单条规则额外新增公开 `rules/` 文件。
- 如果本地存在需要每日刷新的私有订阅域名，统一维护在 `%USERPROFILE%\Desktop\rulemesh-local\current\private_subscription_direct.list`，再通过同步脚本分发到私有配置中的“Chrome 访问节点选择例外 + 订阅更新直连”规则块。
- 个人终端版
  - 用于同事个人终端或可公开分享的配置。
  - 对应本仓库的 [`docs/examples/surge-public.conf`](examples/surge-public.conf)。
  - 默认移除 `SRC-IP` 设备分流、私有订阅地址与整个 `[MITM]`。
  - 默认保持 `allow-wifi-access = false`，不把个人终端直接暴露给局域网其他设备。
  - 不继承工作路由白名单的 `REJECT` 兜底结构。

## 模板保留了什么

- 总开关 + 手动切换 + 自动测速切换
- 香港、台湾、日本、新加坡、美国、韩国的区域自动组
- `geoip-maxmind-url` 显式固定到与 Mihomo 共用的本仓库 Release 镜像地址
- `reject`、`direct`、`proxy`、`region` 四类 RuleMesh 产物接入
- `github_ssh_direct` 后先保留 `DOMAIN,raw.githubusercontent.com,"🚀 节点选择"` 自举入口，再显式接入 `proxy/github_core_proxy.list`，承接 GitHub 网页、`api.github.com`、Gist、Raw、静态资源与附件；同时继续保留 `raw.githubusercontent.com = server:https://cloudflare-dns.com/dns-query` 这一条规则产物解析例外，但它不是代理节点 bootstrap，不能替代 `proxy-node-domains` 的 AliDNS 解析
- `region/hk/hk_brokers.list` 专门承接复星证券/复星财富、致富证券、辉立证券与富途，默认用激进品牌关键词兜底并绑定 `🇭🇰 香港-自动选择`
- `region/hk/global_media.list` 额外承接 X / Twitter 网页、短链与静态资源，以及 Polymarket 显式域名与激进关键词兜底，并默认绑定 `🇭🇰 香港-自动选择`
- `region/us/ai_us.list` 统一承接 OpenAI / Claude / Gemini / Copilot / Cursor / Grok / Windsurf / Augment 等海外 AI 平台，并保留更激进的关键词兜底；客户端默认绑定 `🇺🇸 美国-自动选择`
- `direct/ai_cn_direct.list` 显式承接 Kimi / DeepSeek / 豆包 / 即梦 / Trae 中国大陆 / 元宝 / 混元 / 通义 / 千问 / 智谱 / MiniMax / 文心等国内 AI 入口，并应放在 `direct/bytedance_direct.list` 与 `direct/cn_direct.list` 前
- 阿里云香港 SSH 继续走 `direct/alicloud_hk_ipv4_ssh22_direct.list`；阿里云控制面 `aliyuncs.com` 与出口探测 `check.myclientip.com` 通过单条 `DIRECT` 规则显式放行
- AWS 香港区域入口已统一为 `region/hk/hk_aws_ipv4.list`
- 多地区链式 SOCKS5 端点入口已统一为 `region/multi/chain_socks5_ipcidr.list`，默认应绑定统一的自动选择 / 负载均衡组，而不是 `🇯🇵 日本-自动选择`
- 阿里云香港 SSH 直连入口已统一为 `direct/alicloud_hk_ipv4_ssh22_direct.list`，并继续在入口文件里直接保留 `SSH TCP/22` 条件，不要求本地配置二次拼装端口规则
- AdsPower 专项 `reject/direct/proxy` 规则集与 `proxy/gfw.list` 广谱代理规则的顺序关系
- Polygon 主网 RPC 专项 `proxy/polygon_rpc_proxy.list` 与 `proxy/gfw.list` 的顺序关系
- BSC 主网 RPC 专项 `proxy/bsc_rpc_proxy.list` 与 `proxy/gfw.list` 的顺序关系
- 海外 DNS 主 IPv4 端点专项 `proxy/overseas_dns_ipv4_proxy.list` 与 `proxy/gfw.list` 的顺序关系
- `direct/os_time_direct.list` 与其他普通直连规则的顺序关系
- `dist/surge/dns/cn_dns_domains.list` 作为国内业务域名 DNS 白名单，可在 `[Host]` 中映射到 AliDNS / DNSPod；它与 `proxy-node-domains` 分离维护，不能混入代理节点 server 域名
- `allow-wifi-access = false`、`test-timeout = 3`、`use-local-host-item-for-proxy = false`、`hijack-dns = *:53` 与 `encrypted-dns-follow-outbound-mode = true` 这组运行时默认值
- 默认关闭 `ipv6 = false`，并注释 `ipv6-vif = auto`；如需 IPv6，应先完成 DNS 泄漏、WebRTC 与出口一致性测试
- Surge profile 不写 `dns-mode = fake-ip`；Fake IP 由 Surge Enhanced Mode / VIF 运行时提供，Mac 端加载 profile 后需要在 Surge 里启用 Enhanced Mode
- `skip-proxy`、`always-real-ip`、海外全局 DNS 与测速参数
- `skip-proxy` 不再包含 Apple `17.0.0.0/8`，避免 macOS 更新流量绕过前置拒绝规则和后续美国分流规则

## 模板刻意移除了什么

- 按局域网源 IP 的设备分流（`SRC-IP` + `AND/OR`）
- 私有 `policy-path` 地址与真实机场命名
- 整个 `[MITM]` 段及证书参数
- 1Password 重度用户专项入口；如需启用，请另行接入 `proxy/onepassword_proxy.list`

## 使用前只需要替换三处

1. 把模板里所有 `https://example.com/subs/surge/all?target=Surge` 替换成你自己的 Surge 聚合订阅入口。
2. 把 `[Host]` 里的 `https://example.com/share/file/proxy-node-domains` 替换成 Surge 所在设备能直接访问的 Sub-Store 分享文件真实 URL。
3. 如果你不希望最终兜底走总开关，可以把 `FINAL,🚀 节点选择,dns-failed` 改成你想固定兜底的区域组。

`proxy-node-domains` 只能包含订阅节点的 `server` 域名，不得填订阅入口、机场面板域名、IP 或普通目标网站域名。替换前先在同一网络环境里打开 URL，确认返回一行一个域名；如果返回 HTML、404、超时或逗号分隔的一整行，就不要加载到生产 Surge。

## 测速 URL 约定

- Surge 的 `internet-test-url`、`proxy-test-url`、代理 `test-url=`、`smart / fallback / load-balance` 的 `url=` 统一保持 `http://`，不要改成 `https://`；本仓库已经踩过一次真实载入失败。
- 当前公开模板与本地私有 Surge 配置的自动测速组默认优先使用 `smart`，作为 `url-test` 的直接平替。
- 当前公开模板与本地私有 Surge 配置统一采用 `http://www.baidu.com`、`http://www.google.com/generate_204` 与 `http://www.gstatic.com/generate_204` 这组三段式测速基线。
- 这组值不是全网唯一标准答案，但当前更偏“轻量、稳定、便于区分直连检查和代理测速”的默认组合，因此继续保留。
- 只有测速 URL 需要强制保持 `http://`；`policy-path`、`geoip-maxmind-url`、`RULE-SET` 等普通资源 URL 仍然可以继续使用 `https://`。
- 如果后续要替换，请优先继续选择轻量、稳定、支持 HTTP HEAD 的 `http://` 目标。

## 代理组过滤约定

- 本地私有 Surge 配置里，所有基于 `policy-path` 的代理组默认共用同一套排除条件：`剩余流量`、`套餐到期`、`距离下次重置`、`过滤掉`、`Expire Date`、`Traffic Reset` 这类状态/提示项按前缀匹配，`直接连接` 这类独立占位项按整行精确匹配，`联系我们` 与 `1.2 GB | 50 GB` 这类提示继续专项匹配，让手动切换、自动组和地区组尽量只展示真实节点。
- 这套过滤条件需要在所有相关代理组里保持完全一致；当前 Surge 侧的手动组、`smart` 自动组和地区 `smart` 组都必须同步共用同一套 `policy-regex-filter`。
- 如果某个 `policy-path` / provider 会给真实节点额外注入统一前缀，默认先检查是否存在“供应商名宽匹配误伤真实节点”的风险；详见 [docs/proxy-group-filter-methodology.md](proxy-group-filter-methodology.md)。

## 私有订阅域名同步约定

- 真实订阅更新域名只在 `%USERPROFILE%\Desktop\rulemesh-local\current\private_subscription_direct.list` 维护，不写回公开模板
- 修改后运行 `powershell -ExecutionPolicy Bypass -File "%USERPROFILE%\Desktop\rulemesh-local\current\sync_private_subscription_direct.ps1"`，统一同步到两份 Surge 私有配置与两份 Mihomo 私有配置
- Surge 私有配置里的 `PROCESS-NAME + DOMAIN-*` 节点选择例外属于逻辑规则，末尾策略名必须裸写成 `...,🚀 节点选择`，不要手改成 `...,"🚀 节点选择"`；详细说明见 [docs/private-subscription-direct-sync.md](private-subscription-direct-sync.md)
- 同步脚本会先写入 Chrome 访问这些域名时的 `🚀 节点选择` 例外，再写入订阅更新继续 `DIRECT` 的规则
- 这组同步块在 Surge 私有配置中必须位于 `proxy/gfw.list` 前；在工作白名单里则属于显式放行入口
- 详细维护方式见 [docs/private-subscription-direct-sync.md](private-subscription-direct-sync.md)

## 规则顺序建议

1. 拒绝规则
2. 区域精确规则
3. GitHub 仓库 SSH 定向直连
4. GitHub Raw 自举入口
5. GitHub Core 节点选择规则
6. AdsPower 细分直连规则
7. AdsPower 细分节点选择规则
8. Polygon 主网 RPC 节点选择规则
9. BSC 主网 RPC 节点选择规则
10. 海外 DNS 主 IPv4 端点美国分流规则
11. 可选：1Password 核心连接节点选择规则
12. 直连规则
13. 代理优先规则
14. IP 规则
15. `FINAL`

注意：

- `region/us/google_us.list` 必须放在 `region/us/ai_us.list` 与 `region/hk/global_media.list` 等广谱区域规则前。
- Google Play 下载 CDN 与重定向域应继续由 `region/us/google_us.list` 显式承接，不要依赖后面的 `direct/cn_direct.list` 或 `proxy/gfw.list` 兜底。
- `region/us/ai_us.list` 当前聚合海外 AI 平台，且对 Gemini / AI Studio / NotebookLM 保留 AI 视角交叉兜底；它也应继续放在广谱区域规则前，并统一绑定 `🇺🇸 美国-自动选择`。
- `DeepSeek`、`Trae` 中国大陆入口与其他国内 AI 不应并入 `region/us/ai_us.list`；它们应优先由 `direct/ai_cn_direct.list` 承接，字节共享基础设施与中国大陆通用兜底再继续落到 `direct/bytedance_direct.list`、`direct/cn_direct.list`。
- `direct/ai_cn_direct.list` 属于显式国内 AI 直连入口，顺序上应放在 `direct/bytedance_direct.list` 与 `direct/cn_direct.list` 前，避免显式国内 AI 域名先被更宽泛的直连规则吞掉。
- `region/hk/hk_brokers.list` 当前只承接复星证券/复星财富、致富证券、辉立证券与富途，应放在 `region/hk/global_media.list` 与 `proxy/gfw.list` 前，并绑定 `🇭🇰 香港-自动选择`。
- `region/hk/global_media.list` 当前还承接 `x.com`、`t.co`、`twimg.com` 与 `twitter.com` 等 X / Twitter 网页域名，以及 `polymarket.com` 与 `DOMAIN-KEYWORD,polymarket` 这组 Polymarket 香港兜底；默认应继续绑定 `🇭🇰 香港-自动选择`，不要再让它们回落到 `proxy/gfw.list` 或误挂到日本区域。
- 公开 `surge-public.conf` 默认接入 `region/jp/domains_to_jp.list`；当前用于让 `opinion.trade` 走 `🇯🇵 日本-自动选择`。
- `direct/github_ssh_direct.list` 必须放在 `proxy/github_core_proxy.list` 与 `proxy/gfw.list` 前，只给 `github.com:22` 与 `ssh.github.com:443` 直连，避免把 GitHub 网页误放直连。
- GitHub Raw 自举入口建议在 `direct/github_ssh_direct.list` 后额外保留一条 `DOMAIN,raw.githubusercontent.com,"🚀 节点选择"`，避免外部规则首轮下载依赖尚未加载完成的后续远程规则集；同时继续保留 `raw.githubusercontent.com = server:https://cloudflare-dns.com/dns-query` 这一条规则产物解析例外，避免回落到本地/国内系统 DNS；这不是代理节点 bootstrap，不得影响 `proxy-node-domains` 继续使用 AliDNS DoH。
- `proxy/github_core_proxy.list` 应放在 `proxy/gfw.list` 前，显式承接 GitHub 网页、`api.github.com`、Gist、Raw、静态资源与附件；这也会覆盖 `https://api.github.com/gists`、`https://api.github.com/users` 与 `https://gist.githubusercontent.com/...` 这类连接。
- `direct/alicloud_hk_ipv4_ssh22_direct.list`、`DOMAIN-SUFFIX,aliyuncs.com,DIRECT` 与 `DOMAIN,check.myclientip.com,DIRECT` 应统一放在直连段显式维护；其后可额外保留一条阿里云广覆盖 `REJECT` 观察兜底，用于发现上游阿里云规则的漏网之鱼。
- `direct/adspower_direct.list` 与 `proxy/adspower_proxy.list` 都应放在 `proxy/gfw.list` 前，确保 AdsPower 的细分直连与节点选择优先命中。
- `proxy/polygon_rpc_proxy.list` 应放在 `proxy/gfw.list` 前，确保 Polygon 主网 RPC 域名优先走 `🚀 节点选择`。
- `proxy/bsc_rpc_proxy.list` 应放在 `proxy/gfw.list` 前，确保 BSC 主网 RPC 域名优先走 `🚀 节点选择`。
- `proxy/overseas_dns_ipv4_proxy.list` 应放在 `proxy/gfw.list` 前，并在 Surge 配置中以 `RULE-SET,...,"🇺🇸 美国-自动选择",no-resolve` 方式接入，确保 `1.1.1.1/32`、`8.8.8.8/32` 与 `9.9.9.9/32` 优先走美国地区策略。
- `DOMAIN,dns.alidns.com,DIRECT` 与 `DOMAIN,doh.pub,DIRECT` 是代理节点 bootstrap DNS 直连例外，应紧跟海外 DNS 主 IPv4 端点规则，并放在 `PROTOCOL,DOH` / `DOH3` / `DOQ` 前，避免代理尚未建立时产生 DNS 走代理的循环依赖。
- 如果你是 1Password 重度用户，可额外接入 `proxy/onepassword_proxy.list`，并同样放在 `proxy/gfw.list` 前；这条规则由仓库每日自动抓取 1Password 官方支持页生成，默认只覆盖官方自有核心域名与更新/基础设施端点，详情见 [docs/onepassword-proxy-rules.md](onepassword-proxy-rules.md)。
- `reject/adspower_reject.list` 应和其他拒绝规则一起放在最前，先拦截隐私追踪与可安全阻断端点。
- `direct/os_time_direct.list` 建议放在其他普通 `direct/*.list` 前，优先保障 `time.windows.com`、`time.apple.com` 与 `time-macos.apple.com` 直连。
- 如果你希望默认禁用系统更新、升级时再临时放行，建议同时接入 `direct/os_time_direct.list`、`reject/os_update_reject.list`、`region/us/microsoft_us.list` 与 `region/us/macos_update_us.list`；平时由 `reject` 先拦截升级流量，系统时间同步仍由 `os_time_direct` 保持直连，放开拒绝入口后 Microsoft / macOS 更新流量统一走美国节点。
- `proxy/gfw.list` 建议放在国内直连规则之后，至少晚于 `LAN`、`direct/os_time_direct`、`direct/ai_cn_direct`、`direct/bytedance_direct`、`direct/netease_direct`、`direct/bilibili_direct` 与 `direct/cn_direct`，避免国内域名被广谱代理规则提前抢走；GitHub、AdsPower、RPC、海外 DNS 端点等精确代理入口仍应放在 `proxy/gfw.list` 前。
- 私有 `rulemesh-substore-surge-work-whitelist.conf` 是白名单例外：它保留设备分流、区域精确、香港券商、GitHub SSH、GitHub Raw 自举入口、GitHub Core 代理入口、GitHub 广覆盖 `REJECT` 观察兜底、私有订阅域名同步块、1Password 核心连接、AdsPower、Polygon 主网 RPC、BSC 主网 RPC、海外 DNS 主 IPv4 端点、代理节点 bootstrap DNS 直连例外、海外加密 DNS 显式入口、`LAN,DIRECT`、`direct/os_time_direct`、`region/us/microsoft_us`、`region/us/macos_update_us`、阿里云指定直连与 ByteDance；其中只有设备分流继续保留 `SRC-IP` 约束，并按指定 AWS 区域 / 多地区链式 SOCKS5 IP 段定向到对应工作机亚洲出口组，后续规则不再额外限制源 IP，原独立 `IP 规则` 段已移除；`github_ssh_direct` 后先保留 `DOMAIN,raw.githubusercontent.com` 自举入口，再显式放行 `proxy/github_core_proxy.list`，并额外用 `DOMAIN-KEYWORD,github,REJECT` 观察 GitHub 漏网之鱼；阿里云香港 SSH、`aliyuncs.com` 与 `check.myclientip.com` 统一收敛到“指定直连”段显式放行，其后额外保留一条阿里云广覆盖 `REJECT` 观察兜底；私有订阅域名统一从本地单一源文件同步到白名单显式放行段，并在订阅更新直连前额外插入 Chrome 访问这些域名时改走 `🚀 节点选择` 的例外；`proxy/onepassword_proxy.list` 也作为白名单显式放行入口放在 `proxy/gfw` 之前；AdsPower 细分规则后额外保留一条 `DOMAIN-KEYWORD,adspower,REJECT` 广覆盖观察兜底，用来发现细分规则漏网之鱼；海外 DNS 主 IPv4 端点统一走美国地区策略，`dns.alidns.com` / `doh.pub` 作为节点 bootstrap DNS 直连例外，DoH / DoH3 / DoQ 与 `cloudflare-dns.com`、`dns.google`、`dns.quad9.net` 也统一作为美国出口白名单入口；未命中上述入口的流量最终统一 `REJECT`。不要把公开模板里的广谱放行段机械同步回去。
- 工作白名单模式下，广覆盖观察规则统一只允许使用 `REJECT`；personal 配置即使当前风险可接受，也不应把 `DIRECT` / `PROXY + extended-matching` 这类写法继续扩散回白名单模板。
- 若只新增某个白名单专属的单个拒绝域名，或只用于阻断浏览器扩展更新链路的拒绝规则，默认直接维护在这份私有白名单的拒绝段，不为单条规则额外新增公开 `rules/` 文件。

## 使用原则

- 客户端规则只引用 `dist/surge/rules/`；DNS 专用域名清单只引用 `dist/surge/dns/cn_dns_domains.list`
- `rules/` 是源规则层，不建议在 Surge 配置中直接引用
- 不要在客户端继续引用第三方原始规则 URL
- GeoIP 数据库是当前例外：公开模板默认显式固定到本仓库的 Release 镜像地址
- 不要手改 `dist/`，应先改 `rules/` 后重新构建
- 私有工作路由白名单约定见 [docs/surge-work-cluster-whitelist.md](surge-work-cluster-whitelist.md)；该约定只影响本地 Surge 工作路由文件，不影响公开模板。
- 私有订阅域名同步约定见 [docs/private-subscription-direct-sync.md](private-subscription-direct-sync.md)；该约定同样只影响本地私有配置，不影响公开模板。
- 1Password 重度用户专项规则约定见 [docs/onepassword-proxy-rules.md](onepassword-proxy-rules.md)；公开模板默认不内置，需要时再显式接入。
- GeoIP 上游选择与维护边界见 [docs/geoip-upstream.md](geoip-upstream.md)。
- DNS 防泄漏与解析边界见 [docs/network-security/dns-leak-prevention.md](network-security/dns-leak-prevention.md)；任何 DNS、DoH、fake-ip、Host 或 Sub-Store 节点域名清单调整后，都要做外部 DNS 泄漏验证。
