# Clash Mi iOS 专用配置

使用私人仓库的 `rulemesh-substore-mihomo-clashmi-ios.yaml`。它以桌面版为业务基线，适配 iOS；不要直接导入安卓版本，后者包含 Google Play 和券商应用包名规则。

## 差异与维护边界

- 保留机场来源、地区过滤器、业务选择组、规则顺序、既有更新拒绝和最终 `MATCH,DIRECT`。AI 美国、Crypto 台湾、日本入口、香港券商的地区边界保持。
- 默认国内 AliDNS / DNSPod 双 DoH，只有 AI 使用绑定 AI 组的海外 DoH；节点 bootstrap 仍为国内双 DoH。保留 IPv4、fake-ip、ARC 和 TCP 并发。安卓 YouTube / Google DNS 专项不迁入。
- 关闭进程匹配；移除桌面 `tun` 与 `dns.listen`，VPN 隧道由 Clash Mi 管理。共享规则集里的进程条件不作为 iOS 路由保障，业务靠域名和 IP 匹配。
- 机场健康检查与自动组采用 600 秒周期；业务组主动检测、备用地区按需检测。机场后台下载保留 DIRECT 与原 User-Agent，规则下载保留现有出站。
- 官方 FAQ 明确 iOS 不支持 ASN 数据库。阿里云 SSH 规则保留精确 TCP/22 网段，派生为内联 classical provider，去除该集合与主规则中的 ASN 兜底。此内联快照随派生器更新；它不会在手机端独立远程刷新。其他规则继续使用现有三条产物线，GeoIP 上游登记保持。
- iOS 不支持的 ASN 例外不扩散到桌面、安卓或 Surge。现有文件保持原样。

## 导入与应用设置

1. 将专用 YAML 私下传到 iPhone 的“文件”，在 Clash Mi 添加配置时选择从文件导入。不要公开包含真实订阅的 YAML；GitHub 私人仓库网页地址不能直接当作匿名订阅地址。
2. 使用规则模式。在核心设置中保留 **TUN 覆写、启用**，协议栈使用应用提供的 **gVisor**，开启 DNS 劫持。iOS 的 Network Extension 由应用建立，不复制桌面 auto-detect-interface / strict-route。
3. 关闭 **DNS 覆写**、配置的 **规则覆写**与**代理组覆写**，不叠加额外自定义规则模板。可以保留 App 覆写并逐项关闭 DNS；不要把 TUN 一并关闭。以当前版本显示的最终运行配置为准。
4. 默认关闭“附加 HTTP 代理到 VPN”，保留 IPv6 关闭。停止并重新连接 VPN，让设置生效。
5. 检查机场 provider 下载、节点列表与业务选择。文件导入属于快照，未来更新需重新导入；如果改用私有分享 URL，应自行确认 iPhone 可访问并保护链接。

## 验收与限制

静态检查涵盖派生一致性、DNS policy、地区业务组、常用目的地首条命中及引用。验收还需要 iPhone 的 Clash Mi 版本、最终运行配置与实际网络，不能把桌面 Mihomo `-t` 等同于 Clash Mi 内核或 iOS 已通过。

连接后验证国内业务直连、AI 美国出口、Crypto 台湾与券商香港；同时核对普通业务 DNS 使用国内双 DoH、AI DNS 通过 AI 所选美国组、节点域名使用国内 bootstrap。仅网页可打开不证明 DNS 出口正确。再测试锁屏后恢复、Wi-Fi / 蜂窝切换与原有应用业务。

官方 FAQ 说明 iOS VPN 扩展存在约 50 MB 内存上限，并建议减少大规则/使用 MRS。本版保留现有业务规则，尚未在用户 iPhone 验证内存与持续连接；没有承诺一定低于上限。当前检查不增加新的 MRS 产物线。若连接立刻断开，应查看设备错误/内存记录，再决定是否缩减规则或节点；不能只凭节点测速成功判断配置可用。

## 派生与检查

派生器只用 Python 标准库；本机默认 Python 和 bundled Python 均不保证有 PyYAML，不能把它作为维护脚本的隐式依赖。先完成规则构建，再从私人桌面配置派生，最后检查：

```powershell
powershell -ExecutionPolicy Bypass -File tools/build_rules.ps1
& "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe" -B -X utf8 tools/derive_clashmi_profile.py
powershell -ExecutionPolicy Bypass -File tools/check.ps1
```

默认解析 `rulemesh-local/current`，不存在时使用私人仓库根目录；可显式传 `--private-root`。派生器只写 iOS 文件，不修改桌面或安卓。桌面业务、订阅同步块或规则构建资产变更后重新派生；`tools/check.ps1` 会拒绝已存在但过期的 iOS 文件。未部署 iOS 文件的机器可以跳过派生检查。

遇到格式变化、重复字段、新增未经审核的进程/ASN 规则应停止派生并更新适配逻辑。头部与正文的性能/业务标记统一保留一次，有回归测试防止重复。

FlClash 的 `FlClashCore.exe` 是应用通信服务入口，不是标准 Mihomo CLI，不能向它传 `-v` / `-t`；独立核心语法检查须使用确认支持这些参数的官方 Mihomo CLI，并使用任务临时目录。

参考（核对于 2026-10-05）：[Clash Mi 官方 FAQ](https://clashmi.app/guide/faq)、[官方源码的 iOS 覆写与 TUN 行为](https://github.com/KaringX/clashmi/blob/07bd273b7d0e7caa900903e389438fc76a54392f/lib/app/modules/clash_setting_manager.dart)。官网和源码可能比手机 App Store 版本新，因此最终仍需核对本机行为。
