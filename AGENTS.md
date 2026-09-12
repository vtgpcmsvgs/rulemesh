# AGENTS.md

## 仓库重点

- 源规则只维护在 `rules/`
- 构建产物只发布三条线：
  - `dist/surge/rules/`
  - `dist/surge/dns/`
  - `dist/mihomo/classical/`
- 不要重新引入这些已废弃目录：
  - `dist/surge/domainset/`
  - `dist/mihomo/domain/`
  - `dist/mihomo/ipcidr/`

## 构建入口

- Windows 本地与 Codex 会话统一优先使用 `tools/build_rules.ps1`
- 不要默认直接跑 `python tools/build_rules.py`
- 这个包装脚本会优先探测：
  - `$env:RULEMESH_PYTHON`
  - 仓库内 `.venv\Scripts\python.exe`
  - `%LocalAppData%\Programs\Python\Python314\python.exe`
  - `python`
  - `py -3`

## Codex 注意事项

- 在 Codex Windows 沙箱里，`python` / `py -3` 可能不可用，即使 Python 已安装
- 使用 `rg` 搜索以连字符开头的模式（例如 `-Target`）时，必须在模式前加 `--`，避免被解析成命令行选项
- PowerShell 不会替 `rg` 展开任何路径通配符（包括 `tools/check*.py`、`docs/examples/*`）；统一传实际目录并用 `--glob` 筛选。读取未确认存在的文件前先用 `rg --files` 定位，避免从业务简称猜测文件名；命令失败必须立即处理，不能由后续读取成功掩盖。
- PowerShell 的语句级 `foreach (...) { ... }` 不能直接在右花括号后接管道；需要继续 `Format-Table`、`Where-Object` 等处理时，先把循环结果赋给任务专用变量，或用 `@(...)` 收集后再接管道
- PowerShell 的 `New-Item` 不支持 `-LiteralPath`；创建已验证的明确路径时使用 `-Path`，不要把其他文件 cmdlet 的参数习惯直接套用到 `New-Item`
- `rg` 未命中时会以退出码 `1` 结束；把“确认不存在”作为预期结果的审计命令应单独处理该退出码，避免让后续已完成的检查被误报为失败
- 重跑任务临时验证脚本前先检查其 `param` 块或 `Get-Help`，显式传入全部必需参数，不要假设临时脚本可以无参数运行
- 对包含多个重复 `[Rule]`、`dns:` 或同型多行字符串的测试 / 配置使用 `apply_patch` 时，补丁上下文必须带唯一函数名、节名或文件级锚点；应用后先检查实际命中区块，再运行测试，避免修改到更早的相似夹具
- 诊断或编辑 Surge 节时必须匹配独占一行的节标题并断言目标唯一，不能用 `split('[Rule]')` 或全文替换 `[Host]`；注释也可能引用节名，误命中会造成规则全部漏检。多文件替换应先核对全部锚点，脚本非零退出后必须立即停止，不能用后续 Git 命令的退出码掩盖失败。
- 当前机器已确认存在的解释器路径是：
  - `%LocalAppData%\Programs\Python\Python314\python.exe`
- 如果直接执行该解释器出现 `Access is denied`（访问被拒绝），这是沙箱限制，不是仓库问题；需要申请提升权限后再运行
- 维护解析后的私人当前配置目录中的 `sync_private_subscription_direct.ps1` 这类 Windows PowerShell 私有同步脚本时，不要直接硬编码中文或 emoji 策略组名；UTF-8 无 BOM 的 `.ps1` 在 Windows PowerShell 5.1 下可能被按本地代码页误读，导致 Mihomo / Surge 配置里写出乱码策略组名并触发 `proxy not found`。优先保持脚本源码 ASCII-only，或从目标配置提取现有策略组名后再写回
- 运行上述私有订阅同步脚本时必须显式传入 `-Target surge`、`-Target mihomo` 或 `-Target all`；用户明确要求只改某一客户端时，只运行对应目标，不得用共享源文件为理由顺带改动另一客户端
- 上述私有订阅同步脚本在生成 Surge 的 `AND,((PROCESS-NAME,...),(...)),策略名` 逻辑规则时，末尾策略名必须裸写，不要再套双引号；`RULE-SET,...,"🚀 节点选择"` 这类普通规则允许带引号，但 `AND` 规则若写成 `...,"🚀 节点选择"`，Surge 会把引号算进策略名并报 `unknown policy`
- 维护解析后的私人当前配置目录里的私有机场 provider 时，如果某个机场同时存在“入口域名”和“真实落地主机”，默认两者都要加入私有订阅端点源；优先使用精确 `DOMAIN` / `IP-CIDR`，不要用无必要的宽后缀覆盖，也不要只保留入口域名，否则 FlClash 桌面端 / Mihomo 可能在刷新 provider 时走偏、报 EOF，或把本地缓存刷成不完整内容
- 维护两份 Mihomo 私有配置里的机场 `proxy-providers` 时，默认每个机场 provider 都要显式保留 `proxy: DIRECT`，表示 Mihomo 后台下载 / 更新订阅 URL 直连；普通流量访问这些订阅端点则由 `rules` 中的精确域名 / IP 规则统一交给节点选择，不使用 Surge 的 `PROCESS-NAME + 域名` 逻辑规则，也不要把 `rule-providers` 拉 GitHub 规则集用的代理出站逻辑套到机场订阅 provider 上
- 对会按请求头协商响应格式的私有机场 provider，先实际探测返回内容；若通用 Mihomo 标识不能稳定返回 Clash YAML，可在该 provider 上显式使用已验证的 `header.User-Agent`，并让两份 Mihomo 配置保持一致
- 检查当前全部机场 provider 的有效期与可用性时，默认采用 30 秒目标、60 秒上限的只读快速路径：
  - 仅以两份 Mihomo 配置 `proxy-providers` 下的二级键为当前清单，并先核对名称、直属 `url`、`proxy: DIRECT` 与 `header.User-Agent` 是否一致；任一不一致时停止外部探测并先报告配置漂移。解析直属四空格 `url`，不得把六空格的 `health-check.url` 当成订阅地址，也不得用运行目录中的旧缓存反推当前清单
  - 因机场 provider 固定为 `proxy: DIRECT`，订阅探测必须使用相同 User-Agent 且显式绕过系统代理；PowerShell 路径统一使用 `HttpClient` + `SocketsHttpHandler.UseProxy = false`，任务开始即对全局 `CancellationTokenSource` 调用 60 秒 `CancelAfter`，每请求 linked token 再调用 10 秒 `CancelAfter`，并发成批检查 HTTP 状态、顶层 `proxies`、`Subscription-Userinfo` 到期与剩余流量。不得把 `Invoke-WebRequest -OperationTimeoutSeconds` 当作完整请求 deadline；单项只可在全局预算仍充足时短重试一次
  - 运行中的 FlClash 只读取实际已配置的 Mihomo HTTP 控制器；`external-controller` 与 `external-controller-pipe` 都为空时报告运行态未知，不能把 FlClash 私有 IPC 当 HTTP 管道。已配置管道使用 linked token 的 `ConnectAsync` / `WriteAsync` / `ReadAsync`，只请求一次 `/providers/proxies`；存活节点必须同时满足 `alive = true`，并按实际客户端的 `health-check.interval` 判断最新 `history` 的新鲜度且 `delay > 0`。`history` 为空、过旧或时间不可解析只能报告“存活未知”；不得猜测 TCP 端口或把 mixed-port 当控制端口
  - 结论必须拆成端点 / 内容、配额、日历有效期与运行态四项：明确 `0 < expire <= now` 或在有效正数 `total` 下 `upload + download >= total` 时总体无效；`Expire = 0`、缺失配额或缺失到期时间只能报告“服务端未提供”，不能擅自解释为永久有效；其余项通过且至少一个节点有近期成功健康历史时才可报告当前可用，个别节点失败不影响结论
  - 默认不得调用可能长时间阻塞的强制 `/healthcheck`、启动隔离 Mihomo、重载客户端或反复试错；运行态不可读时，立即把订阅有效与节点存活拆开报告证据缺口，只有用户明确要求深挖时才升级验证
  - 常规检查由主流程一次完成，不先分派多个重复审计；子审计结果必须由主流程复核后才能使用。输出只保留 provider 名、HTTP 状态、节点计数、存活计数、剩余比例与到期时间，不得输出 URL、token、节点名、server、控制器密钥、header 或响应正文
- 用 Mihomo 原生 `-t -d` 做临时语法检查时，`-d` 必须指向已确认位于任务临时目录下的专用目录；PowerShell 变量不得使用大小写不敏感的 `$home` / `$HOME`，避免把缓存或数据库误写到用户主目录
- 私有机场 provider 若发生重命名（例如机场别名变更），除同步更新 `current` 下的 Mihomo / Surge 配置外，还要检查 FlClash 桌面端 运行目录中的旧 provider 缓存、辅助 profile、remote profile 注册项与历史当前项；避免新旧 provider id 并存，导致 UI 继续读取旧缓存或把问题误判成“节点被过滤”
- 2026-09-09 用户已批准性能基线：普通业务默认国内双 DoH，海外 AI（含 Google AI）美国出口与独立海外解析；Crypto 台湾、明确日本入口与香港券商保留地区，其余海外代理自动择优。完整约束见 docs/performance-baseline.md；不得恢复旧版默认海外 DNS 和大量镜像 policy。
- 维护 Surge DNS 时只能使用 `[Host] + DOMAIN-SET` 隔离节点 server 域名；`use-local-host-item-for-proxy` 默认保持 `false`，不要在 Surge 里伪造 Mihomo 的 `proxy-server-nameserver`
- Surge profile 不要写 `dns-mode = fake-ip`；Fake IP 由 Surge Enhanced Mode / VIF 运行时提供，Mac 端在 Surge 里启用 Enhanced Mode，不要把 Mihomo / Stash 的 `dns-mode` 搬进 Surge
- Surge 的 `skip-proxy` 不要再放行 Apple `17.0.0.0/8`；macOS 更新入口已收敛到 `region/us/macos_update_us`，必须让前置拒绝规则和后续美国分流规则有机会命中
- 给 Surge / Mihomo 新增 DNS、fake-ip、Tun 或透明代理字段前，必须先按目标客户端自己的 profile 语义确认；不要用“另一个客户端有同名或近似字段”来推断可用性
- Surge 私有配置允许继续维护自己的复杂 DNS 版本；不要因为 Surge 正常，就反推 Mihomo 私有文件也应保持同样结构
- 两份 Mihomo 与公开模板采用国内 nameserver + AI 专用 nameserver-policy + 国内 proxy-server-nameserver bootstrap；ipv6、use-hosts、use-system-hosts、respect-rules 均为 false，开启 tcp-concurrent，保留 ARC 与 fake-ip。
- 新版静态检查与生产运行态必须分别报告。历史 v1.19.25 查询未命中模拟 resolver；即使静态检查已通过，DNS 路由运行时仍未确认时也不得声称已经生效。
- 两份 Surge Personal、两份 Mihomo 与公开模板的通用 FINAL/MATCH 按 2026-09-12 用户要求使用 DIRECT；仅工作白名单保持 FINAL,REJECT，前置代理规则继续使用指定组；FlClash 桌面 provider 与 url-test 使用 interval: 300、安卓使用 600；provider 与实际业务组 lazy: false，备用地区组 lazy: true，全地区 tolerance: 50、美国 tolerance: 100。全地区组只排除套餐占位项，不限制地区标签。
- 七份配置的 ai_us 必须为第一条有效规则并包含 Google AI；国内精选直连、日本精确入口、Crypto 台湾和香港券商在 google_hk 完整 IP 规则前。google_hk 兼容路径和官方完整地址空间保留，普通 Google 流量自动择优。
- Mihomo 私有文件里的机场 provider `health-check.url` 与 `url-test` 组测速 URL 统一使用 HTTPS `https://www.google.com/generate_204`；不要改回 HTTP
- `proxy-node-domains` 必须是从 Sub-Store 聚合订阅提取的节点 `server` 域名清单，且必须过滤 IP 并按一行一个域名输出；不得包含订阅链接域名、机场面板域名或普通目标网站域名，也不得输出逗号分隔清单
- Surge `[Host]` 引用 `proxy-node-domains` 时，必须使用 Surge 生产设备可直接访问的 Sub-Store 分享文件 URL；不要把未经同网络验证的 `https://sub.store/api/file/proxy-node-domains` 写进生产配置
- 涉及代理、旁路由、Surge、Mihomo、Sub-Store、DNS、DoH、fake-ip、mapping、Tun、透明代理或规则分流时，默认同时检查 DNS 出口；不能只验证“网页能打开”

## 本地 Surge 监控约束

- `tools/monitor_surge.py` 与 `tools/install_surge_monitor_macos.sh` 组成只读监控层；采集器只能调用 Surge CLI 的 `dump` 类命令与公共轻量 HTTPS 探测，不得自动执行 `set`、`reload`、`flush dns`、`switch-profile`、策略切换、外部资源更新或配置编辑
- 日报只能生成 `RM-INV-*`，状态为 `pending_investigation_approval`；用户回复 `批准调查 RM-INV-*` 只授权只读调查，不能授权任何变更。调查形成精确 diff、风险、回滚与复测步骤后，必须另行生成不可变的 `RM-EXEC-*` 并获得第二次明确批准才可实施
- 原始 CLI 输出只能在内存中解析；不得落盘 URL 路径 / 查询、设备名、MAC / 客户端 IP、真实策略 / 节点名、header、body、原始 profile、订阅 URL 或密钥
- 允许落盘的主机名只限关注目标和失败 `FINAL` 候选；设备、策略、DNS 答案、远端地址与事件只保留随机盐生成的不可逆摘要。全量请求去重键固定保留 1 小时加一次清理间隔，关注请求明细固定保留 36 小时，其余采样和建议索引默认保留 14 天
- macOS LaunchAgent 使用 `com.rulemesh.surge-monitor`，运行副本位于 `~/Library/Application Support/RuleMesh/surge-monitor/runtime`，避免直接读取受 TCC 保护的仓库目录；修改监控程序或国内 DNS 分类清单后必须重新运行安装器同步运行副本
- Codex 每日任务必须调用状态目录中的已安装运行副本与运行配置，只运行只读 `report` 并发送 `RM-INV-*`；不得在无人值守任务中运行 `collect`、接受 `RM-EXEC-*`、修改 Surge、编辑仓库、提交或推送
- 飞书 Webhook 只能作为 Scheduled 日报的旁路提醒：默认由本地守护进程在每日 `09:05 Asia/Shanghai` 发送采集质量与待查看项数量，不发送证据、域名、`RM-*` ID 或配置。飞书回复永远不构成调查或执行授权；Webhook 配置 / 网络失败不得阻断采集、`report` 或 Scheduled，真实 URL / 签名密钥只允许保存在状态目录的私有 `config.json`

- AWS IP 与链式 SOCKS5 的源规则、上游登记和构建产物继续保留；当前配置不得注册或调用，停用配置不等于删除资产。
- GeoIP 直接使用 MetaCubeX/meta-rules-dat 持续更新的 country.mmdb，不再经由本仓库 Release；未定制公共资源优先活跃上游，自定义规则继续使用 dist。
- 批量替换出口前列出地区例外，并从实际业务路由解析目标组；多个组可复用地区过滤器，不得假定美国组唯一。

## 仓库默认流程

- 动手前先按“源规则、上游登记、公开文档/模板、构建与检查脚本、私有同步项”给本次任务分类；高风险联动没分清前，不要直接编辑
- 对本仓库的任何实际修改，默认同时同步更新解析后的私人当前配置目录中对应文件；除非用户明确说明不要同步
- 修改前后都要在解析后的私人当前配置目录中判断是否存在对应文件；只有存在对应关系时才同步；若本次没有对应同步项，最终回复中必须明确写出“本次无对应同步项”
- 私有配置目录解析必须以实际仓库布局为准：优先使用 `%USERPROFILE%\Desktop\rulemesh-local\current`；若该目录不存在、但 `rulemesh-local` 根目录直接存在五份主配置与同步脚本，则使用仓库根目录作为当前配置目录，不要凭空创建 `current` 或因此跳过同步，并在最终回复说明实际路径
- `%USERPROFILE%\Desktop\rulemesh-local` 是独立的私有 Git 仓库，远程默认分支是私有配置的最终数据源，本地目录仅作为工作副本；不要把它嵌入或合并到公开 `rulemesh` 仓库
- 根目录 `private-repository.json` 是私人仓库远程地址、本地默认路径与布局候选的机器可读单一登记；当前登记仓库为 `vtgpcmsvgs/rulemesh-local`，恢复流程见 `docs/private-repository-bootstrap.md`
- 同一 GitHub 账号的登录状态不会自动建立本地目录映射；当 `rulemesh-local` 在本机不存在时，必须先读取登记文件、通过 GitHub 查询登记仓库并按文档恢复，不能直接声称私人配置不存在，也不能新建同名空仓库
- Codex 沙箱若把已登记私人仓库报为 `dubious ownership`，只对当前命令使用 `git -c "safe.directory=<已确认的私人仓库绝对路径>" ...`，不要修改全局 `safe.directory`；PowerShell 中包含 `@{upstream}` 的 Git revision 必须整体加引号，避免被解释为哈希表语法
- Codex 当前工作区若只允许写公开仓库，私有同步脚本可能在 `WriteAllText` 阶段报 `Access denied`；这是独立私人仓库的沙箱写权限限制，应在确认目标绝对路径后申请提升权限重跑，不要误改脚本或配置来绕过
- Windows PowerShell 5.1 的一次性诊断命令禁止使用 `$HOME` / `$home`、`$Host` / `$host` 等自动变量名作为临时变量；变量名大小写不敏感，会与只读系统变量冲突。统一使用带任务语义的变量名（例如 `$endpointHost`）。哈希计算不要依赖较新 .NET 的 `SHA256.HashData` 或 `Convert.ToHexString`，统一使用 `SHA256.Create()` 与 `BitConverter`
- 跨 Windows PowerShell 5.1 与 PowerShell 7 检查文件 BOM 时，不要使用版本语义不一致的 `Get-Content -Encoding Byte`；统一用 `[System.IO.File]::ReadAllBytes()` 读取前三个字节后判断，避免验证命令本身因版本差异失败
- Codex 沙箱若不允许写 `.git/FETCH_HEAD`、索引或对象库，`git fetch` / `add` / `commit` 应在确认仓库路径后申请提升权限；不要把后续只读命令的成功退出码误当成前一个 Git 写操作也已成功
- 修改 `rulemesh-local` 前先确认工作区、当前分支和远程同步状态；修改完成后必须提交并推送，且只有远程推送成功并确认本地未领先远程时才算私有配置同步完成
- 私有仓库可以完整纳管配置内容，但检查、提交和验证过程中仍不得在回复或日志中回显真实订阅地址、密钥、签名、证书参数或其他敏感值
- 检查私有配置时，脱敏必须在命令或工具产生输出之前完成；不要先输出整行再事后遮盖。默认只查看字段名、命中计数、哈希或已经替换 URL、令牌、密钥与证书参数的片段
- 私人仓库使用 `.gitattributes` 的 `* -text` 时，保留未修改行的既有换行风格；新增或重写行统一使用 LF，并在提交前运行 `git diff --check`，避免 CR 字符被识别为行尾空白
- 修改私人仓库名称、所有者、默认分支、本地默认路径或布局候选时，必须同步更新 `private-repository.json`、`docs/private-repository-bootstrap.md`、`README.md`、本文件与对应检查脚本
- 修改完成后，必须检查整个仓库中同类问题是否仍然存在，并检查是否有耦合项、重复项、残留项；发现后应一并处理或明确报告
- 公私仓库提交前都必须先 `git fetch` 并检查本地分支相对远端的 ahead / behind；只要 behind 非零，必须先完成 rebase 或其他明确的集成处理并重新验证，不能把 `rev-list` 检查与 `commit` / `push` 放进不会按结果中止的无条件命令链
- 任务执行中一旦出现命令失败、错误假设、用户纠正、验证失败、回滚或安全边界误触，自动触发“现象—根因—修复—防复发”经验沉淀，不等到用户再次提醒
- 错误经验必须在当前任务内落到最窄且可执行的位置：能机械验证的优先新增测试、检查或 guardrail；不能机械验证的写入对应脚本注释、专项文档或 `AGENTS.md`，并删除会诱发同类错误的旧说明
- 沉淀前先区分可复现的仓库问题与一次性外部故障；临时网络波动、外部服务偶发失败不写成永久规则，但要记录本次验证限制。每次沉淀后重新执行受影响的最小验证与全量检查，形成持续迭代闭环
- 提交前默认运行 `powershell -ExecutionPolicy Bypass -File tools/check.ps1`；若因为环境或权限限制无法执行，必须在最终回复中明确说明
- `tools/check.ps1` 默认包含 `tools/check_change_guardrails.py` 变更联动闸门：当前对“源规则 `.list` 新增 / 删除 / 重命名未同步 `rules/upstream/sources.yaml` 与 `rules/upstream/merge.yaml`”以及“`docs/rule-authoring-style.md` 变更未同步 `AGENTS.md` 与 `README.md`”直接失败；其余高风险联动至少会显式提醒
- 新增、删除或重命名 `rules/{reject,direct,proxy,region}/` 下的 `.list` 源规则文件时，必须同步更新 `rules/upstream/sources.yaml` 与 `rules/upstream/merge.yaml`
- 新增或调整默认对外使用的规则入口、规则顺序、策略含义或公开模板行为时，必须同步更新 `README.md`、`docs/usage-surge.md`、`docs/usage-mihomo.md`、`docs/examples/surge-public.conf`、`docs/examples/mihomo-public.yaml`
- 若本次修改影响使用方式、规则组织、构建方式、产物结构或维护约定，必须同步更新相关文档
- 2026-05-07 下线的两类激进 `reject` 入口不再恢复到源规则、公开模板或私有配置，除非用户明确要求重新启用
- 私有 `rulemesh-substore-surge-work-whitelist.conf` 属于长期特化的工作路由白名单配置；它与两份 Surge Personal、`rulemesh-substore-mihomo-flclash-desktop.yaml`、`rulemesh-substore-mihomo-flclash-android.yaml` 从现在起允许永久不一致，不得因为“统一模板”或“对齐 personal 配置”而回滚
- Surge Personal 固定维护家庭版 `rulemesh-substore-surge-personal.conf` 与公司版 `rulemesh-substore-surge-personal-company.conf`；两者只允许用途标识和 MITM 不同，路由与 DNS 结构必须同步。Personal 专用的 `personal_priority_hk`、`notion_hk`、`hk_securities_aggressive`、`apple_direct`、`outlook_direct` 与 `microsoft_store_us` 不得同步进工作白名单
- 工作配置也使用默认国内 DNS；可保留小型 cn_dns_domains，不引用性能型清单，DNS 调整不授予流量放行。
- 维护 `rulemesh-substore-surge-work-whitelist.conf` 时，默认应维持“仅放行明确白名单入口，其余流量对工作电脑统一 REJECT”的原则；若要恢复广谱放行（如 `proxy/gfw`、广谱 `direct`、`FINAL` 兜底放行），必须得到用户明确确认
- 工作白名单保留既有精确放行、设备条件与观察规则，新增 cn_social_direct 精确直连；AI 美国、Crypto/RPC 台湾、明确日本入口与香港券商保留地区，其他代理自动择优。AWS IP 和链式 SOCKS5 调用停用；最终保持 FINAL,REJECT，不恢复 cn_direct 或 gfw 广谱放行。
- region/hk/wps_kdocs 仍是工作白名单精确放行入口，位于 FINAL,REJECT 前；当前自动择优并使用默认国内 DNS，不再强制香港与海外解析。
- GitHub 在该工作路由文件中除 `github_ssh_direct` 外，还允许紧随其后保留 `DOMAIN,raw.githubusercontent.com` 下载入口与一条广覆盖 `DOMAIN-KEYWORD,github` 观察兜底；它们用于显式放行 GitHub Raw 规则产物下载，并发现 SSH / Raw 之外的漏网之鱼，不得被“去重”或“收敛”掉
- GitHub Raw 下载链路默认还应保留独立 `[Host]` 解析例外；当前私有配置使用 `raw.githubusercontent.com = server:https://cloudflare-dns.com/dns-query`，避免规则产物下载回落到本地/国内系统 DNS；但这不是代理节点 bootstrap，不能影响 `proxy-node-domains` 继续使用 AliDNS DoH
- AdsPower 按 2026-09-12 用户要求在五份私有配置与两份公开模板停用：移除三类调用、专用 provider 和工作观察兜底，保留主清单、源规则、登记、派生器与产物；重新启用须用户明确要求。
- Outlook 直连覆盖邮件、精确共享登录与认证资源，不扩大到 Microsoft 根域；共享认证也影响其他应用。默认国内 DNS 已获批准，Microsoft Store 使用自动代理，不再固定美国。
- 上述工作路由白名单特化只适用于工作路由文件本身，不自动扩散到两个 `personal` 配置，也不要把 `personal` 配置的通用结构反向覆盖到该工作路由文件
- 只要工作路由白名单逻辑、适用范围、维护边界发生变化，必须同步更新 `docs/surge-work-cluster-whitelist.md`、`README.md` 与相关使用说明，避免后续失忆式回滚
- 若本次任务产生了实际文件变更，且用户没有明确禁止提交，则默认在验证完成后提交 git commit
- 如果上述任一步无法执行，不得静默跳过；必须在最终回复中明确说明未完成项、原因以及阻塞点
- 只有实际执行过构建、检查、`git status`、全仓搜索等动作，最终回复里才可写“已验证”“已检查”或等价表述；不能把推断写成已完成
- 最终回复默认应包含：同步状态、全仓检查结果、文档更新情况、验证结果、提交状态

## 源规则编排约定

- 修改 `rules/{reject,direct,proxy,region}/` 下的中大型 `.list` 源规则文件时，默认按“同平台 / 同服务聚合展示 + 上游优先 + 本地兜底”维护，不要把显式域名和关键词兜底简单堆成一坨
- 文件头必须先写清楚：这份规则负责什么、不负责什么、与相邻规则文件的边界是什么、客户端顺序上应放在哪里
- 像多地区链式 SOCKS5 端点这类非单一区域入口，不要因为历史来源继续挂在 `rules/region/jp/` 之类的单国家目录；应按当前语义放到更合适的路径，并在文件头写清客户端能力边界：Surge 可以在规则层把端点连接交给链式 / 负载均衡组，Mihomo 普通 `RULE-SET` 不等价于节点拨号层的 `dialer-proxy`
- `rules/region/multi/chain_socks5_ipcidr.list` 维护私有代理服务商导出清单的脱敏快照；更新时必须在内存中完整校验每行 IPv4、端口与认证字段，拒绝空响应、异常行、非公网 IPv4 和重复 IP，全部通过后再按 IPv4 数值排序并原子全量替换。公开仓库只能保留 `IP-CIDR,<IPv4>/32`，不得保存或输出下载地址、端口、用户名、密码、令牌或 `plan_id`
- 两份 Mihomo 私有配置与公开 Mihomo 模板默认不得注册或调用 `region/multi/chain_socks5_ipcidr`；只有完成 `dialer-proxy` 配置、节点选择关系与运行时出口复测后才能恢复，不能因为 Surge 存在同名规则入口就机械对齐
- `IP-CIDR`、`IP-CIDR6`、`GEOIP`、`IP-ASN`、`ASN` 这类 IP 判断规则构建时默认补 `no-resolve`；纯 IP 规则集在客户端 `RULE-SET` 调用层仍建议保留 `no-resolve`
- 同一小节内部默认顺序是：
  - 小节注释
  - `INCLUDE,upstream/...`
  - 显式域名 / 网段 / IP 入口
  - `DOMAIN-KEYWORD` 或其他高价值兜底
- `ai_us`、`ai_cn_direct`、`bytedance_direct`、`google_hk`、`crypto_tw` 这类多平台或多服务混合文件，优先按平台或服务分组
- `wps_kdocs` 这类从大陆通用直连中切出的区域特化入口，客户端必须排在 `cn_direct` 前，并同时检查 DNS 清单是否存在更宽后缀覆盖
- region/hk/global_media 继续承接上游主体与 X/Twitter，默认自动择优；Polymarket 的显式后缀与关键词维护在 region/tw/crypto_tw，台湾出口优先于媒体广谱。
- `cn_direct`、`telegram` 这类入口型或通用基础兜底文件，可以保持“上游主体 + 本地最高优先级兜底”的简单结构，但仍要把边界写清楚
- 本地兜底只补“真实需要、上游暂未稳定覆盖、或需要更激进覆盖”的高价值入口，不要把本地规则膨胀成上游镜像
- 如果本次修改只涉及注释、分组与顺序，且构建后确认 `dist/` 内容没有变化，允许最终只提交源文件；但仍然必须完整执行 `tools/build_rules.ps1` 与 `tools/check.ps1`
- 只要本次修改改变了源规则的编排方式、分组风格、文件边界或维护习惯，必须同步更新 `AGENTS.md`、`README.md` 与 `docs/rule-authoring-style.md`

## 私有配置与脱敏

- `.rulemesh.local.json`、`%USERPROFILE%\Desktop\rulemesh-local` 整个私人仓库、私有 `policy-path`、真实机场订阅地址、Webhook、AccessKey、STS、`[MITM]` 证书参数、局域网设备分流规则都视为私有内容
- 默认不要把私有文件内容或敏感值写回公开仓库，也不要在回复中完整回显真实密钥、签名、订阅 URL 或其他敏感参数
- 即使需要在公开仓库里记录工作路由白名单维护约定，也只允许写“固定工作电脑”“白名单模式”“与 personal 永久不一致”这类抽象说明；不要把真实 `SRC-IP` 范围、私有设备标识、订阅地址或本地策略分组细节写回公开仓库
- 若 `rulemesh-substore-mihomo-flclash-desktop.yaml` 出现“某个 provider 全部测速失败，但同一订阅直导 FlClash 桌面端 正常”的现象，默认先对比运行时 `dns:`，并通过 Mihomo API / 命名管道与日志确认实际生效配置；不要先把问题归因到节点失效，也不要只停留在更换测速 URL 这一层
- 新版 Mihomo 只允许 AI 专用 policy 与国内节点 bootstrap；respect-rules: true、fallback、direct-nameserver、proxy-server-nameserver-policy 继续禁止。不要把当前已批准 proxy-server-nameserver 误判为旧版回滚。
- 若本地私有配置结构发生变化，必须同步更新 `.rulemesh.local.example.json` 与相关文档，但只允许写入脱敏占位值
- 若任务需要参考私有配置，默认只说明字段名、用途与是否生效，不直接暴露真实值

## 验证步骤

- 修改 `rules/`、`tools/build_rules.py`、文档或产物结构后，运行：
  - `powershell -ExecutionPolicy Bypass -File tools/build_rules.ps1`
- 提交前检查：
  - `dist/` 目录树是否仍然只有 `surge/rules`、`surge/dns` 与 `mihomo/classical`
  - `dist/build-report.json`
  - `git status`

## 警告约定

- 当前构建预期应为 `0` 条 warning
- 如果构建 warning 数量增加，先检查是否引入了：
  - BOM 字符
  - 不受支持的 Mihomo 规则
  - 被误判为普通文本的注释行

## 语言约束

- 仓库自写内容默认工作语言统一为中文
- `rules/{reject,direct,proxy,region}/` 中的自写注释必须使用中文；纯英文注释视为构建错误，不允许提交
- `tools/` 中生成 `rules/upstream/` 的头部说明、`dist/` 的生成头部说明统一使用中文
- 第三方原样同步的上游快照内容可保留原始语言，但不要在本仓库自写说明里继续追加英文注释

## 文件规范

- 规则与文档统一使用 UTF-8 无 BOM
- 新增或修改文本文件后，提交前要顺手检查是否意外写入 BOM；尤其是 `rules/`、`docs/`、`README.md`、`AGENTS.md`、`.github/`、`tools/`、`tests/`
- 如果看到首行注释被构建脚本误报为 `unrecognized plain rule`，先检查 BOM
- 不要手改 `dist/`；一律改 `rules/` 或构建脚本后重建
- 提交前若新增或修改注释，先确认是否为中文表达，而不是英文占位说明

## 机场手动组与配置归并补充

- 机场手动组是用户明确保留的界面功能，不得以无规则引用、规则不可达或性能精简为由删除。三份私人 Surge 当前各七组，保留原订阅和过滤器、可见并接入手动选择入口；数量变更须同步保护检查。停用 AWS 设备组不能波及机场组。
- 归并规则先确认既有规则集覆盖和首条命中顺序；Google Play 复用 google_hk，Surge Personal 爱思复用 aisi_direct，Apple 官方更新复用 apple_direct。ai_dns_us 单独保证 Surge AI DoH 美国出口，不扩大工作白名单或机械增加 Mihomo provider。私有 SRC-IP、端点及同步标记不写入公开规则。
- 多文件修改先完成全部唯一锚点和数量预检再写入；补丁存在空更新区块等格式错误时立即修正并重新预检，不得假设已部分成功。

规则停用约定：从授权配置移除调用、内联观察项与专用 provider / DNS 依赖，保留远程源规则、登记、构建逻辑和产物；暂停专用定时任务，共用任务只停对应专用步骤，通用构建保留。重新启用须用户明确要求。AdsPower 为当前停用实例，细则见公开仓库 docs/rule-deactivation.md。`ips5.vip` 独立使用 direct/ips5_direct，AI 之后、Google 广谱和拒绝之前 DIRECT，沿用国内 DNS。

- 多文件字节保真编辑的锚点须按实际文件换行匹配，不得根据终端显示假定 CRLF；兼容 LF / CRLF 后仍断言唯一，全部预检通过再写入。
- `tools/check.ps1` 包含重建和会暂时调整产物的测试；必须等待完整进程成功退出后再读取 `dist/`、构建报告或生成提交文件清单，避免并发审计把中间态误报为产物丢失。

## FlClash 迁移与极致优化

- 桌面、安卓唯一现用客户端均为 FlClash，对应私人文件为 rulemesh-substore-mihomo-flclash-desktop.yaml / rulemesh-substore-mihomo-flclash-android.yaml。以 docs/flclash-performance.md 为当前接入、测速、覆写与复测依据；旧客户端缓存和命名管道不能代表 FlClash 运行态。
- 标准模式导入规则，DNS 覆写关闭；必须检查 preferences 中的 patchClashConfig 和生成 config.yaml。进程匹配 strict，不能直接 off。
- cn_direct_light 由构建自动推导，只适用于紧接 gfw_precise、最终 DIRECT 的末尾；工作白名单不调用。完整 cn_direct/gfw、AWS/链式和已停用 AdsPower 资产保留。
- 校验 native validateConfig 只代表 YAML 能解析，需区分真正加载；provider 缓存须位于隔离 home 内。API 404 不能误报节点不可用，DNS UDP 被 TUN 缓存命中不能误报公网解析器更快。
- 阅读第三方源码前先用 rg --files 确认路径，不能把旧文件布局当作当前事实；脚本依赖用明确运行时路径，临时 PyYAML 不假设系统环境全局可用。
