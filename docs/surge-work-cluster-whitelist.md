# Surge 工作路由白名单约定

仅适用于私有 `rulemesh-substore-surge-work-whitelist.conf`。它长期独立于两份 Surge Personal、两份 Mihomo 与公开模板；不得为了统一模板取消白名单。

## 当前放行边界

用户最新性能要求适用于已允许的连接，详见 [性能基线](performance-baseline.md)。固定工作电脑仍执行 `FINAL,REJECT`，保留既有设备条件，公开文档不得记录真实源地址、设备标识、订阅或 MITM。

1. AI（含 Google AI）第一条规则固定美国。
2. 抖音和新增微信、小红书精选入口前置 DIRECT，不增加整个腾讯或中国通用白名单。
3. 日本明确访问例外、Crypto 台湾、香港券商香港先于 Google 通用入口。
4. Google 普通业务与完整地址空间、WPS 和其他已批准代理入口自动择优。
5. 保留既有拒绝、设备条件、GitHub SSH/Raw/Core、1Password、AdsPower、订阅端点、Polygon/BSC RPC、DNS、LAN、系统时间和指定直连。
6. 其余连接最终 `FINAL,REJECT`。

AWS IP 与链式 SOCKS5 设备分流调用已停用；仓库源规则与产物保留。其他设备条件不扩大成全流量放行。阿里业务的既有源地址条件保留，出口改为自动组。

## 精确维护约定

- 不接入 `proxy/gfw`、`direct/cn_direct`、网易或哔哩哔哩广谱直连。Personal 的 Apple、Outlook、Notion、personal_priority、香港证券增强和 Microsoft Store 专项不复制进工作文件。
- WPS 保留显式入口，自动代理并早于最终拒绝。`zsxq.com`、`yikaiying.com` 的既有精确 DIRECT 继续保留。
- GitHub SSH carve-out、Raw 下载、Core 规则和已有 GitHub 广覆盖观察项独立保留；AdsPower 三类规则与已有观察兜底也保持原动作。不得把观察规则因去重而删除或扩大放行。
- 订阅源只在私人目录维护，起止标记必须保留。`-Target surge` 同步浏览器自动代理例外和普通订阅更新 DIRECT；其他客户端不因共享源顺带改动。
- Polygon/BSC RPC 与 Crypto 同属台湾出站；1Password 和其他无地区要求的白名单代理用自动组。
- 阿里云 SSH 保留 TCP/22 内联兜底、远程 `DIRECT,no-resolve` 与指定控制面、出口探测直连；不扩展端口或恢复阿里云广谱放行。
- 系统时间继续 DIRECT；Windows/macOS 更新仍先受既有拒绝规则控制，放行后使用自动代理。禁止通过 skip-proxy 绕过 Apple 17/8 的规则判断。

## DNS 与运行时

普通业务采用国内双 DoH；AI 在 Host 中单独使用 Cloudflare DoH，并由独立域名规则走美国。保留 GitHub Raw 海外 Host 解析、节点 DOMAIN-SET bootstrap、hijack-dns、代理侧解析及加密 DNS 遵守出站。

小型 cn_dns_domains 引用可保留，不替换为性能型清单。DNS 解析本身不授予白名单放行。国内 DoH 端点显式 DIRECT，其他加密 DNS 入口保持白名单规则；Cloudflare 是 AI 解析美国例外，其余默认自动代理。

Surge Enhanced Mode 由客户端启用，profile 不写 dns-mode；保留 localhost.weixin.qq.com 精确回环例外、IPv4 与关闭额外 Wi-Fi 代理入口。GeoIP 改用 MetaCubeX 直接上游。

## 联动

每次修改白名单逻辑同步本文件、README、使用说明与私有配置；验证最终拒绝、精确放行、同步标记和地区例外。通用性能调整不授权扩大设备或业务范围。安装在 Mac 的只读监控遵守原有两阶段审批，不自动执行配置变更。
