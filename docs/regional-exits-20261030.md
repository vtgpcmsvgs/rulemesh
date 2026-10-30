# 私人配置美国单落地迁移（2026-10-30 最终修订）

用户撤销本日早期三个出口方案，并明确要求全部私人客户端接入新美国单落地。六份文件包括两份 FlClash、Clash Mi iOS、两份 Surge Personal 与 Surge 工作白名单。香港恢复普通机场节点，不设香港链式前置。真实地址和认证仅存独立私人仓库；旧方案由 Git 历史追溯，不得拿旧测试作为本轮证据。

| 入口 | 最终路径 |
| --- | --- |
| AI、Microsoft 美国候选、Store、六地区菜单的美国 | 美国最终组 → 唯一 RM-US-Exit |
| 美国节点拨号 | RM-US-Front → 六个前置专用地区自动组 → 机场 |
| Google 默认、Notion、香港地区 | 普通香港机场；安卓保留手动 select 与历史隔离 |
| 香港券商 | 原香港-provider 自动子组 |
| 地区例外 | Crypto 台湾、日本精确入口；Microsoft DIRECT 选项保留 |
| 普通全地区自动/手动组 | 保留原用途，不限制在美国或香港 |

前置选择器控制如何连接美国落地，不改变最终出口地区。默认香港；各地区候选均只收机场，不引用业务组、最终出口或 DIRECT。桌面 300 秒、安卓/iOS 600 秒；前置 lazy true，美国容差 100、其余 50。Surge 的前置使用独立地区 url-test 与机场来源，300 秒。`RM-US-Front`、美国最终组明确可见；源文件可见性与客户端实际加载分别验收。

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

`check_android_us_chain.py` 保留历史模块名兼容调用，现验证六份私人配置的 v4 登记、唯一美国节点、节点与登记端点一致、认证、前置无环、香港无链、无旧出口和地区引用。公开模板保持机场通用方案。规则层、DNS、工作白名单的其他闸门继续执行，不以新标记跳过。

工作版此前没有 [Proxy] 节；迁移应先验证节唯一性，再补节点节，不能假定所有 Surge 文件都已有内联节点。迁移写入前检查完整结构；失败时不写该文件。已存在的桌面嗅探改动保留，不从旧版本覆盖。

早期发现桌面文件疑似截断时曾从 HEAD 恢复；复核恢复前备份、迁移前备份和企业微信任务记录，差异为该任务后来明确撤销的临时 TUN 网段排除，因此不恢复这些排除。现有企业微信嗅探排除项保留，iOS 按桌面派生。以后遇到疑似截断，应先重复读取、核对时间及哈希并保留字节备份；发现内容变化须先核对并发写入，不能直接用 git restore 覆盖工作副本。

Git 自带解析器本轮出现 getaddrinfo 线程失败；系统 DNS 可正常解析。使用当前命令的 http.curloptResolve 指定经系统解析的 GitHub 地址后 fetch 恢复，不修改永久 Git/DNS 设置。此项属于本机工具链限制。

供应商单节点 SOCKS5 HTTPS trace 实测返回登记 IP 与 US。首次握手失败后一次短重试成功，不能据此保证长期稳定或机场前置全链路。最终全量检查、三平台设备与 DNS 运行态结果必须单独记录，不把供应商直连测试写成客户端验收。

## 本轮验收记录

- 构建完成：45 份源文件、0 条告警。完整 check.ps1 和在线订阅闸门通过；回归套件共 412 项，396 项通过、16 项按环境条件跳过。六配置 DNS 优先级、链式登记和跨客户端认证一致性通过。
- 桌面、安卓、iOS 三份 YAML 均通过 Mihomo v1.19.25 原生语法检查。Surge 已完成结构检查，尚未在 Mac 内核加载验证。
- check_task_acceptance.py 的基线通过，但安卓 USB/ADB 采集失败，无本轮设备证据，整体验收失败。iPhone、Mac 和各客户端 DNS 运行态未验收。
- FlClash 桌面仍加载旧配置；导入操作遇到窗口激活失败，后续用户停止了桌面自动操作，因此没有确认新配置加载或界面显示。
- 本机回环测试环境阻止了原生 UDP 回归测试，该项跳过而非通过。供应商直连 trace 不能替代机场前置、设备 DNS、移动 Google 搜索和业务冷启动验收。
