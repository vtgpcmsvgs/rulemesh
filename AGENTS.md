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
- PowerShell 不会替 `rg` 展开 `tools/check*.py` 这类路径通配符；应改用 `rg <pattern> tools --glob 'check*.py'`，避免 Windows 将星号路径直接传给 `rg` 后报路径语法错误
- `rg` 未命中时会以退出码 `1` 结束；把“确认不存在”作为预期结果的审计命令应单独处理该退出码，避免让后续已完成的检查被误报为失败
- 重跑任务临时验证脚本前先检查其 `param` 块或 `Get-Help`，显式传入全部必需参数，不要假设临时脚本可以无参数运行
- 对包含多个重复 `[Rule]`、`dns:` 或同型多行字符串的测试 / 配置使用 `apply_patch` 时，补丁上下文必须带唯一函数名、节名或文件级锚点；应用后先检查实际命中区块，再运行测试，避免修改到更早的相似夹具
- 当前机器已确认存在的解释器路径是：
  - `%LocalAppData%\Programs\Python\Python314\python.exe`
- 如果直接执行该解释器出现 `Access is denied`（访问被拒绝），这是沙箱限制，不是仓库问题；需要申请提升权限后再运行
- 维护解析后的私人当前配置目录中的 `sync_private_subscription_direct.ps1` 这类 Windows PowerShell 私有同步脚本时，不要直接硬编码中文或 emoji 策略组名；UTF-8 无 BOM 的 `.ps1` 在 Windows PowerShell 5.1 下可能被按本地代码页误读，导致 Mihomo / Surge 配置里写出乱码策略组名并触发 `proxy not found`。优先保持脚本源码 ASCII-only，或从目标配置提取现有策略组名后再写回
- 运行上述私有订阅同步脚本时必须显式传入 `-Target surge`、`-Target mihomo` 或 `-Target all`；用户明确要求只改某一客户端时，只运行对应目标，不得用共享源文件为理由顺带改动另一客户端
- 上述私有订阅同步脚本在生成 Surge 的 `AND,((PROCESS-NAME,...),(...)),策略名` 逻辑规则时，末尾策略名必须裸写，不要再套双引号；`RULE-SET,...,"🚀 节点选择"` 这类普通规则允许带引号，但 `AND` 规则若写成 `...,"🚀 节点选择"`，Surge 会把引号算进策略名并报 `unknown policy`
- 维护解析后的私人当前配置目录里的私有机场 provider 时，如果某个机场同时存在“入口域名”和“真实落地主机”，默认两者都要加入私有订阅端点源；优先使用精确 `DOMAIN` / `IP-CIDR`，不要用无必要的宽后缀覆盖，也不要只保留入口域名，否则 Clash Verge / Mihomo 可能在刷新 provider 时走偏、报 EOF，或把本地缓存刷成不完整内容
- 维护两份 Mihomo 私有配置里的机场 `proxy-providers` 时，默认每个机场 provider 都要显式保留 `proxy: DIRECT`，表示 Mihomo 后台下载 / 更新订阅 URL 直连；普通流量访问这些订阅端点则由 `rules` 中的精确域名 / IP 规则统一交给节点选择，不使用 Surge 的 `PROCESS-NAME + 域名` 逻辑规则，也不要把 `rule-providers` 拉 GitHub 规则集用的代理出站逻辑套到机场订阅 provider 上
- 对会按请求头协商响应格式的私有机场 provider，先实际探测返回内容；若通用 Mihomo 标识不能稳定返回 Clash YAML，可在该 provider 上显式使用已验证的 `header.User-Agent`，并让两份 Mihomo 配置保持一致
- 用 Mihomo 原生 `-t -d` 做临时语法检查时，`-d` 必须指向已确认位于任务临时目录下的专用目录；PowerShell 变量不得使用大小写不敏感的 `$home` / `$HOME`，避免把缓存或数据库误写到用户主目录
- 私有机场 provider 若发生重命名（例如机场别名变更），除同步更新 `current` 下的 Mihomo / Surge 配置外，还要检查 Clash Verge 运行目录中的旧 provider 缓存、辅助 profile、remote profile 注册项与历史当前项；避免新旧 provider id 并存，导致 UI 继续读取旧缓存或把问题误判成“节点被过滤”
- DNS 泄漏按安全事故级别处理：普通目标网站域名默认不得交给国内 DNS；国内 DNS 只能作为“DNS 服务器域名 bootstrap”、“代理节点 server 域名 bootstrap”以及两层明确国内业务清单的专用例外。小型精选 `cn_dns_domains` 只服务工作白名单等严格范围；自动合并中国直连域名主体的性能型 `cn_performance_dns_domains` 只服务 Surge Personal 与两份 Mihomo 性能配置，绝不因模板统一或工作白名单维护而互换。
- 维护 Surge DNS 时只能使用 `[Host] + DOMAIN-SET` 隔离节点 server 域名；`use-local-host-item-for-proxy` 默认保持 `false`，不要在 Surge 里伪造 Mihomo 的 `proxy-server-nameserver`
- Surge profile 不要写 `dns-mode = fake-ip`；Fake IP 由 Surge Enhanced Mode / VIF 运行时提供，Mac 端在 Surge 里启用 Enhanced Mode，不要把 Mihomo / Stash 的 `dns-mode` 搬进 Surge
- Surge 的 `skip-proxy` 不要再放行 Apple `17.0.0.0/8`；macOS 更新入口已收敛到 `region/us/macos_update_us`，必须让前置拒绝规则和后续美国分流规则有机会命中
- 给 Surge / Mihomo 新增 DNS、fake-ip、Tun 或透明代理字段前，必须先按目标客户端自己的 profile 语义确认；不要用“另一个客户端有同名或近似字段”来推断可用性
- Surge 私有配置允许继续维护自己的复杂 DNS 版本；不要因为 Surge 正常，就反推 Mihomo 私有文件也应保持同样结构
- 维护 `rulemesh-substore-mihomo-clash-verge.yaml` 与 `rulemesh-substore-mihomo-clash-meta.yaml` 时，默认保持“单一业务 DNS 真相”：`ipv6: false`、`dns.ipv6: false`（若字段存在）、`use-hosts: false`、`use-system-hosts: false`、`respect-rules: false`；普通目标网站默认使用海外 `nameserver`，已批准的高优先级 rule-set `nameserver-policy` 镜像同一海外 DNS。
- 2026-08-21 用户已批准两份 Mihomo 私有文件采用分层 `nameserver-policy`：实际启用且位于中国大陆通用兜底前的 `reject/`、`proxy/`、`region/` 规则集必须优先使用海外 DNS，`rule-set:cn-performance-dns-domains` 才使用国内 DNS；OpenAI / ChatGPT 所在的 `region/us/ai_us` 必须同时固定美国出口与海外解析。静态检查已通过，两份真实配置的 Mihomo `v1.19.25` 原生语法检查也已通过；DNS 查询未命中模拟 resolver，因此 DNS 路由运行时仍未确认。不要回滚已批准架构，但其他 `nameserver-policy` key 与 `respect-rules: true`、`proxy-server-nameserver`、`proxy-server-nameserver-policy`、`direct-nameserver`、`fallback` 继续禁止，也不得把 Surge 的复杂 DNS 结构照搬到 Mihomo。
- 三份通用私有配置默认以性能优先：普通国际 `FINAL` / `MATCH` 使用现有全地区自动选择组，`region/us/ai_us` 继续固定美国组；两份 Mihomo 的 provider 与 `url-test` 统一使用 `interval: 300`、`lazy: false`，美国组 `tolerance: 100`
- 五份私有配置与公开模板必须将 `region/hk/google_hk` 放在全部拒绝、`region/us/ai_us`、国内直连、海外 DNS IP 美国分流与广谱兜底之前，并绑定香港自动选择组；Google AI 不得残留在 `ai_us`。Google 规则完整同步 `goog.json` 的 IPv4 / IPv6 地址空间且故意保留 Google Cloud 客户地址，`dns.google` 与 `8.8.8.8` 也应被前置规则送往香港
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
- Windows PowerShell 5.1 的一次性诊断命令也禁止使用 `$HOME` / `$home` 作为临时变量；变量名大小写不敏感，会与只读系统变量冲突。哈希计算不要依赖较新 .NET 的 `SHA256.HashData` 或 `Convert.ToHexString`，统一使用 `SHA256.Create()` 与 `BitConverter`
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
- 私有 `rulemesh-substore-surge-work-whitelist.conf` 属于长期特化的工作路由白名单配置；它与两份 Surge Personal、`rulemesh-substore-mihomo-clash-verge.yaml`、`rulemesh-substore-mihomo-clash-meta.yaml` 从现在起允许永久不一致，不得因为“统一模板”或“对齐 personal 配置”而回滚
- Surge Personal 固定维护家庭版 `rulemesh-substore-surge-personal.conf` 与公司版 `rulemesh-substore-surge-personal-company.conf`；两者只允许用途标识和 MITM 不同，路由与 DNS 结构必须同步。Personal 专用的 `personal_priority_hk`、`notion_hk`、`hk_securities_aggressive`、`apple_direct`、`outlook_direct` 与 `microsoft_store_us` 不得同步进工作白名单
- 工作白名单的国内 DNS 继续且只能引用小型精选 `cn_dns_domains`；不得引用性能型 `cn_performance_dns_domains`，也不得为了提高覆盖率改变其严格白名单边界。
- 维护 `rulemesh-substore-surge-work-whitelist.conf` 时，默认应维持“仅放行明确白名单入口，其余流量对工作电脑统一 REJECT”的原则；若要恢复广谱放行（如 `proxy/gfw`、广谱 `direct`、`FINAL` 兜底放行），必须得到用户明确确认
- 当前该工作路由白名单默认允许入口包括：最高优先级 `region/hk/google_hk` 全业务香港入口、设备分流、其他区域精确规则、GitHub SSH、GitHub Raw 下载入口、GitHub 广覆盖观察兜底、私有订阅域名同步块、1Password、AdsPower、Polygon RPC、BSC RPC、海外 DNS 主 IPv4 端点、代理节点 bootstrap DNS 直连例外（dns.alidns.com / doh.pub）、海外加密 DNS 显式入口、`LAN,DIRECT`、`direct/os_time_direct`、`region/us/microsoft_us`、`region/us/macos_update_us`、阿里云指定直连与 `direct/bytedance_direct`；Google DNS 走香港，其余海外加密 DNS 端点走美国；`[Host]` 中的 `cn_dns_domains` 只用于国内业务域名解析调度，不新增流量放行，但工作规则层显式允许 `zsxq.com` 与 `yikaiying.com` 两个精确 DIRECT 入口；2.1 设备分流继续保留既有源地址约束，未命中白名单入口的流量最终 `FINAL,REJECT`
- `region/hk/wps_kdocs` 是工作白名单的区域精确显式放行入口，统一绑定香港自动选择并放在 `FINAL,REJECT` 前；Surge `[Host]` 必须在 `cn_dns_domains` 前复用该规则集绑定海外 DoH，避免 `.cn` 国内解析覆盖 WPS / 金山文档
- GitHub 在该工作路由文件中除 `github_ssh_direct` 外，还允许紧随其后保留 `DOMAIN,raw.githubusercontent.com` 下载入口与一条广覆盖 `DOMAIN-KEYWORD,github` 观察兜底；它们用于显式放行 GitHub Raw 规则产物下载，并发现 SSH / Raw 之外的漏网之鱼，不得被“去重”或“收敛”掉
- GitHub Raw 下载链路默认还应保留独立 `[Host]` 解析例外；当前私有配置使用 `raw.githubusercontent.com = server:https://cloudflare-dns.com/dns-query`，避免规则产物下载回落到本地/国内系统 DNS；但这不是代理节点 bootstrap，不能影响 `proxy-node-domains` 继续使用 AliDNS DoH
- AdsPower 在该工作路由文件中除精细 `adspower_direct` / `adspower_proxy` 外，还允许紧随其后保留一条广覆盖 `DOMAIN-KEYWORD,adspower` 观察兜底；它是故意用于发现细分规则漏网之鱼的，不得被“去重”或“收敛”掉
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
- `region/hk/global_media` 继续承接 `blackmatrix7/global_media` 主体，并允许额外收敛 X / Twitter 网页域名与 Polymarket；若上游仍只有 `gfw` 通用条目，本地可保留 `DOMAIN-SUFFIX,polymarket.com` + `DOMAIN-KEYWORD,polymarket` 这类高价值香港兜底，不要再回挂到 `region/jp`
- `cn_direct`、`telegram` 这类入口型或通用基础兜底文件，可以保持“上游主体 + 本地最高优先级兜底”的简单结构，但仍要把边界写清楚
- 本地兜底只补“真实需要、上游暂未稳定覆盖、或需要更激进覆盖”的高价值入口，不要把本地规则膨胀成上游镜像
- 如果本次修改只涉及注释、分组与顺序，且构建后确认 `dist/` 内容没有变化，允许最终只提交源文件；但仍然必须完整执行 `tools/build_rules.ps1` 与 `tools/check.ps1`
- 只要本次修改改变了源规则的编排方式、分组风格、文件边界或维护习惯，必须同步更新 `AGENTS.md`、`README.md` 与 `docs/rule-authoring-style.md`

## 私有配置与脱敏

- `.rulemesh.local.json`、`%USERPROFILE%\Desktop\rulemesh-local` 整个私人仓库、私有 `policy-path`、真实机场订阅地址、Webhook、AccessKey、STS、`[MITM]` 证书参数、局域网设备分流规则都视为私有内容
- 默认不要把私有文件内容或敏感值写回公开仓库，也不要在回复中完整回显真实密钥、签名、订阅 URL 或其他敏感参数
- 即使需要在公开仓库里记录工作路由白名单维护约定，也只允许写“固定工作电脑”“白名单模式”“与 personal 永久不一致”这类抽象说明；不要把真实 `SRC-IP` 范围、私有设备标识、订阅地址或本地策略分组细节写回公开仓库
- 若 `rulemesh-substore-mihomo-clash-verge.yaml` 出现“某个 provider 全部测速失败，但同一订阅直导 Clash Verge Rev 正常”的现象，默认先对比运行时 `dns:`，并通过 Mihomo API / 命名管道与日志确认实际生效配置；不要先把问题归因到节点失效，也不要只停留在更换测速 URL 这一层
- 若两份 Mihomo 私有文件中任意一份再次出现 `respect-rules: true`、已批准高优先级海外例外与 `rule-set:cn-performance-dns-domains` 之外的 `nameserver-policy`、`proxy-server-nameserver` 或 `fallback`，默认按配置回滚事故处理；先恢复到“单一业务 DNS 真相 + 高优先级海外 DNS 例外 + 性能型国内 DNS 清单”的当前分层基线，保留已批准例外，并继续禁止 `direct-nameserver`、`proxy-server-nameserver-policy` 等复杂字段，再讨论是否存在必须保留的客户端特化例外。
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
