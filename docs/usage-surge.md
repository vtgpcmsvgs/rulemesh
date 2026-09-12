# Surge 使用说明

当前公开参考配置是 [surge-public.conf](examples/surge-public.conf)，适合个人终端。五份私有配置与公开模板共同遵循 [2026-09-09 性能基线](performance-baseline.md)；工作白名单仍有独立放行边界。

## 接入

1. 将模板中的示例 `policy-path` 换成自己的 Surge 聚合订阅地址。
2. 将 `proxy-node-domains` 换成生产设备可访问的 Sub-Store 分享文件 URL。文件只能包含节点 server 域名，一行一个，过滤 IP、订阅地址与面板域名。
3. 在 Surge Mac 启用 Enhanced Mode / VIF；profile 不使用 `dns-mode = fake-ip`。
4. 更新外部规则后检查实际策略与 DNS 出口。当前 Windows 环境无法替代 Mac 上的运行验证。

## 默认规则顺序

1. 海外 AI 美国入口，包括 Google AI。
2. 国内 AI、抖音、微信与小红书精选直连。
3. 日本明确访问例外、Crypto 台湾、香港券商与 Personal 香港证券。
4. Google 通用业务自动择优，保留官方完整地址空间。
5. Personal 精选规则与既有拒绝规则；Apple / Outlook 直连及 Microsoft Store 优先入口保持各自边界。
6. 其他精确业务、GitHub SSH/Raw/Core、AdsPower、Polygon/BSC RPC、订阅端点与 DNS 出口。
7. LAN、系统时间、阿里云 TCP/22 和其他国内直连。
8. `gfw` 使用全地区 smart；未命中前置规则时 `FINAL,DIRECT,dns-failed`，工作白名单保持 `FINAL,REJECT`。

命中普通海外规则时使用全地区 smart 组，未命中规则的 `FINAL` 使用 DIRECT；AI 美国、Crypto/RPC 台湾、`opinion.trade` 日本、券商香港是明确例外。地区组仍可用于手动选择。AWS IP 规则和链式 SOCKS5 规则仅保留仓库源文件与产物，配置不再调用。

`global_media` 承接 X / Twitter 和媒体服务；Polymarket 已移入 Crypto 台湾。WPS、Notion、Microsoft Store 等没有当前强制地区要求的业务自动择优；文件名中的旧地区只是兼容路径。国内 AI 由 `ai_cn_direct` 承接，不扩入海外 AI。

## DNS 与连接

普通业务使用 AliDNS / DNSPod 国内双 DoH，AI 在 `[Host]` 中单独使用 Cloudflare DoH，其连接固定美国。保留 `encrypted-dns-follow-outbound-mode = true`、`use-local-host-item-for-proxy = false` 与 `hijack-dns = *:53`。传统 53 DNS 接管不等于任意应用内置 DoH 都自动遵守业务策略，最终生效路径仍应检查。

GitHub Raw 继续保留独立海外解析入口 `raw.githubusercontent.com = server:https://cloudflare-dns.com/dns-query`；该入口用于规则下载，不替代节点 bootstrap。默认国内 DNS 后，Personal 不再重复加载 `cn_performance_dns_domains`；工作保留的小型清单不授予任何流量放行。

`always-real-ip` 只精确保留 `localhost.weixin.qq.com` 的回环例外；不要扩大成 `*.weixin.qq.com`。`skip-proxy` 不放行 Apple `17.0.0.0/8`。IPv6 保持关闭，测速 URL 保留 Surge 当前要求的 HTTP；不能机械改成 Mihomo 的 HTTPS 或移植其 DNS 字段。

## 精确边界

- GitHub SSH 直连必须先于 GitHub Core / gfw，Raw 自举入口独立存在，GitHub 网页和 API 使用自动代理。
- Outlook 邮件、精确共享登录和认证资源直连，不扩展到整个 Microsoft 根域；共享认证被其他应用复用时也直连。
- 阿里云远程 SSH 规则之前保留只限 TCP/22 的内联兜底；`aliyuncs.com` 和 `check.myclientip.com` 保持既有精确直连。普通配置不恢复阿里云广谱观察放行。
- AdsPower 保留拒绝、直连、代理三类规则；1Password 可按需接入其专用产物。
- 工作文件保留既有观察规则、设备条件与最终拒绝，不复制 Personal 专用入口。

## 分发与维护

自定义规则只引用 `dist/surge/rules/`，DNS 可选资产位于 `dist/surge/dns/`。GeoIP 直接使用 [MetaCubeX country.mmdb](https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/country.mmdb)，不经过本仓库 Release。

源规则修改后执行 `tools/build_rules.ps1` 与 `tools/check.ps1`，不要手改 dist。私有配置维护必须提交并推送独立私人仓库。

相关说明：[工作白名单](surge-work-cluster-whitelist.md)、[订阅端点同步](private-subscription-direct-sync.md)、[GeoIP](geoip-upstream.md)、[DNS 边界](network-security/dns-leak-prevention.md)、[只读本地监控](surge-local-monitoring.md)。监控只生成调查建议，仍须分开取得调查和执行授权，不因本次性能维护改变该流程。

机场手动组必须独立保留并在选择入口可访问，不能因普通规则直接使用自动组而删除。公开模板提供单机场占位示例；私人三份 Surge 各保留七组。爱思规则集中在 `direct/aisi_direct`（仅 Personal）；Google Play 重复项复用 `google_hk`；AI DNS 用 `region/us/ai_dns_us` 绑定美国，早于设备、加密 DNS 协议和最终兜底。
