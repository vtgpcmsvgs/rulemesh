# AWS 区域 IPv4 规则

当前状态（2026-09-09）：源规则、上游同步与 dist 产物继续维护；默认公开模板和五份私有配置已停用 AWS IP 与链式代理调用。以下接入方式仅作将来手动启用时的参考。

这些规则链接由 [AWS ip-ranges.json](https://ip-ranges.amazonaws.com/ip-ranges.json) 自动生成，客户端应从 `dist/` 引用，不要直接引用 `rules/`。

本仓库使用的区域映射：

- `ap-east-1` = 香港
- `ap-northeast-1` = 东京
- `ap-northeast-3` = 大阪
- `ap-northeast-2` = 首尔
- `ap-east-2` = 台北

命名约定补充：

- 统一使用“城市 / 地区 + `aws` + `ipv4`”命名，因此香港入口现为 `hk_aws_ipv4`

同步链路如下：

1. `.github/workflows/sync-upstream-rules.yml` 每天 `01:30 UTC`（`09:30 Asia/Shanghai`）自动运行，也支持手动触发。
2. `tools/sync_upstream_rules.py` 拉取最新 AWS JSON，保存到 `rules/upstream/aws/ip-ranges.json`，并生成香港、东京、大阪、首尔、台北的 IPv4 快照。
3. `tools/build_rules.py` 重建面向客户端的产物目录：`dist/surge/rules/` 和 `dist/mihomo/classical/`。

仓库引导说明：

- 如果 `rules/upstream/aws/ip-ranges.json` 仍是仓库引导占位内容，或任一必需的 AWS 区域快照文件仍是占位内容，则下一次执行 `powershell -ExecutionPolicy Bypass -File tools/build_rules.ps1` 会先自动同步 AWS，再重建 `dist/`。

## 可直接使用的链接

Surge：

- 香港：`https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/region/hk/hk_aws_ipv4.list`
- 东京：`https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/region/jp/tokyo_aws_ipv4.list`
- 大阪：`https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/region/jp/osaka_aws_ipv4.list`
- 首尔：`https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/region/kr/seoul_aws_ipv4.list`
- 台北：`https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/region/tw/taipei_aws_ipv4.list`

Mihomo / FlClash 桌面端：

- 香港：`https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/region/hk/hk_aws_ipv4.yaml`
- 东京：`https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/region/jp/tokyo_aws_ipv4.yaml`
- 大阪：`https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/region/jp/osaka_aws_ipv4.yaml`
- 首尔：`https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/region/kr/seoul_aws_ipv4.yaml`
- 台北：`https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/region/tw/taipei_aws_ipv4.yaml`

## 示例

Surge：

```ini
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/region/hk/hk_aws_ipv4.list,HK-AUTO,no-resolve
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/region/jp/tokyo_aws_ipv4.list,TOKYO-AUTO,no-resolve
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/region/jp/osaka_aws_ipv4.list,OSAKA-AUTO,no-resolve
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/region/kr/seoul_aws_ipv4.list,SEOUL-AUTO,no-resolve
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/surge/rules/region/tw/taipei_aws_ipv4.list,TW-AUTO,no-resolve
```

Mihomo / FlClash 桌面端：

```yaml
rule-providers:
  aws-hk-classical:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/region/hk_aws_ipv4.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/rulemesh/main/dist/mihomo/classical/region/hk/hk_aws_ipv4.yaml
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

rules:
  - RULE-SET,aws-hk-classical,HK-AUTO,no-resolve
  - RULE-SET,aws-tokyo-classical,TOKYO-AUTO,no-resolve
  - RULE-SET,aws-osaka-classical,OSAKA-AUTO,no-resolve
  - RULE-SET,aws-seoul-classical,SEOUL-AUTO,no-resolve
  - RULE-SET,aws-taipei-classical,TW-AUTO,no-resolve
```
