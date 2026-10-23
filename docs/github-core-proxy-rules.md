# GitHub 核心代理规则

GitHub 网页、API、Gist、Raw、静态资源和附件使用代理；Git SSH 由 direct/github_ssh_direct 精确直连。2026-10-23 起，客户端通过 `proxy/general_proxy` 统一接入 GitHub 核心与 1Password，不再单独注册 GitHub Core provider。

`rules/proxy/github_core_proxy.list` 作为通用入口的源组件与兼容产物保留，范围为 api.github.com、gist.github.com、gist.githubusercontent.com、raw.githubusercontent.com 及 github.com、githubassets.com、githubusercontent.com 的后缀，不扩大到 github.io。

当前客户端顺序以两份公开模板为准：AI 美国优先，国内精选和地区必需规则早于 Google 广谱；GitHub SSH 与 Surge Raw 自举早于通用代理，末尾使用 cn_direct_light → gfw_precise → DIRECT。Crypto 入口已包括 Polygon/BSC RPC，1Password 已包括在 general_proxy。工作白名单仍以 FINAL,REJECT 结束。

Surge 接入 `dist/surge/rules/proxy/general_proxy.list`；Mihomo 注册 `proxy_general`，引用 `dist/mihomo/classical/proxy/general_proxy.yaml`。目标为既有全地区自动选择组。Surge 保留 raw.githubusercontent.com 内联下载自举与独立 Host 解析例外；Mihomo 使用 rule-provider 的 proxy 字段下载。完整示例见 [Surge](examples/surge-public.conf) 与 [Mihomo](examples/mihomo-public.yaml)。
