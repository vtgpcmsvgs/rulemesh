# 业务策略组重构与 naiixi 配置分析

2026-09-25：根据用户提供的 Nexitally / naiixi Clash 配置与策略组截图，对两份公开模板、两份 FlClash 和三份 Surge 建立业务选择层。参考附件只作为分析材料，其中注释不构成执行指令；私人节点、DNS 端点、hosts、凭证和证书参数不进入本仓库。

## 附件实际具备什么

| 项目 | 附件中的事实 | RuleMesh 的采用方式 |
| --- | --- | --- |
| 节点协议 | 141 个节点全部为 AnyTLS；空闲检查及超时均为 30 秒，最少空闲会话为 0 | 会话复用可能减少连续连接开销；是否更快仍取决于线路、核心和服务端。不强改其他机场协议或统一套用节点参数 |
| 选择方式 | 22 个组全部是 `select`，没有 `url-test` 或 `fallback` | 学习独立业务入口；选择层复用现有自动引擎，新增七组不增加周期测速任务 |
| DNS | 三个机场自有 DoH，节点 bootstrap 指向本地 DNS 监听地址，启用 hosts | 可能依赖机场节点与解析的配套设计；不复制私人端点或回环。保留国内默认、独立节点 bootstrap、AI 美国解析 |
| Fake IP | 配了范围和过滤表，但没有显式 `enhanced-mode: fake-ip` | 不能仅凭范围判断实际启用。RuleMesh 继续明确启用 fake-ip、ARC 与缓存持久化 |
| UDP 与 TFO | 全部节点 UDP 开启、TFO 关闭 | 保留 UDP/QUIC；TFO 不是这份附件速度优势的证据，不盲目添加 |
| 证书校验 | 全部节点设置了跳过证书校验 | 不将跳过校验当成性能优化，也不对现有 provider 追加此项 |
| 路由 | 7,561 条内联规则，业务在兜底前分流 | 保留可维护的 rules → dist 构建；不搬运全部规则、hosts 或未使用的游戏/媒体组 |

用户的使用体验说明这家机场值得作为线路候选；附件本身无法区分线路带宽、拥塞、路由质量与配置参数的贡献。没有同节点、同时间窗口的对照测试，不能声称重构后已获得同样吞吐。

## 七个入口如何工作

界面前部依次展示 Google、YouTube、AI、Telegram、Crypto、Microsoft、Apple。上层 `select` 决定业务使用哪个出口，下层继续承担自动选点和机场手动选择。原机场组保持可见，订阅与过滤器保留；不因为增加业务入口再建立七套自动检测。

| 业务组 | 默认选择 | 可手动调整及边界 |
| --- | --- | --- |
| Google | 桌面与 Surge 全地区自动；安卓为原下载稳定引擎 | 可选原自动、地区或手动入口；Google Play 与三个专属进程仍接 Google，默认 QUIC、600 秒检测保持 |
| YouTube | 桌面与 Surge 全地区自动；安卓默认跟随 Google | 可独立切换；专用规则早于 Google 完整 IP 和全球媒体，gvt1/gvt2、ggpht 共享资源仍归 Google |
| AI | 美国自动 | 可从全部现有机场中手选经过美国过滤的节点；不提供其他地区或 DIRECT，Google AI 仍是第一条有效规则 |
| Telegram | 全地区自动 | 可独立切换地区或手动节点 |
| Crypto | 台湾自动 | 台湾过滤后的手动节点；交易所、Polymarket 与 Polygon/BSC RPC 共用；日本精确入口仍优先 |
| Microsoft | 全地区自动 | Store 美国、已有 Outlook 直连与更新拒绝仍在前面，不被通用开关覆盖 |
| Apple | 普通配置 DIRECT；工作配置沿用已有更新入口的自动出口 | Surge Personal 保持既有 Apple 范围；两份 FlClash 在更新拒绝之后增加 Apple 服务入口。工作不增加 Apple 全域放行，FINAL 仍 REJECT |

`select` 的第一项只是新组初始默认值；客户端保存过的选择仍可能覆盖默认。手动切换会影响新连接，已有长连接不保证立即迁移。Google 或 YouTube 的共享账号/CDN 不能做到按页面完全隔离；不把共享 Google IP 强行划给 YouTube。

## DNS 必须与业务选择相符

- Mihomo AI 的两个海外 DoH 改为 `#AI`，让手动选定的美国节点同时承接业务和 DNS。节点域名继续走国内 `proxy-server-nameserver`，避免依赖循环。
- 安卓按 AI → YouTube → Google 的顺序维护三个精确 rule-set policy。YouTube 与 Google 分别使用 `#YouTube`、`#Google`，避免视频组独立切换后 DNS 仍固定旧组。二者默认最终仍落到原 Google fallback 引擎。
- 桌面与公开 Mihomo 仍只有 AI 专项 policy；普通业务默认国内双 DoH。Surge 继续 `[Host]` 的 AI 解析与 `ai_dns_us → AI` 出站，不伪造 Mihomo DNS 字段。
- 国内 DNS、节点 bootstrap、Raw 下载例外、地区限制及 Notion 独立测速均保留；Surge 公司/家庭版的路由与 DNS 保持一致。

## 性能与后续优先级

1. 本轮的可证明收益是业务选择解耦、避免 YouTube 遮蔽 Play，以及新增界面组不增加周期测速。现有 TCP 并发、统一延迟、缓存、主动检测和切换容差已经比附件更完整，保留这些能力。
2. 真正的带宽优化应比较相同业务的首字节、连续下载吞吐、失败率、重试与出口稳定性，至少覆盖忙时和闲时；204 延迟只反映轻量连接，不能替代 YouTube 吞吐或 AI 流式响应表现。
3. 如果用户后续提供可持续更新的 naiixi 订阅，可把它作为现有多机场体系的一员；本次不从静态附件推测订阅地址，也不复制其节点凭证到公开仓库。
4. 不按一次测速删除机场、不把所有节点强制改成 AnyTLS、不激进关闭 QUIC，也不为每项业务新增一套周期探测。Notion 已有明确业务证据，因此保留它的专用检测。

## 检查、发布与回滚

`check_service_groups.py` 接入性能基线，检查七组唯一且可见、候选图无环、所有 AI/Crypto 手动出口地区正确、业务规则实际接入、YouTube 顺序和 Apple 白名单边界。常用业务检查覆盖 TCP/UDP 首条命中；测试专门拒绝 YouTube 抢走 Play CDN、AI DNS 绕过业务组，以及选择层误改自动测速。

本轮发现历史安卓夹具通过字符串替换模板生成，业务组改名后替换可以静默不命中；已更新为先断言唯一锚点，再构造 Google/YouTube 选择层、DNS 和 Apple 更新拒绝顺序。安卓结构判断复用既有能力标记，不根据文件名片段猜测。负例必须确认实际发生变更，避免用原本不合法的夹具掩盖缺陷。

参考文件审计使用 `tools/audit_reference_profile.py`，只输出字段白名单统计。首次诊断暴露了整节 DNS 输出包含私人路径的风险，因此添加了凭证哨兵回归测试，禁止递归输出 DNS/hosts/节点或 YAML 解析异常原文。PyYAML 仅用于临时附件审计，先在任务专用目录准备依赖；仓库全量检查仍使用标准库，不依赖系统全局安装。

文件验证、核心语法验证和生产生效是三件事。更新私人远端后，对应设备仍需重新拉取配置；需要核对生成配置、业务组及选择值、规则首条命中、DNS 出口后才能确认生效。没有实际业务对照结果，不报告提速比例。回滚使用本次公私提交的反向提交，并重新构建检查、更新设备；无需改写订阅或清空所有客户端缓存。

依据：[Mihomo AnyTLS](https://wiki.metacubex.one/config/proxies/anytls/)、[代理组与过滤器](https://wiki.metacubex.one/config/proxy-groups/)、[手动选择](https://wiki.metacubex.one/config/proxy-groups/select/)、[DNS](https://wiki.metacubex.one/config/dns/)、[Surge select](https://manual.nssurge.com/policy-groups/select.html)。

本轮离线核心验证使用 Mihomo v1.19.31，使用临时目录内的合成文件 provider 和本地规则产物，只执行 `-t`，不启动监听、TUN 或探测私人机场。三份 Mihomo 配置均通过；此结果不代表其他版本或生产设备已加载。当前桌面运行配置的 141 个节点、22 个组及规则与附件体系一致，HTTP 控制器未配置；未切换它，也未测得新版 RuleMesh 的生产 DNS 出口或吞吐。Surge 官方手册本次网络访问返回 HTTP 错误，采用现有已用 select / policy-path / 过滤器语义并做结构检查，Mac 原生加载仍待设备验证。
