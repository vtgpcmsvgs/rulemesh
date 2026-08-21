# 性能型中国 DNS 架构重构设计

## 背景

当前中国大陆流量存在两套彼此脱节的分类真相：

- `rules/direct/cn_direct.list` 通过 Loyalsoldier `direct.txt`、`cncidr.txt` 与本地兜底维护中国大陆直连路由；当前构建产物包含约 11.1 万条域名规则。
- `rules/dns/cn_dns_domains.list` 是 241 条左右的人工白名单，只覆盖少量国内业务域名。

因此，大量已经被路由层认定为中国大陆直连的域名，仍会先交给海外 DNS。只有海外 DNS 成功返回地址后，客户端才有机会通过中国 IP-CIDR / GEOIP 兜底改为直连。海外 DNS 的解析位置会影响国内 CDN 调度，失败时 IP 兜底也无法执行。

`yikaiying.com` 在本地显式补充前不属于任何现有中国域名上游；`.com`、ICP备案、注册商与服务器位置之间也不存在客户端可直接推导的协议关系。静态规则无法保证实时识别所有新注册国内域名，但可以消除“已被中国直连域名集收录、却仍使用海外 DNS”的大规模结构性缺口。

## 已批准范围

本次重构影响：

- 公开规则源、构建器、检查器、测试与文档。
- 私有 `rulemesh-substore-surge-personal.conf`。
- 私有 `rulemesh-substore-mihomo-clash-verge.yaml`。
- 私有 `rulemesh-substore-mihomo-clash-meta.yaml`。

本次明确不影响：

- 私有 `rulemesh-substore-surge-work-whitelist.conf` 的任何字节、规则、DNS 行为或引用资源。
- OpenAI / ChatGPT 固定美国出口语义。
- 机场 provider 的 `proxy: DIRECT`、请求头、订阅地址或节点内容。
- Mihomo 的 `respect-rules: false`、单一默认海外 `nameserver`、`ipv6: false`、`use-hosts: false` 与 `use-system-hosts: false` 基线。
- Mihomo 不恢复 `fallback`、`direct-nameserver`、`proxy-server-nameserver` 或相应 policy 字段。

## 方案比较

### 方案 A：独立性能型中国 DNS 集合 + 客户端海外例外优先（采用）

新增一份仅供 Personal Surge 与两份 Mihomo 使用的性能型中国 DNS 域名集合。该集合自动合并 Loyalsoldier 中国直连域名主体与现有人工国内 DNS 白名单。客户端先用自身已启用的拒绝、代理、美国、香港、台湾等高优先级规则选择海外 DNS，再用性能型中国集合选择 AliDNS / DNSPod，最后由默认海外 DNS 处理其余域名。

优点：国内覆盖随上游自动增长；可以表达 `WPS 香港`、`Microsoft 美国` 等“父域属于中国直连集，但具体业务需要海外区域策略”的优先级；不改变工作白名单。缺点：三个性能配置需要维护可机械检查的 DNS 例外顺序。

### 方案 B：构建时从中国集合减去所有海外重叠（不采用）

构建器可以删除与拒绝、代理、区域规则重叠的中国域名。但 `DOMAIN-SUFFIX` 与子域例外无法无损相减：为了排除一个海外子域，可能被迫删除整个国内父域，明显损失性能覆盖。

### 方案 C：所有未知域名同时查询国内和海外 DNS（不采用）

Mihomo 的 `fallback` / `fallback-filter` 可以根据 GeoIP 选择答案，理论上能发现尚未进入静态域名集的新 `.com` 国内站点。但它会把普通海外目标也发送给国内 DNS，扩大 DNS 暴露面，并恢复此前已证明容易引发运行时复杂性的双 DNS 真相。本次不启用。

## 架构

### 1. 保留两份不同用途的 DNS 产物

现有 `rules/dns/cn_dns_domains.list` 与 `dist/surge/dns/cn_dns_domains.list` 保持“小型人工白名单”语义，继续服务工作白名单及其他需要严格控制国内 DNS 范围的配置。

新增：

- 源：`rules/dns/cn_performance_dns_domains.list`
- 产物：`dist/surge/dns/cn_performance_dns_domains.list`

性能型源显式包含：

```text
INCLUDE,upstream/loyalsoldier/direct.txt
INCLUDE,dns/cn_dns_domains.list
```

构建器对 DNS 域名集合支持现有 `INCLUDE` 递归展开语义。Loyalsoldier 原始普通域名按 `DOMAIN-SUFFIX` 语义输出为 `.example.com`，现有人工条目保留精确域名或后缀语义；去重保持首次出现顺序。

性能型产物不得包含 IP、GEOIP、ASN、进程规则、订阅入口、代理节点 server 或逗号分隔规则。

### 2. DNS 优先级必须镜像路由优先级

三个性能配置按以下顺序选择 DNS：

1. 已启用的拒绝、代理与区域规则集合：海外 DoH。
2. 性能型中国 DNS 域名集合：DNSPod / AliDNS DoH。
3. 未分类域名：现有默认海外 DoH。

需要海外 DNS 例外的集合从配置自身实际启用的 rule-provider / RULE-SET 得出，而不是维护一份与配置脱节的手写总表。判断依据是公开规则 URL 的目录类别：`reject/`、`proxy/`、`region/`。只有在路由顺序位于中国大陆通用兜底之前的已启用集合才需要 DNS 例外。

DNS 例外必须位于性能型中国 DNS 条目之前。这样可以覆盖已经确认的真实重叠：GFW、阿里香港、WPS 香港、全球媒体、香港券商、加密货币台湾、OpenAI/AI 美国、Google 美国、Microsoft 美国与 macOS 更新美国等。

### 3. Surge Personal

`[Host]` 中：

- 保留代理节点 bootstrap 与现有专用解析入口。
- 为已启用的 `reject/`、`proxy/`、`region/` RULE-SET 保持或补齐海外 DoH 映射。
- 所有海外例外排在性能型中国 DNS DOMAIN-SET 之前。
- 用性能型中国 DNS 产物替换 Personal 对小型 `cn_dns_domains` 的通用国内解析引用。

`[Rule]` 中保持现有路由顺序、OpenAI 美国策略和全局性能型 `FINAL` 不变。

### 4. 两份 Mihomo

两份 Mihomo 新增同名 `cn-performance-dns-domains` rule-provider，使用性能型 DNS 文本产物，`behavior: domain`，并保持下载逻辑与现有公开 rule-provider 约定一致。

`dns.nameserver-policy` 按 YAML 顺序维护：

- 已启用的高优先级 `reject/`、`proxy/`、`region/` rule-set 使用与 `dns.nameserver` 相同的海外 DoH 数组。
- `rule-set:cn-performance-dns-domains` 使用 DNSPod / AliDNS DoH。

两份文件必须保持相同 DNS 结构。OpenAI / ChatGPT 的 `ai-us` 路由继续绑定美国策略，其 rule-set 同时作为海外 DNS 例外。默认 `nameserver` 继续只有海外 DoH；不启用 `fallback` 或 DNS 路由跟随。

### 5. 工作白名单隔离

`rulemesh-substore-surge-work-whitelist.conf`：

- 文件不得修改。
- 继续引用小型 `cn_dns_domains`，不得引用性能型产物。
- 继续保持 `FINAL,REJECT` 和现有显式白名单行为。

实施前后通过 Git blob ID、`git diff --exit-code -- <file>` 和语义检查三重确认零变化。公开性能检查器应拒绝工作白名单引用 `cn_performance_dns_domains`。

## 自动化检查

新增或扩展检查器，验证：

- 性能型 DNS 产物包含 Loyalsoldier 中国直连域名主体和人工国内 DNS 条目，规模不低于 10 万条。
- 每个性能配置实际启用且位于中国大陆兜底前的 `reject/`、`proxy/`、`region/` 集合，都存在对应海外 DNS 例外。
- 海外例外位于性能型中国 DNS 规则之前。
- OpenAI / `ai-us` 同时保持美国路由与海外 DNS。
- Surge Personal 与两份 Mihomo 使用性能型产物。
- 工作白名单不使用性能型产物，文件本身无变更。
- 两份 Mihomo 继续禁止 `respect-rules: true`、`fallback`、`direct-nameserver`、`proxy-server-nameserver` 及相关 policy 字段。

## 测试与运行时验证

测试驱动顺序：

1. 先为 DNS 源 `INCLUDE`、普通域名后缀化、去重、非法条目拒绝写失败测试。
2. 再为性能型产物规模、代表性上游域名、`yikaiying.com`、`zsxq.com` 写失败测试。
3. 再为三份性能配置的海外 DNS 例外覆盖与工作白名单隔离写失败测试。
4. 实现最小构建和配置变更，使测试转绿。

完成后必须：

- 运行 `tools/build_rules.ps1`，保持 0 warning。
- 运行 `tools/check.ps1`。
- 用官方稳定版 Mihomo 对两份真实私有配置执行隔离 `-t -d` 语法检查。
- 用不含私密数据的最小运行配置验证：代表性中国域名使用国内 DoH，`chatgpt.com` 使用海外 DoH。
- 对 Surge Personal 做 `[Host]` 与 `[Rule]` 顺序静态验证。
- 确认工作白名单 Git blob ID 未变化。
- 对公开与私有仓库执行 `git diff --check`、全仓残留搜索、提交、推送和 0/0 同步确认。

## 成功标准

- 三份性能配置不再让已进入中国直连域名主体的绝大多数域名先走海外 DNS。
- OpenAI / ChatGPT 固定美国出口与海外 DNS 不变。
- 区域特化和代理规则的 DNS 优先级高于宽泛中国集合。
- 工作白名单文件及其 DNS 行为完全不变。
- 新上游中国域名在下一次同步构建时自动进入性能型 DNS 产物，无需重复手工维护。
- 对完全未进入任何上游的新 `.com` 国内域名，继续使用人工高优先级覆盖；本次不通过全域双查询扩大 DNS 暴露面。
