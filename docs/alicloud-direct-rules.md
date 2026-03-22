# 阿里云香港 SSH 直连规则

这组规则沿用 AWS 区域 IPv4 的每日同步方式，但数据源改为阿里云官方 VPC OpenAPI：

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

## 首次启用

这条链路需要阿里云鉴权。仓库工作流固定引用 GitHub Environment `upstream-sync`，请在：

`Settings -> Environments -> upstream-sync -> Environment secrets`

里配置：

- `RULEMESH_ALICLOUD_ACCESS_KEY_ID`
- `RULEMESH_ALICLOUD_ACCESS_KEY_SECRET`
- `RULEMESH_ALICLOUD_SECURITY_TOKEN`（可选，使用 STS 时再配）

推荐使用最小权限 RAM 用户或 STS 临时凭证，只需要 `vpc:DescribePublicIpAddress` 的读取权限。

## 产物链接

Surge：

- `https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/direct/alicloud_hk_ssh_direct.list`

Mihomo / Clash Verge Rev：

- `https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/direct/alicloud_hk_ssh_direct.yaml`

## 示例

Surge：

```ini
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/direct/alicloud_hk_ssh_direct.list,DIRECT
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
```
