# Mihomo Tun / DNS / 嗅探维护方法论

这份方法论用于沉淀 RuleMesh 在 Mihomo 侧的长期维护约定。目标不是让 Mihomo 和 Surge 逐字段对齐，而是让 Mihomo 在保留同一套路由骨架的前提下，保持稳定、可验证、可回滚。

## 目标

- 把“规则层”和“运行时层”分开维护：规则层负责去向，运行时层负责 Tun、嗅探、DNS、fake-ip 与防泄漏。
- 默认优先稳定性，而不是“看起来更高级”的 DNS 叠层。
- 给后续维护留下明确红线，避免因为复用 Surge 思路而把 Mihomo 私有文件改崩。

## 多客户端边界

- `Surge`、`Clash Verge Rev`、`Clash Meta for Android` 即使策略组、规则顺序和规则产物入口一致，运行时 DNS 行为也可能完全不同。
- `Surge` 可以继续维护自己验证过可用的复杂 DNS 版本；这不等于 Mihomo 私有文件也应该保持同样结构。
- `Clash Verge Rev` 与 `Clash Meta for Android` 允许长期分别维护两份 Mihomo 私有文件，但它们当前都默认遵循同一套“单一 DNS 真相”约束。

## Mihomo 私有配置红线

以下红线默认同时约束：

- `rulemesh-substore-mihomo-clash-verge.yaml`
- `rulemesh-substore-mihomo-clash-meta.yaml`

默认只允许“单一 DNS 真相”版本：

- `ipv6: false`
- `dns.ipv6: false`，若该字段存在
- `use-hosts: false`
- `use-system-hosts: false`
- `dns:` 里只保留 `default-nameserver`、`nameserver`、`fake-ip-filter` 与客户端确实需要的最小字段，例如 `listen`、`fake-ip-range`

未经用户明确确认并完成运行时复测，不得在两份 Mihomo 私有文件里恢复：

- `respect-rules: true`
- `nameserver-policy`
- `proxy-server-nameserver`
- `proxy-server-nameserver-policy`
- `direct-nameserver`
- `fallback`

同样默认禁止：

- 把 Surge 的复杂 DNS 结构、`[Host]` 思路或同名近义字段直接照搬到 Mihomo
- 因为某条规则最终走 `DIRECT`，就把普通目标网站域名重新送回国内 DNS
- 把 Mihomo 私有文件里的 provider `health-check.url` 或 `url-test.url` 改回 HTTP `generate_204`

## 当前稳定基线

对两份 Mihomo 私有文件，当前默认稳定基线是：

- 普通目标网站域名统一走 `nameserver`
- `default-nameserver` 只承担 DNS 服务器域名 bootstrap
- `fake-ip-filter` 只承担局域网、本地主机名、系统网络探测与确有必要的真实 IP 例外
- Clash Verge Rev 与 Clash Meta for Android 可以保留不同的 `fake-ip-range`、`listen` 等客户端细节，但不要因此重新引入多层 DNS 分流

如果后续必须引入客户端特化例外，必须同时满足：

- 用户明确确认要这么做
- 能说明为什么简单基线不够
- 已完成对应客户端的运行时复测
- 已把例外写回文档与维护约定

## Clash Verge Rev DNS 覆写方法论

- Clash Verge Rev 的 `DNS 覆写` 会用 AppData 下的 `dns_config.yaml` 直接覆盖运行时 `dns` 段，而不是“在源文件 `dns:` 上补几个默认值”。
- 因此只要 `DNS 覆写` 处于开启状态，`rulemesh-substore-mihomo-clash-verge.yaml` 里的 `dns:` 默认就不再是实际生效的单一真相。
- 如果目标是“把私有 Mihomo 文件当成唯一权威配置”，Clash Verge Rev 侧默认应关闭 `DNS 覆写`。
- 如果用户明确要保留 `DNS 覆写`，那就要把 `%APPDATA%/io.github.clash-verge-rev.clash-verge-rev/dns_config.yaml` 视为 `dns` 的单一真相，而不要继续假设源文件里的 `dns:` 会原样生效。
- 对当前本地长期维护来说，Clash Verge Rev 私有文件关闭 `DNS 覆写` 后，默认仍应回到“单一 DNS 真相”版本，而不是继续叠 `nameserver-policy`、`proxy-server-nameserver`、`fallback`。

## provider 全部测速失败但直导正常时的排障方法论

- 典型现象是：同一机场订阅在 `rulemesh-substore-mihomo-clash-verge.yaml` 这类 provider 路径下整批 `delay=0` 或全部超时，但把同一订阅直接导入客户端后测速正常。
- 遇到这种组合时，默认先怀疑“运行时 DNS 链与直导配置不一致”，不要第一时间把问题归因到节点本身、机场质量或界面缓存。
- `health-check.url` 从 HTTP 改成 HTTPS 只能算第一层排查；如果改完仍整批失败，不要停在这里。

建议排查顺序：

- 先确认内核是否真的吃到了新配置，而不是只看客户端界面是否点过“重载”或“重启”。
- 再对比“直导正常的那份配置”和“provider 全灭的那份配置”在运行时的 `dns:`，重点看实际生效值，而不是只看源 YAML。
- 再把问题拆成三层分别验证：provider 是否成功拉取、节点域名是否能被当前运行时 DNS 正确解析、测速目标域名是否走上了错误解析链。

建议使用的验证手段：

- 优先看 Mihomo 运行日志，确认是否出现 `EOF`、`context deadline exceeded`、批量 `delay=0` 或 DNS 相关异常。
- 优先通过 Mihomo API 或 Clash Verge Rev 命名管道回读运行时 `/configs`。
- 对代表性节点直接做 `/proxies/<node>/delay` 测试，避免只盯着策略组或 UI 汇总结果。
- 如有需要，再分别检查 provider 列表、DNS 查询结果与节点明细。

修复原则：

- 先把失败配置的运行时 DNS 收敛到“与直导正常配置同一套逻辑”，优先恢复单一真相。
- 如果直导正常而 provider 路径整批失败，优先回到更简单、更接近直导行为的 DNS 链，不要一开始就在复杂分层上继续叠补丁。
- 如果两份 Mihomo 私有文件里再次出现 `respect-rules: true`、`nameserver-policy`、`proxy-server-nameserver` 或 `fallback` 回流，默认按 DNS 回归处理。

## Surge 例外边界

- Surge 私有配置可以继续维护自己的复杂 DNS 版本。
- Surge 侧可以继续使用自己的 `[Host]`、域名集隔离、客户端专属 DNS 能力与运行时兜底。
- 不要因为 Surge 版本稳定，就反向推断 Mihomo 私有文件也应该恢复同样结构。
- “Surge 正常、Mihomo 崩了”时，默认优先怀疑 Mihomo 运行时 DNS 回归，而不是先怀疑规则顺序。

## Tun 与嗅探约定

- Mihomo 侧默认以 Tun 为主路径，不再把“只开系统代理、Tun 关闭”的体验当成主要维护目标。
- `strict-route` 是否开启，按目标客户端与网络环境单独评估；不要为了追求结构统一而跨客户端互抄。
- 域名嗅探默认开启，减少“只看到 IP、规则命不中、误走兜底”的情况。
- 嗅探跳过名单只保留少量明确容易出问题的域名，不做大面积保守豁免。

## 安全与隐私边界

- 不要把真实机场地址、Token、控制器密钥、私有设备分流信息写回公开仓库。
- 方法论可以写“国内 DNS 仅限 bootstrap”“Mihomo 采用单一 DNS 真相”“Surge 可保留复杂 DNS 版本”这类抽象约束，但不要写入真实私有域名或订阅地址。
- 私有订阅域名同步块继续只在本地私有目录维护，不回写公开模板。

## 防回滚提醒

- 不要把 Surge 可用的复杂 DNS 版本回灌到任何 Mihomo 私有文件。
- 不要把 Mihomo 私有文件重新改成 `respect-rules: true + nameserver-policy + proxy-server-nameserver + fallback` 这套多层叠加结构。
- 不要把 provider `health-check.url` 或 `url-test.url` 改回 HTTP `generate_204`。
- 不要因为某条规则最终是 `DIRECT`，就把普通目标网站域名重新交给国内 DNS。
- 如果必须做 DNS 例外，必须把原因、适用客户端、验证结果与回滚条件写清楚。

## 变更后检查清单

- 运行时 `/configs` 是否已确认吃到预期 DNS 配置。
- 代表性节点的单点测速是否恢复，不再是整批 `delay=0`。
- provider 汇总结果与单点测速结果是否一致，而不是只靠 UI 旧缓存显示正常或异常。
- 如果本次修复只应影响 Clash Verge Rev 私有链路，是否确认 `rulemesh-substore-mihomo-clash-meta.yaml` 未被误改。
- 如果本次修复只修改了 Android 私有文件，是否确认桌面端运行态没有被顺手回滚。

## 适用范围

- 这份方法论主要约束两份 Mihomo 私有配置与 Mihomo 相关维护约定。
- 如果同时维护 Clash Verge Rev 与 Clash Meta for Android，本地私有目录允许拆成两份 Mihomo 配置；规则骨架可保持一致，但客户端细节必须各自验证。
- Surge 侧可以继续保留 Surge 自己的能力与结构，但不应反向约束 Mihomo。