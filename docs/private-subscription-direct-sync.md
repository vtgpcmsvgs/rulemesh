# 私有订阅端点同步约定

本文只记录本地私有“订阅端点同步块”的维护方式，避免真实订阅域名 / IP 散落在多个配置文件中，也避免把 Surge 与 Mihomo 的不同语义混在一起。

## 适用范围

下文的 `<私有当前配置目录>` 必须按 [private-repository-bootstrap.md](private-repository-bootstrap.md) 解析：优先使用 `rulemesh-local/current`，不存在时使用直接包含主配置与同步脚本的仓库根目录。

- `<私有当前配置目录>\private_subscription_direct.list`
- `<私有当前配置目录>\sync_private_subscription_direct.ps1`
- `<私有当前配置目录>\rulemesh-substore-surge-personal.conf`
- `<私有当前配置目录>\rulemesh-substore-surge-personal-company.conf`
- `<私有当前配置目录>\rulemesh-substore-surge-work-whitelist.conf`
- `<私有当前配置目录>\rulemesh-substore-mihomo-flclash-desktop.yaml`
- `<私有当前配置目录>\rulemesh-substore-mihomo-flclash-android.yaml`

## 当前性能联动

2026-09-09 普通代理端点使用自动组；脚本从现有 onepassword/gfw 路由提取策略，不依赖硬编码中文组名。必须保留 PRIVATE_SUBSCRIPTION_DIRECT_START/END 标记。同步后重新执行性能检查，验证地区专项未变、后台订阅仍为 DIRECT。

## 设计目标

- 真实机场订阅端点只在私有目录维护，不回写公开仓库
- 由单一源文件维护端点集合，避免四份客户端配置重复手改
- 源文件只保存 Surge 与 Mihomo 都支持的规则本体，渲染策略由脚本的 `-Target` 分支决定
- Surge 分支保持既有“Chrome 全地区自动选择例外 + 普通订阅连接直连”结构
- Mihomo 分支把这些端点的普通流量统一交给全地区自动选择，不生成 `PROCESS-NAME` 或 `DIRECT` 规则
- Mihomo 的机场订阅后台更新仍由 `proxy-providers.*.proxy: DIRECT` 独立控制，不能用普通流量规则替代
- 用户明确排除某一客户端时，不得顺带改动该客户端

## 源文件写法

- `private_subscription_direct.list` 每行只写规则本体，不附带策略名
- 允许空行与中文注释；同步脚本会保留分组注释与顺序
- 当前只允许 `DOMAIN`、`DOMAIN-SUFFIX`、`IP-CIDR`、`IP-CIDR6`
- 机场入口主机与实际落地主机都应记录；默认优先使用精确 `DOMAIN`，只有确实需要覆盖整组子域时才使用 `DOMAIN-SUFFIX`
- 单个 IPv4 / IPv6 主机可省略前缀，脚本会分别规范化为 `/32` 或 `/128`
- 脚本会拒绝空源、异常字段数、不支持的规则类型与重复规则
- 不要把订阅 URL 路径、查询参数、令牌、端口或认证信息写入该文件

## 同步方式

1. 修改解析后的私人当前配置目录中的 `private_subscription_direct.list`。
2. 解析实际目录并显式选择目标：

   ```powershell
   $privateRepo = Join-Path $env:USERPROFILE "Desktop\rulemesh-local"
   $privateCurrent = Join-Path $privateRepo "current"
   if (-not (Test-Path -LiteralPath $privateCurrent -PathType Container)) { $privateCurrent = $privateRepo }

   # 只更新 Mihomo
   powershell -ExecutionPolicy Bypass -File (Join-Path $privateCurrent "sync_private_subscription_direct.ps1") -Target mihomo

   # 只更新 Surge
   powershell -ExecutionPolicy Bypass -File (Join-Path $privateCurrent "sync_private_subscription_direct.ps1") -Target surge
   ```

3. 只有用户明确要求两类客户端同时更新时，才使用 `-Target all`。
4. 脚本使用既有的 `PRIVATE_SUBSCRIPTION_DIRECT_START` / `PRIVATE_SUBSCRIPTION_DIRECT_END` 标记段做原位替换；标记名称为历史兼容保留，不代表 Mihomo 分支仍然直连普通端点流量。
5. 同一目标连续运行两次后，目标文件哈希应保持不变。

## 两种目标的语义

### `-Target surge`

- 同时更新两份 Surge 私有配置
- 先为 Chrome 生成 `PROCESS-NAME + 端点` 的节点选择逻辑规则
- 再为同一批端点生成普通 `DIRECT` 规则，供订阅更新连接使用
- 整个同步块必须位于广谱代理规则前；工作白名单中它属于显式放行入口

### `-Target mihomo`

- 同时更新两份 Mihomo 私有配置
- 每个端点只生成一条普通 `DOMAIN` / `IP-CIDR` 节点选择规则
- 不生成 `PROCESS-NAME`，因此浏览器及其他普通流量都遵循相同策略
- `IP-CIDR` / `IP-CIDR6` 自动附加 `no-resolve`
- 同步块必须位于 `proxy_gfw` 前

## Mihomo provider 更新边界

- Mihomo 里有两类 provider：`proxy-providers` 拉机场订阅节点清单，`rule-providers` 拉 GitHub 规则集产物
- `proxy-providers.*.proxy: DIRECT` 只表示后台下载 / 更新机场订阅 URL 时直连，不会覆盖 `rules` 对普通端点流量的节点选择结果
- `rule-providers.*.proxy: "🚀 节点选择"` 是另一条链路；不要把它反向套到机场订阅 provider 上
- 如果订阅服务按请求头协商格式，应先分别探测状态码与响应结构；只有实测需要时，才为对应 provider 显式设置 `header.User-Agent`
- 同一个逻辑机场存在多个等价 URL 时，默认只保留一个 provider，避免节点重复；其余仍需保留的入口可以留在端点源中作为普通流量规则
- 两份 Mihomo 文件的 provider 名称、URL、路径、更新出站、请求头、健康检查与代理组引用必须保持一致

## Mihomo provider 有效性极速审计

这项审计只回答两个问题：订阅当前是否仍在有效期内，以及每个 provider 是否至少有一个经健康历史确认的存活节点。正常情况下以 30 秒完成为目标；从任务开始即设置 60 秒全局 deadline，到点必须取消未完成的网络或命名管道操作，停止扩展试验并准确报告证据缺口。

### 固定判定口径

- 当前清单只取两份 Mihomo 配置 `proxy-providers` 下的二级键；运行目录中的缓存文件只用于辅助对照，不能把已删除 provider 的旧缓存算回当前清单
- 结果固定拆成四项证据，不把它们压成一个含糊的“有效”：端点 / 内容、配额、日历有效期、运行态节点存活
- 端点 / 内容通过要求直属订阅 URL 直连返回成功且响应含非空顶层 `proxies` 清单；缓存可用但端点失败时只能报告缓存运行态，不能据此证明订阅端点当前有效
- `Subscription-Userinfo` 中存在完整数值字段且 `total > 0` 时才计算比例：`upload + download >= total` 判定配额耗尽，小于 `total` 时报告剩余流量；字段缺失、数值无效或 `total <= 0` 时报告“配额未提供 / 未确认”，不能按零消耗处理
- `expire > 0` 且大于当前 Unix 时间时判定仍在日历有效期内；`expire > 0` 且小于等于当前时间时判定已过期；`expire = 0` 或缺失只表示服务端未提供日历到期时间，不能写成“永久有效”。到期时间直接用 Unix 秒转换并输出 ISO 日期，不要把本地化后的月 / 日字符串再次解析
- 运行态存活节点必须同时满足 `alive = true`，并把所有可解析时间戳的 `history` 记录按时间排序后取最新一条，要求该条 `delay > 0` 且仍在新鲜度窗口内；不能用“窗口内任一旧成功记录”替代最新结果。新鲜度窗口取 `max(2 × 该 provider 的 health-check.interval, 10 分钟)`；配置间隔缺失 / 无效、`history` 为空、最新记录过旧或时间不可解析时只能报告“存活未知”，不能利用 Mihomo 初始 `alive = true` 误判存活
- 总体结论中，明确过期或配额耗尽会直接否决“有效”；其余项通过且至少一个节点有近期成功历史时可以报告“当前可用”，但配额或到期元数据缺失时必须同时保留对应“未提供 / 未确认”，不得升级成“有效期内”。个别节点失败不影响结论；结果应写成“确认存活数 / 已加载数”
- 订阅响应里的节点条目数与内核实际加载数可以不同；只要响应非空且运行态确认存活数大于零，先记录差异，不在常规审计里猜测过滤、去重或协议兼容原因

### 默认快速路径

1. 从两份 Mihomo 文件提取 provider 名称、直属 `url`、`proxy`、`header.User-Agent`，断言这些订阅字段一致且每个 provider 都是 `proxy: DIRECT`；任一不一致时停止外部探测，先报告配置漂移，不能任选一份继续。桌面健康检查 300 秒、安卓 600 秒属于已批准差异；按实际运行客户端的间隔计算新鲜度。解析器只能把 provider 直属的四空格 `url` 当订阅地址；六空格 `health-check.url` 是节点测速地址。
2. 启动全局 `CancellationTokenSource` 和单调计时器，并在任务开始立即调用 `CancelAfter(60 秒)`；PowerShell 路径使用 `SocketsHttpHandler` 设置 `UseProxy = false` 与 5 秒 `ConnectTimeout`，每个 `HttpClient` 请求创建与全局 token 联动的 `CancellationTokenSource` 并调用 `CancelAfter(10 秒)`，全部 provider 用 `Task.WhenAll` 并发。`SendAsync(..., linkedToken)` 与 `ReadAsByteArrayAsync(linkedToken)` 必须复用该 token，把响应头和响应体完整读取都纳入同一 deadline；不得用仅限制流读取空闲时间的 `Invoke-WebRequest -OperationTimeoutSeconds` 冒充完整请求超时。只在剩余全局预算不少于一次完整请求预算时，对单项短重试一次。按声明编码或 UTF-8 解码字节，兼容 `application/octet-stream`，不要把 `Byte[]` 直接转成字符串。只在内存中检查 HTTP 状态、顶层 `proxies` 与 `Subscription-Userinfo`，不要输出响应正文；统计节点条目时同时兼容独占一行的 `-` 与 `- ...` 两种 YAML 序列写法。
3. FlClash 正在运行时，从生成配置读取实际已启用的 Mihomo 控制器。TCP 使用配置指定的端点与认证；已配置 HTTP 命名管道的连接最长 2 秒，完整写入与读取最长 5 秒，均使用与全局 token 联动的异步操作。只请求一次 `/providers/proxies`，正确解码 HTTP chunked 后解析 JSON；仅统计 `alive = true`、最新 `history.delay > 0` 且仍在新鲜度窗口内的节点。FlClash 的私有二进制 IPC 不是该接口；两个控制器字段都为空时直接报告运行态未知，不另行启用控制器。
4. 用一张脱敏表返回 provider 名、端点 / 内容、配额、日历有效期、订阅节点条目数、确认存活数 / 已加载数和结论。旧缓存、源响应与运行态数量差异放在表后单独说明；任何未取得的证据都显式写“未提供 / 未确认”，不从其他项推断。

### 默认禁止的慢路径

- 不从 `proxy_provider` 缓存目录枚举“当前 provider”，也不把缓存存在等同于运行时已加载
- 不猜测控制器 TCP 端口，不把 mixed-port、DNS 端口或 FlClash 服务端口当作 Mihomo API；只使用明确配置的 HTTP 控制器，不能根据产品名称推断管道协议
- 不默认调用 `/providers/proxies/<name>/healthcheck`；该调用可能等待整批节点超时并长时间占用控制通道
- 已有分钟级新鲜的运行态 health history 时，不启动隔离 Mihomo、不重载配置、不刷新 provider，也不为了解析 YAML 临时安装依赖
- 不用紧凑的一次性 PowerShell 长命令堆叠解析、下载、管道通信与格式化；先保持步骤短且输出已脱敏，避免语法重试反而超过审计本身耗时
- 不直接采用子审计的“成功”结论；主流程至少复核 provider 清单、订阅响应结构与运行态计数三项

### 快速路径无法闭环时

- 订阅直连成功但运行时未启动：分别报告“端点 / 内容通过”、配额与日历有效期元数据结果，并写“节点存活待运行态确认”；不要把端点成功直接改写成订阅总体有效，也不要擅自启动用户客户端
- 运行态可读但订阅请求超时：保留“`alive = true` 且按时间戳取到的最新健康记录在新鲜度窗口内并且 `delay > 0`”的确认存活证据；若只有 `alive`，或间隔缺失 / 无效、历史为空 / 过旧 / 不可解析，则写“存活未知”，并把端点直连状态写成“本次未确认”。单项最多做一次短重试
- 命名管道暂时忙或不可读：停止强制 health-check 与隔离核心尝试，报告最后一次可验证快照的时间；只有用户明确要求继续深挖时，才设计独立且可清理的临时验证
- 任一失败都不得回显 URL、token、节点名、server、控制器密钥、请求头或响应正文

## Surge 语法防回滚

- Surge 的 Chrome 全地区自动选择例外属于逻辑规则，最终形态是 `AND,((PROCESS-NAME,...),(...)),策略名`
- 逻辑规则末尾策略名必须裸写，不能额外套双引号。正确示例：

```conf
AND,((PROCESS-NAME,chrome.exe),(DOMAIN-SUFFIX,example.com)),🚀 节点选择
```

- 错误示例：

```conf
AND,((PROCESS-NAME,chrome.exe),(DOMAIN-SUFFIX,example.com)),"🚀 节点选择"
```

- 普通规则仍可保留带引号的策略名，例如 `RULE-SET,...,"🚀 节点选择"`
- Surge 分支应继续从目标配置提取现有策略名后拼接逻辑规则，不要硬编码中文或 emoji，也不要把 Mihomo YAML 列表语法带进 Surge

## 编码与临时验证防回滚

- `sync_private_subscription_direct.ps1` 优先保持 ASCII-only；Windows PowerShell 5.1 可能把 UTF-8 无 BOM 脚本中的中文或 emoji 按本地代码页误读，最终触发 `proxy not found`
- 修改脚本后应确认脚本无 BOM、无非 ASCII 字符，并在 Windows PowerShell 5.1 下完成语法解析
- 私人仓库使用 `.gitattributes` 的 `* -text` 时，未修改行保留既有换行；新增或重写行使用 LF，并用 `git diff --check` 防止 CR 被当成行尾空白
- 用 Mihomo 原生 `-t -d` 检查配置时，任务目录变量必须使用专用名称，例如 `$mihomoTestDir`；不要使用 PowerShell 大小写不敏感的 `$home` / `$HOME`
- 运行前先确认 `-d` 解析后的绝对路径位于任务临时目录，运行后删除临时 provider 缓存与数据库；不得把验证产物写进用户主目录或客户端正式运行目录

## 回归检查

- 运行 `-Target surge` 后：
  - 两份 Surge 配置都应包含完整端点集合
  - Chrome 例外应是策略名裸写的 `AND` 规则，后续普通规则应为 `DIRECT`
  - 两份文件的同步块顺序与源文件一致
- 运行 `-Target mihomo` 后：
  - 两份 Mihomo 配置都应包含完整端点集合，普通端点策略全部为节点选择
  - 同步块不得出现 `PROCESS-NAME` 或 `DIRECT`
  - 每个 provider 都应被预期代理组引用，provider 名称与缓存路径不得重复
  - 两份配置分别通过当前官方 Mihomo 内核的 `-t` 检查
- 任一目标都要确认另一客户端文件的哈希未变化，除非本次明确使用了 `-Target all`
- 同时检查源文件与四份目标中是否残留已废弃端点、重复 provider、旧 provider 缓存或孤立代理组引用

## 维护边界

- 不要把真实订阅域名写进 `rules/`、`dist/`、`README.md`、公开模板或公开规则文档
- 不要把这组私有订阅端点规则合并进公开 `direct/*.list`、`proxy/gfw.*` 或其他面向所有用户的规则入口
- Surge 与 Mihomo 可以共用端点源，但不能共用渲染语义；任何语法、DNS 或 provider 字段都必须按目标客户端自己的规范验证
- 如果同步脚本、目标文件名、目标参数或插入顺序发生变化，需同步更新本文以及相关使用说明
