# Mihomo TUN / DNS / 嗅探维护方法论

用户已批准 2026-09-09 性能方案，完整规则见 [性能基线](performance-baseline.md)。旧版默认海外 nameserver 与大量高优先级镜像 policy 不再适用于当前七份配置。

## 当前结构

普通业务国内双 DoH；AI 两个海外 DoH 显式指定美国组；国内 `proxy-server-nameserver` 为代理节点提供独立 bootstrap。AI 业务固定美国，Crypto 台湾和其他已登记地区要求仍优先于自动测速。普通代理规则使用全地区自动组；2026-09-12 起未命中前置规则的 MATCH 使用 DIRECT。

保留 `ipv6: false`、`dns.ipv6: false`、`use-hosts: false`、`use-system-hosts: false`、`respect-rules: false`。保留 TUN、UDP/TCP 53 劫持、域名嗅探、fake-ip、ARC 缓存及必要的 fake-ip-filter，开启 TCP 并发。`fallback`、`direct-nameserver`、`proxy-server-nameserver-policy` 不属于这版最小结构。

`default-nameserver` 引导 DNS 服务器自身；`proxy-server-nameserver` 只解析节点 server 域名；`nameserver` 处理普通目标。这三类用途明确，但允许使用同一国内服务商。不再重复加载中国 DNS 专用大清单。机场 provider 必须 `proxy: DIRECT`；其下载不是普通业务访问订阅端点的连接。

## 运行时验证

本次七份配置的静态检查和三份 Mihomo 的原生语法检查分别执行；DNS 路由运行时仍未确认。旧版 v1.19.25 曾出现 DNS 查询未命中模拟 resolver 的情况，不能拿旧版测试证明新版生效，也不能把“静态检查已通过”解释为线路吞吐已经提升。


发生 provider 全部测速失败但直导可用时，先通过实际 controller/命名管道和日志确认 DNS 及最终配置。只读探测不可读时报告证据缺口，不猜测端口、不强制重复健康检查。运行态审计不得输出节点或订阅秘密。

## 验证顺序

1. 静态检查地区过滤、AI 与 Google 的顺序、AI DNS 的美国组参数，以及节点 bootstrap。
2. 标准 Mihomo 可用 `-t -d` 在专用临时目录检查。FlClashCore 使用原生 IPC，不能传 Mihomo 命令行参数；先 `validateConfig` 检查 YAML，再隔离 `setupConfig` 检查语义与资源加载。禁止把临时缓存写入用户主目录。
3. 客户端加载后对抖音、小红书、微信检查 DIRECT；AI 检查美国，Crypto 检查台湾，券商/日本例外检查对应地区。
4. 检查 DNS 实际出口与连接耗时，再评估吞吐。不要只看网页可打开或健康检查成功。

客户端不同不要求逐字段相同。Surge 的 Host / Enhanced Mode 机制不能搬进 Mihomo；任何新字段都先核对 [Mihomo 官方语义](https://wiki.metacubex.one/config/dns/)。

2026-09-12 FlClash 迁移与优化以 [客户端性能基线](flclash-performance.md) 为准：桌面和安卓使用新文件名；通用末尾改为 cn_direct_light → gfw_precise → DIRECT，完整规则资产保留。工作白名单不接入新兜底，机场手动组保留。桌面 300 秒、安卓 600 秒，备用地区按需检测；以最终生成配置核对界面覆写。
