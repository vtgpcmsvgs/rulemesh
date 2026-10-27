# Mihomo 使用说明

2026-10-24 私人安卓新增用户明确授权的美国五出口链式例外；机场作为前置、五条 SOCKS5 作为最终出口，Google 仍默认香港。任务收尾须运行统一入口并分别验证订阅、真实 Chrome、DNS 与五出口连通和美国地区；用户要求信任这五 IP，不检测纯净度。缺少必要设备证据不算通过；步骤与边界见 [任务收尾验收](task-acceptance.md)。公开模板与其他客户端行为不变。

iPhone 的 Clash Mi 使用独立 `rulemesh-clashmi-ios.yaml`，不要套用安卓应用进程规则。它保留桌面分流与 DNS 基线，测速周期 600 秒，TUN 交给应用管理；关闭 DNS/规则/代理组覆写并保留 TUN 覆写。阿里云 SSH 的 ASN 兜底转换为精确网段内联快照。导入、派生维护与设备验收见 [Clash Mi iOS](clashmi-ios.md)。此专项不改变公开模板。

公开模板为 [mihomo-public.yaml](examples/mihomo-public.yaml)。公开模板、FlClash 桌面端 与 FlClash 安卓端 私有配置共同采用 [2026-09-09 性能基线](performance-baseline.md)。

## 接入

私人配置使用 `rulemesh-flclash-desktop.yaml`、`rulemesh-flclash-android.yaml` 与派生的 `rulemesh-clashmi-ios.yaml`。重命名后已有文件路径或订阅链接需改用新名称；桌面、安卓和 iOS 各自的 DNS 与应用设置保持。

1. 替换示例 `proxy-providers` 订阅地址；每个机场下载都保持 `proxy: DIRECT`。按上游实际返回内容设置 User-Agent，不能把健康检查 URL 当成订阅地址。
2. 使用 `behavior: classical` 与本仓库 `dist/mihomo/classical/` 产物；不要引用旧 domain/ipcidr 目录或源文件。
3. 在客户端确认 TUN、DNS 劫持和最终生效配置。FlClash 的 DNS 覆写会覆盖源文件；使用这份配置为单一真相时应关闭覆写。
4. 更新配置和规则后复核地区出口；仅通过 YAML 或 `-t` 检查不能证明运行时已加载。

## 路由

海外 AI（含 Gemini、GPTZero）固定美国并作为第一条有效规则；GPTZero 的 `gptzero.me` 及子域复用 `us_ai` 和 `rule-set:us_ai` 专用 DNS policy，更新规则 provider 后覆盖。国内 AI、抖音、小红书、微信前置直连。Crypto / Polygon / BSC RPC 固定台湾，`opinion.trade` 保留日本访问例外，香港券商和香港证券保留香港。这些地区入口都早于 Google 官方完整地址空间。

香港券商统一由 `hk_securities` 规则集和“香港券商”策略组承接；AI、Crypto、Microsoft、香港券商按 provider 使用独立 `url-test` 子组，Microsoft 父组使用 `select`。Google、YouTube、Telegram、Apple 复用六个地区自动组。安卓已移除“Google 下载稳定”组，Google 下载相关规则统一进入 Google 业务组。

WPS/金山文档按 2026-09-18 修订统一 DIRECT，继续使用默认国内 DNS，Microsoft Store 专项固定美国，通用 Microsoft 保留美国代理候选并追加 DIRECT。Notion 在 Google 广谱前使用 `hk_notion` 规则集并复用香港自动选择，覆盖网页、API、公开页与图片，沿用国内 DNS；详见 [Notion 网页优化](notion-network-optimization.md)。Google、YouTube、Telegram、Apple 展示香港、台湾、日本、韩国、新加坡、美国六个地区自动组；Apple 在六地区选项后追加 DIRECT。AI 与 Microsoft 按 provider 保留美国自动子组，Crypto 按 provider 选择台湾节点，香港券商按 provider 选择香港节点，AI、Crypto、香港券商不提供 DIRECT；Microsoft 父组使用 select，手动选择美国子组或 DIRECT。AI 中转站使用 `multi_ai_relay`，支付与加密支付使用 `multi_payment_crypto`，住宅代理与住宅代理 API 使用 `multi_residential_proxy`，三者绑定全地区自动选择。GoDaddy 由香港优先规则集承接；尊嘉证券优先命中统一香港券商规则集；supado.com 已迁入 `multi_ai_relay`。未命中前置规则时 `MATCH,DIRECT`。既有前置 DIRECT/REJECT 规则保持作用；Polymarket 从媒体入口移入 Crypto。AWS 地区 IP 与链式代理资产、provider、内联节点及拨号引用已删除。

中转规则已补充 `easyapis.cc`、`ccapi.us` 与截图核实的第三方中转/聚合网关，见[逐项分类](ai-relay-classification.md)。OpenRouter 从 `us_ai` 迁入 `multi_ai_relay`，使用全地区自动选择；`rule-set:us_ai` 的 DNS policy 不再覆盖它，沿用默认国内 DNS。原生模型 API 与纯推理/算力平台不并入中转规则，共用母域只登记确认的服务主机。

2026-10-21 核对 CC Switch 赞助页后，再补齐 AIGoCode、ClaudeCN、GrooRoute、SudoCode.us、XycAi、EveryAPI、AllTokens 的 11 条官网/API/备用规则。既有 `multi_ai_relay` 继续绑定全地区自动选择和默认国内 DNS；更新 provider 资源后覆盖新域名，具体访问限制见分类文档。

`direct_cn_services` 固定第二条，保护国内 DNS 与新华三；AI 仅按审核后的域名边界匹配，避免名称相似网站同时进入美国出口与海外解析。Store 专项在两份 FlClash 中仍晚于既有更新拒绝。见[出口修订](scoped-egress-repair.md)。

GitHub SSH 精确直连在 Core / gfw 前；国内通用直连在 gfw 前。阿里云 SSH 继续保留仅 TCP/22 的内联兜底与 `DIRECT,no-resolve` 调用。2026-10-23：Webshare 网站与其他 24 个住宅代理网站域名保留；删除 ips5 专项直连、五份 AWS 地区 IP、链式 SOCKS5 与阿里系强制代理的源规则、登记、专用同步代码及产物。私有链式节点、负载均衡池和拨号引用一起清理。1Password 官方快照合并到 proxy/general_proxy，Polygon/BSC RPC 快照合并到 region/tw/crypto_tw，继续上游更新；通用代理与 Crypto 台湾出口、默认国内 DNS 保持。AdsPower 资产继续保持删除。 删除专项入口后按其余规则处理。Surge 工作白名单不扩散到 Mihomo。

## DNS、测速与连接

- `nameserver` 使用国内 AliDNS / DNSPod 双 DoH，减少国内 CDN 调度偏差。
- 默认 `nameserver-policy` 为 `rule-set:us_ai`，两个海外 DoH 显式使用 `#AI`。安卓依次追加 `rule-set:proxy_youtube` 与 `rule-set:hk_google`，绑定 `#YouTube`、`#Google` 选择组，默认均为香港（2026-10-24 用户确认）；桌面与公开模板仍只保留 AI policy。节点域名由国内 `proxy-server-nameserver` 独立 bootstrap，避免解析循环。
- 保持 `respect-rules: false`、`use-hosts: false`、`use-system-hosts: false`、IPv4、fake-ip 和 ARC 缓存，不引入 fallback 或二级 policy。
- `tcp-concurrent: true` 并发尝试多个目标 IP。全地区自动组不限制地区标签，套餐占位项仍由 `exclude-filter` 排除；桌面提供方与自动组每 300 秒检测、安卓每 600 秒；实际业务组主动检测，备用地区组按需检测。全地区容差 50、美国容差 100，使用 HTTPS 连通性探测；Microsoft 父组为 select，不设置组级测速字段。
- 保留局域网、系统连通性探测和游戏所需 `fake-ip-filter`；不同终端可保留 `listen` 等运行字段差异。

GeoIP 使用 `geodata-mode: false`，`geox-url.mmdb` 直接引用 [MetaCubeX country.mmdb](https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/country.mmdb)，每 24 小时更新。规则 provider 的下载使用自动代理，机场 provider 下载仍为 DIRECT，两者不能混淆。

## 客户端与维护

安卓反复出现 Play 下载转圈时，采用 [安卓下载保护](android-network-repair.md)：Google 六地区选择组（2026-10-24 用户确认默认香港自动）、同组海外 DNS、三个 Google 专属进程兜底，并保留 QUIC。Google 普通入口还须用移动 UA 验证最终主机与搜索表单，拒绝把 `google.cn/m` 跳转或 204 测速当成正常搜索。实机已发现拒绝 UDP/443 会导致 Cronet 协议错误及下载重试，不能强制其回退 TCP。手机使用全应用 VPN，关闭系统代理与允许绕过，开启 DNS 劫持；这些开关须在 FlClash 界面设置，不能仅导入 YAML。按 [2026-09-16 修订](common-network-reliability.md)，两份 FlClash 停用阿里系强制代理，安卓共享下载管理器按目的地分流，避免其他应用的国内下载绕海外；必须实机完成整包安装，不能只测商店首页。

修改开关或恢复完整备份后，在仪表盘完整停止并启动 VPN，再验证 Android 当前 VPN 已无旧 HTTP 代理；仅核对保存值曾漏掉大智慧行情故障。可使用只读 `tools/check_android_vpn_runtime.py --adb <实际路径>`，然后复测多处原失败组件及应用重开。该运行态检查需要已授权的 USB 手机，不作为离线构建的强制步骤。


私有订阅端点源修改后仅在已授权目标上运行 `sync_private_subscription_direct.ps1 -Target mihomo`；官网和共用端点使用全地区自动组，订阅专用端点使用 DIRECT；后台订阅始终由 provider 的 `proxy: DIRECT` 保证直连。不要输出真实 URL、token、节点名或 server。

规则更新执行 `tools/build_rules.ps1` 与 `tools/check.ps1`；原生语法检查的 `-d` 必须是任务临时目录下的专用路径。相关说明：[DNS/TUN](mihomo-tun-dns-methodology.md)、[过滤](proxy-group-filter-methodology.md)、[订阅同步](private-subscription-direct-sync.md)、[GeoIP](geoip-upstream.md)。

配置精简优先复用已有规则集；Google Play / Android 已由 `hk_google` 覆盖。Surge 专用的 `ai_dns_us` 传输规则和 Personal 爱思入口不机械复制到 Mihomo，AI DNS 继续通过 DoH URL 的美国代理参数生效。既有策略组保持；机场手动入口不能仅因没有规则引用而删除。


2026-09-12 FlClash 迁移与优化以 [客户端性能基线](flclash-performance.md) 为准：桌面和安卓使用新文件名；通用末尾改为 cn_direct_light → gfw_precise → DIRECT，完整规则资产保留。工作白名单不接入新兜底，机场手动组保留。桌面 300 秒、安卓 600 秒，备用地区按需检测；以最终生成配置核对界面覆写。

## 业务组选择（2026-09-25）

2026-09-27 业务选择约定：Google、YouTube、Telegram、Apple 使用 select，手动选择香港、台湾、日本、韩国、新加坡、美国六个地区自动组，Apple 另追加 DIRECT。六地区组均为 url-test，覆盖所有 provider 的对应地区节点。AI 与 Microsoft 共享“美国-provider”自动子组；Microsoft 在所有配置中使用 select，手动选择美国子组或 DIRECT；AI、Crypto、香港券商仅两份私人 Mihomo 的父组使用 select，其余配置保留 url-test；Crypto 引用“台湾-provider”，香港券商引用“香港-provider”。这些子组均为 url-test，逐一对应机场来源；私人配置每个固定地区业务有七个子组。Surge 父组必须用显式成员名称，不能用 include-other-group 代替，否则会展开为节点列表。隐藏状态不再作为功能验收条件。DNS、规则顺序、Store 美国及工作白名单边界保持。

Apple 与其他三个手动入口不设置周期测速字段；实际地区与 provider 子组沿用 HTTPS Google 204 探测，私人 FlClash 更新拒绝仍优先。

AI DoH 使用 #AI；安卓额外按 YouTube → Google 配置各自 DNS 出口，分别跟随对应业务组。桌面不新增视频 DNS policy。新组第一项是初始默认，保存选择可能覆盖；下载速度与 204 延迟须分别验收。详见 [重构说明](service-groups-refactor.md)。

2026-10-24 安卓香港隔离归因复核：五条历史香港隔离项继续保留；现存矩阵能确认三条受信 302 跳转 google.cn，另两条只有超时证据，不能统称五条已证实跳转。三条确认项在私人安卓对应 provider 的 exclude-filter 中按完整名称排除，登记来源和证据于 x-rulemesh-android-provider-quarantine；不删除整个 provider，其他客户端不变。香港业务仍手动固定已验收线路，前置专用香港自动组与之分离；新节点或同名节点更换出口后仍需移动搜索实测。详见 docs/android-network-repair.md。
