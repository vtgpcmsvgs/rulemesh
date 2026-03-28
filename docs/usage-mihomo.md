# Mihomo 使用说明

适用于：

- Clash Verge Rev
- Clash Meta for Android
- 其他兼容 Mihomo `rule-providers` 的客户端

## 推荐入口

- 完整公开参考模板：[`docs/examples/mihomo-public.yaml`](examples/mihomo-public.yaml)
- 规则产物入口：`dist/mihomo/classical/`
- Tun / DNS / 嗅探维护方法论：[`docs/mihomo-tun-dns-methodology.md`](mihomo-tun-dns-methodology.md)

这个模板是基于本地长期使用的 Mihomo 配置整理出来的公开版，保留了多订阅聚合、区域自动切换、`rule-providers` 与完整规则顺序，但移除了真实机场地址和其他不适合公开仓库的私有信息。

## 模板保留了什么

- `tun + sniffer + dns + proxy-providers + proxy-groups + rule-providers + rules` 的完整结构
- `geodata-mode: false` + `geox-url.mmdb` 显式固定到与 Surge 共用的本仓库 Release 镜像地址
- 多订阅聚合后的统一总开关与区域自动组
- `reject`、`direct`、`proxy`、`region` 四类 RuleMesh `classical` 产物接入
- 默认采用“国际域名优先国外加密 DNS、明确的国内直连域名集单独走国内加密 DNS”的分流思路
- 默认启用 Tun 全量接管与域名嗅探，优先把 Mihomo 的实际体验拉到接近 Surge 的水位
- `region/hk/global_media.yaml` 额外承接 X / Twitter 网页、短链与静态资源，并默认绑定 `🇭🇰 香港-自动选择`
- `direct_github_ssh` 后保留一条阿里云广覆盖观察兜底，用于发现 SSH 22 端口之外的漏网之鱼
- AdsPower 专项 `reject/direct/proxy` 规则集与 `proxy/gfw.yaml` 广谱代理规则的顺序关系
- Polygon 主网 RPC 专项 `proxy/polygon_rpc_proxy.yaml` 与 `proxy/gfw.yaml` 的顺序关系
- BSC 主网 RPC 专项 `proxy/bsc_rpc_proxy.yaml` 与 `proxy/gfw.yaml` 的顺序关系
- Google Public DNS 主 IPv4 端点专项 `proxy/google_public_dns_ipv4_proxy.yaml` 与 `proxy/gfw.yaml` 的顺序关系
- `direct/os_time_direct.yaml` 与其他普通直连规则的顺序关系
- 用 `plain_http_reject.yaml` 接管浏览器明文 HTTP 拦截

## 模板刻意移除了什么

- 真实机场订阅链接、供应商命名与 token
- `external-controller`、`secret` 等控制面参数
- 按局域网源 IP 的设备分流逻辑
- 私有 Surge 工作路由白名单特化；那份差异只属于本地 `rulemesh-substore-surge-work-whitelist.conf`
- 私有订阅更新直连域名；这部分只在本地私有目录维护，并通过同步脚本写入两份 Mihomo 私有配置
- 1Password 重度用户专项入口；如需启用，请另行接入 `proxy/onepassword_proxy.yaml`

## 使用前只需要替换两处

1. 把模板里 `provider_a`、`provider_b`、`provider_c` 的 `url` 改成你自己的订阅地址。
2. 如果你不希望最终兜底走总开关，可以把 `MATCH,🚀 节点选择` 改成你想固定兜底的区域组。

另请注意：

- Clash Verge Rev 等支持 Tun 的客户端，建议同时开启 Tun 模式；这份模板默认按 Tun + 嗅探 + 分流 DNS 设计，关闭 Tun 会明显削弱体验。
- 如果你同时维护 Clash Verge Rev 与 Clash Meta for Android，本地私有目录建议拆成 `rulemesh-substore-mihomo-clash-verge.yaml` 与 `rulemesh-substore-mihomo-clash-meta.yaml` 两份；规则骨架可以保持一致，但节点域名解析策略应允许分别维护。
- 这份模板不会把“所有 DIRECT 都交给国内 DNS”；像 GitHub SSH、Microsoft、macOS 更新这类“允许直连但不适合回到国内解析”的国外入口，仍保持默认国外解析。

## Tun / DNS / 嗅探方法论

- Mihomo 的体验优化优先级，不是继续堆规则，而是先把 `tun`、`sniffer`、`dns` 这层运行时补齐。
- DNS 分流不按 `DIRECT` / `PROXY` 两分，而按“国内直连域名集”和“国际域名”拆开；前者走国内加密 DNS，后者默认走国外加密 DNS。
- 新增直连规则时，要先判断它属于“国内直连域名集”还是“国外直连例外”。只有前者才应进入 `nameserver-policy` 的国内解析名单。
- `proxy-server-nameserver` 要与业务 DNS 分开维护；前者只负责节点域名解析，避免规则 DNS 与节点 DNS 互相依赖。
- 详细维护边界、风险提示与检查清单见 [docs/mihomo-tun-dns-methodology.md](mihomo-tun-dns-methodology.md)。

## 私有订阅更新直连约定

- 真实订阅更新域名只在 `%USERPROFILE%\Desktop\rulemesh-local\current\private_subscription_direct.list` 维护，不写回公开模板
- 修改后运行 `powershell -ExecutionPolicy Bypass -File "%USERPROFILE%\Desktop\rulemesh-local\current\sync_private_subscription_direct.ps1"`，统一同步到两份 Mihomo 私有配置与两份 Surge 私有配置
- 这份共享源文件应只保留 Surge / Mihomo 都能直接复用的规则语法；当前优先使用 `DOMAIN`、`DOMAIN-SUFFIX`、`DOMAIN-WILDCARD`
- 在两份 Mihomo 私有配置中，这组规则都应继续放在 `proxy_gfw` 前
- 详细维护方式见 [docs/private-subscription-direct-sync.md](private-subscription-direct-sync.md)

## 规则顺序建议

1. 拒绝规则
2. 区域精确规则
3. GitHub 仓库 SSH 定向直连
4. AdsPower 细分直连规则
5. AdsPower 细分节点选择规则
6. Polygon 主网 RPC 节点选择规则
7. BSC 主网 RPC 节点选择规则
8. Google Public DNS 主 IPv4 端点节点选择规则
9. 可选：1Password 核心连接节点选择规则
10. 代理优先规则
11. 直连规则
12. IP 规则
13. `MATCH`

注意：

- `region/tw/google_tw.yaml` 对应规则应放在 `region/hk/global_media.yaml` 前。
- `region/hk/global_media.yaml` 当前还承接 `x.com`、`t.co`、`twimg.com` 与 `twitter.com` 等 X / Twitter 网页域名，默认应继续绑定 `🇭🇰 香港-自动选择`，不要再让它们回落到 `proxy/gfw.yaml`。
- `direct/github_ssh_direct.yaml` 必须放在 `proxy/gfw.yaml` 前，只给 `github.com:22` 与 `ssh.github.com:443` 直连，避免把 GitHub 网页误放直连。
- 阿里云广覆盖观察兜底应紧跟 `direct/github_ssh_direct.yaml` 之后，保留对 SSH 22 端口之外漏网之鱼的观察入口，不要把它挪回普通 `direct` 段尾部。
- `direct/adspower_direct.yaml` 与 `proxy/adspower_proxy.yaml` 都应放在 `proxy/gfw.yaml` 前，确保 AdsPower 的细分直连与节点选择优先命中。
- `proxy/polygon_rpc_proxy.yaml` 应放在 `proxy/gfw.yaml` 前，确保 Polygon 主网 RPC 域名优先走 `🚀 节点选择`。
- `proxy/bsc_rpc_proxy.yaml` 应放在 `proxy/gfw.yaml` 前，确保 BSC 主网 RPC 域名优先走 `🚀 节点选择`。
- `proxy/google_public_dns_ipv4_proxy.yaml` 应放在 `proxy/gfw.yaml` 前，确保 `8.8.8.8/32` 优先走 `🚀 节点选择`。
- 如果你是 1Password 重度用户，可额外接入 `proxy/onepassword_proxy.yaml`，并同样放在 `proxy/gfw.yaml` 前；这条规则由仓库每日自动抓取 1Password 官方支持页生成，默认只覆盖官方自有核心域名与更新/基础设施端点，详情见 [docs/onepassword-proxy-rules.md](onepassword-proxy-rules.md)。
- `reject/adspower_reject.yaml` 应和其他拒绝规则一起放在最前，先拦截隐私追踪与可安全阻断端点。
- `direct/os_time_direct.yaml` 建议放在其他普通 `direct/*.yaml` 前，优先保障 `time.windows.com`、`time.apple.com` 与 `time-macos.apple.com` 直连。
- 如果你希望默认禁用系统更新、升级时再临时放行，建议同时接入 `direct/os_time_direct.yaml`、`reject/os_update_reject.yaml`、`direct/microsoft_direct.yaml` 与 `direct/macos_update_direct.yaml`；平时由 `reject` 先拦截升级流量，系统时间同步仍由 `os_time_direct` 保持直连。
- `proxy/gfw.yaml` 建议放在其他普通 `direct/*.yaml` 前，减少广谱直连误伤。
- `reject_plain_http` 已有构建产物，公开模板不再建议手写重复的浏览器进程规则。
- Surge 私有工作路由白名单并不迁移到 Mihomo 模板；Mihomo 仍维持这里描述的公开/个人通用结构。

## 使用原则

- 客户端只引用 `dist/mihomo/classical/`
- `rules/` 是源规则层，不建议客户端直接引用
- 不要把 `classical` 产物误配成别的 `behavior`
- 不要再找旧的纯域名或纯 CIDR 产物目录；仓库已经统一走 `classical`
- GeoIP 数据库当前显式固定为 `mmdb`，并统一指向本仓库的 Release 镜像地址
- 不要手改 `dist/`，应先改 `rules/` 后重新构建
- 私有 Surge 工作路由白名单约定见 [docs/surge-work-cluster-whitelist.md](surge-work-cluster-whitelist.md)，但该约定不影响 Mihomo 模板与两份 Mihomo 私有配置。
- 私有订阅更新直连同步约定见 [docs/private-subscription-direct-sync.md](private-subscription-direct-sync.md)；该约定影响两份 Mihomo 私有配置，但不影响公开模板。
- 1Password 重度用户专项规则约定见 [docs/onepassword-proxy-rules.md](onepassword-proxy-rules.md)；公开模板默认不内置，需要时再显式接入。
- GeoIP 上游选择与维护边界见 [docs/geoip-upstream.md](geoip-upstream.md)。
