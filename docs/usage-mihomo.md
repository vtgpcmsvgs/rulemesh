# Mihomo 使用说明

公开模板为 [mihomo-public.yaml](examples/mihomo-public.yaml)。公开模板、FlClash 桌面端 与 FlClash 安卓端 私有配置共同采用 [2026-09-09 性能基线](performance-baseline.md)。

## 接入

1. 替换示例 `proxy-providers` 订阅地址；每个机场下载都保持 `proxy: DIRECT`。按上游实际返回内容设置 User-Agent，不能把健康检查 URL 当成订阅地址。
2. 使用 `behavior: classical` 与本仓库 `dist/mihomo/classical/` 产物；不要引用旧 domain/ipcidr 目录或源文件。
3. 在客户端确认 TUN、DNS 劫持和最终生效配置。FlClash 的 DNS 覆写会覆盖源文件；使用这份配置为单一真相时应关闭覆写。
4. 更新配置和规则后复核地区出口；仅通过 YAML 或 `-t` 检查不能证明运行时已加载。

## 路由

海外 AI（含 Gemini）固定美国并作为第一条有效规则；国内 AI、抖音、小红书、微信前置直连。Crypto / Polygon / BSC RPC 固定台湾，`opinion.trade` 保留日本访问例外，香港券商和香港证券保留香港。这些地区入口都早于 Google 官方完整地址空间。

WPS/金山文档按 2026-09-18 修订统一 DIRECT，继续使用默认国内 DNS，Microsoft Store 专项固定美国，通用 Microsoft 保留代理。Notion 在 Google 广谱前使用 `hk_notion` 规则集并复用香港自动选择，覆盖网页、API、公开页与图片，沿用国内 DNS；详见 [Notion 网页优化](notion-network-optimization.md)。Google、YouTube、Telegram 业务组只显示全部机场来源中的香港节点；Microsoft 业务组只显示美国节点并保留 DIRECT。GoDaddy、尊嘉证券与 supado.com 由香港优先规则集承接。未命中前置规则时 `MATCH,DIRECT`。既有前置 DIRECT/REJECT 规则保持作用；Polymarket 从媒体入口移入 Crypto。AWS IP 与链式代理 provider 和调用均停用，仓库资产继续维护。

`direct_cn_services` 固定第二条，保护国内 DNS 与新华三；AI 仅按审核后的域名边界匹配，避免名称相似网站同时进入美国出口与海外解析。Store 专项在两份 FlClash 中仍晚于既有更新拒绝。见[出口修订](scoped-egress-repair.md)。

GitHub SSH 精确直连在 Core / gfw 前；国内通用直连在 gfw 前。阿里云 SSH 继续保留仅 TCP/22 的内联兜底与 `DIRECT,no-resolve` 调用。AdsPower 三类调用与专用 provider 已停用，远程资产继续保留；系统时间同步与可选 1Password 规则继续保留。Surge 的工作白名单不会扩散到 Mihomo。

## DNS、测速与连接

- `nameserver` 使用国内 AliDNS / DNSPod 双 DoH，减少国内 CDN 调度偏差。
- 默认 `nameserver-policy` 为 `rule-set:us_ai`，两个海外 DoH 显式使用 `#AI`。安卓依次追加 `rule-set:proxy_youtube` 与 `rule-set:hk_google`，分别绑定香港的 `#YouTube`、`#Google` 选择组；桌面与公开模板仍只保留 AI policy。节点域名由国内 `proxy-server-nameserver` 独立 bootstrap，避免解析循环。
- 保持 `respect-rules: false`、`use-hosts: false`、`use-system-hosts: false`、IPv4、fake-ip 和 ARC 缓存，不引入 fallback 或二级 policy。
- `tcp-concurrent: true` 并发尝试多个目标 IP。全地区自动组不限制地区标签，套餐占位项仍由 `exclude-filter` 排除；桌面提供方与自动组每 300 秒检测、安卓每 600 秒；实际业务组主动检测，备用地区组按需检测。全地区容差 50、美国容差 100，使用 HTTPS generate_204。
- 保留局域网、系统连通性探测和游戏所需 `fake-ip-filter`；不同终端可保留 `listen` 等运行字段差异。

GeoIP 使用 `geodata-mode: false`，`geox-url.mmdb` 直接引用 [MetaCubeX country.mmdb](https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/country.mmdb)，每 24 小时更新。规则 provider 的下载使用自动代理，机场 provider 下载仍为 DIRECT，两者不能混淆。

## 客户端与维护

安卓反复出现 Play 下载转圈时，采用 [安卓下载保护](android-network-repair.md)：Google 香港节点选择组、同组海外 DNS、三个 Google 专属进程兜底，并保留 QUIC。实机已发现拒绝 UDP/443 会导致 Cronet 协议错误及下载重试，不能强制其回退 TCP。手机使用全应用 VPN，关闭系统代理与允许绕过，开启 DNS 劫持；这些开关须在 FlClash 界面设置，不能仅导入 YAML。按 [2026-09-16 修订](common-network-reliability.md)，两份 FlClash 停用阿里系强制代理，安卓共享下载管理器按目的地分流，避免其他应用的国内下载绕海外；必须实机完成整包安装，不能只测商店首页。

修改开关或恢复完整备份后，在仪表盘完整停止并启动 VPN，再验证 Android 当前 VPN 已无旧 HTTP 代理；仅核对保存值曾漏掉大智慧行情故障。可使用只读 `tools/check_android_vpn_runtime.py --adb <实际路径>`，然后复测多处原失败组件及应用重开。该运行态检查需要已授权的 USB 手机，不作为离线构建的强制步骤。


私有订阅端点源修改后仅在已授权目标上运行 `sync_private_subscription_direct.ps1 -Target mihomo`；官网和共用端点使用全地区自动组，订阅专用端点使用 DIRECT；后台订阅始终由 provider 的 `proxy: DIRECT` 保证直连。不要输出真实 URL、token、节点名或 server。

规则更新执行 `tools/build_rules.ps1` 与 `tools/check.ps1`；原生语法检查的 `-d` 必须是任务临时目录下的专用路径。相关说明：[DNS/TUN](mihomo-tun-dns-methodology.md)、[过滤](proxy-group-filter-methodology.md)、[订阅同步](private-subscription-direct-sync.md)、[GeoIP](geoip-upstream.md)。

配置精简优先复用已有规则集；Google Play / Android 已由 `hk_google` 覆盖。Surge 专用的 `ai_dns_us` 传输规则和 Personal 爱思入口不机械复制到 Mihomo，AI DNS 继续通过 DoH URL 的美国代理参数生效。既有策略组保持；机场手动入口不能仅因没有规则引用而删除。

2026-09-12：`direct/ips5_direct` 以 DIRECT 覆盖 `ips5.vip` 主域及全部子域，位于 AI 之后、Google 广谱与拒绝之前，使用默认国内双 DoH；工作白名单仅增加该服务。AdsPower 停用范围、资产与定时任务处理见[规则停用与恢复](rule-deactivation.md)。

2026-09-12 FlClash 迁移与优化以 [客户端性能基线](flclash-performance.md) 为准：桌面和安卓使用新文件名；通用末尾改为 cn_direct_light → gfw_precise → DIRECT，完整规则资产保留。工作白名单不接入新兜底，机场手动组保留。桌面 300 秒、安卓 600 秒，备用地区按需检测；以最终生成配置核对界面覆写。

## 业务组选择（2026-09-25）

Google、YouTube、Telegram、AI、Crypto、Microsoft、Apple 可独立选择出口。Google/YouTube/Telegram 只展示香港节点，Microsoft 只展示美国节点并保留 DIRECT；AI/台湾 Crypto 可手选限定地区节点。provider 更新仍 DIRECT。Apple 默认直连，私人 FlClash 保持更新拒绝优先。Store 美国与已有 Outlook 直连例外不受 Microsoft 通用选择覆盖。

AI DoH 使用 #AI；安卓额外按 YouTube → Google 配置各自 DNS 出口，分别跟随香港业务组。桌面不新增视频 DNS policy。新组第一项是初始默认，保存选择可能覆盖；下载速度与 204 延迟须分别验收。详见 [重构说明](service-groups-refactor.md)。
