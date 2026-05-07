# Surge 工作路由白名单约定

本文只记录私有工作路由文件的维护约定，用来防止后续把它误改回“和个人模板完全一致”的结构。

## 适用范围

- 仅适用于本地私有 Surge 文件 `rulemesh-substore-surge-work-whitelist.conf`
- 不适用于 `rulemesh-substore-surge-personal.conf`
- 不适用于 `rulemesh-substore-mihomo-clash-verge.yaml`
- 不适用于 `rulemesh-substore-mihomo-clash-meta.yaml`
- 不适用于仓库里的公开模板 `docs/examples/surge-public.conf` 与 `docs/examples/mihomo-public.yaml`

## 隐私边界

- 这份工作路由文件里的真实 `SRC-IP` 列表、私有 `policy-path`、订阅地址、私有订阅更新域名与 `[MITM]` 参数继续只保留在本地私有目录
- 公开仓库只记录“有 6 台固定工作电脑使用白名单模式”这一维护事实，不回写真实局域网 IP 或其他敏感值

## 当前白名单原则

- 工作路由仍以那 6 台固定工作电脑为核心维护对象，并继续采用白名单模式
- 拒绝规则维持当前逻辑
- 设备分流继续按“源 IP + AWS 区域 / 多地区链式 SOCKS5 IP 段”定向到对应设备组
- 只有 2.1 设备分流继续保留“源 IP + AWS 区域 / 多地区链式 SOCKS5 IP 段”约束；2.2-2.10 不再额外限制源 IP
- 多地区链式 SOCKS5 端点属于自维护链式代理入口，不再视为日本区域规则，也不应再挂到单一国家目录或固定日本组
- 区域精确规则继续保留，且 `Google TW` 与 `AI US` 都必须先于广谱区域规则
- `AI US` 入口继续作为白名单显式放行项，但当前只承接海外 AI 平台并统一走美国节点；国内 AI 不应借这条入口放行
- GitHub 仓库 SSH 定向直连继续保留独立 carve-out
- GitHub 相关访问继续拆成三段：先保留 `DOMAIN,raw.githubusercontent.com` 自举入口，再显式放行 `proxy/github_core_proxy.list`，其后的 `DOMAIN-KEYWORD,github` 广覆盖观察兜底在工作白名单模式下统一使用 `REJECT`，专门用于发现 SSH / GitHub Core 之外的漏网之鱼
- `raw.githubusercontent.com` 继续作为规则产物下载自举入口，但不再绑定 `server:system`；当前改用海外 DoH 解析，避免规则产物下载回落到本地/国内系统 DNS
- 工作白名单默认不额外开放局域网代理入口；旁路由已接管流量，`allow-wifi-access` 继续保持 `false`
- Surge profile 不写 `dns-mode = fake-ip`；Fake IP 由 Surge Enhanced Mode / VIF 运行时提供，工作路由设备加载 profile 后需要在 Surge 里启用 Enhanced Mode
- IPv6 默认关闭，等完成 IPv6 DNS 泄露、WebRTC 与出口测试后再重新评估
- `hijack-dns = *:53` 负责接管传统 UDP/TCP 53 DNS；加密 DNS 流量只能作为显式白名单入口放行，不能靠 `FINAL` 兜底
- 海外 `encrypted-dns-server`、`encrypted-dns-follow-outbound-mode = true` 与 `use-local-host-item-for-proxy = false` 继续保留，配合 `[Host]` 中的 GitHub Raw 规则产物解析与 `proxy-node-domains` 节点 server 域名专用 bootstrap 解析
- 私有订阅域名同步块继续保留独立显式放行入口，顺序位于 GitHub 观察兜底之后、1Password 之前；域名清单统一在 `%USERPROFILE%\Desktop\rulemesh-local\current\private_subscription_direct.list` 维护，再通过同步脚本先插入 Chrome 访问这些域名时改走 `🚀 节点选择` 的例外，再保留订阅更新直连
- `proxy/onepassword_proxy.list` 继续保留 `🚀 节点选择`，用于白名单模式下显式放行 1Password 核心连接；其上游快照由仓库每天自动抓取官方支持页生成，但默认只覆盖官方自有核心域名与更新/基础设施端点
- AdsPower 继续维持 `adspower_reject`、`adspower_direct`、`adspower_proxy` 三段细分
- 在 `adspower_direct` 与 `adspower_proxy` 之后，额外保留一条广覆盖 `DOMAIN-KEYWORD,adspower,REJECT` 观察兜底，专门用于发现细分规则漏网之鱼
- `proxy/polygon_rpc_proxy.list` 继续保留 `🚀 节点选择`，用于白名单模式下显式放行 Polygon 主网 RPC 域名
- `proxy/bsc_rpc_proxy.list` 继续保留 `🚀 节点选择`，用于白名单模式下显式放行 BSC 主网 RPC 域名
- `proxy/overseas_dns_ipv4_proxy.list` 继续保留，并在 Surge 配置里以 `RULE-SET,...,"🇺🇸 美国-自动选择",no-resolve` 接入，用于白名单模式下显式放行 `1.1.1.1/32`、`8.8.8.8/32` 与 `9.9.9.9/32`
- DoH / DoH3 / DoQ 以及 `cloudflare-dns.com`、`dns.google`、`dns.quad9.net` 继续作为海外加密 DNS 显式白名单入口，并统一走 `🇺🇸 美国-自动选择`
- `LAN,DIRECT` 继续保留在白名单直连入口中
- `direct/os_time_direct` 继续保留 `DIRECT`，用于 Windows / Apple 系统时间同步，不并入节点选择
- 单个白名单专属直连域名（例如 `smtp.163.com`）优先直接维护在 2.10“指定直连”入口，不为单条规则额外新增公开 `rules/` 文件
- 单个白名单专属拒绝域名，或只用于阻断浏览器扩展更新链路的拒绝规则，优先直接维护在 1)“拒绝规则”入口，不为单条规则额外新增公开 `rules/` 文件
- `direct/microsoft_direct` 继续保留 `DIRECT`
- `direct/macos_update_direct` 继续保留 `DIRECT`，用于需要时临时放开 macOS 系统升级；它只匹配 Apple 官方标注为 macOS only 的更新主机
- `alicloud_hk_ipv4_ssh22_direct`、`DOMAIN-SUFFIX,aliyuncs.com` 与 `DOMAIN,check.myclientip.com` 继续保留；其后额外保留一条阿里云广覆盖 `REJECT` 观察兜底，用于发现上游阿里云规则的漏网之鱼
- 工作白名单模式下，广覆盖观察规则统一只允许使用 `REJECT`；不要对 `DIRECT` 或 `PROXY` 规则使用 `extended-matching`，否则会把可伪造的 Host / SNI 纳入放行判断，放大绕过白名单的风险
- `bytedance_direct.list` 继续保留 `DIRECT`
- 原独立 2.6 `IP 规则` 段已删除，避免与 2.1 设备分流重复
- 未命中上述白名单入口的流量最终统一落到 `FINAL,REJECT`

## 永久差异约定

- 这份工作路由白名单是对工作软路由的长期特化，不再追求和两个 `personal` 配置完全一致
- 后续如果调整个人模板、公开模板或 Mihomo 模板，不要顺手把工作路由改回通用 `proxy/gfw + 广谱 direct + 放行型 FINAL` 结构
- 反过来，工作路由里的白名单 `REJECT` 兜底也不要迁移到个人模板或 Mihomo 模板

## 维护时必须保留的顺序

1. 拒绝规则
2. 设备分流
3. 区域精确规则
4. GitHub 仓库 SSH 定向直连
5. GitHub Raw 自举入口
6. GitHub Core 代理入口
7. GitHub 广覆盖 REJECT 观察兜底
8. 私有订阅域名同步块
9. 1Password 核心连接节点选择入口
10. AdsPower 细分规则
11. AdsPower 广覆盖 REJECT 观察兜底
12. Polygon 主网 RPC 节点选择入口
13. BSC 主网 RPC 节点选择入口
14. 海外 DNS 主 IPv4 端点美国分流入口
15. 海外加密 DNS 显式白名单入口
16. 指定直连入口（含阿里云广覆盖 REJECT 观察兜底）
17. 全局 `FINAL,REJECT` 兜底

## 不要误恢复的广谱放行项

若需求没有重新明确变更，不要把下列广谱放行项重新塞回工作路由白名单阶段：

- `proxy/gfw`
- `direct/netease_direct`
- `direct/bilibili_direct`
- `direct/cn_direct`

## 变更联动

- 只要工作路由白名单逻辑发生变化，就要同时更新这份文档
- 如果只是个人模板或 Mihomo 模板调整，不代表工作路由也应同步同构
- 如果未来白名单设备范围、允许入口或兜底策略发生变化，优先先确认这是“工作路由私有特化”还是“整个仓库公开默认行为”的变化，再决定是否更新公开模板
- 如果未来私有订阅域名同步块的源文件、同步脚本或插入顺序发生变化，也要同步更新 [docs/private-subscription-direct-sync.md](private-subscription-direct-sync.md)
