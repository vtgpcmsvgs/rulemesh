# GeoIP 上游说明

## 当前结论

- RuleMesh 当前统一选择 `MetaCubeX/meta-rules-dat` 的 `country.mmdb` 作为上游
- 对外分发不再直接引用第三方仓库，而是统一走本仓库 Release 镜像：
  - `https://github.com/vtgpcmsvgs/rulemesh/releases/download/geoip-country-mmdb/country.mmdb`
- 对应公开模板与本地私有 personal 配置都应显式写明这个镜像地址，避免继续依赖客户端默认值
- 上游登记快照位于 `rules/upstream/geodata/metacubex_country_mmdb.yaml`

## 为什么选它

- Mihomo 官方文档的 `geox-url` 默认示例直接指向 `MetaCubeX/meta-rules-dat`
- 同时提供 `country.mmdb`、`geoip.dat`、`geoip.db`、`lite` 变体，适合 Surge 与 Mihomo 共用
- 上游 README 明确标注 `country.mmdb / geoip.dat / geoip.db` 内容同 `Loyalsoldier/v2ray-rules-dat`，便于交叉验证

## 为什么不继续默认用 Hackl0us

- `Hackl0us/GeoIP2-CN` 更适合只做 `GEOIP,CN` 的轻量 CN-only 场景
- 该项目不适合作为当前跨 Surge + Mihomo 的统一默认上游，因为它不是 Mihomo 官方文档默认入口，也不提供与 Mihomo 生态常用的 `dat/db` 全套配套格式
- 如果未来明确回到“只服务 CN-only 轻量分流”的目标，可以再重新评估

## 维护约定

- 不把大体积 mmdb 二进制直接提交进本仓库
- 通过 `tools/sync_upstream_rules.py` 同步 `rules/upstream/geodata/metacubex_country_mmdb.yaml`，只登记来源、下载入口与维护边界
- 通过 GitHub Actions 在 `geoip-country-mmdb` 这个稳定 Release tag 下覆盖上传最新 `country.mmdb`
- 若未来切换 GeoIP 默认来源，必须同时更新：
  - `rules/upstream/geodata/`
  - `README.md`
  - `docs/usage-surge.md`
  - `docs/usage-mihomo.md`
  - `docs/examples/surge-public.conf`
  - `docs/examples/mihomo-public.yaml`
  - `.github/workflows/build-dist.yml`
  - `.github/workflows/sync-upstream-rules.yml`
  - 本地 `rulemesh-local/current` 中对应的 Surge / Mihomo personal 配置
