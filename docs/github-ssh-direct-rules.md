# GitHub 仓库 SSH 定向直连规则

这组规则用于把 GitHub 仓库 SSH 连接单独放到直连，同时保留 GitHub 网页、API、Gist、Raw 内容与其他 GitHub 站点流量继续走代理。

当前源规则文件：`rules/direct/github_ssh_direct.list`

匹配范围只有两条：

- `github.com:22`
- `ssh.github.com:443`

这样可以覆盖两种常见场景：

- 标准 SSH remote：`git@github.com:owner/repo.git`
- 显式启用 SSH over 443：通过 `ssh.github.com:443` 连接

## 为什么要放在 `proxy/gfw` 前

上游 `proxy/gfw` 当前已经包含 `.github.com` 与 `.githubusercontent.com`。现在仓库还额外提供了 [`proxy/general_proxy`](github-core-proxy-rules.md) 这组更细的显式代理入口，用来专门承接 GitHub 网页、API、Gist、Raw 与静态资源。

如果把 GitHub SSH 定向直连规则放在 `proxy/general_proxy` 或 `proxy/gfw` 后面，`github.com:22` 会先命中广谱代理规则，后面的直连规则就不会再生效。

因此客户端接入时应使用下面顺序：

1. 拒绝规则
2. 区域精确规则
3. `direct/github_ssh_direct`
4. Surge 专用：`DOMAIN,raw.githubusercontent.com,"🚀 节点选择"` 自举入口
5. `proxy/general_proxy`
6. Crypto 台湾等前置业务入口；Polygon/BSC RPC 已并入 Crypto
7. `proxy/gfw`
8. 其他普通 `direct/*`
9. IP 规则
10. 最终兜底

## 产物链接

Surge：

- `https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/direct/github_ssh_direct.list`

Mihomo / FlClash 桌面端：

- `https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/direct/github_ssh_direct.yaml`

## 示例

Surge：

```ini
# 必须放在 GitHub Core / proxy/gfw.list 前；Crypto 台湾入口已统一覆盖 Polygon/BSC RPC
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/direct/github_ssh_direct.list,DIRECT
DOMAIN,raw.githubusercontent.com,"🚀 节点选择"
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/proxy/general_proxy.list,"🚀 节点选择"
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/proxy/gfw.list,"🚀 节点选择"
```

Mihomo / FlClash 桌面端：

```yaml
rule-providers:
  direct_github_ssh:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/direct/github_ssh_direct.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/direct/github_ssh_direct.yaml
    interval: 86400

  proxy_general:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/proxy/general_proxy.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/proxy/general_proxy.yaml
    interval: 86400

rules:
  # 必须放在 proxy_general / proxy_gfw 前；Crypto 台湾入口已统一覆盖 Polygon/BSC RPC
  - RULE-SET,direct_github_ssh,DIRECT
  - RULE-SET,proxy_general,🚀 节点选择
  - RULE-SET,proxy_gfw,🚀 节点选择
```

2026-10-23：GitHub 核心 HTTPS 通过 `proxy/general_proxy` 与 1Password 共同接入通用自动选择；`github_core_proxy.list` 作为源组件保留，客户端不再单独调用。SSH 精确直连与 Raw 自举顺序保持。
