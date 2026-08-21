# 四份私有配置性能优先改造设计

## 背景与结论

当前三份通用配置把未命中流量送往美国出口，两份 Mihomo 配置还让普通域名统一使用海外 DNS。该结构有利于维持美国网络身份，但会让国内 `.com` 业务出现跨境解析或跨境转发，并让普通国际流量失去就近选路机会。

只读诊断确认：

- `zsxq.com` 已被 `direct/cn_direct` 覆盖，但没有进入 `dns/cn_dns_domains`，因此存在“流量直连、DNS 仍绕海外”的分裂。
- `yikaiying.com` 未命中公开直连规则，也未进入国内 DNS 白名单；三份通用配置会把它送入美国兜底，工作白名单配置会拒绝它。
- 两份 Mihomo 配置虽然注册了 `cn_dns_domains` 规则提供器，但没有通过 `nameserver-policy` 使用它。
- Clash Verge 版的 provider 与自动测速组使用 `interval: 900`、`lazy: true`；链路劣化后，测速状态可能比 Meta 版更陈旧。
- 当前 Windows 主机没有运行 Surge 或 Mihomo。无配置客户端参与的三次 ChatGPT 直连基线中，一次 TLS 建连约为 10 秒，另外两次约为 0.2 秒，说明国际偶发卡顿不能只归因于 DNS，也需要改善出口选择的新鲜度。

## 目标

1. 国内明确业务域名优先使用国内 DNS 并直连，避免跨境解析和跨境转发。
2. 普通国际流量从“固定美国兜底”调整为“全地区低延迟自动选择”。
3. OpenAI、ChatGPT 与现有美国专项规则继续固定美国出口。
4. 缩短 Mihomo 健康状态的陈旧窗口，提高链路劣化后的切换速度。
5. 保持 DNS 防泄漏边界：只有显式登记在 `cn_dns_domains` 的国内业务域名可使用国内 DNS。
6. 保持工作白名单配置的 `FINAL,REJECT`，不恢复广谱放行。

## 非目标

- 不把所有 `cn_direct` 域名机械交给国内 DNS。
- 不恢复 Mihomo 的 `respect-rules: true`、`proxy-server-nameserver`、`direct-nameserver` 或 `fallback`。
- 不改变 OpenAI、ChatGPT、Google 等已有专项区域规则的策略含义。
- 不把 Surge 的复杂 DNS 结构复制到 Mihomo。
- 不新增或恢复多地区链式 SOCKS5 入口。

## 方案比较

### 方案 A：显式 DNS 白名单 + 性能兜底（采用）

把已确认的国内业务域名加入 `cn_dns_domains`，两份 Mihomo 仅对该规则集启用 `nameserver-policy`；通用国际 FINAL/MATCH 改为现有全地区自动选择组；OpenAI 继续美国出口；Verge 健康检查与 Meta 对齐到 300 秒主动检测。

优点是国内外性能都能改善，DNS 泄漏边界仍可审计，且不需要引入新的策略组。代价是新的国内 `.com` 业务仍需显式登记。

### 方案 B：只补两个域名，保留美国兜底

只处理 `zsxq.com` 与 `yikaiying.com`，不改变通用 FINAL/MATCH。风险最低，但普通国际网站仍被固定送往美国，不能满足“性能优先”的核心目标。

### 方案 C：让全部国内直连规则使用国内 DNS

让 `cn_direct` 或宽泛 geosite 集合直接驱动国内 DNS。维护成本最低，但会扩大国内 DNS 可见范围，也可能让误分类或上游漂移影响普通目标网站，违反本仓库的 DNS 安全边界，因此不采用。

## 规则与 DNS 数据流

### 国内明确业务域名

```text
目标域名
  -> 命中 cn_dns_domains
  -> Surge [Host] / Mihomo nameserver-policy 选择国内加密 DNS
  -> 命中明确直连入口或 cn_direct
  -> DIRECT
```

- `zsxq.com`：加入 `cn_dns_domains`；继续复用现有 `cn_direct` 流量规则。
- `yikaiying.com`：加入 `cn_dns_domains`，并加入 `cn_direct` 的本地显式兜底。
- 工作白名单配置不接入宽泛 `cn_direct`，只增加上述两个精确后缀的显式 DIRECT 入口。

### OpenAI 与 ChatGPT

```text
OpenAI / ChatGPT 域名
  -> 先命中现有 ai_us 专项规则
  -> 美国自动选择组
  -> 不进入通用 MATCH / FINAL
```

美国组保留地区过滤，只调整 Mihomo 的检测新鲜度与切换阻尼，不允许香港、日本或台湾节点进入 OpenAI 出口。

### 普通国际流量

```text
未命中专项规则的国际域名
  -> Surge personal FINAL / Mihomo MATCH
  -> 现有全地区自动选择组
  -> 从当前可用节点中择快
```

工作白名单配置不走该路径，仍然 `FINAL,REJECT`。

## 文件级设计

### 公开仓库

- `rules/dns/cn_dns_domains.list`
  - 按国内知识服务与明确自有站点分组加入 `.zsxq.com`、`.yikaiying.com`。
- `rules/direct/cn_direct.list`
  - 仅增加 `DOMAIN-SUFFIX,yikaiying.com` 本地兜底；不重复加入上游已经覆盖的 `zsxq.com`。
- `dist/surge/dns/cn_dns_domains.list`、`dist/surge/rules/direct/cn_direct.list`、`dist/mihomo/classical/direct/cn_direct.yaml`
  - 只由 `tools/build_rules.ps1` 重建，不手工编辑。
- 相关测试与检查脚本
  - 先增加能够复现“国内业务 DNS 清单未被 Mihomo 实际消费”和“性能优先兜底仍指向美国”的失败检查，再修改配置。
- 文档
  - 更新 DNS 方法论、Surge/Mihomo 使用说明和工作白名单说明，明确“显式国内 DNS 白名单、普通国际性能兜底、OpenAI 固定美国”的新边界。

### 私有仓库

- `rulemesh-substore-surge-personal.conf`
  - 保留 `[Host]` 的 `cn_dns_domains -> 国内 DNS` 映射。
  - 将 `FINAL` 从美国自动选择组改为现有全地区自动选择组。
  - OpenAI 的美国专项规则保持原顺序和策略。
- `rulemesh-substore-surge-work-whitelist.conf`
  - 为 `zsxq.com`、`yikaiying.com` 增加精确 DIRECT 入口。
  - 保持 `FINAL,REJECT`，不接入 `cn_direct`、`proxy/gfw` 或通用国际兜底。
- `rulemesh-substore-mihomo-clash-verge.yaml`
  - 增加仅针对 `rule-set:cn_dns_domains` 的 `nameserver-policy`，复用现有国内加密 DNS。
  - 保持 `respect-rules: false`、`use-hosts: false`、`use-system-hosts: false`。
  - 保持 `proxy-server-nameserver`、`direct-nameserver`、`fallback` 缺失。
  - 将 `MATCH` 从美国自动选择组改为现有全地区自动选择组。
  - provider 与自动测速组统一为 `interval: 300`、`lazy: false`。
  - 全地区自动组保留较低切换阻尼；美国组降低过高阻尼，但仍避免相近节点频繁变更出口。
- `rulemesh-substore-mihomo-clash-meta.yaml`
  - 应用相同 DNS 策略和 MATCH 变更。
  - 保持现有 `interval: 300`、`lazy: false`，只同步美国组阻尼调整。
- `README.md` 与私有 `AGENTS.md`
  - 记录新默认语义与回滚边界，不记录订阅地址、节点名、策略名或密钥。

## Mihomo DNS 恢复门槛

`nameserver-policy` 曾被列为需要明确批准和运行时复测的高风险字段。本设计把用户对本规格的批准视为字段级明确授权，但实际写入后必须完成以下闭环才可提交：

1. 使用官方 Mihomo 可执行文件和任务专用临时目录执行 `-t -d`，不得把缓存写入用户主目录。
2. 临时启动经过端口隔离的配置副本，确认配置能够进入运行态。
3. 对 `zsxq.com`、`yikaiying.com` 和一个普通国际对照域名执行 DNS 查询；只输出命中角色、耗时与结果一致性，不输出节点、订阅或控制器密钥。
4. 确认国内目标命中 `cn_dns_domains`，普通国际对照域名不命中国内 DNS。
5. 若无法取得官方运行时或行为证据不符合预期，回退 `nameserver-policy` 变更，不以静态语法通过替代运行时复测。

## 测试与验证

### 修改前失败检查

- 验证 `zsxq.com` 与 `yikaiying.com` 尚未同时具备国内 DNS 调度。
- 验证三份通用配置的兜底仍指向美国组。
- 验证 Verge 的健康检查仍为 900 秒惰性模式。

### 修改后检查

- 运行 `tools/build_rules.ps1`，构建 warning 必须为 0。
- 运行 `tools/check.ps1`，包含 DNS 安全检查与变更联动闸门。
- 检查 `dist/` 仍只有 `surge/rules`、`surge/dns`、`mihomo/classical` 三条产物线。
- 对四份私有配置运行脱敏结构审计，确认：
  - OpenAI 仍命中美国组；
  - Surge personal 与两份 Mihomo 的通用兜底命中全地区自动组；
  - 工作白名单仍为 `FINAL,REJECT`；
  - 国内 DNS 只由 `cn_dns_domains` 驱动；
  - 两份 Mihomo 机场 provider 继续显式 `proxy: DIRECT`；
  - 两份 Mihomo 的健康检查 URL 继续使用既有 HTTPS Google 204 地址。
- 执行 Mihomo 运行时 DNS 复测和目标网站请求时延采样；Surge 因当前 Windows 环境无运行时，只做配置语义审计，并在交付中明确该限制。
- 两个仓库均运行 `git diff --check`、全仓同类问题搜索和 `git status`。

## 回滚

- 公开规则回滚：移除新增 DNS 后缀和 `yikaiying.com` 直连兜底后重建。
- Mihomo DNS 回滚：只移除新增 `nameserver-policy`，保留当前单一海外 DNS 结构。
- 通用国际兜底回滚：将 Surge personal `FINAL` 与两份 Mihomo `MATCH` 恢复为美国自动选择组。
- 健康检查回滚：Verge 恢复 900 秒惰性检测，美国组恢复原阻尼。
- 工作白名单回滚：移除两个新增精确 DIRECT 入口，`FINAL,REJECT` 始终不变。

