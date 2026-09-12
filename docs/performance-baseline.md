# 2026-09-09 性能基线

本基线适用于两份公开模板与五份私有主配置，取代 2026-08-21 的默认海外 DNS、Google 全业务香港和全业务按地区名固定出口的方案。用户已接受普通业务使用国内 DNS；地区访问条件仍优先于测速结果。

| 业务 | 出口 | DNS |
| --- | --- | --- |
| 海外 AI，包括 OpenAI、Claude、Gemini、AI Studio、NotebookLM | 美国自动组 | 两个海外 DoH，通过美国出口 |
| Crypto，包括交易所、Polymarket、Polygon/BSC RPC | 台湾自动组 | 默认国内双 DoH |
| 已登记的 `opinion.trade` 日本访问例外 | 日本自动组，优先于 Crypto 通用入口 | 默认国内双 DoH |
| 香港券商、Personal 香港证券入口 | 香港自动组 | 默认国内双 DoH |
| 抖音、小红书、微信 | DIRECT，前置于 Google 广谱与广告拒绝 | 国内双 DoH |
| 其他既有直连业务 | 保持 DIRECT | 国内双 DoH |
| 命中前置规则的其余海外代理业务 | 全地区自动组 | 默认国内 DNS；Surge 代理连接继续允许代理侧解析 |
| 未命中前置规则的普通业务 | DIRECT；工作白名单为 REJECT | 默认国内双 DoH |

地区绑定记录当前用户要求和已登记访问条件。新增地区限制应记录具体业务和依据，不应仅凭 `region/` 路径名推断。

## 规则与性能

- AI 入口放在第一条有效规则，避免 Google 完整 IP 地址空间和其他广谱规则抢先匹配；国内 AI 继续使用 `ai_cn_direct` 直连。
- 抖音复用 `bytedance_direct`；新增 `cn_social_direct` 仅维护微信、小红书及专用 CDN 域名，不放宽整个腾讯或通用云服务。
- 日本精确例外、Crypto 和香港券商都早于 Google 广谱规则。`google_hk`、`global_media` 等旧路径保留以兼容已有订阅，但一般业务默认自动择优。
- 全地区组去掉国家标签筛选，只排除套餐占位项，允许没有地区标签的有效节点参与。Mihomo 使用 300 秒主动测速、全地区容差 50、美国容差 100；测速只衡量连接延迟，不等同于下载吞吐。
- Mihomo 开启 `tcp-concurrent`，并发尝试目标的多个 IP，采用先成功的连接；保持 IPv4、ARC 缓存和 fake-ip。Surge 保持原有 smart 组与客户端自身连接机制，不机械移植同名字段。
- AWS IP 区域组和 `chain_socks5_ipcidr` 不再注册或调用于配置；`rules/`、上游登记与 `dist/` 产物继续保留，暂停使用不等于删除维护资产。
- Surge 只清理随 AWS/链式功能停用的设备专用组。机场手动组是独立选择功能，即使没有规则引用也必须保留；三份私人 Surge 各恢复七组，保持原订阅与过滤器，设为可见并接入手动选择入口。两份 Mihomo 原有九组未删除，本轮保留。

## DNS

普通业务默认使用 AliDNS 与 DNSPod 两个国内 DoH，减少国内 CDN 调度偏差及海外解析绕行。不再为普通代理、拒绝或地区规则镜像大量海外 DNS policy，也不重复加载十万条性能型 DNS 专用域名清单。原清单仍保留为可选规则资产。

Surge 保留 `use-local-host-item-for-proxy = false`、`hijack-dns = *:53` 与 `encrypted-dns-follow-outbound-mode = true`。`[Host]` 第一项将 `ai_us` 指定到 Cloudflare DoH，独立 `region/us/ai_dns_us` 规则集使用相同美国组；GitHub Raw 规则下载保留同一解析例外。节点域名仍通过 Sub-Store 的 `proxy-node-domains` 分享文件单独 bootstrap，不能写入订阅域名或 IP。

Mihomo 的 `nameserver` 使用国内双 DoH；唯一 `nameserver-policy` 为 `rule-set:us_ai`，将 Cloudflare 和 Google DoH 都显式附加 `#美国组名`。按 Mihomo 原生语义，同时配置国内 `proxy-server-nameserver` 解析节点域名，避免指定代理的 AI DNS 形成自举循环。`respect-rules`、`use-hosts`、`use-system-hosts`、`ipv6` 保持 false；不引入 `fallback`、`direct-nameserver` 或第二层节点 DNS policy。

依据：[Mihomo DNS 文档](https://wiki.metacubex.one/config/dns/)与 [TCP 并发说明](https://wiki.metacubex.one/config/general/)。此处的 `proxy-server-nameserver` 是本次明确采用的自举依赖，旧版禁止该字段的说明不再适用于这版基线。

## 工作白名单与分发

工作配置保留既有设备条件和 `FINAL,REJECT`，仅在原有抖音直连基础上补充微信、小红书精选入口；不增加 `cn_direct` 或 `gfw` 广谱放行。国内默认 DNS 本身不授予流量放行。已有小型 `cn_dns_domains` 引用可保留，但不替换为性能型清单。Personal 专项规则仍不复制到工作配置。

GeoIP 直接使用 `https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/country.mmdb`，Mihomo 保持每 24 小时更新；停止本仓库的自动二次 Release 分发。自定义规则必须继续引用本仓库构建产物，以保留本地补充、顺序与客户端格式；其他未定制的公共资源优先选择维护活跃的上游入口。

## 校验与经验

`tools/check_performance_baseline.py` 校验带日期标记的当前配置；旧版检查仍用于没有该标记的历史配置与回归夹具。新的校验不是豁免：必须验证真实地区过滤条件、规则先后顺序、AI DNS 的代理参数、国内自举、工作拒绝边界、AWS 停用与上游地址。

- 精简注释时曾丢失私有订阅同步块标记；已按原始规则身份恢复，新增私有标记完整性检查，确保后续同步脚本仍可定位。
- 实际运行订阅同步时发现 Surge 分支传入空缩进，但必填字符串参数拒绝空值；已在最窄的 Prefix 参数添加 AllowEmptyString，并以真实 PowerShell 参数绑定回归验证。必填参数不等于非空内容要求。
- 首轮迁移预检发现多个组可以复用相同美国过滤器；已改为从实际 `ai_us` 路由解析目标，再验证过滤条件。不得按“美国组必须唯一”猜测；所有配置先预检再写入。
- 用户补充地区要求后，已将地区例外加入机械检查，防止全局性能替换再次覆盖 Crypto 或券商要求。
- 本机系统 Python 不保证安装 PyYAML；静态检查复用仓库标准库解析器，真实 YAML 语法交给 Mihomo `-t -d`。不要把依赖缺失误判成配置错误。
- Windows 全仓搜索用目录加 `--glob`，不向 `rg` 传递 PowerShell 未展开的通配路径；非零退出立即处理。
- 构建与静态校验通过不代表生产运行时已加载。Surge 必须在实际 Mac 上更新配置并检查出口；Mihomo 需要确认最终生效配置与外层覆写。不得把未发生的吞吐提升写成测试结果。

## 机场组恢复与规则归并

- 上轮把没有规则引用的机场组误判为无用设备组；现已分开维护，检查器要求三份私人 Surge 的机场保护块各有七个有效且可见的独立 select 组，并验证手动入口引用。机场增减时同步调整该基线及检查，不能静默删组。
- 爱思的四条域名及关键词集中到 `direct/aisi_direct`，只在 Surge Personal 与对应公开模板调用；两个 Apple 下载域名由既有 `apple_direct` 覆盖。Google Play / Android 的五条重复域名由更早的 `google_hk` 覆盖。
- `region/us/ai_dns_us` 只集中 Cloudflare DoH 精确主机，不合并进普通海外 DNS 或 AI 业务域名集。Mihomo 保留 DoH URL 的美国代理参数，不增加无用 provider。
- 设备源地址、订阅端点与同步标记留在私人配置；GitHub Raw、自举 DNS 及工作观察项继续独立。归并不能越过设备条件或扩大白名单。
- 多文件补丁预检失败时不继续落盘；迁移先核对全部节标题、数量和历史来源，通过后统一写入。正则替换含过滤器的文本时使用函数返回字面内容，避免反斜杠被解释为替换转义。
- 发布后核对 GitHub Raw 内容时，应与已提交的 `git show HEAD:<路径>` 内容比较；Windows 工作区可能经过 CRLF 转换，直接比较工作区字节会把正确发布误报为内容不一致。

## 2026-09-12 兜底直连补充

用户要求两份 Surge Personal、两份 Mihomo 与两份公开模板的最终兜底统一 DIRECT，减少未被国内规则覆盖的业务绕行。Surge 保留 `FINAL,DIRECT,dns-failed`，Mihomo 使用 `MATCH,DIRECT`；工作白名单保持 `FINAL,REJECT`。这一变更同样适用于未命中前置规则的海外域名，不会自动保证其可达。

AI、Crypto、其他明确地区、Google、gfw 等前置规则和机场组不变；默认国内 DNS、AI 专用美国 DoH 与节点 bootstrap 不变。检查器按当前基线拒绝把普通兜底改回自动组，历史无标记夹具继续保留历史校验语义。
