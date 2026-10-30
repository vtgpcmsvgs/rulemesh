# 私人安卓三出口迁移（2026-10-30）

本次针对原持有五个美国链式落地的 `rulemesh-flclash-android.yaml`。旧五出口全部退役，替换为用户登记的两个美国 Comcast 和一个香港 Lumen SOCKS5。真实 IP、认证信息和供应商身份仅保存在独立私人仓库。本次不新建源规则、上游登记或公开订阅，不将私人链式配置扩散到其他客户端。

## 拓扑与地区边界

| 业务/入口 | 最终路径 |
| --- | --- |
| AI、Microsoft 美国候选、Microsoft Store、六地区菜单中的美国 | 美国地区 `load-balance` → 两个 Comcast |
| Google 默认、Notion、用户香港专项、香港券商、六地区菜单中的香港 | 香港地区单节点 `load-balance` → 唯一 Lumen |
| 三个 SOCKS5 的拨号 | 可见 `RM-US-Front` → 六个前置专用地区 `url-test` → 机场 provider |
| 地区例外 | Crypto 台湾、日本精确入口保持；Microsoft 的 DIRECT 仍为显式选项 |
| 通用自动/手动机场组 | 延续非固定地区业务用途；不承诺这些入口最终落在某一地区 |

保留两个历史地区组名称兼容规则和 DNS 引用。香港券商同时迁移，删除过时的香港-provider 最终子组；不能只替换 Google 共享香港组。前置只含机场，最终组只含购买的落地，完整候选图不得形成环。机场前置健康不等于完整 SOCKS5 链路健康。

美国采用 `consistent-hashing`，按目标主域名稳定分配到两个节点，并按存活状态选择。它不保证每个网站都用两个 IP，也不保证每段时间严格 50/50；这是为避免同一站点连接频繁换 IP 选择的取舍。`tolerance` 是 URL-test 的防抖参数，不放进负载均衡组。两节点同时失效不会加入机场或 DIRECT 最终出口。

前置保留可见手动地区选择，默认香港；六地区子组自动测速，600 秒、lazy true，美国容差 100、其余 50。原名 `RM-US-Front` 现在由美国和香港三条链共用，仅为兼容保留，不增加额外网络跳数。

## DNS 和协议能力

普通业务维持国内 DoH，AI 专用 DoH 通过美国组，安卓 Google 专用 DoH 通过香港业务组。节点域名仍使用独立国内 bootstrap；不改 `respect-rules`、hosts、IPv6 或规则优先级。配置层的 DNS 路径核对与实际设备的 DNS 连接证据分别报告。

三条 SOCKS5 均按已确认的 TCP 能力设置 `udp: false`。香港采用单节点负载均衡封装：Mihomo v1.19.25 的 Selector 向上传递节点的 `SupportUDP=false`，路由匹配会继续下一条规则，最终可能落入 DIRECT；LoadBalance 保持匹配，UDP 在不支持的落地处失败。不得在美国/香港组设置 `disable-udp: true`，否则会重新引入规则跳过。不宣称 QUIC、语音视频或 Google/Cronet 已通过实机验证；保留既有无全局 UDP 拒绝的规则并不赋予节点 UDP 能力。

## 设计依据

依据 Mihomo 官方资料与当前设备基线版本源码核对：

- https://wiki.metacubex.one/config/proxy-groups/load-balance/
- https://wiki.metacubex.one/config/proxies/dialer-proxy/
- https://raw.githubusercontent.com/MetaCubeX/mihomo/v1.19.25/adapter/outboundgroup/loadbalance.go
- https://raw.githubusercontent.com/MetaCubeX/mihomo/v1.19.25/hub/route/proxies.go
- https://raw.githubusercontent.com/MetaCubeX/mihomo/v1.19.25/tunnel/tunnel.go
- https://raw.githubusercontent.com/MetaCubeX/mihomo/v1.19.25/adapter/outboundgroup/selector.go

官方负载均衡实现按目标主域名哈希、检查节点存活；LoadBalance 没有 Selector 的 Set 接口，也没有 URLTest 的 fixed/now 语义。验收不能通过 PUT 强行切换它，再把 200/204 或配置中的 IP 当成观测结果。

## 验证与防回归

- 结构检查覆盖三节点、唯一公网身份、端口、认证、地区组成员、香港券商、可见性及所有前置候选；只有完整验证的登记节点可取得地区语义。
- 实机探测从真实 AI / Notion 业务 trace 读取 IP 和地区，并在请求期间记录链上的新返回字节；不修改生产路由或切换负载均衡组。若自然哈希未覆盖两个美国节点、trace 不可用或设备断开，则失败/未验收，禁止虚构完整性。
- 用户只确认了两个美国端口的地区，未确认各自 IP 顺序。验证以用户指定的美国 IP 集合加两个不同实际公网 IP 为准，不猜测端口与 IP 的对应顺序。
- 香港 Google 200、静态登记和机场延迟不能代替香港公网 IP；三出口均有同样严格的运行态身份要求。纯净度检测沿用用户此前不检测的约定。
- 保留五出口历史记录用于追溯，历史成功不能替代本轮结果。收尾入口见 `task-acceptance.md`。

本轮本地检查同时遇到既有桌面企业微信块的域名与 Windows 进程混排，导致待提交的 iOS 派生器严格匹配失败。配套修复仅剥离明确登记的 Windows 进程，保留已存在的目的地域名；未知域名、未知进程及缺少替代入口仍拒绝。对应回归防止为通过检查而丢失已有用户规则。该既有桌面/iOS 工作与本次安卓迁移分别保留，不混入出口迁移提交。

## 本轮可确认的结果

供应商三端口通过带认证的 SOCKS5 实际请求核对，得到用户指定集合中的三个不同公网 IP，地区为两美国一香港，登记端口对应无需调整。此项是供应商端口测试，不冒充手机上的机场前置链路验收。

官方 Mihomo v1.19.25 下载资产经发布方 SHA-256 校验，在任务专用临时目录执行完整安卓配置 `-t` 成功。完整本地检查及强制在线订阅闸门的结果以本轮验收报告为准。第一轮一次订阅传输失败在后续完整检查中恢复，未因此改动 provider 或豁免闸门。

新增 `test_chain_udp_native.py` 可用已验证的原生 CLI 做回环正反对照。本机甚至 Python 自建 TCP 监听器的回环连接都超时，故该运行回归标记环境跳过，不能算作 UDP 无泄漏实测成功。香港单节点 LB 方案当前依据官方路由/组实现及静态约束；更换内核后须重新执行该原生回归。

本轮 USB 设备连接返回 `UsbAdbError`，因此未导入或重载手机配置，手机 VPN、Chrome、DNS 实际出口和三条机场前置链路仍未验收；收尾入口明确返回失败。Git 发布与设备加载分别报告，不将更新后的源文件当作已运行的配置。
