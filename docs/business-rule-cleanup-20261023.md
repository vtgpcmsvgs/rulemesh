# 2026-10-23 业务规则清理审计

用户确认业务调整，不再需要 Webshare（用户称 webshares）与 AdsPower。

## 本次删除

- AdsPower：主清单、三类源规则、对应登记、专用派生脚本及测试和六份 Surge/Mihomo 产物；构建不再生成这些资产。保留阻止旧配置重新引用的检查。
- Webshare：住宅代理清单与 Loyalsoldier GFW 本地快照中的 `webshare.io`；GFW 同步排除主域及子域，因此完整与精确两份 GFW 产物也会移除。
- 六份私人主配置没有两类业务的直接调用或内联规则，继续引用共享规则集。私有当前目录实际为 `rulemesh-local` 根目录，没有 `current/`。
- 检查 DNS 专用清单和私人配置中的两类业务引用；没有专用例外时沿用各客户端现有 DNS 基线。静态结果与设备实际加载、DNS 出口分开报告。

## 等待确认的类似资产

下列内容本次全部保留。是否仍有业务需求不能从配置引用或域名列表推断。

| 候选 | 当前用途与风险 | 确认方向 |
| --- | --- | --- |
| `region/multi/residential_proxy` | 其余 24 个住宅代理、ISP 代理与抓取 API 主域；含 Cliproxy、Decodo、Bright Data、Oxylabs 等，六份私人配置仍调用 | 住宅代理采购/管理业务是否全部结束；可整组撤销或逐个保留 |
| `direct/ips5_direct` | `ips5.vip` 专项直连，当前配置仍调用 | 若代理相关业务也已结束，可单独删除；不能因为 Webshare 删除就默认撤销 |
| 五份地区 AWS IP 与上游 AWS 快照 | 香港、东京、大阪、首尔、台北网段；客户端已停用，仍保留同步和产物 | 是否从“停用保留”改为彻底删除 |
| `region/multi/chain_socks5_ipcidr` | 私有链式 SOCKS5 端点的旧脱敏 IP 快照，客户端已停用 | 旧链式代理业务是否结束；仅旧 IP 清单无法证明当前有效性 |
| `region/hk/alibaba_hk` | 六份当前私人配置均未调用的阿里系强制代理资产，仍保留源规则、上游和产物 | 国内日常业务已改直连，是否删除旧专用入口；共享上游先核对依赖 |
| `proxy/onepassword_proxy` | 六份私人配置仍调用的 1Password 专项规则与每日官方域名更新 | 若已不用 1Password 或无需专项分流，可删除独立维护链 |
| `proxy/polygon_rpc_proxy`、`proxy/bsc_rpc_proxy` | Crypto 台湾 RPC 规则，Chainlist 快照采用只增不减 | 是否仍使用这两条链；历史累计节点应单独审计，不能直接等同于已失效 |
| 完整 `proxy/gfw`、`direct/cn_direct` | 普通配置已用精简入口，但保留兼容产物；`cn_direct` 仍参与推导 `cn_direct_light` | 可评估停止发布完整兼容产物，不能直接删掉精简构建所依赖的源规则 |

## 共享依赖不作为废弃项

- `check.myclientip.com` 是阿里云隧道共用探测入口，不随 AdsPower 删除。
- `hk_brokers`、`hk_securities_aggressive`、`android_brokers_aggressive` 被统一券商规则 INCLUDE；没有客户端直接引用不代表无依赖。
- 机场手动组、节点域名 bootstrap 与订阅下载 DIRECT 属于共享基础配置，不按“没有直接业务规则引用”删除。

本次解析六份私人文件的有效 RULE-SET 调用及递归 INCLUDE 后，未被调用图覆盖的源规则共九份：完整 `cn_direct`/`gfw`、`alibaba_hk`、五份 AWS 地区规则和链式 SOCKS5。`cn_direct` 仍有构建期依赖；此清单不代表可以全部删除。

## 维护经验

- 现象：只从住宅代理清单删除 Webshare 会遗漏 GFW。根因是同一业务存在专用与通用上游两条来源；修复同时移除两处，防复发通过同步入口排除和真实同步路径回归测试实现。
- 残留审计应区分可执行规则与登记说明：`sources.yaml`/`merge.yaml` 的删除记录不属于仍生效的规则。先按文件角色筛选，再检查规则行，避免把防恢复说明误报为残留。
- 一次性修改先预检所有唯一锚点；同文件的多处补丁按原文顺序排列，避免反序查找失败。PowerShell 循环结果先赋给任务变量再格式化，错误立即中止依赖步骤。命令编写错误与临时网络故障不归为业务规则故障。
