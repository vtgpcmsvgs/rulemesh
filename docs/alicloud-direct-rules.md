# 阿里云香港 SSH 直连与广覆盖观察兜底

其中“香港 SSH 直连规则集”沿用 AWS 区域 IPv4 的每日同步方式，但数据源改为阿里云官方 VPC OpenAPI：

- 官方接口：`DescribePublicIpAddress`
- 官方文档：<https://help.aliyun.com/zh/eip/developer-reference/api-vpc-2016-04-28-describepublicipaddress-eips>
- 地域：`cn-hongkong`
- Endpoint：`vpc.cn-hongkong.aliyuncs.com`

同步链路如下：

1. `.github/workflows/sync-upstream-rules.yml` 每日运行 `tools/sync_upstream_rules.py`
2. 先拉取阿里云香港全部公网 IPv4 前缀，写入 `rules/upstream/alicloud/hk_ipv4.txt` 与 `rules/upstream/alicloud/hk_ipv4.json`
3. 再从这些官方 IPv4 前缀派生 `rules/upstream/alicloud/hk_ssh22.txt`
4. `rules/direct/alicloud_hk_ssh_direct.list` 只保留单一 `INCLUDE`
5. `tools/build_rules.py` 统一生成 `dist/surge/rules/` 与 `dist/mihomo/classical/`

除此之外，个人模板与本地 personal 配置还额外保留一条手写“阿里云广覆盖观察兜底”：

- 作用：用于发现 `SSH 22` 端口之外的阿里云漏网之鱼
- 语义：不是替代 `alicloud_hk_ssh_direct` 的官方前缀规则，而是补在它之外的一条观察型广覆盖入口
- 顺序：必须紧跟 `github_ssh_direct` 之后，继续放在 `proxy/gfw` 之前，不要把它挪回普通 `direct` 段尾部

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
- 非 GitHub Actions 场景如果未配置阿里云凭据、但仓库里已经有上次成功同步的阿里云快照，脚本会跳过阿里云 upstream 并保留现有文件，不再把这类“本地无凭据”误报成 webhook 告警

## 产物链接

Surge：

- `https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/direct/alicloud_hk_ssh_direct.list`

Mihomo / Clash Verge Rev：

- `https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/direct/alicloud_hk_ssh_direct.yaml`

## 示例

Surge：

```ini
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/direct/alicloud_hk_ssh_direct.list,DIRECT
OR,((AND,((DEST-PORT,22), (PROTOCOL,TCP))), (OR,((IP-ASN,56040,no-resolve), (IP-ASN,45102,no-resolve))), (DOMAIN-KEYWORD,aliyun,extended-matching)),DIRECT
```

Mihomo / Clash Verge Rev：

```yaml
rule-providers:
  alicloud-hk-ssh-direct:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/direct/alicloud_hk_ssh_direct.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/direct/alicloud_hk_ssh_direct.yaml
    interval: 86400

rules:
  - RULE-SET,alicloud-hk-ssh-direct,DIRECT
  - OR,((AND,((DST-PORT,22), (NETWORK,tcp))), (OR,((IP-ASN,56040,no-resolve), (IP-ASN,45102,no-resolve))), (DOMAIN-KEYWORD,aliyun,extended-matching)),DIRECT
```
