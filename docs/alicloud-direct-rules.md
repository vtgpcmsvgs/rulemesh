# 阿里云香港 SSH 直连与广覆盖观察兜底

其中“香港 SSH 直连规则集”沿用 AWS 区域 IPv4 的每日同步方式，但数据源改为阿里云官方 VPC OpenAPI：

- 官方接口：`DescribePublicIpAddress`
- 官方文档：<https://help.aliyun.com/zh/eip/developer-reference/api-vpc-2016-04-28-describepublicipaddress-eips>
- 地域：`cn-hongkong`
- Endpoint：`vpc.cn-hongkong.aliyuncs.com`

同步链路如下：

1. `.github/workflows/sync-upstream-rules.yml` 每日运行 `tools/sync_upstream_rules.py`
2. 每页先保留原始条目，持续翻页直到累计数量达到官方 `TotalCount`；禁止再用页内去重后的“短页”判断结束
3. 每页校验 `PageNumber`、`PageSize`、`RegionId` 与稳定的 `TotalCount`，并连续两次完整抓取到相同规范化集合
4. 写盘前校验原始条目数、唯一前缀数、重复条目数与唯一 IPv4 地址覆盖量；新旧集合交集若未保留上次 95% 的地址覆盖，默认拒绝发布并告警
5. 将通过校验的结果写入 `rules/upstream/alicloud/hk_ipv4.txt` 与 `rules/upstream/alicloud/hk_ipv4.json`，再派生 `rules/upstream/alicloud/hk_ssh22.txt`
6. `rules/direct/alicloud_hk_ipv4_ssh22_direct.list` 只保留单一 `INCLUDE`，`tools/build_rules.py` 统一生成两类客户端产物

命名与语义约定补充：

- `rules/upstream/alicloud/hk_ipv4.txt` 继续保留纯 IPv4 快照，便于后续派生其他规则
- 对外入口统一命名为 `alicloud_hk_ipv4_ssh22_direct`
- 这个入口文件本身直接保留 `AND,((IP-CIDR,...,no-resolve),(PROTOCOL,TCP),(DST-PORT,22))` 最终语义；Surge 构建为 `PROTOCOL + DEST-PORT`，Mihomo 构建为 `NETWORK + DST-PORT`
- `no-resolve` 保证字面 IPv4 的规则判断不会额外触发 DNS；规则集调用层仍统一保留 `no-resolve` 作为客户端侧保险

除此之外，配置文件里当前只保留三条手写阿里云显式直连入口：

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
- 正常变更若确需让旧地址保留率低于 95%，必须人工核对官方撤回后临时设置 `RULEMESH_ALICLOUD_ALLOW_COVERAGE_SHRINK=1`；不得长期保留该开关
- API 错误日志只保留错误码与请求 ID，不记录签名串、AccessKey ID、SecurityToken 或其他鉴权请求细节

## 2026-06-30 分页截断事故

- 2026-06-29 的最后完整快照为 `TotalCount=808`、9 页、808 个唯一前缀；从 2026-06-30 起，旧实现连续只发布前 5 页的 499 个前缀，虽然 API 同期报告的 `TotalCount` 始终超过 800
- 根因是旧实现先对单页去重，再把“去重后少于 100 条”误判为最后一页；一个重复条目就会让第 6 页及以后全部丢失
- 修复提交先恢复 2026-06-29 最后一次完整官方快照作为安全基线，再由新的完整分页链路接管后续更新；不要把历史快照永久求并集，也不要用覆盖全球地域的 Alibaba ASN 规则兜底
- 普通本地构建与仓库测试都会独立核对 JSON 元数据、纯 IPv4 快照、SSH 派生文件和两类客户端产物，任何数量或集合不一致都会阻止发布

## 产物链接

Surge：

- `https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/direct/alicloud_hk_ipv4_ssh22_direct.list`

Mihomo / Clash Verge Rev：

- `https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/direct/alicloud_hk_ipv4_ssh22_direct.yaml`

## 示例

Surge：

```ini
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
    interval: 86400

rules:
  - RULE-SET,alicloud-hk-ipv4-ssh22-direct,DIRECT,no-resolve
  - DOMAIN-SUFFIX,aliyuncs.com,DIRECT
  - DOMAIN,check.myclientip.com,DIRECT
```
