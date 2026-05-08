# DNS 防泄漏与解析边界方法论

这份文档用于记录 RuleMesh 的 DNS 信任边界。DNS 泄漏不是连通性小问题，而是会让目标域名、账号平台、金融服务、AI 服务与代理出口 IP 形成不一致指纹的安全风险。后续只要维护代理、旁路由、Surge、Mihomo、Sub-Store、DoH、fake-ip、mapping、Tun、透明代理或规则分流，都必须默认检查 DNS 解析路径。

## DNS 三分法

维护时必须先区分三类域名：

- 订阅链接域名：用于拉取订阅配置，例如 Sub-Store 入口、机场订阅入口、机场面板域名。
- 代理节点 server 域名：订阅拉下来后每个节点里的 `server` 字段，例如 `hk01.example.com`、`us01.example.net`。
- 普通目标网站域名：用户真正访问的服务，例如 `google.com`、`whoer.net`、`openai.com`、`claude.ai`、`paypal.com`。

这三类域名不能混在同一个 DNS 策略里处理。订阅链接域名不是节点 server 域名；节点 server 域名也不是普通目标网站域名。

## 默认安全姿态

- 普通目标网站域名默认不得交给国内 DNS。
- 国内 DNS 只能作为 DNS 服务器域名 bootstrap、代理节点 server 域名 bootstrap，以及 `cn_dns_domains` 专用国内业务域名白名单的受限例外。
- 不要为了让节点更容易首连，就把 Surge 的 `dns-server`、`encrypted-dns-server` 或 Mihomo 的业务 `nameserver` 全局改成国内 DNS。
- 任何把业务 DNS 改成 `system`、阿里云 DNS、腾讯云 DNS、`114.114.114.114` 或其他国内解析入口的操作，都必须按高风险变更处理；`default-nameserver` / `proxy-server-nameserver` 例外只能服务 bootstrap。
- 不能只用“网页能打开”“节点能测速”作为验收结论；DNS 出口也必须被验证。

## Surge 实现规范

Surge 没有 Mihomo 的 `proxy-server-nameserver` 或 `dns-mode` 字段，不能伪造同名配置。Fake IP 由 Surge Enhanced Mode / VIF 运行时提供，profile 中不要写 `dns-mode = fake-ip`。新增 DNS、fake-ip、Tun 或透明代理字段时，必须按目标客户端自己的 profile 语义确认，不要用“另一个客户端有近似字段”来推断可用性。Surge 必须使用：

- Surge Mac/iOS 运行时的 Enhanced Mode / VIF
- `use-local-host-item-for-proxy = false`
- `[Host]` 里的 `DOMAIN-SET:<proxy-node-domains URL> = server:<节点专用 DNS>`

推荐基线：

```ini
use-local-host-item-for-proxy = false
dns-server = 1.1.1.1, 8.8.8.8, 9.9.9.9
encrypted-dns-server = https://cloudflare-dns.com/dns-query, https://dns.google/dns-query
encrypted-dns-follow-outbound-mode = true

[Host]
raw.githubusercontent.com = server:https://cloudflare-dns.com/dns-query
DOMAIN-SET:https://example.com/rulemesh/dist/surge/dns/cn_dns_domains.list = server:https://dns.alidns.com/dns-query
DOMAIN-SET:https://example.com/share/file/proxy-node-domains = server:https://dns.alidns.com/dns-query
```

`raw.githubusercontent.com = server:https://cloudflare-dns.com/dns-query` 是规则产物下载解析例外，不得被扩展成普通目标网站解析方案，也不是代理节点 bootstrap。

`cn_dns_domains` 是国内业务域名 DNS 例外，只能包含明确国内业务域名 / 国内域名后缀，不包含代理节点 server 域名、订阅入口域名、IP 或复杂规则。它的职责是减少海外 DNS 导致的国内 CDN 调度偏差，不是把所有 `DIRECT` 流量交给国内 DNS。

上述海外 `dns-server` 的明文 IPv4 端点应先命中 `proxy/overseas_dns_ipv4_proxy` 并统一走美国地区策略，避免 1.1.1.1 / 8.8.8.8 / 9.9.9.9 的出口与普通代理出口错位。

`DOMAIN-SET` 引用的 `proxy-node-domains` 必须只包含代理节点的 `server` 域名。一行一个域名，不写 `DOMAIN-SUFFIX,` 前缀，不写 IP，不写订阅 URL，不写机场面板域名，不写普通目标网站域名，也不要输出逗号分隔的一整行。

## Mihomo 实现规范

Mihomo 必须使用原生 DNS 机制，不套用 Surge 的 `[Host]`。

推荐基线：

```yaml
dns:
  default-nameserver:
    - 223.5.5.5
    - 119.29.29.29
  nameserver:
    - https://cloudflare-dns.com/dns-query
    - https://dns.google/dns-query
  nameserver-policy:
    "rule-set:cn-dns-domains":
      - https://dns.alidns.com/dns-query
      - https://doh.pub/dns-query
  proxy-server-nameserver:
    - https://dns.alidns.com/dns-query
    - https://doh.pub/dns-query
```

含义：

- `default-nameserver` 只负责 DNS 服务器域名 bootstrap，可以使用国内可直连 DNS。
- `nameserver` 负责普通目标网站域名，默认使用海外 DNS。
- `nameserver-policy` 只允许把 `rule-set:cn-dns-domains` 这类专用国内业务域名白名单交给国内 DNS；不要按 `DIRECT` / `PROXY` 动作泛化。
- `proxy-server-nameserver` 负责代理节点 server 域名，可以使用国内可直连 DoH 提高节点首连稳定性。

禁止把国内 DNS 写进业务 `nameserver`、非 `cn-dns-domains` 的 `nameserver-policy` 或 `direct-nameserver` 来处理普通目标网站域名。即使某条规则最终是 `DIRECT`，它也仍然可能是账号平台、海外服务或敏感业务域名，不能因此默认回到国内解析链。

Mihomo 的 provider 更新也要分清两条链路：

- `proxy-providers` 拉机场订阅节点清单，默认应在每个机场 provider 上显式写 `proxy: DIRECT`，让后台订阅 URL 更新直连。
- `rule-providers` 拉本仓库 GitHub 规则集产物，可以按当前网络环境使用 `proxy: "🚀 节点选择"`，避免规则更新被 GitHub 访问质量影响。
- 浏览器打开机场官网 / 面板不走 provider 下载逻辑，应由 `rules` 里的 `PROCESS-NAME + 域名` 规则控制；不要用 `proxy-providers.*.proxy` 去推断浏览器访问路径。

## Sub-Store proxy-node-domains 要求

`proxy-node-domains` 的职责是从 Sub-Store 聚合订阅 `global-egress` 中自动提取所有节点的 `server` 字段，过滤 IP，只保留域名，一行一个。

必须满足：

- 自动生成，不手工维护机场节点域名。
- 节点变化后自动更新。
- 输出格式适配 Surge `DOMAIN-SET`。
- 只包含节点 `server` 域名。
- 不包含订阅链接域名、机场面板域名、普通网站域名。
- 默认去重、转小写、去掉空白。

Sub-Store 的 file 脚本应直接输出文本内容，不要把数组赋给 `$content`；数组会被序列化成逗号分隔文本，不符合 Surge `DOMAIN-SET` 预期。脚本逻辑可按这个职责实现：

```js
var domains = new Set();
var excludeList = new Set(["localhost", "null"]);
var ipv4Pattern = /^(?:\d{1,3}\.){3}\d{1,3}$/;
var ipv6Pattern = /:/;
var domainPattern = /^(?:[A-Za-z0-9_-]+\.)+[A-Za-z0-9-]+$/;

let clashMetaProxies = await produceArtifact({
    type: "collection",
    name: "global-egress",
    platform: "ClashMeta",
    produceType: "internal"
});

for (var i = 0; i < clashMetaProxies.length; i++) {
  var p = clashMetaProxies[i];
  var server = (p.server || "").trim().toLowerCase();
  if (!server) continue;
  server = server.replace(/^\[(.*)\]$/, "$1");
  if (excludeList.has(server)) continue;
  if (ipv4Pattern.test(server) || ipv6Pattern.test(server)) continue;
  if (!domainPattern.test(server)) continue;
  domains.add(server);
}

$content = Array.from(domains).sort().join("\n") + "\n";
```

实际发布 URL 应使用 Surge 所在设备能直接访问的 Sub-Store 分享文件链接，例如 `https://<你的 Sub-Store 后端或反代域名>/share/file/proxy-node-domains`。不要把这里固定写成公网 `https://sub.store/...`，除非它在生产 Surge 环境中确实能稳定访问到你的 Sub-Store 后端。

提交或加载生产配置前，必须先在 Surge 所在设备或同网络环境中直接打开该 URL，确认返回值是一行一个节点 `server` 域名，而不是 HTML 页面、404、超时、订阅链接、IP 清单或逗号分隔文本。

## 验收标准

每次改 DNS、代理、Sub-Store、规则集、Tun、透明代理或 fake-ip 相关配置后，都必须验证：

- `whoer.net` DNS 检测不再显示阿里云、腾讯云或其他非预期国内 DNS。
- `dnsleaktest.com` 不再泄漏到国内 DNS。
- `browserleaks.com/dns` 不再泄漏到国内 DNS。
- Surge DNS 日志 / 请求日志中，普通海外目标域名没有走国内 DNS。
- Mihomo 运行时 `/configs` 或客户端日志中，业务 `nameserver`、DNS 服务器 bootstrap `default-nameserver` 与节点 `proxy-server-nameserver` 分工符合预期。
- 普通浏览器访问海外网站时，DNS 出口与代理出口 IP 不再冲突。
- 代理节点仍能正常连接。
- 订阅与规则集仍能正常更新。

外部检测必须在真实客户端生效后执行。仓库静态检查只能防止明显危险配置进入模板，不能替代真实网络出口验证。

## 禁止项

- 禁止把 Surge 全局 `dns-server` 设置为 `system + 国内 DNS`，除非是明确标注的临时排障，并且排障后立即回滚。
- 禁止把 `https://dns.alidns.com/dns-query` 或 `https://doh.pub/dns-query` 设置为 Surge 全局 `encrypted-dns-server`。
- 禁止把国内 DNS 写入 Mihomo 业务 `nameserver`。
- 禁止把所有 `DIRECT`、所有国内直连规则或代理节点 server 域名混进 `cn_dns_domains`。
- 禁止把订阅链接域名误当成节点 server 域名。
- 禁止把机场面板域名、订阅转换链接、Sub-Store 入口或普通网站域名写进 `proxy-node-domains`。
- 禁止在生产 Surge 配置中直接使用未经同网络验证的 `https://sub.store/api/file/proxy-node-domains`；应使用可直达的 Sub-Store 后端/反代分享文件 URL。
- 禁止只验证“网页能打开”，不验证 DNS 出口。
- 禁止在 Surge 和 Mihomo 之间混用 DNS 方案。

## 复盘要求

如果再次发现 DNS 泄漏或 DNS 出口与代理出口不一致，复盘时至少回答：

- 普通目标网站域名实际走了哪条 DNS 链？
- 代理节点 server 域名实际走了哪条 DNS 链？
- 订阅链接域名是否被误塞进节点 server 域名清单？
- 静态检查为什么没有拦住？
- 外部验收为什么没有覆盖？
- 是否需要更新 `tools/check_dns_safety.py`、公开模板、私有同步脚本或本方法论文档？
