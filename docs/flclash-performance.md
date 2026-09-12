# FlClash 客户端与性能基线

2026-09-12 用户批准一次完成迁移和优化。桌面与安卓统一使用 FlClash，Mihomo 是协议内核名称；不得把节点订阅协商所需的 `clash.meta` User-Agent 改成产品名。

## 文件与接入

- 桌面：`rulemesh-substore-mihomo-flclash-desktop.yaml`。
- 安卓：`rulemesh-substore-mihomo-flclash-android.yaml`。
- 两份文件位于独立私人仓库根目录；同步脚本与公开检查使用新文件名。文件级分享链接也必须切换到新文件名。
- Windows 已核实 FlClash 0.8.97，数据目录为 `%APPDATA%/com.follow/clash`。配置元数据在 `database.sqlite`，选中项与界面覆写在 `shared_preferences.json`，导入原文在 `profiles/<id>.yaml`；根目录 `config.yaml` 是生成结果，不是编辑入口。
- 默认保持标准覆写模式、DNS 覆写关闭、最终策略不单独覆写；导入本仓库规则与组。界面补丁的 `find-process-mode` 应为 `strict`，IPv6 关闭、TCP 并发开启。不得只改导入文件而忽略界面补丁。
- 桌面配置文件已生成不代表安卓已加载。安卓导入或更新后必须单独核对实际运行配置及 VPN/DNS 接管；本机未连接安卓时，不宣称已完成手机运行验证。

## 规则加载

完整 `cn_direct` 和 `gfw` 资产继续维护。日常通用配置末尾固定为以下三项，顺序不可变，中间不得插入其他规则：

1. `direct/cn_direct_light` → DIRECT。
2. `proxy/gfw_precise` → 全地区自动组。
3. FINAL / MATCH → DIRECT。

`gfw_precise` 只包含具体 GFW 域名与 `decodo.com` 主域及子域，不再包含 829 个顶级域泛匹配或任意位置的 decodo 关键词。`cn_direct_light` 由完整直连表与精确代理表自动推导，只移除最终仍会 DIRECT 的域名；保留双向域名重叠和全部既有 IP/GEOIP 规则。当前从 120,809 条减至 9,755 条，后续数量随上游变化。

构建在 `tools/build_rules.ps1` 内自动执行推导，输出仍只有既有三条产物线。若代理表出现关键词、通配或 IP 等新语法，推导必须失败，不能猜测等价。测试覆盖所有当前源域名的根域与子域，以及 IP 规则完整保留。

工作白名单不接入这组新兜底，继续 FINAL,REJECT。AI 美国、Crypto 台湾、其他地区约束、国内精选直连、ips5 直连及 AdsPower 停用均保持。Surge 机场手动组继续保留。

## 测速与连接

- 桌面 provider 与自动组间隔 300 秒；安卓为 600 秒。订阅下载周期仍为 21,600 秒，规则下载周期保持原配置。
- 实际承担流量的自动组保持 `lazy: false`；仅供手动备用的地区组使用 `lazy: true`。provider 保持主动检测。使用 provider 节点时，不能把 provider 数和组数相加推断实际重复请求次数。
- 美国切换容差 100、全地区 50 保留。所有机场和有效节点仍可手动选择；单次短测不能证明晚高峰质量，不能据此永久删除节点或只留下少数节点。
- `find-process-mode: strict` 保留按需进程识别；不能设为 off，因为前置 Google 等规则内含进程条件。
- TUN 的 mixed 已对 TCP 使用系统栈。system 与 mixed 的取舍主要需评估 UDP；没有可比吞吐证据时保留 mixed，不把改字段当成实测性能提升。
- 国内普通 DNS 与 AI 专用美国 DoH 分开验证。UDP DNS 测试可能被 TUN 劫持并命中缓存；只有确认实际出口、冷缓存和正确回应后，才能据此更换传输。AI DoH 的美国代理参数不变。

## 复测与恢复

迁移前保存私人配置、FlClash 选中 profile、数据库备份与 preferences 到私人任务目录。先发布新规则集，再更新客户端，验证 AI/地区/国内/最终兜底与实际 DNS 路径。桌面重载允许短暂重连，不调整操作系统电源。

恢复时按功能恢复对应配置和 AppData 备份；工作文件不得被通用备份覆盖。动态测速候选、真实节点名、订阅地址、数据库和控制器秘密不得进入公开仓库。

经验：FlClash 的内核可通过它自己的 IPC `validateConfig` 检查 YAML；真正的代理语义需继续执行隔离 `setupConfig` 或客户端加载。隔离内核的文件 provider 缓存必须复制到其专用 home 下，否则路径限制会让加载失败。REST 接口未暴露 provider 节点导致的 404 不能记为节点不通，独立测试应使用匿名显式节点或客户端原生测速接口。

参考：[FlClash 源码](https://github.com/chen08209/FlClash)、[Mihomo 策略组](https://wiki.metacubex.one/config/proxy-groups/)、[TUN](https://wiki.metacubex.one/config/inbound/tun/)、[DNS](https://wiki.metacubex.one/config/dns/)。
