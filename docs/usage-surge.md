# Surge 使用说明

## 先看原则

- 客户端只引用 `dist/surge/rules/`
- `rules/` 是源规则层，不建议在 Surge 配置中直接引用
- 本仓库统一输出显式规则行，统一通过 `RULE-SET` 接入
- Google 相关（含 Google Play / Gemini / YouTube / FCM）统一接 `region/tw/google_tw.list` 并绑定 `TW-AUTO`
- 局域网设备分流（`SRC-IP` + `AND/OR`）建议在客户端配置中硬编码维护，不放在仓库 `dist` 规则集中

本文示例统一使用主分支 raw 地址：

```text
https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main
```

## RULE-SET 示例

```ini
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/reject/plain_http_reject.list,REJECT
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/reject/os_update_reject.list,REJECT
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/reject/wps_reject.list,REJECT
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/reject/adblock_reject.list,REJECT
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/region/tw/google_tw.list,TW-AUTO
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/proxy/gfw.list,PROXY
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/direct/cn_direct.list,DIRECT
```

## 推荐顺序

建议顺序：

1. 拒绝规则
2. 区域规则
3. 代理规则
4. 直连 / 香港区域规则
5. IP 规则
6. `FINAL`

注意：

- `region/tw/google_tw.list` 必须放在 `region/hk/global_media.list` 等广谱区域规则之前。
- `proxy/gfw.list` 建议放在 `direct/cn_direct.list` 前，减少广谱直连误伤。

一个最小可用 `[Rule]` 片段：

```ini
[Rule]
# 1. 拒绝
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/reject/plain_http_reject.list,REJECT
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/reject/os_update_reject.list,REJECT
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/reject/wps_reject.list,REJECT
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/reject/adblock_reject.list,REJECT

# 2. 区域
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/region/tw/ai_tw.list,TW-AUTO
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/region/tw/google_tw.list,TW-AUTO
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/region/tw/crypto_tw.list,TW-AUTO
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/region/jp/domains_to_jp.list,JP-AUTO

# 3. 代理
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/proxy/gfw.list,PROXY

# 4. 直连 / 香港区域
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/direct/aliyun_ssh_direct.list,DIRECT
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/direct/microsoft_direct.list,DIRECT
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/direct/cn_direct.list,DIRECT
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/direct/bytedance_direct.list,DIRECT
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/direct/netease_direct.list,DIRECT
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/direct/bilibili_direct.list,DIRECT
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/region/hk/telegram.list,HK-AUTO
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/region/hk/global_media.list,HK-AUTO

# 5. IP 规则
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/region/hk/aws_ipv4.list,HK-AUTO,no-resolve
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/region/jp/tokyo_aws_ipv4.list,TOKYO-AUTO,no-resolve
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/region/jp/osaka_aws_ipv4.list,OSAKA-AUTO,no-resolve
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/region/kr/seoul_aws_ipv4.list,SEOUL-AUTO,no-resolve
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/region/tw/taipei_aws_ipv4.list,TW-AUTO,no-resolve
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/region/jp/jp_socks5_ipcidr.list,JP-AUTO,no-resolve

# 6. 最终规则
FINAL,PROXY
```

## 常见误区

- 不要继续引用 `rules/` 源文件路径
- 不要在客户端直接引用第三方原始规则 URL
- 不要再引入无扩展名源文件；构建脚本会拒绝