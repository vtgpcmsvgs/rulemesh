# Mihomo Tun / DNS / 嗅探维护方法论

这份方法论用于沉淀 RuleMesh 在 Mihomo 侧的长期维护约定，目标不是让 Mihomo 和 Surge 逐字段对齐，而是让 Mihomo 在保留同一套路由骨架的前提下，尽量补齐客户端体验、安全边界与性能表现。

## 目标

- 让 Mihomo 的实际体验尽量接近 Surge，而不是只复制 Surge 的规则顺序。
- 把“规则层”和“运行时层”分开维护：规则层负责去向，运行时层负责接管、还原域名、DNS 分流与防泄漏。
- 给后续维护留清晰边界，避免因为“看起来能简化”而误删 Tun、嗅探、分流 DNS 等关键补偿层。

## 核心判断

- Mihomo 的体验瓶颈通常不在 `rule-providers` 或规则顺序本身，而在 `tun`、`sniffer`、`dns` 这层是否补齐。
- Surge 自带更强的系统整合能力；Mihomo 如果只移植规则，不补运行时，体感通常会明显落后。
- 因此 Mihomo 不应再追求“和 Surge 长得一样”，而应追求“在 Mihomo 里把该开的能力开起来”。

## 多客户端运行时差异

- 同一套路由骨架，不等于同一个运行时结果；`Surge`、`Clash Verge Rev`、`Clash Meta for Android` 即使策略组、规则顺序和规则产物入口一致，DNS 启动链也可能完全不同。
- `Surge` 更偏系统整合型客户端，很多解析与连接细节由客户端自身兜底；`Clash Verge Rev` 虽然使用 Mihomo 生态，但运行在桌面系统上；`Clash Meta for Android` 则额外叠加 Android VPN/Tun、蜂窝网络与系统 DNS 行为差异。
- 因此遇到“Surge 正常、Verge 正常、只有 Clash Meta 异常”的情况时，默认优先怀疑 Android 侧的节点域名解析启动链，而不是先怀疑规则顺序。

## 默认策略

- 默认开启 `tun`，优先使用 `stack: mixed`。
- 默认开启域名嗅探，让 HTTP / TLS / QUIC 流量尽量还原到域名层再命中规则。
- 默认保留 `fake-ip`，不要因为少数个别站点的兼容性问题就整体退回简单模式。
- 默认把最终兜底交给总开关 `🚀 节点选择`，不要把所有漏网流量固定锁死在单一区域。
- 默认把代理节点域名解析与业务 DNS 分开，避免互相依赖导致的解析抖动。

## DNS 方法论

- 国际域名默认优先走国外加密 DNS。
- 明确的国内直连域名集单独走国内加密 DNS。
- 不要把“所有 DIRECT 都交给国内 DNS”当成默认方案。
- 原因很简单：`DIRECT` 里可能混有 GitHub SSH、Microsoft、macOS 更新之类的国外直连例外；如果粗暴映射到国内 DNS，会把这些访问暴露给国内解析链路。
- 更稳妥的做法是按“域名属性”分，而不是按“出站动作”分。

## 节点 DNS 启动链

- `proxy-server-nameserver` 只负责代理节点域名解析，它和业务 `nameserver`、`fallback` 不应混在一起调。
- 如果只有 Clash Meta for Android 在移动网络或特定网络环境下失败，而 Clash Verge Rev 正常，优先检查是否是“节点域名解析无法直连国外 DoH”。
- 这种情况下，第一优先级是单独调整 Android 私有文件的 `proxy-server-nameserver`，而不是立刻把全部业务 DNS 都切回国内。
- 当前仓库的推荐收敛顺序是：
  - 先保持规则骨架一致。
  - 再把 Mihomo 私有配置拆成 `rulemesh-substore-mihomo-clash-verge.yaml` 与 `rulemesh-substore-mihomo-clash-meta.yaml`。
  - 优先只让 Clash Meta 的 `proxy-server-nameserver` 改走国内可直连加密 DNS。
  - 只有在这一步仍不稳定时，才继续评估更保守的 Android 专用启动链。
- 对当前本地长期维护来说，Clash Meta 专用文件的节点域名解析默认优先使用阿里云 / 腾讯云 DoH；这一步只作用于节点域名，不应自动扩散到所有国际业务域名。

## 国内 DNS 适用范围

- `direct_cn`
- 明确属于国内服务的专门直连规则集，例如 `direct_bilibili`、`direct_netease`、`direct_bytedance`
- 局域网、本地域名与私有地址段

## 不应默认回到国内 DNS 的直连例外

- `direct_github_ssh`
- `direct_microsoft`
- `direct_macos_update`
- 其他“允许直连，但服务本身属于国外网络”的规则集

## 维护规则

- 新增一个 `direct/*.list` 或新的 Mihomo 直连入口时，先判断它属于“国内直连域名集”还是“国外直连例外”。
- 只有“国内直连域名集”才应同步加入 `nameserver-policy` 的国内加密 DNS 名单。
- 如果只是“国外直连例外”，保持默认国外解析，不要为了“DIRECT 看起来应该配国内 DNS”而硬塞进去。
- 新增需要优先直连的局域网、本地网段或特殊主机名时，同时检查 `rules:` 里的本地直连段与 `dns.fake-ip-filter` 是否也要补。
- `proxy-server-nameserver` 只负责节点域名解析，不要混入普通业务域名的取舍逻辑。
- 如果本地同时维护 Clash Verge Rev 与 Clash Meta for Android，两份 Mihomo 私有文件允许长期并存；公共规则骨架尽量一致，但节点 DNS 启动链允许有意识地永久不一致。

## Tun 与嗅探约定

- Mihomo 侧默认以 Tun 为主路径，不再把“只开系统代理、Tun 关闭”的体验当成主要维护目标。
- `strict-route` 默认开启，用于更积极地防止流量绕开 Mihomo。
- 域名嗅探默认开启，减少“只看到 IP、规则命不中、误走兜底”的情况。
- 嗅探跳过名单只保留少量明确容易出问题的域名，不做大面积保守豁免，避免把嗅探能力自己削弱掉。

## 风险与取舍

- `strict-route` 可能影响部分局域网入站访问、共享或发现类场景；如果用户明确依赖这类能力，再做定向例外，不要先全局关闭。
- `fake-ip` 可能让少数依赖真实 IP 的服务变得敏感；处理方式优先是补 `fake-ip-filter`，而不是整体放弃 `fake-ip`。
- 如果把最终兜底锁死到固定区域，未知流量的默认体验通常会变差；只有用户明确追求固定出口地区时，才考虑回退。
- 如果把 Clash Meta 的 `proxy-server-nameserver` 调到国内 DNS，这通常意味着国内解析方可能看到“代理节点域名解析”这一步；但这不等于全部国际业务域名都回到国内 DNS。
- 如果威胁模型优先考虑“不要让运营商系统 DNS 看到查询”，阿里云 / 腾讯云这类国内 DoH 往往比 `system` DNS 更可接受；如果威胁模型要求“任何国内解析方都不应看到节点域名”，那就不能把国内 DNS 当作隐私方案，只能继续使用可达的国外解析入口、自建解析或 IP 型节点。

## 性能优化约定

- DNS 默认保持分流友好与隐私优先，不再让国际域名默认回到国内 DNS。
- 代理节点测速、规则更新和业务 DNS 要尽量解耦，不要让单一 DNS 入口同时承担全部角色。
- 本地与局域网相关域名、CIDR 和系统网络探测域名，应显式放入直连或真实 IP 范围，避免 Tun 模式下的额外抖动。

## 安全指引

- 不要把真实机场地址、token、控制器密钥、私有设备分流信息写回公开仓库。
- 方法论可以写“国内 DNS / 国外 DNS / 国外直连例外 / 白名单原则”这类抽象规则，但不要写入真实私有域名或订阅地址。
- 私有订阅更新直连域名仍只在本地私有目录维护，不回写公开模板。

## 防回滚提醒

- 不要因为“规则框架已经和 Surge 一致”就删除 Tun、嗅探或分流 DNS。
- 不要把 Mihomo 简化回“只有 fake-ip + 两个 DNS”的轻配置。
- 不要把所有 DIRECT 一刀切交给国内 DNS。
- 不要把 `MATCH` 默认改回固定香港，除非用户明确要固定区域出口。

## 变更后检查清单

- Tun 模式是否确实开启，且 `stack`、`dns-hijack`、`strict-route` 生效。
- 规则命中前是否能通过嗅探把纯 IP 连接还原到域名。
- 国内直连域名是否优先走国内加密 DNS。
- Google 等国际域名是否不再回到国内 DNS。
- 节点订阅更新、规则更新与节点域名解析是否仍然稳定。
- 局域网、本地主机名、系统网络探测与系统时间同步是否正常。
- 如果同时维护 Clash Verge Rev 与 Clash Meta for Android，是否已确认“桌面正常、安卓正常”分别由对应私有文件负责，而不是误把一端的启动链回滚到另一端。

## 适用范围

- 这份方法论主要约束 Mihomo 模板与两份 Mihomo 私有配置。
- 如果同时维护 Clash Verge Rev 与 Clash Meta for Android，本地私有目录允许拆成两份 Mihomo 配置；规则骨架可保持一致，但节点域名解析策略可以分别维护。
- Surge 侧可以继续保留 Surge 自己的能力与结构，不要求强行做同构。
- 私有 Surge 工作路由白名单特化不受本方法论约束，不要反向套用到 Mihomo。
