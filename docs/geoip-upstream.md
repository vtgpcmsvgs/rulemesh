# GeoIP 上游说明

Surge 与 Mihomo 直接使用 `MetaCubeX/meta-rules-dat` 持续更新的 [country.mmdb](https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/country.mmdb)。这是 Mihomo 官方文档采用的主流入口；不对项目“最热门”作未经统计的排名判断。

Surge 设置 `geoip-maxmind-url`；Mihomo 设置 `geodata-mode: false` 与 `geox-url.mmdb`，并保留每 24 小时自动更新。首次下载仍需要可用网络。

上游同时提供 mmdb/dat/db/lite 格式，country.mmdb 内容与 Loyalsoldier/v2ray-rules-dat 同源。当前按跨客户端兼容使用完整 mmdb，未切换到仅中国的专用数据库。

仓库仅在 `rules/upstream/geodata/metacubex_country_mmdb.yaml` 登记来源与下载入口，不提交二进制。构建和每日同步工作流不再二次发布 GeoIP Release。原有历史 Release 无需删除，但当前配置不再引用它。

未定制公共资产优先活跃上游；本仓库有本地补充、合并或客户端格式转换的自定义规则继续引用 dist。未来切换默认来源时同步更新登记生成器、模板、私有配置、测试和使用文档。
