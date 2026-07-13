# 阿里云香港 SSH 直连与广覆盖观察兜底

“香港 SSH 直连规则集”采用地域精确数据、全球阿里 BGP 兜底和客户端本地应急兜底三层结构：

- 官方接口：`DescribePublicIpAddress`
- 官方文档：<https://help.aliyun.com/zh/eip/developer-reference/api-vpc-2016-04-28-describepublicipaddress-eips>
- 地域：`cn-hongkong`
- Endpoint：`vpc.cn-hongkong.aliyuncs.com`
- BGP 数据：RIPE NCC RIPEstat `announced-prefixes`
- 兜底 ASN：`AS45102`、`AS134963`、`AS24429`
- BGP 可见度阈值：`min_peers_seeing=1`

阿里官方文档明确说明 `DescribePublicIpAddress` 只能查询指定地域 VPC 内的公网 IP，不能查询经典网络。因此它仍是香港地域的高质量精确来源，但不再被当成“阿里云全部公网 IP”的完整清单。

同步链路如下：

1. `.github/workflows/sync-upstream-rules.yml` 每日运行 `tools/sync_upstream_rules.py`
2. 每页先保留原始条目，持续翻页直到累计数量达到官方 `TotalCount`；禁止再用页内去重后的“短页”判断结束
3. 每页校验 `PageNumber`、`PageSize`、`RegionId` 与稳定的 `TotalCount`，并连续两次完整抓取到相同规范化集合
4. 写盘前校验原始条目数、唯一前缀数、重复条目数与唯一 IPv4 地址覆盖量
5. 分别连续抓取 RIPEstat 中三个兜底 ASN 的完整 IPv4 公告，使用一个对等体可见的最低阈值，跨 ASN 去重并折叠
6. 官方当前快照继续独立写入 `hk_ipv4.txt/json`；BGP 当前快照写入 `fallback_asns_ipv4.txt/json`
7. 首次迁移时回看仓库 120 份官方快照，把当前 BGP 未覆盖的 28 个旧前缀固化为历史种子；随后将官方当前、BGP 当前与 `ssh22_ipv4_history.txt` 的既有覆盖合并
8. `hk_ssh22.txt` 由单调历史 CIDR 派生，并在末尾增加三个 `IP-ASN + TCP/22` 运行时兜底；源入口仍只保留单一 `INCLUDE`

命名与语义约定补充：

- `rules/upstream/alicloud/hk_ipv4.txt` 继续保留纯 IPv4 快照，便于后续派生其他规则
- `rules/upstream/alicloud/fallback_asns_ipv4.txt` 是当前 BGP 宽覆盖快照，不表示香港地理归属
- `rules/upstream/alicloud/ssh22_ipv4_history.txt` 是实际 SSH 发布覆盖的单调并集；它从仓库 120 份历史快照的 942 个曾见前缀起步，删除只能人工审计
- 对外入口统一命名为 `alicloud_hk_ipv4_ssh22_direct`
- 这个入口文件本身直接保留 `AND,((IP-CIDR,...,no-resolve),(PROTOCOL,TCP),(DST-PORT,22))` 最终语义；Surge 构建为 `PROTOCOL + DEST-PORT`，Mihomo 构建为 `NETWORK + DST-PORT`
- `no-resolve` 保证字面 IPv4 的规则判断不会额外触发 DNS；规则集调用层仍统一保留 `no-resolve` 作为客户端侧保险

配置文件在远程规则前增加了仅限 TCP/22 的本地应急兜底，随后保留三类显式直连入口：

- `8.208.0.0/12` 与已验证的 `47.*` 阿里注册大块：防止远程规则仍缓存分页事故期间的残缺版本
- `IP-ASN,45102/134963/24429`：承接静态快照同步间隙的新公告；ASN 数据库可能滞后，因此不能替代静态 CIDR
- `RULE-SET,.../direct/alicloud_hk_ipv4_ssh22_direct...,DIRECT,no-resolve`：阿里云香港 SSH TCP/22 入口
- `DOMAIN-SUFFIX,aliyuncs.com,DIRECT`：阿里云 SSH 控制面入口
- `DOMAIN,check.myclientip.com,DIRECT`：AdsPower / 阿里云隧道出口探测入口
- 它们统一放在直连段显式维护；工作白名单模式下还允许在其后追加一条阿里云广覆盖 `REJECT` 观察兜底，用于发现上游阿里云规则的漏网之鱼
- 工作白名单模式下，广覆盖观察规则统一只允许使用 `REJECT`；除 `REJECT` 外不要对 `DIRECT` 或 `PROXY` 规则使用 `extended-matching`

## 首次启用

这条链路需要阿里云鉴权。仓库工作流固定引用 GitHub Environment `upstream-sync`，请在：

`Settings -> Environments -> upstream-sync -> Environment secrets`

里配置：

- `RULEMESH_ALICLOUD_ACCESS_KEY_ID`
- `RULEMESH_ALICLOUD_ACCESS_KEY_SECRET`
- `RULEMESH_ALICLOUD_SECURITY_TOKEN`（可选，使用 STS 时再配）

推荐使用最小权限 RAM 用户或 STS 临时凭证，只需要 `vpc:DescribePublicIpAddress` 的读取权限。

如果本地 Windows / Codex / 计划任务也要主动执行 `tools/sync_upstream_rules.py`，可额外任选一种本地配置方式：

- 环境变量：`RULEMESH_ALICLOUD_ACCESS_KEY_ID`、`RULEMESH_ALICLOUD_ACCESS_KEY_SECRET`、`RULEMESH_ALICLOUD_SECURITY_TOKEN`
- 私有配置：在 `.rulemesh.local.json` 中填写 `alicloud.access_key_id`、`alicloud.access_key_secret`、`alicloud.security_token`

维护约定补充：

- GitHub Actions 场景仍保持严格要求；如果 `upstream-sync` 环境缺少阿里云 secret，应继续失败并报警
- 非 GitHub Actions 场景只有在现有快照通过完整性校验时，才允许因缺少凭据而跳过；残缺快照不能再伪装成“可用快照”
- 发布覆盖不再采用“允许回撤 5%”的阈值；自动同步永不删除既有 SSH 覆盖，确需收窄时必须人工审计并直接修改历史基线
- API 错误日志只保留错误码与请求 ID，不记录签名串、AccessKey ID、SecurityToken 或其他鉴权请求细节

## 2026-06-30 分页截断事故

- 2026-06-29 的最后完整快照为 `TotalCount=808`、9 页、808 个唯一前缀；从 2026-06-30 起，旧实现连续只发布前 5 页的 499 个前缀，虽然 API 同期报告的 `TotalCount` 始终超过 800
- 根因是旧实现先对单页去重，再把“去重后少于 100 条”误判为最后一页；一个重复条目就会让第 6 页及以后全部丢失
- 2026-07-13 再次收到某个旧地址落入 `FINAL` 的报告；核验发现当前仓库与远端已经包含它，根因是客户端仍可能缓存事故期间的 499 条残缺产物
- 这次复盘同时确认：95% 防缩水阈值仍允许少量旧前缀自动消失，而官方接口本身又明确不含经典网络；因此发布模型升级为“官方当前审计 + 三个阿里 ASN BGP 当前 + 永不自动缩小的历史并集 + 客户端内联兜底”
- 普通本地构建与仓库测试会独立核对两类元数据、三个静态快照、SSH 派生文件和两类客户端产物，任何集合不一致都会阻止发布

## 产物链接

Surge：

- `https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/direct/alicloud_hk_ipv4_ssh22_direct.list`

Mihomo / Clash Verge Rev：

- `https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/direct/alicloud_hk_ipv4_ssh22_direct.yaml`

## 示例

Surge：

```ini
# 完整内联兜底见 docs/examples/surge-public.conf，必须放在远程规则前。
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/direct/alicloud_hk_ipv4_ssh22_direct.list,DIRECT,no-resolve
DOMAIN-SUFFIX,aliyuncs.com,DIRECT
DOMAIN,check.myclientip.com,DIRECT
```

Mihomo / Clash Verge Rev：

```yaml
rule-providers:
  alicloud-hk-ipv4-ssh22-direct:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/direct/alicloud_hk_ipv4_ssh22_direct.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/direct/alicloud_hk_ipv4_ssh22_direct.yaml
    interval: 3600

rules:
  # 完整内联兜底见 docs/examples/mihomo-public.yaml，必须放在远程 provider 前。
  - RULE-SET,alicloud-hk-ipv4-ssh22-direct,DIRECT,no-resolve
  - DOMAIN-SUFFIX,aliyuncs.com,DIRECT
  - DOMAIN,check.myclientip.com,DIRECT
```
