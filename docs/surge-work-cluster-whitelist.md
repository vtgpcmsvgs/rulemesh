# Surge 工作路由白名单约定

本文只记录私有工作路由文件的维护约定，用来防止后续把它误改回“和个人模板完全一致”的结构。

## 适用范围

- 仅适用于本地私有 Surge 文件 `rulemesh-substore-surge-work-whitelist.conf`
- 不适用于 `rulemesh-substore-surge-personal.conf`
- 不适用于 `rulemesh-substore-mihomo-personal.yaml`
- 不适用于仓库里的公开模板 `docs/examples/surge-public.conf` 与 `docs/examples/mihomo-public.yaml`

## 隐私边界

- 这份工作路由文件里的真实 `SRC-IP` 列表、私有 `policy-path`、订阅地址与 `[MITM]` 参数继续只保留在本地私有目录
- 公开仓库只记录“有 6 台固定工作电脑使用白名单模式”这一维护事实，不回写真实局域网 IP 或其他敏感值

## 当前白名单原则

- 工作路由对那 6 台固定工作电脑采用白名单模式
- 拒绝规则维持当前逻辑
- 设备分流继续按“源 IP + AWS 区域”定向到对应设备组
- 区域精确规则继续保留，且 `Google TW` 必须先于广谱区域规则
- GitHub 仓库 SSH 定向直连继续保留独立 carve-out；如果将来重新启用 `proxy/gfw`，它仍必须放在 `gfw` 前
- AdsPower 继续维持 `adspower_reject`、`adspower_direct`、`adspower_proxy` 三段细分
- `LAN,DIRECT` 继续保留在白名单直连入口中
- `direct/microsoft_direct` 继续保留 `DIRECT`
- `alicloud_hk_ssh_direct` 与阿里云抢占式 IP 直连继续保留
- `bytedance_direct.list` 继续保留 `DIRECT`
- `dist/surge/rules/region/` 下现有 IP 规则继续完整接入
- 其他源 IP 与未命中白名单的流量最终统一落到 `FINAL,REJECT`

## 永久差异约定

- 这份工作路由白名单是对工作软路由的长期特化，不再追求和两个 `personal` 配置完全一致
- 后续如果调整个人模板、公开模板或 Mihomo 模板，不要顺手把工作路由改回通用 `proxy/gfw + 广谱 direct + 放行型 FINAL` 结构
- 反过来，工作路由里的白名单 `REJECT` 兜底也不要迁移到个人模板或 Mihomo 模板

## 维护时必须保留的顺序

1. 拒绝规则
2. 设备分流
3. 区域精确规则
4. GitHub 仓库 SSH 定向直连
5. AdsPower 细分规则
6. 指定直连入口
7. IP 规则
8. 全局 `FINAL,REJECT` 兜底

## 不要误恢复的广谱放行项

若需求没有重新明确变更，不要把下列广谱放行项重新塞回工作路由白名单阶段：

- `proxy/gfw`
- `direct/netease_direct`
- `direct/bilibili_direct`
- `direct/cn_direct`

## 变更联动

- 只要工作路由白名单逻辑发生变化，就要同时更新这份文档
- 如果只是个人模板或 Mihomo 模板调整，不代表工作路由也应同步同构
- 如果未来白名单设备范围、允许入口或兜底策略发生变化，优先先确认这是“工作路由私有特化”还是“整个仓库公开默认行为”的变化，再决定是否更新公开模板
