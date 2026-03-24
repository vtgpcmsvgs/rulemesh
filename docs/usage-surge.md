# Surge 使用说明

## 推荐入口

- 个人终端版公开参考模板：[`docs/examples/surge-public.conf`](examples/surge-public.conf)
- 规则产物入口：`dist/surge/rules/`

这个模板是基于本地长期使用的 Surge 配置整理出来的公开版，保留了总开关、区域自动切换、拒绝规则、直连规则与 IP 规则的完整结构，但移除了不适合公开仓库的个人化部分。

## 版本划分

- 软路由集群版
  - 用于工作电脑集群接入软路由 Surge。
  - 可保留 `SRC-IP` 设备分流、私有订阅地址与完整 `[MITM]`。
  - 这类内容不适合入公开仓库，建议只在本地私有目录维护。
- 个人终端版
  - 用于同事个人终端或可公开分享的配置。
  - 对应本仓库的 [`docs/examples/surge-public.conf`](examples/surge-public.conf)。
  - 默认移除 `SRC-IP` 设备分流、私有订阅地址与整个 `[MITM]`。

## 模板保留了什么

- 总开关 + 手动切换 + 自动测速切换
- 香港、台湾、日本、新加坡、美国、韩国的区域自动组
- `reject`、`direct`、`proxy`、`region` 四类 RuleMesh 产物接入
- 1 条 `DOMAIN-KEYWORD,adspower` 内联规则与 `proxy/gfw.list` 广谱代理规则的顺序关系
- `skip-proxy`、`always-real-ip`、基础 DNS 与测速参数

## 模板刻意移除了什么

- 按局域网源 IP 的设备分流（`SRC-IP` + `AND/OR`）
- 私有 `policy-path` 地址与真实机场命名
- 整个 `[MITM]` 段及证书参数

## 使用前只需要替换两处

1. 把模板里所有 `https://example.com/subs/surge/all?target=Surge` 替换成你自己的 Surge 聚合订阅入口。
2. 如果你不希望最终兜底走总开关，可以把 `FINAL,🚀 节点选择` 改成你想固定兜底的区域组。

## 规则顺序建议

1. 拒绝规则
2. 区域精确规则
3. GitHub 仓库 SSH 定向直连
4. 少量内联关键词代理规则（如 AdsPower）
5. 代理优先规则
6. 直连规则
7. IP 规则
8. `FINAL`

注意：

- `region/tw/google_tw.list` 必须放在 `region/hk/global_media.list` 等广谱区域规则前。
- `direct/github_ssh_direct.list` 必须放在 `proxy/gfw.list` 前，只给 `github.com:22` 与 `ssh.github.com:443` 直连，避免把 GitHub 网页误放直连。
- `DOMAIN-KEYWORD,adspower` 建议放在 `proxy/gfw.list` 前；当前公开模板只保留这一条 AdsPower 关键词规则，方便按你的实际环境自行继续细化。
- `proxy/gfw.list` 建议放在其他普通 `direct/*.list` 前，减少广谱直连误伤。
- 浏览器明文 HTTP 拦截推荐直接接 `plain_http_reject.list`，不要再手写重复规则。

## 使用原则

- 客户端只引用 `dist/surge/rules/`
- `rules/` 是源规则层，不建议在 Surge 配置中直接引用
- 不要在客户端继续引用第三方原始规则 URL
- 不要手改 `dist/`，应先改 `rules/` 后重新构建
