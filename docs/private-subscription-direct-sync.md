# 私有订阅域名同步约定

本文只记录本地私有“订阅域名同步块”的维护方式，避免后续把真实订阅域名重新散落回多个配置文件，或误写进公开仓库。

## 适用范围

- `%USERPROFILE%\Desktop\rulemesh-local\current\private_subscription_direct.list`
- `%USERPROFILE%\Desktop\rulemesh-local\current\sync_private_subscription_direct.ps1`
- `%USERPROFILE%\Desktop\rulemesh-local\current\rulemesh-substore-surge-personal.conf`
- `%USERPROFILE%\Desktop\rulemesh-local\current\rulemesh-substore-surge-work-whitelist.conf`
- `%USERPROFILE%\Desktop\rulemesh-local\current\rulemesh-substore-mihomo-clash-verge.yaml`
- `%USERPROFILE%\Desktop\rulemesh-local\current\rulemesh-substore-mihomo-clash-meta.yaml`

## 设计目标

- 真实机场订阅更新域名只在私有目录维护，不回写公开仓库
- 由单一源文件统一维护，避免 `Surge personal`、`Surge work whitelist`、`Mihomo Clash Verge`、`Mihomo Clash Meta` 四处重复手改
- 同一组规则同时服务 Surge 与 Mihomo，因此源文件只写双方都支持的规则语法
- Chrome 浏览器访问这些域名时仍可先走 `🚀 节点选择`，不再被订阅更新直连误伤
- 整个同步块必须位于 `proxy/gfw` 前；其中 Chrome 例外在前，订阅更新直连在后；在工作白名单里则属于显式放行入口
- Mihomo 的机场订阅后台更新还必须由 `proxy-providers.*.proxy: DIRECT` 显式控制；同步块只负责规则命中，不能替代 provider 自己的下载出站设置

## 源文件写法

- `private_subscription_direct.list` 每行只写规则本体，不要附带 `,DIRECT`
- 允许空行与中文注释；同步脚本会按原顺序把注释一并带入四份目标文件，方便按机场分组阅读
- 优先使用 `DOMAIN`、`DOMAIN-SUFFIX`、`DOMAIN-WILDCARD`、`IP-CIDR` 这类 Surge / Mihomo 都能直接复用的语法
- `IP-CIDR` 源规则会在直连块自动补成 `IP-CIDR,<ip>,DIRECT,no-resolve`；浏览器例外块若未写前缀，则自动按 `/32` 生成匹配
- 如果某条规则只被单一客户端支持，不要写进这份共享源文件

## 同步方式

1. 修改 `private_subscription_direct.list`
2. 运行 `powershell -ExecutionPolicy Bypass -File "%USERPROFILE%\Desktop\rulemesh-local\current\sync_private_subscription_direct.ps1"`
3. 脚本会自动刷新四份本地私有配置中的“Chrome 访问节点选择例外 + 订阅更新直连”规则块，并保留源文件中的分组注释与顺序
4. 如需人工确认，可检查四份目标文件中的 `PRIVATE_SUBSCRIPTION_DIRECT_START` 与 `PRIVATE_SUBSCRIPTION_DIRECT_END` 标记段

## Mihomo provider 更新边界

- Mihomo 里有两类 provider：`proxy-providers` 拉机场订阅节点清单，`rule-providers` 拉 GitHub 规则集产物。
- `proxy-providers.*.proxy: DIRECT` 只表示“后台下载 / 更新这个机场订阅 URL 时直连”；它不会把浏览器访问机场官网 / 面板也强制直连。
- 浏览器打开机场网站时，连接会进入 `rules`，先命中同步脚本生成的 `PROCESS-NAME + 域名` 规则，再走 `🚀 节点选择`。
- 后台订阅更新不是 Chrome 进程，也不应依赖浏览器例外规则；因此必须在每个私有机场 `proxy-provider` 上保留 `proxy: DIRECT`。
- `rule-providers.*.proxy: "🚀 节点选择"` 是另一条链路，用于让 GitHub 规则产物更新走代理；不要把它反向套到机场订阅 provider 上。
- 维护时请记住目标拆成两句话：浏览器访问机场网站走代理；Mihomo 后台刷新机场订阅直连。

## Surge 语法防回滚

- 这组“Chrome 访问节点选择例外”在 Surge 里属于逻辑规则，最终形态是 `AND,((PROCESS-NAME,...),(...)),策略名`
- Surge 的逻辑规则末尾策略名必须直接裸写，不要额外套双引号；正确示例：

```conf
AND,((PROCESS-NAME,chrome.exe),(DOMAIN-SUFFIX,example.com)),🚀 节点选择
```

- 错误示例：

```conf
AND,((PROCESS-NAME,chrome.exe),(DOMAIN-SUFFIX,example.com)),"🚀 节点选择"
```

- 上面这种错误写法在视觉上很像普通 `RULE-SET,...,"🚀 节点选择"`，但 Surge 会把双引号也当成策略名的一部分，最终报 `unknown policy`
- 因此，同一个策略组在不同规则类型里允许出现两种写法：
  - 普通规则引用策略组时，可继续保留双引号，例如 `RULE-SET,...,"🚀 节点选择"`、`DOMAIN,raw.githubusercontent.com,"🚀 节点选择"`
  - `AND` / `OR` 等逻辑规则收尾到策略组时，必须写成 `...,🚀 节点选择`
- 后续维护 `sync_private_subscription_direct.ps1` 时，Surge 分支应继续只从目标配置提取裸策略名，再拼出逻辑规则；不要为了“统一格式”把 `AND` 规则也改成带引号版本

## 编码防回滚提醒

- 这条链路的真实故障案例是：在 `sync_private_subscription_direct.ps1` 里直接写入中文或 emoji 策略组名字面量后，Windows PowerShell 5.1 可能把 UTF-8 无 BOM 的脚本按本地代码页误读，最终把 `🚀 节点选择` 之类的策略组名写成乱码
- 乱码一旦进入 Mihomo / Surge 私有配置，典型症状就是重新载入时报 `proxy not found`；报错通常出现在新插入的 `PROCESS-NAME + DOMAIN-*` 规则，而同文件原本已有的 `proxy_onepassword`、`onepassword_proxy.list` 或 `proxy_gfw` 规则仍然正常
- 因此，后续维护 `sync_private_subscription_direct.ps1` 时，优先保持脚本源码 ASCII-only；如果需要引用带中文或 emoji 的策略组名，不要直接硬编码，优先从目标配置中提取现有值后再写回
- 修改同步脚本后，至少人工抽查一次四份目标文件中的新增规则：新写入的策略组名必须与同文件里已有的 `proxy_onepassword` / `onepassword_proxy.list` / `proxy_gfw` 行完全一致，不能出现乱码
- Surge 侧的 `AND,((PROCESS-NAME,...),(...)),策略名` 逻辑规则不要给末尾策略名再套双引号；例如应写成 `...,🚀 节点选择`，不要写成 `...,"🚀 节点选择"`，否则 Surge 会把引号也当成策略名的一部分并报 `unknown policy`

## 回归检查

- 每次跑完 `sync_private_subscription_direct.ps1` 后，至少抽查两份 Surge 私有配置：
  - `rulemesh-substore-surge-personal.conf`
  - `rulemesh-substore-surge-work-whitelist.conf`
- 抽查时重点看 `PRIVATE_SUBSCRIPTION_DIRECT_START` 标记段后的第一条 Chrome 例外规则：
  - 必须是 `AND,((PROCESS-NAME,...),(...)),🚀 节点选择`
  - 不能出现 `...,"🚀 节点选择"`
  - 不能出现乱码策略名
- 同时确认注释分组与 `private_subscription_direct.list` 保持一致，特别是域名规则与 `IP-CIDR` 规则的机场说明不要丢失
- 如果 Surge 报 `unknown policy`，优先对照报错行是否属于这段同步块；若是，先检查“策略名是否乱码”与“逻辑规则是否误加引号”，不要先怀疑 `RULE-SET` 顺序或节点组本身不存在

## 维护边界

- 不要把真实订阅域名写进 `rules/`、`dist/`、`README.md`、公开模板或公开规则文档
- 不要把这组私有订阅域名同步规则合并进公开 `direct/*.list`、`proxy/gfw.*` 或其他面向所有用户的规则入口
- 如果未来某条规则只影响单一客户端而非全部三份配置，先评估它是否还适合继续放在共享源文件里
- 如果同步脚本、目标文件名或插入顺序发生变化，需同步更新本文以及相关使用说明
