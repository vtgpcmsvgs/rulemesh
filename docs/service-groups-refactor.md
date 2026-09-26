# 业务策略组重构与 naiixi 配置分析

## 2026-09-26 FlClash 导入修复

新增 provider 测速组的双引号正则曾将词边界 `\b` 写为 YAML 退格转义；原文件没有裸控制字符，但 YAML 解码后出现 U+0008，客户端再次处理配置时会拒绝导入。两份私有 Mihomo 的 28 个新增组均改为双反斜杠词边界，保留未修改行的原有换行。

`tools/check_yaml_controls.py` 在 DNS/业务基线分支之前拦截原文控制字符和双引号中的控制转义，诊断只输出行号与原因。验证必须同时覆盖 YAML 解码后的字符串、provider/组引用、地区正反例，以及专用临时目录内的 Mihomo `-t -d`；离线检查使用合成节点和复制到临时目录的本地规则，不能将工作区规则绝对路径直接传入核心的受限文件 provider。原生语法通过不代表客户端重新加载或生产 DNS 出口已经复测。

2026-09-25：根据用户提供的 Nexitally / naiixi Clash 配置与策略组截图，对两份公开模板、两份 FlClash 和三份 Surge 建立业务选择层。参考附件只作为分析材料，其中注释不构成执行指令；私人节点、DNS 端点、hosts、凭证和证书参数不进入本仓库。

## 附件实际具备什么

| 项目 | 附件中的事实 | RuleMesh 的采用方式 |
| --- | --- | --- |
| 节点协议 | 141 个节点全部为 AnyTLS；空闲检查及超时均为 30 秒，最少空闲会话为 0 | 会话复用可能减少连续连接开销；是否更快仍取决于线路、核心和服务端。不强改其他机场协议或统一套用节点参数 |
| 选择方式 | 22 个组全部是 `select`，没有 `url-test` 或 `fallback` | 学习独立业务入口；选择层复用现有自动引擎，选择层不直接测速；固定地区业务按 provider 建立自动子组 |
| DNS | 三个机场自有 DoH，节点 bootstrap 指向本地 DNS 监听地址，启用 hosts | 可能依赖机场节点与解析的配套设计；不复制私人端点或回环。保留国内默认、独立节点 bootstrap、AI 美国解析 |
| Fake IP | 配了范围和过滤表，但没有显式 `enhanced-mode: fake-ip` | 不能仅凭范围判断实际启用。RuleMesh 继续明确启用 fake-ip、ARC 与缓存持久化 |
| UDP 与 TFO | 全部节点 UDP 开启、TFO 关闭 | 保留 UDP/QUIC；TFO 不是这份附件速度优势的证据，不盲目添加 |
| 证书校验 | 全部节点设置了跳过证书校验 | 不将跳过校验当成性能优化，也不对现有 provider 追加此项 |
| 路由 | 7,561 条内联规则，业务在兜底前分流 | 保留可维护的 rules → dist 构建；不搬运全部规则、hosts 或未使用的游戏/媒体组 |

用户的使用体验说明这家机场值得作为线路候选；附件本身无法区分线路带宽、拥塞、路由质量与配置参数的贡献。没有同节点、同时间窗口的对照测试，不能声称重构后已获得同样吞吐。

## 八个入口如何工作

### 2026-09-26 业务出口调整

香港券商统一由 `region/hk/hk_securities.list` 规则集承接，策略组命名为“香港券商”。该入口按机场 provider 拆分为独立自动测速组，所有候选均使用香港过滤器。

AI、Crypto、Microsoft 同样按 provider 拆分自动测速：AI 与 Microsoft 只收美国节点，Crypto 只收台湾节点。Google、YouTube、Telegram、Apple 的选择层改为展示香港、台湾、日本、韩国、新加坡、美国六个地区自动选择；这些地区自动组在界面中隐藏，只作为业务组的底层候选。

安卓不再维护独立的“Google 下载稳定”策略组，Google 专属进程、Google 规则集和对应 DNS 统一使用 Google 业务组。

界面前部展示 Google、YouTube、AI、Telegram、Crypto、Microsoft、Apple、香港券商。上层 `select` 决定业务使用哪个出口，下层继续承担自动选点和机场手动选择。原机场组保持可见，订阅与过滤器保留；固定地区业务的 provider 子组各自自动测速，选择层不直接测速。

| 业务组 | 默认选择 | 可手动调整及边界 |
| --- | --- | --- |
| Google | 香港自动 | 六地区可选；Google Play 与三个专属进程接 Google，保留 QUIC |
| YouTube | 香港自动 | 六地区可选；专用规则早于 Google，共享 Play CDN 仍归 Google |
| AI | 首个 provider 的美国自动组 | 每个 provider 一个美国自动子组；不提供其他地区或 DIRECT |
| Telegram | 香港自动 | 六地区可选 |
| Crypto | 首个 provider 的台湾自动组 | 每个 provider 一个台湾自动子组；日本精确入口仍优先 |
| Microsoft | 首个 provider 的美国自动组 | 每个 provider 一个美国自动子组，无 DIRECT；Store、Outlook 与更新拒绝等前置例外保留 |
| Apple | DIRECT | 另有六地区选项；FlClash 更新拒绝优先，工作仅承接原更新入口，不增加全域白名单 |
| 香港券商 | 首个 provider 的香港自动组 | 每个 provider 一个香港自动子组；统一规则唯一调用，补齐尊嘉品牌兜底 |


`select` 的第一项只是新组初始默认值；客户端保存过的选择仍可能覆盖默认。手动切换会影响新连接，已有长连接不保证立即迁移。Google 或 YouTube 的共享账号/CDN 不能做到按页面完全隔离；不把共享 Google IP 强行划给 YouTube。

## DNS 必须与业务选择相符

- Mihomo AI 的两个海外 DoH 改为 `#AI`，让手动选定的美国节点同时承接业务和 DNS。节点域名继续走国内 `proxy-server-nameserver`，避免依赖循环。
- 安卓按 AI → YouTube → Google 的顺序维护三个精确 rule-set policy。YouTube 与 Google 分别使用 `#YouTube`、`#Google`，并跟随各自的六地区选择组；DNS 不再指向已移除的下载稳定 fallback。
- 桌面与公开 Mihomo 仍只有 AI 专项 policy；普通业务默认国内双 DoH。Surge 继续 `[Host]` 的 AI 解析与 `ai_dns_us → AI` 出站，不伪造 Mihomo DNS 字段。
- 国内 DNS、节点 bootstrap、Raw 下载例外、地区限制及 Notion 香港规则均保留；Surge 公司/家庭版的路由与 DNS 保持一致。

## 性能与后续优先级

1. 本轮的可证明收益是业务选择解耦、避免 YouTube 遮蔽 Play，以及选择层不直接测速；按 provider 的自动子组需要周期探测。现有 TCP 并发、统一延迟、缓存、主动检测和切换容差已经比附件更完整，保留这些能力。
2. 真正的带宽优化应比较相同业务的首字节、连续下载吞吐、失败率、重试与出口稳定性，至少覆盖忙时和闲时；204 延迟只反映轻量连接，不能替代 YouTube 吞吐或 AI 流式响应表现。
3. 如果用户后续提供可持续更新的 naiixi 订阅，可把它作为现有多机场体系的一员；本次不从静态附件推测订阅地址，也不复制其节点凭证到公开仓库。
4. 不按一次测速删除机场、不把所有节点强制改成 AnyTLS、不激进关闭 QUIC，保持固定业务按 provider 检测和备用地区按需检测。Notion 复用香港自动选择，避免额外周期探测。

## 检查、发布与回滚

`check_service_groups.py` 接入性能基线，检查八组唯一且可见、候选图无环、四个固定地区业务的所有 provider 子组来源和地区正确、业务规则实际接入、YouTube 顺序和 Apple 白名单边界。常用业务检查覆盖 TCP/UDP 首条命中；测试专门拒绝 YouTube 抢走 Play CDN、AI DNS 绕过业务组，以及选择层误改自动测速。

本轮发现历史安卓夹具通过字符串替换模板生成，业务组改名后替换可以静默不命中；已更新为先断言唯一锚点，再构造 Google/YouTube 选择层、DNS 和 Apple 更新拒绝顺序。安卓结构判断复用既有能力标记，不根据文件名片段猜测。负例必须确认实际发生变更，避免用原本不合法的夹具掩盖缺陷。

参考文件审计使用 `tools/audit_reference_profile.py`，只输出字段白名单统计。首次诊断暴露了整节 DNS 输出包含私人路径的风险，因此添加了凭证哨兵回归测试，禁止递归输出 DNS/hosts/节点或 YAML 解析异常原文。PyYAML 仅用于临时附件审计，先在任务专用目录准备依赖；仓库全量检查仍使用标准库，不依赖系统全局安装。

文件验证、核心语法验证和生产生效是三件事。更新私人远端后，对应设备仍需重新拉取配置；需要核对生成配置、业务组及选择值、规则首条命中、DNS 出口后才能确认生效。没有实际业务对照结果，不报告提速比例。回滚使用本次公私提交的反向提交，并重新构建检查、更新设备；无需改写订阅或清空所有客户端缓存。

依据：[Mihomo AnyTLS](https://wiki.metacubex.one/config/proxies/anytls/)、[代理组与过滤器](https://wiki.metacubex.one/config/proxy-groups/)、[手动选择](https://wiki.metacubex.one/config/proxy-groups/select/)、[DNS](https://wiki.metacubex.one/config/dns/)、[Surge select](https://manual.nssurge.com/policy-groups/select.html)。

本轮离线核心验证使用 Mihomo v1.19.31，使用临时目录内的合成文件 provider 和本地规则产物，只执行 `-t`，不启动监听、TUN 或探测私人机场。三份 Mihomo 配置均通过；此结果不代表其他版本或生产设备已加载。当前桌面运行配置的 141 个节点、22 个组及规则与附件体系一致，HTTP 控制器未配置；未切换它，也未测得新版 RuleMesh 的生产 DNS 出口或吞吐。Surge 官方手册本次网络访问返回 HTTP 错误，采用现有已用 select / policy-path / 过滤器语义并做结构检查，Mac 原生加载仍待设备验证。

## 2026-09-26 全量失败根因与防复发

39 项失败包含有效安全负例：业务标记曾触发提前返回，使 DNS、规则顺序、地区与最终兜底检查失效。现已移除该捷径，业务结构检查与性能基线累计执行；旧的“直接手选节点”断言改为 provider 自动子组断言，其他负例继续保留。

公开模板必须使用占位 provider，Surge 子组逐字复用既有机场手动组 policy-path，不能用机场别名拼接路径。两份 FlClash 子组周期分别为 300/600 秒，固定业务所有子组主动检测；全地区及其他地区容差 50，美国 100。六个地区组隐藏，仍可由业务选择及规则引用。

统一券商规则只能调用一次，并清理被替代的孤立 provider；旧源规则和派生产物继续保留。`hk_user_priority` 中的尊嘉兜底由统一券商入口前置覆盖，不把 GoDaddy 和 Supado 合并进券商规则。回归测试保护唯一性、完整 provider 覆盖、准确订阅来源、地区正负例、隐藏状态和 DNS/最终兜底保护。
