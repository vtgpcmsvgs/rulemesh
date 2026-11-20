# AdsPower 桌面统一 SOCKS5 上游

2026-11-20 用户授权仅为私人 FlClash 桌面配置增加统一上游入口，所有浏览器环境通过 AdsPower 的全局设置共用它。2026-10-23 删除的 AdsPower 域名、进程规则、专用 provider 和 DNS 资产继续保持删除；本次不恢复这些资产，也不逐个登记环境代理服务器。

## 配置与接入

私人 `rulemesh-flclash-desktop.yaml` 增加以下脱敏结构，其中 `通用自动组` 必须换成该文件实际 `RULE-SET,proxy_gfw` 引用的既有机场自动组：

```yaml
listeners:
  - name: adspower-upstream
    type: socks
    listen: 127.0.0.1
    port: 7898
    proxy: 通用自动组
```

Mihomo 的 SOCKS5 入站类型写作 `socks`，不要写成出站节点类型 `socks5`。`proxy` 直接指定出站组，进入该监听器的连接不再使用普通目的地规则决定 DIRECT；该组必须使用现有机场 provider，不能包含 DIRECT。监听地址仅为回环，不向局域网开放。普通系统代理、TUN、业务规则、地区例外、DNS 和末尾 MATCH,DIRECT 保留原有配置。

在 AdsPower「个人设置 → 本地设置」开启「使用系统代理连接代理」，将配置方式设为「手动配置 SOCKS」，地址为 `127.0.0.1`、端口为 `7898`，保存设置。它是 AdsPower 全局上游，不需要修改每个环境原有的 HTTP/SOCKS 代理地址、账号或密码。已打开的环境需关闭后重新打开，让新连接采用保存后的上游设置。

路径为：AdsPower → 本机 SOCKS5 7898 → 机场自动组 → 环境配置的远程代理 → 目标网站。系统代理检测通常显示机场出口 IP 和地区；浏览器中的最终 IP 通常仍属于环境配置的远程代理。没有配置远程代理的环境、不同代理协议及 UDP 行为另行实测，不能由单次 IP 检测推断所有环境均已接管。

这套手动全局设置与 Windows 系统代理自动检测分开；Windows 的普通代理端口继续按 FlClash 当前设置使用。AdsPower 的「自动检测系统代理」得到规则分流入口时，即使已成功接入，也可能因为某个检测目标命中 DIRECT 而显示本地公网 IP。

## 验证与维护

- 静态检查保护监听地址、SOCKS 类型、端口及实际自动组引用；拒绝恢复旧域名、进程、provider 或 DNS 入口。
- iOS 派生器先校验该桌面监听器，再剥离整个监听节；安卓、iOS、Surge 与公开通用模板不增加该入口。
- 构建使用 `tools/build_rules.ps1`，完整检查使用 `tools/check.ps1`，包括在线订阅闸门。配置文件构建成功和客户端实际加载分开报告。
- 独立语法检查使用官方 Mihomo CLI 的 `-t -d <任务专用临时目录> -f <配置文件>`。FlClash 自带 `FlClashCore.exe` 是 IPC 服务入口，不支持标准 CLI 的 `-t`、`-v` 或 `--help`，不能用它替代原生校验器。
- DNS 默认国内双 DoH 与 AI 专用海外解析基线保持；客户端导入后检查实际 DNS、系统代理检测及至少两个不同环境的完整代理链。HTTP 204、节点名称或静态检查不能代替这些验收。

本轮用户选择自行导入和测试。交付时不重载客户端，不修改其应用数据或系统代理；如没有设备验收，应明确报告未验收。

## 本次纠正

检测显示相同 IP 只证明检测请求出口相同，不能直接判定 AdsPower 没有读取系统代理。逐个为远程代理端点补规则可以改变分流，但不满足用户要求的全局统一上游。应先核对应用支持的全局代理方式，再提供固定出站的本机入口，并用专门检查保护其作用范围。

参考：[AdsPower 系统代理配置](https://help.adspower.com/docs/Network-Diagnostics-System-Proxy-Supports-Customization)、[Mihomo 入站配置](https://wiki.metacubex.one/en/config/inbound/)。
