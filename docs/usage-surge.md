# Surge 使用说明

## 先看原则

- 客户端以后只引用 `dist/surge/rules/`
- `rules/` 是源规则，不建议在 Surge 配置里直接引用
- 本仓库统一输出显式规则行，供 `RULE-SET` 使用
- 纯域名规则也会在产物里写成 `DOMAIN` / `DOMAIN-SUFFIX`，不会再生成单独的纯域名目录
- `DOMAIN-KEYWORD`、`DOMAIN-WILDCARD`、`IP-CIDR`、`SRC-IP`、`AND/OR` 这类规则同样统一走 `RULE-SET`

本文示例统一使用当前仓库主分支的 raw 地址：

```text
https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main
```

## RULE-SET 示例

无论是纯域名、关键词、IP 规则，还是 mixed 规则、设备源地址规则，都统一接这里：

```ini
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/device/srcip_pc01.list,JP-AUTO
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/device/srcip_hk_wifi.list,HK-AUTO
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/reject/adblock.list,REJECT
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/reject/reject.list,REJECT
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/direct/microsoft_direct.list,DIRECT
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/direct/cn_direct.list,DIRECT
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/proxy/global_media.list,PROXY
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/proxy/telegram.list,PROXY
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/region/hk/aws_ipv4.list,HK-AUTO,no-resolve
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/region/jp/tokyo_aws_ipv4.list,TOKYO-AUTO,no-resolve
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/region/jp/osaka_aws_ipv4.list,OSAKA-AUTO,no-resolve
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/region/kr/seoul_aws_ipv4.list,SEOUL-AUTO,no-resolve
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/region/tw/aws_ipv4.list,TW-AUTO,no-resolve
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/region/jp/jp_socks5_ipcidr.list,JP-AUTO,no-resolve
```

## 推荐顺序

建议顺序：

1. 设备规则
2. reject
3. region
4. direct / proxy 规则
5. IP 规则
6. `FINAL`

一个最小可用的 `[Rule]` 片段可以写成：

```ini
[Rule]
# 1. device
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/device/srcip_pc01.list,JP-AUTO
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/device/srcip_pc02.list,JP-AUTO
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/device/srcip_hk_wifi.list,HK-AUTO

# 2. reject
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/reject/adblock.list,REJECT
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/reject/reject.list,REJECT

# 3. region
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/region/hk/domains_to_hk.list,HK-AUTO
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/region/tw/ai_tw.list,TW-AUTO
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/region/tw/crypto_tw.list,TW-AUTO
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/region/tw/domains_to_tw.list,TW-AUTO
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/region/jp/domains_to_jp.list,JP-AUTO

# 4. direct / proxy
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/direct/microsoft_direct.list,DIRECT
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/direct/cn_direct.list,DIRECT
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/direct/direct.list,DIRECT
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/proxy/google.list,PROXY
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/proxy/telegram.list,PROXY
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/proxy/global_media.list,PROXY

# 5. ip rules
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/region/hk/aws_ipv4.list,HK-AUTO,no-resolve
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/region/jp/tokyo_aws_ipv4.list,TOKYO-AUTO,no-resolve
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/region/jp/osaka_aws_ipv4.list,OSAKA-AUTO,no-resolve
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/region/kr/seoul_aws_ipv4.list,SEOUL-AUTO,no-resolve
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/region/tw/aws_ipv4.list,TW-AUTO,no-resolve
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/region/jp/jp_socks5_ipcidr.list,JP-AUTO,no-resolve

# 6. final
FINAL,PROXY
```

## 源规则与产物的关系

- 如果源文件里写的是 `.g42.ai`、`.polymarket.com` 这类纯域名写法，构建后会规范化成 `DOMAIN-SUFFIX,g42.ai` 这类显式规则行
- 如果源文件里写的是 `DOMAIN-KEYWORD`、`DOMAIN-WILDCARD`、`AND/OR`、`SRC-IP`、`GEOIP`、`IP-CIDR`，构建后会原样或按 Surge 兼容形式保留在 `RULE-SET` 产物中
- `rules/` 下参与构建的源规则文件统一使用 `.list` 命名，例如 `rules/region/tw/google_tw.list`

## 常见误区

- 不要继续引用 `rules/reject/reject.list` 这类源文件路径
- 不要再找旧的纯域名产物目录；仓库已经统一走 `RULE-SET`
- 不要继续在客户端里直接引用 ACL4SSR / Loyalsoldier / blackmatrix7 的原始 URL
- 不要再引入无扩展名源文件；构建脚本会直接拒绝这种历史写法
