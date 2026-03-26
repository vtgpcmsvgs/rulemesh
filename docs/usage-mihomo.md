# Mihomo 使用说明

适用于：

- Clash Verge Rev
- Clash Meta for Android
- 其他兼容 Mihomo `rule-providers` 的客户端

## 推荐入口

- 完整公开参考模板：[`docs/examples/mihomo-public.yaml`](examples/mihomo-public.yaml)
- 规则产物入口：`dist/mihomo/classical/`

这个模板是基于本地长期使用的 Mihomo 配置整理出来的公开版，保留了多订阅聚合、区域自动切换、`rule-providers` 与完整规则顺序，但移除了真实机场地址和其他不适合公开仓库的私有信息。

## 模板保留了什么

- `dns + proxy-providers + proxy-groups + rule-providers + rules` 的完整结构
- 多订阅聚合后的统一总开关与区域自动组
- `reject`、`direct`、`proxy`、`region` 四类 RuleMesh `classical` 产物接入
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
- 私有订阅更新直连域名；这部分只在本地私有目录维护，并通过同步脚本写入 Mihomo personal 配置
- 1Password 重度用户专项入口；如需启用，请另行接入 `proxy/onepassword_proxy.yaml`

## 使用前只需要替换两处

1. 把模板里 `provider_a`、`provider_b`、`provider_c` 的 `url` 改成你自己的订阅地址。
2. 如果你不希望最终兜底走总开关，可以把 `MATCH,🚀 节点选择` 改成你想固定兜底的区域组。

## 私有订阅更新直连约定

- 真实订阅更新域名只在 `%USERPROFILE%\Desktop\rulemesh-local\current\private_subscription_direct.list` 维护，不写回公开模板
- 修改后运行 `powershell -ExecutionPolicy Bypass -File "%USERPROFILE%\Desktop\rulemesh-local\current\sync_private_subscription_direct.ps1"`，统一同步到 Mihomo personal 与两份 Surge 私有配置
- 这份共享源文件应只保留 Surge / Mihomo 都能直接复用的规则语法；当前优先使用 `DOMAIN`、`DOMAIN-SUFFIX`、`DOMAIN-WILDCARD`
- 在 Mihomo personal 中，这组规则应继续放在 `proxy_gfw` 前
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
- `direct/github_ssh_direct.yaml` 必须放在 `proxy/gfw.yaml` 前，只给 `github.com:22` 与 `ssh.github.com:443` 直连，避免把 GitHub 网页误放直连。
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
- 不要手改 `dist/`，应先改 `rules/` 后重新构建
- 私有 Surge 工作路由白名单约定见 [docs/surge-work-cluster-whitelist.md](surge-work-cluster-whitelist.md)，但该约定不影响 Mihomo 模板与 Mihomo personal 配置。
- 私有订阅更新直连同步约定见 [docs/private-subscription-direct-sync.md](private-subscription-direct-sync.md)；该约定影响 Mihomo personal，但不影响公开模板。
- 1Password 重度用户专项规则约定见 [docs/onepassword-proxy-rules.md](onepassword-proxy-rules.md)；公开模板默认不内置，需要时再显式接入。
