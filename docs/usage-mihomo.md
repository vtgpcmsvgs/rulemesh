# Mihomo 使用说明

公开模板为 [mihomo-public.yaml](examples/mihomo-public.yaml)。公开模板、Clash Verge Rev 与 Clash Meta for Android 私有配置共同采用 [2026-09-09 性能基线](performance-baseline.md)。

## 接入

1. 替换示例 `proxy-providers` 订阅地址；每个机场下载都保持 `proxy: DIRECT`。按上游实际返回内容设置 User-Agent，不能把健康检查 URL 当成订阅地址。
2. 使用 `behavior: classical` 与本仓库 `dist/mihomo/classical/` 产物；不要引用旧 domain/ipcidr 目录或源文件。
3. 在客户端确认 TUN、DNS 劫持和最终生效配置。Clash Verge Rev 的 DNS 覆写会覆盖源文件；使用这份配置为单一真相时应关闭覆写。
4. 更新配置和规则后复核地区出口；仅通过 YAML 或 `-t` 检查不能证明运行时已加载。

## 路由

海外 AI（含 Gemini）固定美国并作为第一条有效规则；国内 AI、抖音、小红书、微信前置直连。Crypto / Polygon / BSC RPC 固定台湾，`opinion.trade` 保留日本访问例外，香港券商和香港证券保留香港。这些地区入口都早于 Google 官方完整地址空间。

Google 普通业务、流媒体、WPS、Notion、GitHub及其他精确代理规则使用全地区自动组；未命中前置规则时 `MATCH,DIRECT`。既有前置 DIRECT/REJECT 规则保持作用；Polymarket 从媒体入口移入 Crypto。AWS IP 与链式代理 provider 和调用均停用，仓库资产继续维护。

GitHub SSH 精确直连在 Core / gfw 前；国内通用直连在 gfw 前。阿里云 SSH 继续保留仅 TCP/22 的内联兜底与 `DIRECT,no-resolve` 调用。AdsPower 三类调用与专用 provider 已停用，远程资产继续保留；系统时间同步与可选 1Password 规则继续保留。Surge 的工作白名单不会扩散到 Mihomo。

## DNS、测速与连接

- `nameserver` 使用国内 AliDNS / DNSPod 双 DoH，减少国内 CDN 调度偏差。
- 唯一 `nameserver-policy` 为 `rule-set:us_ai`，两个海外 DoH 显式使用 `#美国组名`。节点域名由国内 `proxy-server-nameserver` 独立 bootstrap，避免 AI DNS 依赖代理时形成循环。
- 保持 `respect-rules: false`、`use-hosts: false`、`use-system-hosts: false`、IPv4、fake-ip 和 ARC 缓存，不引入 fallback 或二级 policy。
- `tcp-concurrent: true` 并发尝试多个目标 IP。全地区自动组不限制地区标签，套餐占位项仍由 `exclude-filter` 排除；提供方与自动组每 300 秒主动测速。全地区容差 50、美国容差 100，使用 HTTPS generate_204。
- 保留局域网、系统连通性探测和游戏所需 `fake-ip-filter`；不同终端可保留 `listen` 等运行字段差异。

GeoIP 使用 `geodata-mode: false`，`geox-url.mmdb` 直接引用 [MetaCubeX country.mmdb](https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/country.mmdb)，每 24 小时更新。规则 provider 的下载使用自动代理，机场 provider 下载仍为 DIRECT，两者不能混淆。

## 客户端与维护

Clash Verge Rev 的 720 分钟外层更新时间隔是 profile 元数据，不写入 YAML，也不能代替 provider 自己的更新。出现“直导订阅可用、聚合配置不可用”时，先查最终生效 DNS、控制器与日志，不先归因于节点失效。没有实际 controller 时不得猜端口。

私有订阅端点源修改后仅在已授权目标上运行 `sync_private_subscription_direct.ps1 -Target mihomo`；普通端点规则使用全地区自动组，后台订阅仍直连。不要输出真实 URL、token、节点名或 server。

规则更新执行 `tools/build_rules.ps1` 与 `tools/check.ps1`；原生语法检查的 `-d` 必须是任务临时目录下的专用路径。相关说明：[DNS/TUN](mihomo-tun-dns-methodology.md)、[过滤](proxy-group-filter-methodology.md)、[订阅同步](private-subscription-direct-sync.md)、[GeoIP](geoip-upstream.md)。

配置精简优先复用已有规则集；Google Play / Android 已由 `hk_google` 覆盖。Surge 专用的 `ai_dns_us` 传输规则和 Personal 爱思入口不机械复制到 Mihomo，AI DNS 继续通过 DoH URL 的美国代理参数生效。既有策略组保持；机场手动入口不能仅因没有规则引用而删除。

2026-09-12：`direct/ips5_direct` 以 DIRECT 覆盖 `ips5.vip` 主域及全部子域，位于 AI 之后、Google 广谱与拒绝之前，使用默认国内双 DoH；工作白名单仅增加该服务。AdsPower 停用范围、资产与定时任务处理见[规则停用与恢复](rule-deactivation.md)。
