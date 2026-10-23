# 1Password 通用代理规则

2026-10-23 用户确认继续使用 1Password，但无需专项规则。客户端统一调用 `proxy/general_proxy`，通过 INCLUDE 合并 GitHub 核心 HTTPS 与 `rules/upstream/onepassword/core_domains.list`；不再发布 `proxy/onepassword_proxy` 或注册独立 provider。使用既有全地区自动选择，沿用默认国内 DNS。

`tools/sync_upstream_rules.py` 继续每日读取 [1Password 官方端口与域名说明](https://support.1password.com/ports-domains/)，生成官方核心域名快照。必须保留 `1password.com`、`1passwordservices.com`、`1passwordusercontent.com`、`app-updates.agilebits.com`、`1infra.net`、`cache.agilebits.com`。支持官方的 .ca / .eu 变体；抓取失败、结构异常或核心域名缺失时保留旧快照并报告失败。

Watchtower、Fastmail、Brex、Privacy Cards 等第三方依赖不自动纳入。规则不能扩展成宽泛共享根域或关键词。

Surge 使用 `dist/surge/rules/proxy/general_proxy.list`；Mihomo 使用 `dist/mihomo/classical/proxy/general_proxy.yaml`，provider 为 `proxy_general`。放在 GitHub SSH 精确直连与 Raw 自举之后、广谱规则之前。工作白名单只放行上述精确服务，最终仍为 REJECT。公开模板与私有配置一致接入此通用入口。
