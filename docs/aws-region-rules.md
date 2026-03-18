# AWS Region IPv4 Rules

These rule links are generated from [AWS ip-ranges.json](https://ip-ranges.amazonaws.com/ip-ranges.json) and are meant to be imported from `dist/`, not from `rules/`.

Region mapping used by this repo:

- `ap-east-1` = Hong Kong
- `ap-northeast-1` = Tokyo
- `ap-northeast-3` = Osaka
- `ap-northeast-2` = Seoul
- `ap-east-2` = Taiwan

The sync path is:

1. `.github/workflows/sync-upstream-rules.yml` runs every day at `01:30 UTC` (`09:30 Asia/Shanghai`) and also supports manual trigger.
2. `tools/sync_upstream_rules.py` fetches the latest AWS JSON, stores it in `rules/upstream/aws/ip-ranges.json`, and derives IPv4 snapshots for Hong Kong, Tokyo, Osaka, Seoul, and Taiwan.
3. `tools/build_rules.py` rebuilds the client-facing artifacts under `dist/surge/rules/` and `dist/mihomo/classical/`.

Bootstrap note:

- If `rules/upstream/aws/ip-ranges.json` is still the repo bootstrap placeholder, or if any required AWS regional snapshot file is still a placeholder, the next `powershell -ExecutionPolicy Bypass -File tools/build_rules.ps1` run will auto-sync AWS before rebuilding `dist/`.

## Ready-to-use Links

Surge:

- Hong Kong: `https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/region/hk/aws_ipv4.list`
- Tokyo: `https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/region/jp/tokyo_aws_ipv4.list`
- Osaka: `https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/region/jp/osaka_aws_ipv4.list`
- Seoul: `https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/region/kr/seoul_aws_ipv4.list`
- Taiwan: `https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/region/tw/aws_ipv4.list`

Mihomo / Clash Verge Rev:

- Hong Kong: `https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/mihomo/classical/region/hk/aws_ipv4.yaml`
- Tokyo: `https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/mihomo/classical/region/jp/tokyo_aws_ipv4.yaml`
- Osaka: `https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/mihomo/classical/region/jp/osaka_aws_ipv4.yaml`
- Seoul: `https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/mihomo/classical/region/kr/seoul_aws_ipv4.yaml`
- Taiwan: `https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/mihomo/classical/region/tw/aws_ipv4.yaml`

## Example

Surge:

```ini
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/region/hk/aws_ipv4.list,HK-AUTO,no-resolve
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/region/jp/tokyo_aws_ipv4.list,TOKYO-AUTO,no-resolve
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/region/jp/osaka_aws_ipv4.list,OSAKA-AUTO,no-resolve
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/region/kr/seoul_aws_ipv4.list,SEOUL-AUTO,no-resolve
RULE-SET,https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/surge/rules/region/tw/aws_ipv4.list,TW-AUTO,no-resolve
```

Mihomo / Clash Verge Rev:

```yaml
rule-providers:
  aws-hk-classical:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/region/aws_hk_ipv4.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/mihomo/classical/region/hk/aws_ipv4.yaml
    interval: 86400

  aws-tokyo-classical:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/region/aws_tokyo_ipv4.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/mihomo/classical/region/jp/tokyo_aws_ipv4.yaml
    interval: 86400

  aws-osaka-classical:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/region/aws_osaka_ipv4.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/mihomo/classical/region/jp/osaka_aws_ipv4.yaml
    interval: 86400

  aws-seoul-classical:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/region/aws_seoul_ipv4.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/mihomo/classical/region/kr/seoul_aws_ipv4.yaml
    interval: 86400

  aws-tw-classical:
    type: http
    behavior: classical
    format: yaml
    path: ./rule-providers/region/aws_tw_ipv4.yaml
    url: https://raw.githubusercontent.com/vtgpcmsvgs/surge-config/main/dist/mihomo/classical/region/tw/aws_ipv4.yaml
    interval: 86400

rules:
  - RULE-SET,aws-hk-classical,HK-AUTO,no-resolve
  - RULE-SET,aws-tokyo-classical,TOKYO-AUTO,no-resolve
  - RULE-SET,aws-osaka-classical,OSAKA-AUTO,no-resolve
  - RULE-SET,aws-seoul-classical,SEOUL-AUTO,no-resolve
  - RULE-SET,aws-tw-classical,TW-AUTO,no-resolve
```
