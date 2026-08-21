# Surge Personal 激进分流与双 MITM 设计

## 目标

在不改变 `rulemesh-substore-surge-work-whitelist.conf` 文件及其远端规则语义的前提下，为两份 Surge Personal 配置建立一致的激进分流：Notion 与个人优先站点走香港自动、港交所参与者与老虎证券走香港自动、Apple 全域名直连、Outlook 邮箱直连、Microsoft Store 与其余 Microsoft 流量走美国；同时把家庭与公司 MITM 拆成两个兼容命名的文件。

## 配置文件边界

- 家庭配置继续使用 `rulemesh-substore-surge-personal.conf`，保留现有 MITM 与引用路径。
- 公司配置新增为 `rulemesh-substore-surge-personal-company.conf`，只替换用途注释与用户批准的公司 MITM。
- 两份 Personal 配置除用途注释和 `[MITM]` 两个字段外必须保持字节级语义一致。
- `rulemesh-substore-surge-work-whitelist.conf` 不编辑，也不允许因共享规则扩张而改变其允许范围。
- 两份 Mihomo 私有配置不接入本次 Personal 激进规则。

## 公开规则分层

为避免扩张现有 `region/hk/hk_brokers` 后间接改变工作白名单，新建 Personal 专用规则入口：

- `region/hk/personal_priority_hk`：承接 `doubleclick.net`、`xygj.pro`、`h3c.com`。
- `region/hk/notion_hk`：承接 Notion 官方域名族、旧域名与 `notion` 品牌关键词兜底。
- `region/hk/hk_securities_aggressive`：承接港交所当前 SEHK 参与者公开网站快照、老虎证券完整品牌域名族与低误伤品牌关键词。
- `direct/apple_direct`：承接 Apple 官方企业网络清单涉及的 Apple、iCloud、CloudKit、CDN 与内容域名族。
- `direct/outlook_direct`：承接 Outlook、Hotmail、Exchange Online 邮箱数据面；Microsoft 共享认证域名不放入这里。
- `region/us/microsoft_store_us`：承接 Microsoft Store 目录、购买、授权、下载、Delivery Optimization 与 Windows Update 相关端点。

现有 `region/us/microsoft_us` 继续承接 Store / Outlook carve-out 之后的其余 Microsoft 与 OneDrive 流量。

## 港交所参与者数据

港交所当前参与者查询页公开 SEHK 参与者名称与网站地址，是可机械提取域名、最接近香港证券公司网站全集的官方来源。同步逻辑必须：

1. 读取首页的参与者总数与总页数，再抓取全部页面。
2. 只接受 HTTP/HTTPS 公网主机名，拒绝 IP、凭据 URL、空值与异常主机。
3. 仅移除开头 `www.`，不擅自扩大 `sec.example.com.hk` 为整个 `example.com.hk`。
4. 去重、排序并生成 `DOMAIN-SUFFIX` 快照。
5. 总记录数、页面数或唯一域名数低于安全阈值时拒绝覆盖现有快照。
6. 采用并发受限抓取、明确 User-Agent、重试与原子写入；上游失败沿用现有告警机制。

由于部分参与者没有网站、网站已过期或交易 API 使用未公开域名，不能宣称数学意义上的百分之百覆盖。老虎证券与主要零售券商通过显式后缀和品牌关键词补强；不使用 `tiger`、`broker`、`securities`、`capital`、`finance` 等通用关键词。

## Personal 规则顺序

两份 Personal 的调用顺序固定为：

1. Apple DIRECT，位于 Apple 更新拒绝与 macOS 美国更新之前，因此 Apple 更新也改为直连。
2. Personal 香港优先、Notion 香港、香港证券激进规则，位于广告拒绝、中国直连与 GFW 之前。
3. Microsoft Store 美国，位于 Outlook 与通用 Microsoft 之前。
4. Outlook DIRECT，位于通用 Microsoft 美国规则之前。
5. 现有 `microsoft_us` 继续兜底其余 Microsoft 流量。

`yikaiying.com` 继续由现有 `direct/cn_direct` 与性能型国内 DNS 清单承接，并在 Personal 中保留显式 DIRECT 优先规则。Apple、Notion、券商、Outlook 与 Store 的 DNS 继续使用海外解析链路；不把这些新增规则泛化到国内 DNS 白名单。

## 安全与验证

- 公司 MITM 只写入私有仓库，不进入公开文档、测试夹具、命令输出或提交信息。
- 私有测试只比较字段存在性、摘要、顺序与两份配置的规范化差异，不回显值。
- 增加红—绿测试覆盖规则内容、规则顺序、港交所解析失败保护、双 Personal 文件登记、工作白名单哈希不变与公开仓库无 MITM 凭据。
- 完成后运行构建、全量检查、`git diff --check`、仓库结构审计、私有配置检查，并分别提交和推送两个仓库。

