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
- 默认同时开启 `ipv6: true` 与 `dns.ipv6: true`，让 Mihomo 真正接收 IPv6 流量并返回 AAAA 结果，而不是继续停留在“规则是双栈、运行时却主动关 IPv6”的半开状态。
- 对来自订阅的代理节点，默认在 `proxy-providers.*.override` 里显式写 `ip-version: dual`；先打开双栈，不默认强推 `ipv6-prefer`，避免把机场 IPv6 质量波动直接放大成首连故障。

## 规则兼容方法论

- 源规则层优先表达完整意图，不要因为 Mihomo 当前版本有能力缺口，就直接从 `rules/` 源文件删掉 Surge 仍可使用的规则类型。
- 对 `URL-REGEX` 这类当前 Mihomo classical 明确不支持、但 Surge 仍需要保留的规则，做法应是“源规则保留、Surge 产物保留、Mihomo 产物构建时按兼容矩阵跳过”，而不是把源规则收缩成只剩两端都支持的最小交集。
- 这种跳过是“面向当前 Mihomo 版本的兼容降级”，不是永久语义裁剪；只要后续 Mihomo 官方版本已支持，且本仓库构建验证确认可用，就应恢复 Mihomo 产物输出，并同步移除对应特判。
- 目标不是让 Mihomo 永久比 Surge 少一层能力，而是在“当前可用、warning 保持 0、未来容易放开”之间保留清晰边界。

## DNS 方法论

- 普通目标网站域名默认优先走海外加密 DNS。
- 国内 DNS 只作为代理节点 `server` 域名解析的专用例外。
- 不要把“国内直连域名集”或“所有 DIRECT”交给国内 DNS 当成默认方案。
- 原因很简单：DNS 信任边界不等于出站动作。即使某条规则最终是 `DIRECT`，它仍然可能是账号平台、系统服务、AI 服务或其他敏感目标域名。
- 更稳妥的做法是把业务 `nameserver` 与节点 `proxy-server-nameserver` 分开，而不是按 `DIRECT` / `PROXY` 把目标网站域名重新分给国内 DNS。

## 节点 DNS 启动链

- `proxy-server-nameserver` 只负责代理节点域名解析，它和业务 `nameserver`、`fallback` 不应混在一起调。
- 如果只有 Clash Meta for Android 在移动网络或特定网络环境下失败，而 Clash Verge Rev 正常，优先检查是否是“节点域名解析无法直连国外 DoH”。
- 这种情况下，第一优先级是单独调整 Android 私有文件的 `proxy-server-nameserver`，而不是立刻把全部业务 DNS 都切回国内。
- 当前仓库的推荐收敛顺序是：
  - 先保持规则骨架一致。
  - 再把 Mihomo 私有配置拆成 `rulemesh-substore-mihomo-clash-verge.yaml` 与 `rulemesh-substore-mihomo-clash-meta.yaml`。
  - 优先只让对应客户端文件的 `proxy-server-nameserver` 改走国内可直连加密 DNS。
  - 只有在这一步仍不稳定时，才继续评估更保守的 Android 专用启动链。
- 对当前本地长期维护来说，节点域名解析默认允许优先使用阿里云 / 腾讯云 DoH；这一步只作用于代理节点 server 域名，不应自动扩散到任何普通目标网站域名。

## Clash Verge Rev DNS 覆写方法论

- Clash Verge Rev 的 `DNS 覆写` 不是“在配置文件 `dns:` 上补几个默认值”，而是会用 AppData 下的 `dns_config.yaml` 直接覆盖运行时 `dns` 段。
- 因此只要 `DNS 覆写` 处于开启状态，`rulemesh-substore-mihomo-clash-verge.yaml` 里的 `dns:` 默认就不再是实际生效的单一真相。
- 如果目标是“把私有 Mihomo 文件当成唯一权威配置”，Clash Verge Rev 侧默认应关闭 `DNS 覆写`，让 `rulemesh-substore-mihomo-clash-verge.yaml` 自己负责完整 `dns:`。
- 如果用户明确要保留 `DNS 覆写`，那就要把 `%APPDATA%/io.github.clash-verge-rev.clash-verge-rev/dns_config.yaml` 视为 `dns` 的单一真相，而不要再假设源文件里的 `dns:` 会原样生效。
- 遇到“关闭 DNS 覆写后，国内可访问、国外代理不通”的情况，默认先怀疑桌面端私有文件的节点域名解析启动链，而不是先怀疑规则顺序或 `rule-providers`。
- 对当前本地长期维护来说，Clash Verge Rev 私有文件在关闭 `DNS 覆写` 后，默认采用这组收敛原则：
  - `respect-rules: false`，避免节点 DNS 再跟随规则链递归绕回代理组。
  - `proxy-server-nameserver` 优先使用当前网络可直连的加密 DNS，例如阿里云 / 腾讯云 DoH。
  - `proxy-server-nameserver-policy` 继续只承载少量明确需要专用解析链的节点域名，不把这层逻辑扩散到普通业务域名。
  - 这一步只修复代理节点 server 域名解析，不应顺手把业务 `nameserver`、`nameserver-policy`、`direct-nameserver` 或国际业务 DNS 改回国内。
- 当前本地已验证可用的 Clash Verge Rev 修法是：
  - 关闭应用侧 `DNS 覆写`
  - 在 `rulemesh-substore-mihomo-clash-verge.yaml` 中保持 `respect-rules: false`
  - 让 `proxy-server-nameserver` 走阿里云 / 腾讯云 DoH
  - 保留确有必要的节点专用解析策略
- 这套修法的目标是把“桌面端 Mihomo 私有文件重新变回单一真相”，而不是长期依赖 Clash Verge Rev 的界面覆写兜底。

## provider 全部测速失败但直导正常时的排障方法论

- 现象特征通常是：同一机场订阅在 `rulemesh-substore-mihomo-clash-verge.yaml` 这类 provider 路径下整批 `delay=0` 或全部超时，但把同一订阅直接导入 Clash Verge Rev 后测速正常。
- 遇到这种组合时，默认先怀疑“Verge 运行时 DNS 链与直导配置不一致”，不要第一时间把问题归因到节点本身、机场质量或界面缓存。
- 这类问题里，`health-check.url` 从 HTTP 改成 HTTPS 只能算第一层排查；如果改完仍整批失败，不要停在这里。

### 建议排查顺序

- 先确认内核是否真的吃到了新配置，而不是只看客户端界面是否点过“重载”或“重启”。
- 再对比“直导正常的那份配置”和“provider 全灭的那份配置”在运行时的 `dns:`，重点看实际生效值，而不是只看源 YAML。
- 再把问题拆成三层分别验证：
  - provider 本身是否成功拉取
  - 节点域名是否能被当前运行时 DNS 正确解析
  - 测速目标域名是否走上了错误的解析链或错误的分流链

### 建议使用的验证手段

- 优先看 Mihomo 运行日志，确认是否出现 `EOF`、`context deadline exceeded`、批量 `delay=0` 或 DNS 相关异常。
- 优先通过 Mihomo API 或 Clash Verge Rev 命名管道回读运行时 `/configs`，确认当前 `dns`、`ipv6`、`use-hosts`、`use-system-hosts`、`listen`、`fake-ip-range` 是否符合预期。
- 对代表性节点直接做 `/proxies/<node>/delay` 测试，避免只盯着策略组或 UI 汇总结果。
- 如有需要，再分别检查 provider 列表、DNS 查询结果与节点明细，确认是“节点解析失败”还是“测速目标解析链异常”。

### 在 Clash Verge Rev 里优先关注什么

- 是否开启了 `DNS 覆写`，以及 AppData 下的 `dns_config.yaml` 是否覆盖了源文件里的 `dns:`。
- `use-hosts`、`use-system-hosts`、`ipv6` 是否与直导正常配置一致。
- `listen`、`fake-ip-range`、`default-nameserver`、`nameserver` 是否形成了单一且自洽的解析链。
- 是否额外挂了 `nameserver-policy`、`direct-nameserver`、`proxy-server-nameserver`、`fallback` 等多层策略，导致节点域名解析和业务域名解析缠在一起。

### 修复原则

- 先把失败配置的运行时 DNS 收敛到“与直导正常配置同一套逻辑”，优先恢复单一真相，再决定是否需要逐层加回额外策略。
- 如果直导正常而 provider 路径整批失败，优先回到更简单、更接近直导行为的 DNS 链，不要一开始就在复杂分层上继续叠补丁。
- 只有在验证恢复后，才评估哪些差异是 Clash Verge Rev 私有文件长期需要保留的特化行为。

### 公开仓库与私有配置的边界

- 若最终可用方案依赖私有订阅、私有 DoH、AppData 运行态文件或本地长期维护脚本，公开仓库只沉淀方法，不记录真实值。
- 仓库内只保留“看什么、比什么、怎么验证、先后顺序是什么”，真实解析上游、真实订阅地址与本地路径细节继续留在私有目录。

### 收尾检查清单

- 运行时 `/configs` 已确认吃到预期 DNS 配置。
- 代表性节点的单点测速已恢复，不再是整批 `delay=0`。
- provider 汇总结果与单点测速结果一致，而不是只靠 UI 旧缓存显示正常或异常。
- 如本次修复只应影响 Clash Verge Rev 私有链路，则确认 `rulemesh-substore-mihomo-clash-meta.yaml` 等其他客户端配置未被误改。

## 国内 DNS 适用范围

- 仅限 `proxy-server-nameserver` 里的代理节点 `server` 域名解析。
- 如果使用 `proxy-server-nameserver-policy`，也只能承载明确的节点 server 域名解析策略，不得混入普通目标网站域名。
- 局域网、本地域名与私有地址段应通过本地直连、`fake-ip-filter` 或系统网络能力处理，不作为把普通目标网站域名送往国内 DNS 的理由。

## 不应默认回到国内 DNS 的目标域名

- `direct_cn`
- `direct_ai_cn`
- `direct_bilibili`
- `direct_netease`
- `direct_bytedance`
- `direct_github_ssh`
- `direct_microsoft`
- `direct_macos_update`
- 其他所有普通目标网站域名集合

## 维护规则

- 新增一个 `direct/*.list` 或新的 Mihomo 直连入口时，先判断它是否是普通目标网站域名。只要是目标网站域名，就默认由海外业务 `nameserver` 解析。
- 不要为了“DIRECT 看起来应该配国内 DNS”而把目标网站域名加入国内 `nameserver-policy`。
- 如果确实需要针对某个节点 server 域名调整解析，必须放在 `proxy-server-nameserver` 或节点专用策略里，并写清楚它不是普通目标网站域名。
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
- 如果把 `proxy-server-nameserver` 调到国内 DNS，这通常意味着国内解析方可能看到“代理节点域名解析”这一步；但这不等于普通目标网站域名可以回到国内 DNS。
- 如果威胁模型优先考虑“不要让运营商系统 DNS 看到查询”，阿里云 / 腾讯云这类国内 DoH 往往比 `system` DNS 更可接受；如果威胁模型要求“任何国内解析方都不应看到节点域名”，那就不能把国内 DNS 当作隐私方案，只能继续使用可达的国外解析入口、自建解析或 IP 型节点。

## 性能优化约定

- DNS 默认保持隐私优先，不再让普通目标网站域名默认回到国内 DNS。
- 代理节点测速、规则更新和业务 DNS 要尽量解耦，不要让单一 DNS 入口同时承担全部角色。
- 本地与局域网相关域名、CIDR 和系统网络探测域名，应显式放入直连或真实 IP 范围，避免 Tun 模式下的额外抖动。

## 安全指引

- 不要把真实机场地址、token、控制器密钥、私有设备分流信息写回公开仓库。
- 方法论可以写“国内 DNS 仅限节点 server 域名 / 海外业务 DNS / 白名单原则”这类抽象规则，但不要写入真实私有域名或订阅地址。
- 私有订阅域名同步块仍只在本地私有目录维护，不回写公开模板。

## 防回滚提醒

- 不要因为“规则框架已经和 Surge 一致”就删除 Tun、嗅探或分流 DNS。
- 不要把 Mihomo 简化回“只有 fake-ip + 两个 DNS”的轻配置。
- 不要把所有 DIRECT 一刀切交给国内 DNS。
- 不要把 `nameserver-policy` 或 `direct-nameserver` 重新改成国内 DNS 来处理普通目标网站域名。
- 不要把 `MATCH` 默认改回固定香港，除非用户明确要固定区域出口。
- 不要因为 Mihomo 当前不支持 `URL-REGEX`，就把这类规则从源规则层永久删掉；应保留 Surge 语义，并让 Mihomo 输出按当前能力选择性跳过。
- 如果后续 Mihomo 已支持 `URL-REGEX`，不要忘记同步取消构建特判并恢复 Mihomo 产物；“现在先跳过”不应演变成长期失忆式阉割。

## 变更后检查清单

- Tun 模式是否确实开启，且 `stack`、`dns-hijack`、`strict-route` 生效。
- 规则命中前是否能通过嗅探把纯 IP 连接还原到域名。
- 普通目标网站域名是否默认走海外加密 DNS。
- whoer.net、dnsleaktest.com、browserleaks.com/dns 是否不再显示非预期国内 DNS。
- 节点订阅更新、规则更新与节点域名解析是否仍然稳定。
- 局域网、本地主机名、系统网络探测与系统时间同步是否正常。
- 如果同时维护 Clash Verge Rev 与 Clash Meta for Android，是否已确认“桌面正常、安卓正常”分别由对应私有文件负责，而不是误把一端的启动链回滚到另一端。
- 如果维护 Clash Verge Rev 私有文件，是否已确认当前到底是“源文件 `dns:` 生效”还是“App 侧 `dns_config.yaml` 生效”，避免在两个入口同时改 DNS 后误判问题来源。
- 如果刚关闭 Clash Verge Rev 的 `DNS 覆写`，是否已验证国内站点直连正常、通过本地代理端口访问国外站点正常，以及运行时生成的 `clash-verge.yaml` 已回到期望的 `dns:` 配置。

## 适用范围

- 这份方法论主要约束 Mihomo 模板与两份 Mihomo 私有配置。
- 如果同时维护 Clash Verge Rev 与 Clash Meta for Android，本地私有目录允许拆成两份 Mihomo 配置；规则骨架可保持一致，但节点域名解析策略可以分别维护。
- Surge 侧可以继续保留 Surge 自己的能力与结构，不要求强行做同构。
- 私有 Surge 工作路由白名单特化不受本方法论约束，不要反向套用到 Mihomo。
