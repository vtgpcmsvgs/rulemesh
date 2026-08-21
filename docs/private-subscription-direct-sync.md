# 私有订阅端点同步约定

本文只记录本地私有“订阅端点同步块”的维护方式，避免真实订阅域名 / IP 散落在多个配置文件中，也避免把 Surge 与 Mihomo 的不同语义混在一起。

## 适用范围

下文的 `<私有当前配置目录>` 必须按 [private-repository-bootstrap.md](private-repository-bootstrap.md) 解析：优先使用 `rulemesh-local/current`，不存在时使用直接包含主配置与同步脚本的仓库根目录。

- `<私有当前配置目录>\private_subscription_direct.list`
- `<私有当前配置目录>\sync_private_subscription_direct.ps1`
- `<私有当前配置目录>\rulemesh-substore-surge-personal.conf`
- `<私有当前配置目录>\rulemesh-substore-surge-personal-company.conf`
- `<私有当前配置目录>\rulemesh-substore-surge-work-whitelist.conf`
- `<私有当前配置目录>\rulemesh-substore-mihomo-clash-verge.yaml`
- `<私有当前配置目录>\rulemesh-substore-mihomo-clash-meta.yaml`

## 设计目标

- 真实机场订阅端点只在私有目录维护，不回写公开仓库
- 由单一源文件维护端点集合，避免四份客户端配置重复手改
- 源文件只保存 Surge 与 Mihomo 都支持的规则本体，渲染策略由脚本的 `-Target` 分支决定
- Surge 分支保持既有“Chrome 节点选择例外 + 普通订阅连接直连”结构
- Mihomo 分支把这些端点的普通流量统一交给节点选择，不生成 `PROCESS-NAME` 或 `DIRECT` 规则
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

## Surge 语法防回滚

- Surge 的 Chrome 节点选择例外属于逻辑规则，最终形态是 `AND,((PROCESS-NAME,...),(...)),策略名`
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
