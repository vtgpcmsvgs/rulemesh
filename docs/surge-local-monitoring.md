# Surge 7×24 本地监控与审批闭环

这套机制面向长期运行并承担 DHCP、网关与全局流量接管的 Surge Mac。它持续区分两类常见故障：

- 中国大陆网站是否因为 DNS 解析异常、规则遗漏或误入美国 `FINAL` 而失败
- Google、ChatGPT 等美国入口是否因为当前策略或节点短时不可用而出现几十秒恢复窗口

监控只负责采集、归因和提出建议，不直接改变 Surge。审批分两步：`RM-INV-*` 只授权独立的只读调查；调查形成精确 diff、风险、回滚与复测步骤后，必须另行生成不可变的 `RM-EXEC-*`，获得第二次明确批准才允许变更。

## 设计边界

- 使用 macOS `launchd` 常驻运行，标签固定为 `com.rulemesh.surge-monitor`
- 与 Surge 的交互只调用 Surge Mac 自带的 `surge-cli`，默认路径为 `/Applications/Surge.app/Contents/Applications/surge-cli`
- 不开启 `external-controller-access`，不增加 HTTP API 或远程控制面
- 不启用 MITM，不解密 HTTPS，不读取请求头、响应头或正文
- 不自动执行 `set`、`reload`、`flush dns`、`switch-profile`、配置编辑或策略切换
- 不因为某个网站“能打开”就忽略 DNS 出口；每条获批变更的实施验证都要同时检查规则命中、代理出口与 DNS 出口

有效 profile 审计只检查已知解析器、`[Host]` 引用、DNS 劫持和 `FINAL` 顺序等基础边界，是回归提示而不是完整的 DNS 安全证明；任何 DNS 结论仍需结合客户端实际命中与出口复测。

Surge 官方资料：

- [Surge Mac CLI](https://manual.nssurge.com/others/cli.html)
- [Surge DNS Server](https://manual.nssurge.com/dns/dns-override.html)
- [Surge Mac 网关模式配置指南](https://kb.nssurge.com/surge-knowledge-base/zh/guidelines/gateway)
- [Surge Smart Group](https://kb.nssurge.com/surge-knowledge-base/guidelines/smart-group)

## 采样节奏

默认节奏固定为：

| 任务 | 间隔 | 用途 |
| --- | --- | --- |
| 请求增量采样 | 20 秒 | 统计关注主机名、`FINAL` 候选、规则类型、策略与错误类别 |
| DNS 与有效配置摘要 | 5 分钟 | 关联关注目标的 DNS 错误、解析器类别和配置指纹变化 |
| 轻量主动探测 | 15 分钟 | 比较国内入口与 Google / ChatGPT 入口的端到端状态和计时 |
| 本地聚合报告 | 每日 | Codex 调用 `report`，从本地聚合库即时生成脱敏证据 |
| Codex 只读分析 | 每日 09:00（Asia/Shanghai） | 读取报告、发送待审批建议，不改动 Surge |
| 数据清理 | 默认 5 分钟 | 去重键保留 1 小时加一次清理间隔；关注请求明细 36 小时；其他采样与建议索引 14 天 |

主动探测只做连通性与计时检查；响应正文会由 `curl` 丢弃，不解析、不保存，也不把 URL 路径或查询参数写入磁盘。20 秒采样用于发现短时故障，不代表每 20 秒执行一次完整网络诊断。

## 数据流

```text
surge-cli 只读输出 / 轻量探测
              |
              v
       内存解析与立即脱敏
              |
              v
  分层保留的本地脱敏数据
              |
              v
Codex automation 每日 09:00 只读分析
              |
              v
 RM-INV + 脱敏证据 + 风险 + 调查方案
              |
              v
      用户批准后只读调查
              |
              v
 精确 RM-EXEC + diff + 回滚 + 复测
              |
              v
      第二次明确批准后才执行
```

原始 `dump request`、`dump dns`、`dump profile` 或策略输出不得落盘。采集器必须在内存中先删除敏感字段，再写入最小化记录；解析失败时也不能把整段原始输出写进错误日志。

## 隐私最小化

允许保存的字段只有：

- 时间戳、采样类型、主机分类，以及请求是否直连、失败、拒绝、完成或命中 `FINAL` 的布尔值
- 关注主机名，以及失败或拒绝且命中 `FINAL` 的候选主机名
- 使用本机随机盐生成的匿名客户端 ID 与匿名策略 ID
- 规则类型与是否命中 `FINAL`
- 归一化错误类别：`dns`、`no_route`、`timeout`、`refused`、`tls`、`reset`、`rejected`、`http_5xx`、`unexpected_status`、`other` 或 `none`
- DNS 解析器类别、成功布尔值、答案数量与答案加盐摘要；不保存答案原值
- DNS、连接和探测计时，以及聚合次数、失败率和平均值
- 主动探测的名称 / 类别、可达 / 健康布尔值与 HTTP 状态码
- 由请求会话、请求 ID 与开始时间生成的加盐不可逆 `request_key`、最后观察时间与是否终结布尔值，以及远端地址和运行事件的加盐不可逆摘要；不保存原始请求 ID
- 有效 profile 的 SHA-256 前 16 位脱敏指纹与是否发生变化
- DNS / 配置 / 规则基础边界审计 code 的布尔结果，不保存对应原值
- 运行事件类别、采集健康 code / 状态 / 计数，以及不含内部 subject 的脱敏建议状态、证据、调查方案、风险、回滚与验证索引

禁止保存：

- URL 路径、查询参数与片段
- 设备名、MAC 地址、客户端 IP、源端口或可反推出具体设备的原值
- 策略、节点或机场的真实名称
- HTTP headers、cookies、授权信息、请求体或响应体
- 原始 Surge profile、订阅 URL、证书、密钥或完整 CLI 输出

主机名本身仍可能反映访问行为，因此只保留国内分类目标、Google / ChatGPT 及其受控依赖域名、配置中的主动探测主机及其子域、明确命中 `google_us` / `ai_us` 的美国平台目标，以及失败的 `FINAL` 候选，不建立全量浏览历史。全量 `request_seen` 只含 HMAC 请求键、活动时间与是否终结布尔值，用于跨轮询去重，默认保留 1 小时加一次清理间隔（默认最长约 65 分钟）；关注请求明细保留 36 小时；探测、DNS 摘要、配置审计、健康状态与建议索引默认保留 14 天。数据库超过默认 256 MiB 时会优先清理较旧成功明细并逐级限制高基数表，同时把采集质量标为降级；若 checkpoint / `VACUUM` 后仍超预算，采集器会停止写入非必要明细，直到下一轮清理恢复空间。

原始 CLI 输出、SQLite 数据库和匿名化密钥只留在 `~/Library/Application Support/RuleMesh/surge-monitor`，不写入公开仓库。主动探测会向配置中的公共 HTTPS 端点发出最小请求，目标站点可看到探测时间、固定 User-Agent 与当时的出口 IP；每日脱敏聚合报告会进入对应 Codex 任务。卸载守护进程后自动清理不再运行，保留数据不会自行过期。

## 归因原则

### 中国大陆网站打不开

报告应至少区分以下证据链：

- 主机名反复命中 `FINAL`，并通过美国策略失败：优先列为规则遗漏候选
- 在命中规则前出现 DNS 错误：先检查解析链、`[Host]`、DNS 出口和 IP 规则的 `no-resolve`，不要只补一条直连规则
- 已命中明确的中国大陆直连规则但仍失败：继续比较 DNS 结果、直连出口与站点自身状态
- 多个中国大陆目标同时异常：优先判断上游 DNS、网关接管或基础网络问题，避免逐站堆规则

新增国内 DNS 例外时仍遵守仓库的 DNS 安全边界：国内 DNS 只处理明确的国内业务白名单、DNS 服务器 bootstrap 与代理节点 server bootstrap，不把普通海外目标交给国内 DNS。

### Google 与 ChatGPT 偶发等待

报告应把错误按匿名策略 ID、主机名和时间窗口聚合。除了首页探测目标，还会关注 `googleapis.com`、`gstatic.com`、`googleusercontent.com`、`oaistatic.com`、`oaiusercontent.com` 等受控依赖后缀，以及明确命中 `google_us` / `ai_us` 的请求；不会因此扩大为全量浏览历史。

- 故障集中在单一美国策略或节点，其他美国出口正常：建议检查该策略的健康度、过滤条件、权重或候选集
- 同一主机名换策略后立即恢复：可建议评估 Smart Group，但不自动切换或修改组
- 所有美国策略与基础探测同时异常：优先判断本地网络、上游代理或 DNS，而不是把问题归因给单个节点
- 只有 Google / ChatGPT 异常而其他目标正常：分别检查站点特定路由、区域限制、QUIC / TCP 表现与 DNS 出口

Surge 官方说明中，Smart Group 会利用握手时延、连接性、丢包与站点维度历史进行动态选择和快速备用尝试；它适合成为证据充分时的候选方案，但不能识别内容层面的区域限制，因此报告不能把“启用 Smart Group”写成无条件修复。

## 建议与审批协议

日报只生成调查建议：

```yaml
recommendation_id: RM-INV-故障类别-稳定摘要
status: pending_investigation_approval
evidence: 脱敏后的时间窗口、样本量、失败率与关联证据
diagnosis: 当前归因
proposal: 只读调查范围和需要补齐的证据
risk: 调查本身的风险
rollback: 调查不产生变更，无需回滚
validation: 形成目标归属、规则命中、IP 出口与 DNS 出口证据
```

审批规则如下：

- 用户必须回复 `批准调查 RM-INV-*` 才允许开展该 ID 的只读深挖；沉默、查看报告、笼统回复或只说“批准”都不算授权
- `RM-INV-*` 永远不授权配置编辑、重载、策略切换或其他变更
- 只读调查完成后，Codex 必须列明精确文件 / 规则 / 策略、diff、风险、回滚和复测步骤，并生成新的不可变 `RM-EXEC-*`
- 用户第二次明确批准对应 `RM-EXEC-*` 后，独立的交互步骤才可实施；方案发生实质变化时必须生成新的执行 ID
- 监控守护进程与每日 automation 始终保持只读，不得接收或执行 `RM-EXEC-*`
- 修改前先备份并确认当前生效配置，修改后同时验证网页连通性、规则命中、代理出口和 DNS 出口
- 建议被拒绝或暂缓时只在 Codex 任务记录决定，不改变 Surge；本地监控仍按新样本判断问题是否持续

日报没有足够证据时应明确写“继续观察”。请求、profile、DNS、事件采集缺样本、失败或过期，或探测采集器缺样本、执行失败或过期时，日报必须停止网络优化判断，只生成监控采集质量的 `RM-INV-COLLECTOR-*` 调查项，不能基于陈旧数据提出配置方案。普通探测目标返回失败本身是网络证据，不等于采集器失效。默认新鲜度上限分别为：请求 `max(120 秒, 4×request_poll_seconds)`，profile / DNS / 事件 `max(1200 秒, 4×snapshot_seconds)`，探测 `max(3600 秒, 3×probe_seconds)`。守护中断、请求缓冲缺口或采集器失败会重置有效分析起点；恢复后还必须取得所有采集器的新样本并连续观察 `max(5×request_poll_seconds, snapshot_seconds, min(probe_seconds, 900 秒))`，默认即 15 分钟，才恢复网络建议。

## 本地配置

仓库内手动运行时，可以把 [`.rulemesh.local.example.json`](../.rulemesh.local.example.json) 复制为已被 `.gitignore` 忽略的 `.rulemesh.local.json`，或把其中的 `surge_monitor` 合并到现有私有配置。通过安装器常驻运行时，私有覆盖文件改为 `~/Library/Application Support/RuleMesh/surge-monitor/config.json`；文件不存在时使用代码内的安全默认值，如需创建则只复制 `surge_monitor` 节并把 `enabled` 改为 `true`。

`surge_monitor` 字段约定如下：

- `enabled`：示例默认是 `false`；实际启用前必须在私有运行配置中改为 `true`，缺省代码配置则为启用
- `surge_cli_path`：Surge 自带 CLI 的绝对路径
- `state_dir`：空字符串表示使用 `~/Library/Application Support/RuleMesh/surge-monitor`；自定义值必须是名称为 `surge-monitor` 或 `surge-monitor-*` 的专用叶目录，拒绝 `/`、HOME、仓库根、临时目录根及其他宽泛路径，避免安装时误改上层目录权限
- `request_poll_seconds`、`snapshot_seconds`、`probe_seconds`：分别对应 20、300、900 秒的默认周期
- `retention_days`：默认将探测、DNS 摘要、配置 / 健康审计与建议索引保留 14 天；不改变请求明细 36 小时和请求去重键 1 小时的固定边界
- `max_database_mb`：数据库与 WAL 的默认预算为 256 MiB，最低允许配置为 32 MiB
- `probes`：公共轻量 HTTPS 端点，每项只包含 `name`、`category`、`url` 与允许的 `accepted_status`；`category` 只能是 `domestic`、`google` 或 `openai`
- `thresholds`：最小样本数、最小失败数、失败比例、`FINAL` 命中数，以及 DNS、TCP 建连和请求总耗时的慢阈值
- `privacy.store_final_hostnames`：是否在本地短期保存失败 `FINAL` 候选主机名；设为 `false` 会关闭未分类目标的 `FINAL-FAIL` 归因
- `privacy.store_url_paths_queries=false` 与 `privacy.store_device_names_addresses=false`：不可放宽的固定边界

主动探测 URL 只用于发起 HTTPS 端到端检查，采样记录仍只保存主机名、类别、状态与计时，不保存路径或查询。匿名客户端与策略 ID 使用的随机盐由运行时在状态目录自动生成，不应写进仓库配置；每日 `09:00 Asia/Shanghai` 的时间由 Codex automation 管理，也不属于 `surge_monitor`。

## 安装与运行

在仓库根目录执行：

```bash
tools/install_surge_monitor_macos.sh
```

安装器会先用系统 Python 做语法预检，再把监控程序与国内 DNS 分类清单的运行副本放到状态目录，避免 macOS 拒绝 `launchd` 直接读取“文稿”中的仓库文件；随后创建 `~/Library/LaunchAgents/com.rulemesh.surge-monitor.plist`，并以以下只读守护模式运行。升级时若新版 bootstrap 或启动后的运行状态 / `status` 健康检查失败，安装器会恢复旧运行副本和 plist，并尝试重新加载旧服务：

```text
/usr/bin/python3 "$HOME/Library/Application Support/RuleMesh/surge-monitor/runtime/tools/monitor_surge.py" --config "$HOME/Library/Application Support/RuleMesh/surge-monitor/config.json" daemon
```

状态与日志写入 `~/Library/Application Support/RuleMesh/surge-monitor`；守护进程会把错误日志限制在约 1 MiB。可以用以下命令确认 launchd 状态：

```bash
launchctl print gui/$(id -u)/com.rulemesh.surge-monitor
```

仓库开发副本也提供四个明确的只读入口：

```bash
python3 tools/monitor_surge.py daemon
python3 tools/monitor_surge.py collect
python3 tools/monitor_surge.py report
python3 tools/monitor_surge.py status
```

`daemon` 用于 launchd 常驻；`collect` 执行一次到期采集，`report` 生成当前脱敏日报，`status` 读取本地运行状态。四个入口都不得调用 Surge 的修改类命令。仓库脚本默认读取仓库根目录 `.rulemesh.local.json` 的 `surge_monitor` 节；LaunchAgent 明确读取状态目录下的 `config.json`，安装器不会把含其他密钥的整份仓库私有配置复制过去。

每日 Codex automation 必须同时使用 LaunchAgent 的运行副本和运行配置，固定通过以下只读命令生成日报，避免仓库脚本、数据库 schema 与运行版本漂移：

```bash
/usr/bin/python3 "$HOME/Library/Application Support/RuleMesh/surge-monitor/runtime/tools/monitor_surge.py" --config "$HOME/Library/Application Support/RuleMesh/surge-monitor/config.json" report --hours 24
```

仓库里的监控程序或 `rules/dns/cn_dns_domains.list` 变化后不会自动覆盖运行副本，必须重新运行安装器，并比较源文件 / 运行副本哈希、检查 `launchctl print`、`status` 与最近错误日志后，才算升级完成。

从早期直接使用原始请求 ID 的试验库升级时，程序会丢弃对应旧请求明细并执行 checkpoint / `VACUUM`，不会把旧 ID 迁入新 schema；其他不含原始请求 ID 的聚合记录仍按保留期处理。

如果 `state_dir` 为空，采集状态与 launchd 标准输出 / 错误日志使用同一个默认目录。若显式指定其他状态目录，采集数据写入该目录，安装器创建的 launchd 标准输出 / 错误日志仍保留在默认目录；两处都必须保持仅当前用户可读。

卸载时执行：

```bash
tools/install_surge_monitor_macos.sh --uninstall
```

卸载器只停用精确的 launchd 标签并删除对应 plist，默认保留状态目录，避免未经确认删除历史证据。卸载后自动清理也随守护进程停止；确实不再需要数据时，再由用户单独确认清理。Codex automation 是独立组件，卸载脚本不会停用它；不再需要日报时还必须单独暂停或删除 automation，避免继续读取陈旧数据库。

## 运维检查

- Surge 升级后，先用 `surge-cli --help` 确认当前命令和输出格式，再升级解析器
- 如果 Surge CLI 不可用，记录“采集不可用”状态并停止生成配置建议，不要退回 HTTP API 或 MITM
- 如果有效配置指纹变化，日报应标记观察窗口边界，避免把改动前后的样本混为一谈
- 如果 20 秒采样连续失败，不得用 `reload`、`flush dns` 或 `switch-profile` 自愈
- 监控脚本、launchd plist、脱敏配置样例发生变化时，同步更新本文档与 `.rulemesh.local.example.json`
- 监控脚本或国内 DNS 分类清单变化后，重新运行安装器并确认运行副本哈希一致、LaunchAgent 为运行状态、`status` 采集新鲜且 `report` 没有版本错误
- 每次真正执行优化后，在 Codex 任务中保留对应 `recommendation_id`、脱敏前后指标与回滚结果，便于判断改动是否有效
