# GitHub 核心代理规则

这组规则用于把 GitHub 网页、API、Gist、Raw、静态资源与附件流量显式交给节点选择，同时保留 Git 传输继续由 SSH carve-out 单独直连。

当前源规则文件：`rules/proxy/github_core_proxy.list`

## 设计目标

- `git@github.com:owner/repo.git` 这类 Git 传输继续走 `direct/github_ssh_direct`
- GitHub 网页、Issues、Pull Requests、Actions 页面等 HTTPS 访问显式走代理
- `api.github.com`、`gist.github.com`、`gist.githubusercontent.com`、`raw.githubusercontent.com` 等核心入口显式放行到 `🚀 节点选择`
- 不把 `github.io` 这类用户自定义站点默认并入这组规则

## 当前覆盖范围

- `DOMAIN,api.github.com`
- `DOMAIN,gist.github.com`
- `DOMAIN,gist.githubusercontent.com`
- `DOMAIN,raw.githubusercontent.com`
- `DOMAIN-SUFFIX,github.com`
- `DOMAIN-SUFFIX,githubassets.com`
- `DOMAIN-SUFFIX,githubusercontent.com`

这意味着下面这些常见连接都会被这组规则接住：

- `https://api.github.com/gists`
- `https://api.github.com/users`
- `https://api.github.com/gists/<id>`
- `https://gist.githubusercontent.com/<user>/<id>/...`
- GitHub 网页、Gist 页面、Raw 内容、头像、附件与大部分静态资源

## 顺序建议

公开/个人模板建议按下面顺序接入：

1. 拒绝规则
2. 区域精确规则
3. `direct/github_ssh_direct`
4. Surge 专用：`DOMAIN,raw.githubusercontent.com,"🚀 节点选择"` 自举入口
5. `proxy/github_core_proxy`
6. 其他更细的专项入口，例如 Polygon RPC / BSC RPC / Google Public DNS / 1Password
7. `proxy/gfw`
8. 其他普通 `direct/*`
9. IP 规则
10. 最终兜底

其中第 4 步只属于 Surge：它用于让外部规则首轮下载不依赖后面的远程规则集本身。Mihomo 继续直接通过 `rule-providers` 的 `proxy` 字段下载。

## 产物链接

Surge：

- `https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/proxy/github_core_proxy.list`

Mihomo / FlClash 桌面端：

- `https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/proxy/github_core_proxy.yaml`

## 示例

Surge：

```ini
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/direct/github_ssh_direct.list,DIRECT
DOMAIN,raw.githubusercontent.com,"🚀 节点选择"
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/proxy/github_core_proxy.list,"🚀 节点选择"
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

  proxy_github_core:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/proxy/github_core_proxy.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/proxy/github_core_proxy.yaml
    interval: 86400

rules:
  - RULE-SET,direct_github_ssh,DIRECT
  - RULE-SET,proxy_github_core,🚀 节点选择
  - RULE-SET,proxy_gfw,🚀 节点选择
```
