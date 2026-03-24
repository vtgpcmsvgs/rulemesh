# Mihomo 使用说明

适用于：

- Clash Verge Rev
- Clash Meta for Android
- 其他兼容 Mihomo `rule-providers` 的客户端

## 推荐入口

- 完整公开参考模板：[`docs/examples/mihomo-public.yaml`](examples/mihomo-public.yaml)
- 规则产物入口：`dist/mihomo/classical/`

这个模板是基于本地长期使用的 Mihomo 配置整理出来的公开版，保留了多订阅聚合、区域自动切换、`rule-providers` 与完整规则顺序，但移除了真实机场地址和其他不适合公开仓库的私有信息。

## 模板保留了什么

- `dns + proxy-providers + proxy-groups + rule-providers + rules` 的完整结构
- 多订阅聚合后的统一总开关与区域自动组
- `reject`、`direct`、`proxy`、`region` 四类 RuleMesh `classical` 产物接入
- 1 条 `DOMAIN-KEYWORD,adspower` 内联规则与 `proxy/gfw.yaml` 广谱代理规则的顺序关系
- 用 `plain_http_reject.yaml` 接管浏览器明文 HTTP 拦截

## 模板刻意移除了什么

- 真实机场订阅链接、供应商命名与 token
- `external-controller`、`secret` 等控制面参数
- 按局域网源 IP 的设备分流逻辑

## 使用前只需要替换两处

1. 把模板里 `provider_a`、`provider_b`、`provider_c` 的 `url` 改成你自己的订阅地址。
2. 如果你不希望最终兜底走总开关，可以把 `MATCH,🚀 节点选择` 改成你想固定兜底的区域组。

## 规则顺序建议

1. 拒绝规则
2. 区域精确规则
3. GitHub 仓库 SSH 定向直连
4. 少量内联关键词代理规则（如 AdsPower）
5. 代理优先规则
6. 直连规则
7. IP 规则
8. `MATCH`

注意：

- `region/tw/google_tw.yaml` 对应规则应放在 `region/hk/global_media.yaml` 前。
- `direct/github_ssh_direct.yaml` 必须放在 `proxy/gfw.yaml` 前，只给 `github.com:22` 与 `ssh.github.com:443` 直连，避免把 GitHub 网页误放直连。
- `DOMAIN-KEYWORD,adspower` 建议放在 `proxy/gfw.yaml` 前；当前公开模板只保留这一条 AdsPower 关键词规则，方便按你的实际环境自行继续细化。
- `proxy/gfw.yaml` 建议放在其他普通 `direct/*.yaml` 前，减少广谱直连误伤。
- `reject_plain_http` 已有构建产物，公开模板不再建议手写重复的浏览器进程规则。

## 使用原则

- 客户端只引用 `dist/mihomo/classical/`
- `rules/` 是源规则层，不建议客户端直接引用
- 不要把 `classical` 产物误配成别的 `behavior`
- 不要再找旧的纯域名或纯 CIDR 产物目录；仓库已经统一走 `classical`
- 不要手改 `dist/`，应先改 `rules/` 后重新构建
