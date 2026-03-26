# Surge 工作路由白名单约定

本文只记录私有工作路由文件的维护约定，用来防止后续把它误改回“和个人模板完全一致”的结构。

## 适用范围

- 仅适用于本地私有 Surge 文件 `rulemesh-substore-surge-work-whitelist.conf`
- 不适用于 `rulemesh-substore-surge-personal.conf`
- 不适用于 `rulemesh-substore-mihomo-personal.yaml`
- 不适用于仓库里的公开模板 `docs/examples/surge-public.conf` 与 `docs/examples/mihomo-public.yaml`

## 隐私边界

- 这份工作路由文件里的真实 `SRC-IP` 列表、私有 `policy-path`、订阅地址、私有订阅更新域名与 `[MITM]` 参数继续只保留在本地私有目录
- 公开仓库只记录“有 6 台固定工作电脑使用白名单模式”这一维护事实，不回写真实局域网 IP 或其他敏感值

## 当前白名单原则

- 工作路由仍以那 6 台固定工作电脑为核心维护对象，并继续采用白名单模式
- 拒绝规则维持当前逻辑
- 设备分流继续按“源 IP + AWS 区域”定向到对应设备组
- 只有 2.1 设备分流继续保留“源 IP + AWS 区域”约束；2.2-2.7 不再额外限制源 IP
- 区域精确规则继续保留，且 `Google TW` 必须先于广谱区域规则
- GitHub 仓库 SSH 定向直连继续保留独立 carve-out
- GitHub 相关 HTTPS 访问额外保留 `DOMAIN,raw.githubusercontent.com` 下载入口与 `DOMAIN-KEYWORD,github` 观察兜底，策略继续走节点选择，用于白名单模式下拉取规则产物并发现 SSH / Raw 之外的漏网之鱼
- `raw.githubusercontent.com` 继续额外绑定 `server:system` 解析，`dns-server` 也保留 `system + 公共 DNS` 组合，用于降低 GitHub Raw 外部资源偶发超时
- 私有订阅更新直连继续保留独立显式放行入口，顺序位于 GitHub 观察兜底之后、1Password 之前；域名清单统一在 `%USERPROFILE%\Desktop\rulemesh-local\current\private_subscription_direct.list` 维护，再通过同步脚本分发到本地配置
- `proxy/onepassword_proxy.list` 继续保留 `🚀 节点选择`，用于白名单模式下显式放行 1Password 核心连接；其上游快照由仓库每天自动抓取官方支持页生成，但默认只覆盖官方自有核心域名与更新/基础设施端点
- AdsPower 继续维持 `adspower_reject`、`adspower_direct`、`adspower_proxy` 三段细分
- 在 `adspower_direct` 与 `adspower_proxy` 之后，额外保留一条广覆盖 `DOMAIN-KEYWORD,adspower` 观察兜底；策略仍走节点选择，专门用于发现细分规则漏网之鱼
- `proxy/polygon_rpc_proxy.list` 继续保留 `🚀 节点选择`，用于白名单模式下显式放行 Polygon 主网 RPC 域名
- `proxy/bsc_rpc_proxy.list` 继续保留 `🚀 节点选择`，用于白名单模式下显式放行 BSC 主网 RPC 域名
- `proxy/google_public_dns_ipv4_proxy.list` 继续保留 `🚀 节点选择`，用于白名单模式下显式放行 `8.8.8.8/32`
- `LAN,DIRECT` 继续保留在白名单直连入口中
- `direct/os_time_direct` 继续保留 `DIRECT`，用于 Windows / Apple 系统时间同步，不并入节点选择
- `direct/microsoft_direct` 继续保留 `DIRECT`
- `direct/macos_update_direct` 继续保留 `DIRECT`，用于需要时临时放开 macOS 系统升级；它只匹配 Apple 官方标注为 macOS only 的更新主机
- `alicloud_hk_ssh_direct` 与阿里云抢占式 IP 直连继续保留
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
5. GitHub Raw 下载入口
6. GitHub 广覆盖观察兜底
7. 私有订阅更新直连
8. 1Password 核心连接节点选择入口
9. AdsPower 细分规则
10. AdsPower 广覆盖观察兜底
11. Polygon 主网 RPC 节点选择入口
12. BSC 主网 RPC 节点选择入口
13. Google Public DNS 主 IPv4 端点节点选择入口
14. 指定直连入口
15. 全局 `FINAL,REJECT` 兜底

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
- 如果未来私有订阅更新直连的源文件、同步脚本或插入顺序发生变化，也要同步更新 [docs/private-subscription-direct-sync.md](private-subscription-direct-sync.md)
