# DNS 解析边界

用户已批准 2026-09-09 普通业务使用国内 DNS、以性能优先的方案。此文不再要求普通海外业务全部使用海外 DNS；当前唯一强制独立海外解析的是 AI，详见 [性能基线](../performance-baseline.md)。

## 用途分离

DNS 服务域名 bootstrap、代理节点 server 域名、普通目标网站是三类用途。订阅链接和面板域名不能混入 Sub-Store 的 proxy-node-domains；该文件仍要求过滤 IP、一行一个节点域名。

Surge 使用国内全局 DNS，Host 第一项为 ai_us 的 Cloudflare DoH，Cloudflare 连接固定美国；节点域名继续由 DOMAIN-SET 分享文件单独引导。保留代理侧解析、传统 DNS 接管及加密 DNS 遵守出站，不伪造 proxy-server-nameserver 或 dns-mode 字段。

Mihomo 普通 nameserver 使用国内双 DoH，唯一 AI policy 指定两个海外 DoH 和美国组；proxy-server-nameserver 使用国内双 DoH，避免节点解析与 AI DNS 循环。respect-rules、hosts 混入和 IPv6 保持关闭。

## DNS 不决定流量放行

Crypto 台湾、香港券商香港、明确日本入口仍由规则强制出站。工作白名单保持 FINAL,REJECT，抖音、微信、小红书属于精确允许入口；默认国内 DNS 不会把其他网站变成白名单。cn_dns_domains 与 cn_performance_dns_domains 作为可选产物保留，当前通用配置不再依赖它们做国内解析。

GitHub Raw 仍有独立海外解析例外，用于规则下载。其他未定制公共资源优先直接使用活跃上游；自定义规则继续引用仓库构建产物。

## 验证边界

静态检查已通过与运行态已确认是不同结论。历史 v1.19.25 的查询未命中模拟 resolver，不能用于证明新版；当前 DNS 路由运行时仍未确认。生产加载后应同时检查规则、DNS 出口与响应耗时，尤其注意客户端覆写、应用内置 DoH 和缓存。

检查工具对带日期标记的新基线强制校验 DNS/地区边界；无日期标记的旧文件仍按历史保守方案检查。真实订阅地址、密钥、header、证书与节点值禁止进入日志或公开文档。
