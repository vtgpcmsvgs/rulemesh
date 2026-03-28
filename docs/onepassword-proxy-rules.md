# 1Password 专项代理规则约定

本文记录 `proxy/onepassword_proxy` 的维护边界、自动同步来源与接入方式，避免后续把 1Password 的重度用户特化误扩散成公开模板默认行为，或把第三方依赖域名无边界地并进代理入口。

## 适用范围

- `rules/proxy/onepassword_proxy.list`
- `rules/upstream/onepassword/core_domains.list`
- `tools/sync_upstream_rules.py`
- 本地私有 `rulemesh-substore-surge-personal.conf`
- 本地私有 `rulemesh-substore-surge-work-whitelist.conf`
- 本地私有 `rulemesh-substore-mihomo-clash-verge.yaml`
- 本地私有 `rulemesh-substore-mihomo-clash-meta.yaml`

## 设计目标

- 为 1Password 重度用户提供稳定的 `🚀 节点选择` 专项入口
- 规则由仓库每天自动同步，后续无需继续手工追域名
- 只保留 1Password 官方自有核心域名与更新/基础设施端点
- 不把 Watchtower、Fastmail、Brex、Privacy Cards 等第三方依赖域名默认卷入代理入口

## 上游来源

- 主来源：`https://support.1password.com/ports-domains/`
- 同步脚本每天抓取官方支持页，再保守生成 `rules/upstream/onepassword/core_domains.list`
- 解析结果必须保留核心域名：`1password.com`、`1passwordservices.com`、`1passwordusercontent.com`、`app-updates.agilebits.com`、`1infra.net`、`cache.agilebits.com`
- 如果官方页面结构异常、抓取失败或缺少核心域名，本次同步会保留旧快照，不会用异常结果覆盖现有文件

## 自动同步边界

- 自动保留：
  - `1password.com` / `.ca` / `.eu`
  - `1passwordservices.com`
  - `1passwordusercontent.com` / `.ca` / `.eu`
  - `app-updates.agilebits.com`
  - `1infra.net`
  - `cache.agilebits.com`
- 不自动保留：
  - `api.pwnedpasswords.com`
  - `fastmail.com`
  - `jmap.fastmail.com`
  - `api.privacy.com`
  - `accounts.brex.com`
  - `platform.brex.com`
  - 其他只影响特定扩展功能或第三方集成的域名

## 客户端接入

- Surge:
  - 接入 `dist/surge/rules/proxy/onepassword_proxy.list`
  - 顺序必须放在 `proxy/gfw.list` 前
- Mihomo:
  - 接入 `dist/mihomo/classical/proxy/onepassword_proxy.yaml`
  - 顺序必须放在 `proxy_gfw` 前
- Surge 工作白名单:
  - 这条规则属于显式放行入口
  - 建议顺序放在“私有订阅更新直连”之后、“AdsPower”之前

## 公开模板边界

- 公开模板默认不内置 `proxy/onepassword_proxy`
- 原因不是它无效，而是它属于“重度用户特化”而非所有用户的默认行为
- 如果未来决定把它升级成公开模板默认入口，必须同步更新 `README.md`、`docs/usage-surge.md`、`docs/usage-mihomo.md` 与两份公开模板
