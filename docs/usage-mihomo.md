# Mihomo 使用说明

适用于：

- Clash Verge Rev
- Clash Meta for Android
- 其他兼容 Mihomo `rule-providers` 的客户端

## 先看原则

- 客户端只引用 `dist/mihomo/classical/`
- `rules/` 是源规则层，不建议客户端直接引用
- 本仓库统一输出 `behavior: classical`
- Google 相关（含 Google Play / Gemini / YouTube / FCM）统一接 `region/tw/google_tw.yaml` 并绑定 `TW-AUTO`
- 局域网设备分流建议在客户端配置中硬编码（`SRC-IP` + `AND/OR`），不在仓库 `dist` 规则集中维护

本文示例统一使用主分支 raw 地址：

```text
https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main
```

## rule-providers 示例

```yaml
rule-providers:
  reject-plain-http:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/reject/plain_http_reject.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/reject/plain_http_reject.yaml
    interval: 86400

  tw-google-classical:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/region/google_tw.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/region/tw/google_tw.yaml
    interval: 86400

  gfw-classical:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/proxy/gfw.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/proxy/gfw.yaml
    interval: 86400
```

## 推荐顺序

建议顺序：

1. 拒绝规则
2. 区域规则
3. 代理规则
4. 直连 / 香港区域
5. `MATCH`

注意：

- `region/tw/google_tw.yaml` 对应规则应放在 `region/hk/global_media.yaml` 前。
- `proxy/gfw.yaml` 建议放在 `direct/cn_direct.yaml` 前，减少广谱直连误伤。

一个最小可用示例：

```yaml
rule-providers:
  reject-plain-http:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/reject/plain_http_reject.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/reject/plain_http_reject.yaml
    interval: 86400

  reject-os-update:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/reject/os_update_reject.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/reject/os_update_reject.yaml
    interval: 86400

  tw-google-classical:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/region/google_tw.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/region/tw/google_tw.yaml
    interval: 86400

  hk-global-media-classical:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/region/hk/global_media.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/region/hk/global_media.yaml
    interval: 86400

  gfw-classical:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/proxy/gfw.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/proxy/gfw.yaml
    interval: 86400

  cn-direct-classical:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/direct/cn_direct.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/direct/cn_direct.yaml
    interval: 86400

rules:
  - RULE-SET,reject-plain-http,REJECT
  - RULE-SET,reject-os-update,REJECT

  - RULE-SET,tw-google-classical,TW-AUTO
  - RULE-SET,hk-global-media-classical,HK-AUTO

  - RULE-SET,gfw-classical,PROXY
  - RULE-SET,cn-direct-classical,DIRECT

  - MATCH,PROXY
```

## 常见误区

- 不要把 `classical` 产物误配成别的 `behavior`
- 不要继续引用 `rules/` 源规则路径
- 不要再找旧的纯域名或纯 CIDR 产物目录；仓库已经统一走 `classical`
- 不要再引入无扩展名源文件；构建脚本会拒绝