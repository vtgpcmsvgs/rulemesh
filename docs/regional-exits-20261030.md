# 私人配置美国单落地迁移（2026-10-31 前置仅美国）

用户撤销 2026-10-30 早期三个出口方案，并明确要求全部私人客户端接入新美国单落地。六份文件包括两份 FlClash、Clash Mi iOS、两份 Surge Personal 与 Surge 工作白名单。香港恢复普通机场节点，不设香港链式前置。真实地址和认证仅存独立私人仓库；旧方案由 Git 历史追溯，不得拿旧测试作为本轮证据。

| 入口 | 最终路径 |
| --- | --- |
| AI、Microsoft 美国候选、Store、六地区菜单的美国 | 美国最终组 → 唯一 RM-US-Exit |
| 美国节点拨号 | RM-US-Front → 用户手动选定的美国机场节点 |
| Google 默认、Notion、香港地区 | 普通香港机场；安卓保留手动 select 与历史隔离 |
| 香港券商 | 原香港-provider 自动子组 |
| 地区例外 | Crypto 台湾、日本精确入口；Microsoft DIRECT 选项保留 |
| 普通全地区自动/手动组 | 保留原用途，不限制在美国或香港 |

前置选择器控制如何连接美国落地，不改变最终出口地区。按用户最新要求，只显示一个 `RM-US-Front`，直接手动选择美国机场节点，不新增前置地区组。Mihomo 保留全部已登记 provider 的 use 列表并增加美国 filter，Surge 用 include-other-group 展开七个机场来源、include-all-proxies=0 和美国 policy-regex-filter；均排除套餐占位项，不含业务组、最终出口或 DIRECT。机场更新和健康检测沿用各客户端既有周期。

美国最终组显式隐藏，历史名称“美国-自动选择”仅保留兼容业务引用；它只封装一个 RM-US-Exit，并没有多 IP 自动切换。RM-US-Exit 是美国 SOCKS5 落地本身，不是前置。界面只需在 RM-US-Front 选一次美国机场节点，AI 和 Microsoft 的美国候选就会共享该前置。首次加载按美国候选顺序选节点；已保存的非美国节点须在更新后重新选择。源文件可见性与客户端实际加载分别验收。

2026-10-31 纠正：此前简化只去掉了地区子组，因缺少国家过滤，前置展开了各机场全部地区。此次保留全部来源并单独限制美国标签：美国国旗、美国、United States、独立 US（不区分大小写），US 必须有词边界，避免 RUSSIA、AUS、BUS 误入。已核对 provider 名称前后缀不会引入美国标签；测试拒绝缺失过滤、全地区过滤、香港过滤以及运行态中的非美国候选。标签筛选不是实际 IP 地理位置验证，线路与 DNS 出口仍需实机验收。

美国只有一成员，不再做流量分摊。Mihomo 保留单节点 `load-balance` 封装与 `udp: false`：TCP-only Selector 的 SupportUDP=false 可能导致匹配器跳过规则并落入 DIRECT，单节点 LB 保持匹配后失败。禁止 disable-udp。Surge 的单节点 select 使用 SOCKS5 underlying-proxy，显式 `udp-relay=false` 和 `[General] udp-policy-not-supported-behaviour = REJECT`。UDP 能力未经确认，不虚报支持；TCP 回退、语音、视频须实机验收。

默认国内 DNS、AI 海外 DoH 经美国出口、安卓 Google/YouTube DNS 跟随业务选择保持。供应商端点是 IP，无新增节点域名 bootstrap。工作版只调整既有美国入口的代理路径，规则节、白名单、最终 REJECT 不扩大。iOS 先构建再由桌面派生，保留 600 秒、进程 off、应用管理 TUN 和 DNS 基线。

## 官方依据

本轮读取 Surge 官方当前手册，旧 /policy/ 路径已经失效，改用目录导航确认的 /policies/ 路径：

- [Surge 链式代理和策略组前置](https://manual.nssurge.com/policies/parameters.html)
- [Surge SOCKS5 认证格式](https://manual.nssurge.com/policies/socks5.html)
- [Surge 不支持 UDP 的拒绝行为](https://manual.nssurge.com/policies/udp.html)
- [Mihomo dialer-proxy](https://wiki.metacubex.one/config/proxies/dialer-proxy/)
- [Mihomo 负载均衡](https://wiki.metacubex.one/config/proxy-groups/load-balance/)

## 检查与本次问题处置

`check_android_us_chain.py` 保留历史模块名兼容调用，现验证六份私人配置的 v5 登记、唯一美国节点、节点与登记端点一致、认证、前置无环、香港无链、无旧出口和地区引用。公开模板保持机场通用方案。规则层、DNS、工作白名单的其他闸门继续执行，不以新标记跳过。

用户反馈前置卡片过多的原因是先前将六个辅助地区组全部设为可见。此次直接删除六组并隐藏唯一出口包装；回归检查拒绝恢复任何“前置-”策略组，且只允许前置直接引用机场来源。不能仅隐藏辅助组就声称已经删除，也不能用通用业务组替代而引入循环。

工作版此前没有 [Proxy] 节；迁移应先验证节唯一性，再补节点节，不能假定所有 Surge 文件都已有内联节点。迁移写入前检查完整结构；失败时不写该文件。已存在的桌面嗅探改动保留，不从旧版本覆盖。

早期发现桌面文件疑似截断时曾从 HEAD 恢复；复核恢复前备份、迁移前备份和企业微信任务记录，差异为该任务后来明确撤销的临时 TUN 网段排除，因此不恢复这些排除。现有企业微信嗅探排除项保留，iOS 按桌面派生。以后遇到疑似截断，应先重复读取、核对时间及哈希并保留字节备份；发现内容变化须先核对并发写入，不能直接用 git restore 覆盖工作副本。

Git 自带解析器本轮出现 getaddrinfo 线程失败；系统 DNS 可正常解析。使用当前命令的 http.curloptResolve 指定经系统解析的 GitHub 地址后 fetch 恢复，不修改永久 Git/DNS 设置。此项属于本机工具链限制。

供应商单节点 SOCKS5 HTTPS trace 实测返回登记 IP 与 US。首次握手失败后一次短重试成功，不能据此保证长期稳定或机场前置全链路。最终全量检查、三平台设备与 DNS 运行态结果必须单独记录，不把供应商直连测试写成客户端验收。

## 单落地迁移验收记录（前置简化前）

- 构建完成：45 份源文件、0 条告警。完整 check.ps1 和在线订阅闸门通过；回归套件共 412 项，396 项通过、16 项按环境条件跳过。六配置 DNS 优先级、链式登记和跨客户端认证一致性通过。
- 桌面、安卓、iOS 三份 YAML 均通过 Mihomo v1.19.25 原生语法检查。Surge 已完成结构检查，尚未在 Mac 内核加载验证。
- check_task_acceptance.py 的基线通过，但安卓 USB/ADB 采集失败，无本轮设备证据，整体验收失败。iPhone、Mac 和各客户端 DNS 运行态未验收。
- FlClash 桌面仍加载旧配置；导入操作遇到窗口激活失败，后续用户停止了桌面自动操作，因此没有确认新配置加载或界面显示。
- 本机回环测试环境阻止了原生 UDP 回归测试，该项跳过而非通过。供应商直连 trace 不能替代机场前置、设备 DNS、移动 Google 搜索和业务冷启动验收。

## 单前置界面简化复验（2026-10-30）

六份私人配置均采用 v5：一个可见 RM-US-Front、零个“前置-地区”组、隐藏的单成员美国最终组。规则、DNS、机场来源、落地认证与香港业务路径未改变。iOS 在构建后重新派生；三份 YAML 通过 Mihomo v1.19.25 原生语法检查。

本轮 check_task_acceptance.py 已重新执行完整 check.ps1：基线与在线订阅闸门通过，测试套件共 412 项。安卓仍因 UsbAdbError 没有设备证据，整体验收失败；Mac、iPhone 及设备 DNS 出口未验收。桌面加载操作被用户停止，当前应用是否已更新到 v5 须另行确认。

针对截图的超时，供应商 SOCKS5 直连 HTTPS trace 返回 HTTP 200、登记 IP 与 US；当前桌面代理端口上的 AI trace 请求则发生 TLS 握手失败，HTTP 状态为 0。运行配置没有 HTTP 控制器或控制器管道，无法取得实际链路与 DNS 请求证据；没有更换线路或把超时判为已修复。隐藏出口包装仅简化界面，不改变连接健康状态。

## 前置仅美国复验（2026-10-31）

六份私人配置的登记维持 v5，front-mode 改为 airport-us-select；前置同时具有美国筛选与原有占位排除。7 家 provider 的当前订阅均保留，按桌面规则筛出 79 个美国标签节点，每家均有候选。首次订阅读取失败，重新下载后全部 HTTP 200；未将旧缓存当成本轮证据。该计数只证明订阅内容及标签筛选，不证明节点存活或真实地理位置。

构建与 iOS 重新派生完成，三份 Mihomo YAML 原生语法通过。完整 check.ps1、413 项测试套件和在线订阅闸门通过；收尾入口仍因安卓 UsbAdbError 无设备证据而失败。配置 DNS 内容保持原样，设备 DNS 与客户端实际导入尚未验收；此前桌面 TLS 问题没有在本轮宣称修复。
