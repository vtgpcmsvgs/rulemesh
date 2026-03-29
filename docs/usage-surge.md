# Surge 使用说明

## 推荐入口

- 个人终端版公开参考模板：[`docs/examples/surge-public.conf`](examples/surge-public.conf)
- 规则产物入口：`dist/surge/rules/`

这个模板是基于本地长期使用的 Surge 配置整理出来的公开版，保留了总开关、区域自动切换、拒绝规则、直连规则与 IP 规则的完整结构，但移除了不适合公开仓库的个人化部分。

## 版本划分

- 软路由集群版
  - 用于工作电脑集群接入软路由 Surge。
  - 可保留 `SRC-IP` 设备分流、私有订阅地址与完整 `[MITM]`。
  - 这类内容不适合入公开仓库，建议只在本地私有目录维护。
- 其中私有 `rulemesh-substore-surge-work-whitelist.conf` 当前使用工作电脑白名单模式，并与两个 `personal` 配置永久有意不一致。
- 维护这份白名单文件时请同时参考 [docs/surge-work-cluster-whitelist.md](surge-work-cluster-whitelist.md)。
- 若只新增某个白名单专属的单个直连域名，默认直接维护在 2.10“指定直连”入口，不为单条规则额外新增公开 `rules/` 文件。
- 如果本地存在需要每日刷新的私有订阅域名，统一维护在 `%USERPROFILE%\Desktop\rulemesh-local\current\private_subscription_direct.list`，再通过同步脚本分发到私有配置。
- 个人终端版
  - 用于同事个人终端或可公开分享的配置。
  - 对应本仓库的 [`docs/examples/surge-public.conf`](examples/surge-public.conf)。
  - 默认移除 `SRC-IP` 设备分流、私有订阅地址与整个 `[MITM]`。
  - 不继承工作路由白名单的 `REJECT` 兜底结构。

## 模板保留了什么

- 总开关 + 手动切换 + 自动测速切换
- 香港、台湾、日本、新加坡、美国、韩国的区域自动组
- `geoip-maxmind-url` 显式固定到与 Mihomo 共用的本仓库 Release 镜像地址
- `reject`、`direct`、`proxy`、`region` 四类 RuleMesh 产物接入
- `dns-server = system + 公共 DNS` 与 `raw.githubusercontent.com = server:system` 的 GitHub Raw 解析兜底
- `region/hk/global_media.list` 额外承接 X / Twitter 网页、短链与静态资源，并默认绑定 `🇭🇰 香港-自动选择`
- 阿里云香港 SSH 继续走 `direct/alicloud_hk_ipv4_ssh22_direct.list`；阿里云控制面 `aliyuncs.com` 与出口探测 `check.myclientip.com` 通过单条 `DIRECT` 规则显式放行
- AWS 香港区域入口已统一为 `region/hk/hk_aws_ipv4.list`
- 阿里云香港 SSH 直连入口已统一为 `direct/alicloud_hk_ipv4_ssh22_direct.list`，并继续在入口文件里直接保留 `SSH TCP/22` 条件，不要求本地配置二次拼装端口规则
- AdsPower 专项 `reject/direct/proxy` 规则集与 `proxy/gfw.list` 广谱代理规则的顺序关系
- Polygon 主网 RPC 专项 `proxy/polygon_rpc_proxy.list` 与 `proxy/gfw.list` 的顺序关系
- BSC 主网 RPC 专项 `proxy/bsc_rpc_proxy.list` 与 `proxy/gfw.list` 的顺序关系
- Google Public DNS 主 IPv4 端点专项 `proxy/google_public_dns_ipv4_proxy.list` 与 `proxy/gfw.list` 的顺序关系
- `direct/os_time_direct.list` 与其他普通直连规则的顺序关系
- `skip-proxy`、`always-real-ip`、基础 DNS 与测速参数

## 模板刻意移除了什么

- 按局域网源 IP 的设备分流（`SRC-IP` + `AND/OR`）
- 私有 `policy-path` 地址与真实机场命名
- 整个 `[MITM]` 段及证书参数
- 1Password 重度用户专项入口；如需启用，请另行接入 `proxy/onepassword_proxy.list`

## 使用前只需要替换两处

1. 把模板里所有 `https://example.com/subs/surge/all?target=Surge` 替换成你自己的 Surge 聚合订阅入口。
2. 如果你不希望最终兜底走总开关，可以把 `FINAL,🚀 节点选择` 改成你想固定兜底的区域组。

## 测速 URL 约定

- Surge 的 `internet-test-url`、`proxy-test-url`、代理 `test-url=`、`url-test / fallback / load-balance` 的 `url=` 统一保持 `http://`，不要改成 `https://`；本仓库已经踩过一次真实载入失败。
- 当前公开模板与本地私有 Surge 配置统一采用 `http://www.baidu.com`、`http://www.google.com/generate_204` 与 `http://www.gstatic.com/generate_204` 这组三段式测速基线。
- 这组值不是全网唯一标准答案，但当前更偏“轻量、稳定、便于区分直连检查和代理测速”的默认组合，因此继续保留。
- 只有测速 URL 需要强制保持 `http://`；`policy-path`、`geoip-maxmind-url`、`RULE-SET` 等普通资源 URL 仍然可以继续使用 `https://`。
- 如果后续要替换，请优先继续选择轻量、稳定、支持 HTTP HEAD 的 `http://` 目标。

## 私有订阅更新直连约定

- 真实订阅更新域名只在 `%USERPROFILE%\Desktop\rulemesh-local\current\private_subscription_direct.list` 维护，不写回公开模板
- 修改后运行 `powershell -ExecutionPolicy Bypass -File "%USERPROFILE%\Desktop\rulemesh-local\current\sync_private_subscription_direct.ps1"`，统一同步到两份 Surge 私有配置与两份 Mihomo 私有配置
- 这组规则在 Surge 私有配置中必须位于 `proxy/gfw.list` 前；在工作白名单里则属于显式放行入口
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
13. `FINAL`

注意：

- `region/tw/google_tw.list` 必须放在 `region/hk/global_media.list` 等广谱区域规则前。
- `region/hk/global_media.list` 当前还承接 `x.com`、`t.co`、`twimg.com` 与 `twitter.com` 等 X / Twitter 网页域名，默认应继续绑定 `🇭🇰 香港-自动选择`，不要再让它们回落到 `proxy/gfw.list`。
- `direct/github_ssh_direct.list` 必须放在 `proxy/gfw.list` 前，只给 `github.com:22` 与 `ssh.github.com:443` 直连，避免把 GitHub 网页误放直连。
- GitHub Raw 规则产物下载建议保留 `raw.githubusercontent.com = server:system` 与 `dns-server = system + 公共 DNS` 这组解析兜底，降低外部资源偶发超时。
- `direct/alicloud_hk_ipv4_ssh22_direct.list`、`DOMAIN-SUFFIX,aliyuncs.com,DIRECT` 与 `DOMAIN,check.myclientip.com,DIRECT` 应统一放在直连段显式维护；其后可额外保留一条阿里云广覆盖 `REJECT` 观察兜底，用于发现上游阿里云规则的漏网之鱼。
- `direct/adspower_direct.list` 与 `proxy/adspower_proxy.list` 都应放在 `proxy/gfw.list` 前，确保 AdsPower 的细分直连与节点选择优先命中。
- `proxy/polygon_rpc_proxy.list` 应放在 `proxy/gfw.list` 前，确保 Polygon 主网 RPC 域名优先走 `🚀 节点选择`。
- `proxy/bsc_rpc_proxy.list` 应放在 `proxy/gfw.list` 前，确保 BSC 主网 RPC 域名优先走 `🚀 节点选择`。
- `proxy/google_public_dns_ipv4_proxy.list` 应放在 `proxy/gfw.list` 前，确保 `8.8.8.8/32` 优先走 `🚀 节点选择`。
- 如果你是 1Password 重度用户，可额外接入 `proxy/onepassword_proxy.list`，并同样放在 `proxy/gfw.list` 前；这条规则由仓库每日自动抓取 1Password 官方支持页生成，默认只覆盖官方自有核心域名与更新/基础设施端点，详情见 [docs/onepassword-proxy-rules.md](onepassword-proxy-rules.md)。
- `reject/adspower_reject.list` 应和其他拒绝规则一起放在最前，先拦截隐私追踪与可安全阻断端点。
- `direct/os_time_direct.list` 建议放在其他普通 `direct/*.list` 前，优先保障 `time.windows.com`、`time.apple.com` 与 `time-macos.apple.com` 直连。
- 如果你希望默认禁用系统更新、升级时再临时放行，建议同时接入 `direct/os_time_direct.list`、`reject/os_update_reject.list`、`direct/microsoft_direct.list` 与 `direct/macos_update_direct.list`；平时由 `reject` 先拦截升级流量，系统时间同步仍由 `os_time_direct` 保持直连。
- `proxy/gfw.list` 建议放在其他普通 `direct/*.list` 前，减少广谱直连误伤。
- 浏览器明文 HTTP 拦截推荐直接接 `plain_http_reject.list`，不要再手写重复规则。
- 私有 `rulemesh-substore-surge-work-whitelist.conf` 是白名单例外：它保留设备分流、区域精确、GitHub SSH、GitHub Raw 下载入口、GitHub 广覆盖 `REJECT` 观察兜底、私有订阅更新直连、1Password 核心连接、AdsPower、Polygon 主网 RPC、BSC 主网 RPC、Google Public DNS 主 IPv4 端点、Cloudflare DNS、`LAN,DIRECT`、`direct/os_time_direct`、`direct/microsoft_direct`、`direct/macos_update_direct`、阿里云指定直连与 ByteDance；其中只有设备分流继续保留 `SRC-IP` 约束，并按指定 AWS 区域 / 日本 SOCKS5 IP 段定向到对应工作机亚洲出口组，后续规则不再额外限制源 IP，原独立 `IP 规则` 段已移除；`github_ssh_direct` 后保留 `DOMAIN,raw.githubusercontent.com` 下载入口，并额外用 `DOMAIN-KEYWORD,github,REJECT` 观察 GitHub 漏网之鱼；阿里云香港 SSH、`aliyuncs.com` 与 `check.myclientip.com` 统一收敛到“指定直连”段显式放行，其后额外保留一条阿里云广覆盖 `REJECT` 观察兜底；私有订阅更新直连统一从本地单一源文件同步到白名单显式放行段；`proxy/onepassword_proxy.list` 也作为白名单显式放行入口放在 `proxy/gfw` 之前；AdsPower 细分规则后额外保留一条 `DOMAIN-KEYWORD,adspower,REJECT` 广覆盖观察兜底，用来发现细分规则漏网之鱼；Google Public DNS 主 IPv4 端点之后还额外保留一条 `DOMAIN-SUFFIX,cloudflare-dns.com` 节点选择入口，用于白名单模式下显式放行 Cloudflare DNS；未命中上述入口的流量最终统一 `REJECT`。不要把公开模板里的广谱放行段机械同步回去。
- 工作白名单模式下，广覆盖观察规则统一只允许使用 `REJECT`；personal 配置即使当前风险可接受，也不应把 `DIRECT` / `PROXY + extended-matching` 这类写法继续扩散回白名单模板。
- 若只新增某个白名单专属的单个拒绝域名，或只用于阻断浏览器扩展更新链路的拒绝规则，默认直接维护在这份私有白名单的拒绝段，不为单条规则额外新增公开 `rules/` 文件。

## 使用原则

- 客户端只引用 `dist/surge/rules/`
- `rules/` 是源规则层，不建议在 Surge 配置中直接引用
- 不要在客户端继续引用第三方原始规则 URL
- GeoIP 数据库是当前例外：公开模板默认显式固定到本仓库的 Release 镜像地址
- 不要手改 `dist/`，应先改 `rules/` 后重新构建
- 私有工作路由白名单约定见 [docs/surge-work-cluster-whitelist.md](surge-work-cluster-whitelist.md)；该约定只影响本地 Surge 工作路由文件，不影响公开模板。
- 私有订阅更新直连同步约定见 [docs/private-subscription-direct-sync.md](private-subscription-direct-sync.md)；该约定同样只影响本地私有配置，不影响公开模板。
- 1Password 重度用户专项规则约定见 [docs/onepassword-proxy-rules.md](onepassword-proxy-rules.md)；公开模板默认不内置，需要时再显式接入。
- GeoIP 上游选择与维护边界见 [docs/geoip-upstream.md](geoip-upstream.md)。
