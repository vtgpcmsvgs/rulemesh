# Notion 网页连通性与稳定选点

2026-09-25 修订：用户要求删除 `📝 Notion-自动选择`，并让全局 Notion 统一走 `🇭🇰 香港-自动选择`。此前的独立业务测速方案已撤回，规则集与 provider 名称继续保留以兼容现有发布路径。

## 路由与客户端行为

- 保留 `region/hk/notion_hk`、`hk_notion` 兼容名称，不表示香港出口。规则覆盖 `notion.com`、`notion.site`、`notionusercontent.com`、`notion-static.com`、旧 `notion.so` 及其子域。保留用户此前批准的品牌关键词兜底，不扩大至共享 Cloudflare、Amazon IP 或根域。
- 六份适用配置的 Notion 入口均早于 Google 广谱；两份 Mihomo 保留 `hk_notion` provider 和调用。工作白名单不接入此 Personal 专项，继续最终拒绝。
- Mihomo 与 Surge 的 Notion 规则都绑定 `🇭🇰 香港-自动选择`，只使用已有香港节点过滤、测速周期和缓存，不复制订阅、不新增专用检测任务。
- Notion 规则集仍覆盖 `notion.com`、`notion.site`、`notionusercontent.com`、`notion-static.com`、旧 `notion.so` 及其子域；品牌关键词兜底范围不变。

## DNS 与运行验证

默认国内双 DoH 与节点 bootstrap 保留，AI 美国及安卓 Google 专项不变。对 app、公开站点、图片和旧静态资源域名，AliDNS、DNSPod、Cloudflare、Google 返回相同 A 地址集合，国内解析更快；没有依据新增 Notion 海外 DNS policy。目标站点经代理后的远端解析仍取决于节点与协议，不能把本地 DNS 对照当成所有设备远端 DNS 已验证。

此前的 FlClash 专项测速实验使用过独立临时目录、关闭 TUN、物理网卡绑定和本地控制器；这些历史数据用于确认 Notion 站点可访问性，不再决定当前策略组结构。当前配置验收以规则首条命中、香港过滤条件和客户端实际加载为准。

初始 270 节点中 223 个通过一次 Notion 探测；候选复测仍出现健康 URL 成功、业务请求超时的差异，故不按一次实验删节点。当前八个 provider 中一个缺少实际指定缓存，未从旧缓存拼凑，也未把缓存缺失解释为订阅失效。

三轮 app 请求中，直连首字节中位数约 629 毫秒，较优候选约 340 毫秒；真实官网公开图片约 523→226 毫秒。短期样本只证明当前线路存在优化空间，不代表所有页面、所有时段或登录后的同步速度。用户提供的公开页面及其图片仅用于本地复测，不在仓库记录页面标识和资源链接。

历史生产采样曾记录 Notion 页面、公开页和图片请求成功，但这些样本不代表本次配置已在设备加载。当前只报告静态规则与配置检查结果；生产 DNS、节点存活和页面吞吐仍需在客户端更新 profile 后单独复测。

最终恢复源 profile，关闭临时控制器并移除密钥；核对生成配置的规则、组、DNS、规则下载 URL 与源文件一致，TUN 开启且 DNS 覆写关闭。Surge 和安卓仅完成文件同步与静态检查，仍须对应设备更新配置；登录工作区的编辑同步未通过写入私人文档验收。

## 检查与防复发

`tools/check_notion_routing.py` 接入性能基线，覆盖真实私有配置和模板，防止遗漏、重复、后置、直连、错误策略组或遗漏 provider，并拒绝重新引入 Notion 专用策略组。`tools/common_route_cases.json` 检查官网、应用、API、泛化公开页、图片和旧入口的 TCP/UDP 首条命中；DNS 与运行态另行验证。

页面标题或 HTML 200 不是正文验收。Notion 图片可能不出现在无障碍树中，应结合截图与 DOM 的 `complete/naturalWidth`；图片 URL 只从已确认 Notion 域名提取，先排除签名/令牌和跟踪域，再输出。临时实验必需参数与当前缓存路径先校验，失败即停；统计只保存匿名样本，不输出节点、端点与认证信息。多文件补丁的任一锚点校验失败后，先确认没有部分写入，再修正完整锚点并重新预检。

回滚时恢复任务前四份私人配置备份及对应公开配置；保留 WPS 直连和其他已批准业务边界。回滚后复核实际生成配置、Notion 首条路由、香港节点过滤与同一公开页面/图片。

FlClash 诊断经验：其 `shared_preferences.json` 中的 `external-controller` 是枚举，仅接受空字符串和 `127.0.0.1:9090`；将隔离 Mihomo 允许的随机本地端口写入该偏好，会使应用在配置反序列化阶段无法正常启动。诊断脚本须先按实际客户端枚举校验、检查端口空闲，附加临时密钥，并在 `finally` 恢复原值；不能把核心字段自由度套到桌面应用偏好。重载后等待核心退出/启动与生成配置就绪，再检查规则和 API。读取仍在写入的诊断日志应使用共享读写方式，并在输出前脱敏。

依据：[Notion 官方网络白名单](https://www.notion.com/help/allowlist-ip)、[Mihomo 代理组](https://wiki.metacubex.one/config/proxy-groups/)、[Mihomo 健康检查实现](https://github.com/MetaCubeX/mihomo/blob/Meta/adapter/provider/healthcheck.go)、[Surge smart](https://manual.nssurge.com/policy-groups/smart.html)。
