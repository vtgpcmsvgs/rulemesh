# Mihomo 使用说明

适用于：

- Clash Verge Rev
- Clash Meta for Android
- 其他兼容 Mihomo `rule-providers` 的客户端

## 先看原则

- 客户端以后只引用 `dist/mihomo/classical/`
- `rules/` 是源规则，不建议客户端直接引用
- 本仓库统一输出 `behavior: classical`
- 纯域名规则会写成 `DOMAIN` / `DOMAIN-SUFFIX`
- CIDR 规则会写成 `IP-CIDR` / `IP-CIDR6`
- mixed、关键词、设备源地址、组合规则也统一落到 `classical`
- Google 相关（含 Google Play / Gemini / YouTube / FCM）统一接 `region/tw/google_tw.yaml` 并绑定 `TW-AUTO`

本文示例统一使用当前仓库主分支的 raw 地址：

```text
https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main
```

## rule-providers 写法

统一使用 `behavior: classical`：

```yaml
rule-providers:
  device-pc01:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/device/srcip_pc01.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/device/srcip_pc01.yaml
    interval: 86400

  reject-classical:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/reject/reject.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/reject/reject.yaml
    interval: 86400
```

## 推荐顺序

建议顺序：

1. 设备规则
2. 拒绝规则
3. 区域规则
4. 直连 / 香港区域
5. `MATCH`

注意：`region/tw/google_tw.yaml` 对应的规则需要放在 `region/hk/global_media.yaml` 等广谱区域规则之前，确保 Google 优先命中 TW。

一个最小可用示例：

```yaml
rule-providers:
  device-pc01:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/device/srcip_pc01.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/device/srcip_pc01.yaml
    interval: 86400

  reject-classical:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/reject/reject.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/reject/reject.yaml
    interval: 86400

  adblock-classical:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/reject/adblock.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/reject/adblock.yaml
    interval: 86400

  tw-ai-classical:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/region/ai_tw.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/region/tw/ai_tw.yaml
    interval: 86400

  tw-google-classical:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/region/google_tw.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/region/tw/google_tw.yaml
    interval: 86400

  microsoft-classical:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/direct/microsoft_direct.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/direct/microsoft_direct.yaml
    interval: 86400

  cn-direct-classical:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/direct/cn_direct.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/direct/cn_direct.yaml
    interval: 86400

  hk-global-media-classical:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/region/hk/global_media.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/region/hk/global_media.yaml
    interval: 86400

  hk-telegram-classical:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/region/hk/telegram.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/region/hk/telegram.yaml
    interval: 86400

  aws-hk-classical:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/region/aws_hk_ipv4.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/region/hk/aws_ipv4.yaml
    interval: 86400

  aws-tokyo-classical:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/region/aws_tokyo_ipv4.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/region/jp/tokyo_aws_ipv4.yaml
    interval: 86400

  aws-osaka-classical:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/region/aws_osaka_ipv4.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/region/jp/osaka_aws_ipv4.yaml
    interval: 86400

  aws-seoul-classical:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/region/aws_seoul_ipv4.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/region/kr/seoul_aws_ipv4.yaml
    interval: 86400

  aws-taipei-classical:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/region/aws_taipei_ipv4.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/region/tw/taipei_aws_ipv4.yaml
    interval: 86400

  jp-socks5-classical:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/region/jp_socks5_ipcidr.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/region/jp/jp_socks5_ipcidr.yaml
    interval: 86400

rules:
  - RULE-SET,device-pc01,JP-AUTO

  - RULE-SET,reject-classical,REJECT
  - RULE-SET,adblock-classical,REJECT

  - RULE-SET,tw-ai-classical,TW-AUTO
  - RULE-SET,tw-google-classical,TW-AUTO

  - RULE-SET,microsoft-classical,DIRECT
  - RULE-SET,cn-direct-classical,DIRECT

  - RULE-SET,hk-global-media-classical,HK-AUTO
  - RULE-SET,hk-telegram-classical,HK-AUTO

  - RULE-SET,aws-hk-classical,HK-AUTO,no-resolve
  - RULE-SET,aws-tokyo-classical,TOKYO-AUTO,no-resolve
  - RULE-SET,aws-osaka-classical,OSAKA-AUTO,no-resolve
  - RULE-SET,aws-seoul-classical,SEOUL-AUTO,no-resolve
  - RULE-SET,aws-taipei-classical,TW-AUTO,no-resolve
  - RULE-SET,jp-socks5-classical,JP-AUTO,no-resolve

  - MATCH,PROXY
```

## 源规则与产物的关系

- 如果源文件里写的是 `.example.com`，构建后会规范化成 `DOMAIN-SUFFIX,example.com` 并写进 `classical` 产物
- `DOMAIN-KEYWORD`、`DOMAIN-WILDCARD`、`AND/OR/NOT` 会保留在 `classical` 产物中
- `IP-CIDR` / `IP-CIDR6` 会保留在 `classical` 产物中
- `SRC-IP` 会为 Mihomo 规范化成 `SRC-IP-CIDR`
- `rules/` 下参与构建的源规则文件统一使用 `.list` 命名，例如 `rules/region/tw/google_tw.list`

## Clash Verge Rev / Clash Meta for Android 的差异

两者接法基本一致，主要只需要注意本地缓存路径：

- Clash Verge Rev 常见 `path` 写到 `./rule-providers/...`
- Clash Meta for Android 也可以沿用同样写法，客户端会自行缓存

如果你只是想保证通用性，优先保留：

- `type: http`
- `behavior: classical`
- `format: yaml`
- `interval: 86400`

## 常见误区

- 不要把 `classical` 产物误配成别的 `behavior`
- 不要继续引用 `rules/` 源规则路径
- 不要再找旧的纯域名或纯 CIDR 产物目录；仓库已经统一走 `classical`
- 不要再引入无扩展名源文件；构建脚本会直接拒绝这种历史写法
