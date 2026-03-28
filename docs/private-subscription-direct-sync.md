# 私有订阅直连同步约定

本文只记录本地私有“订阅更新直连”规则的维护方式，避免后续把真实订阅域名重新散落回多个配置文件，或误写进公开仓库。

## 适用范围

- `%USERPROFILE%\Desktop\rulemesh-local\current\private_subscription_direct.list`
- `%USERPROFILE%\Desktop\rulemesh-local\current\sync_private_subscription_direct.ps1`
- `%USERPROFILE%\Desktop\rulemesh-local\current\rulemesh-substore-surge-personal.conf`
- `%USERPROFILE%\Desktop\rulemesh-local\current\rulemesh-substore-surge-work-whitelist.conf`
- `%USERPROFILE%\Desktop\rulemesh-local\current\rulemesh-substore-mihomo-clash-verge.yaml`
- `%USERPROFILE%\Desktop\rulemesh-local\current\rulemesh-substore-mihomo-clash-meta.yaml`

## 设计目标

- 真实机场订阅更新域名只在私有目录维护，不回写公开仓库
- 由单一源文件统一维护，避免 `Surge personal`、`Surge work whitelist`、`Mihomo Clash Verge`、`Mihomo Clash Meta` 四处重复手改
- 同一组规则同时服务 Surge 与 Mihomo，因此源文件只写双方都支持的规则语法
- 订阅更新直连必须位于 `proxy/gfw` 前；在工作白名单里则属于显式放行入口

## 源文件写法

- `private_subscription_direct.list` 每行只写规则本体，不要附带 `,DIRECT`
- 允许空行与中文注释
- 优先使用 `DOMAIN`、`DOMAIN-SUFFIX`、`DOMAIN-WILDCARD` 这类 Surge / Mihomo 都能直接复用的语法
- 如果某条规则只被单一客户端支持，不要写进这份共享源文件

## 同步方式

1. 修改 `private_subscription_direct.list`
2. 运行 `powershell -ExecutionPolicy Bypass -File "%USERPROFILE%\Desktop\rulemesh-local\current\sync_private_subscription_direct.ps1"`
3. 脚本会自动刷新四份本地私有配置中的订阅直连规则块
4. 如需人工确认，可检查四份目标文件中的 `PRIVATE_SUBSCRIPTION_DIRECT_START` 与 `PRIVATE_SUBSCRIPTION_DIRECT_END` 标记段

## 维护边界

- 不要把真实订阅域名写进 `rules/`、`dist/`、`README.md`、公开模板或公开规则文档
- 不要把这组私有订阅直连规则合并进公开 `direct/*.list`、`proxy/gfw.*` 或其他面向所有用户的规则入口
- 如果未来某条规则只影响单一客户端而非全部三份配置，先评估它是否还适合继续放在共享源文件里
- 如果同步脚本、目标文件名或插入顺序发生变化，需同步更新本文以及相关使用说明
