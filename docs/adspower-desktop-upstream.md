# AdsPower 桌面统一 SOCKS5 上游

2026-11-21 用户授权将私人桌面 `127.0.0.1:7898` 固定到 `666clouds` 单节点 VLESS TCP Reality 中继，替代 2026-11-20 的机场自动组方案。此处日期和固定出口是维护约束：以后不得因机场菜单同步、美国出口迁移或“统一配置”恢复自动组或扩散到其他客户端。

## 固定结构与作用范围

仅私人 `rulemesh-flclash-desktop.yaml` 保存实际连接参数；公开仓库只登记结构。以下为脱敏示意，不能直接导入：

```yaml
# AdsPower desktop upstream: SOCKS5 7898
socks-port: 7898
allow-lan: false
proxy-providers:
  # >>> RULEMESH_DESKTOP_666CLOUDS_PROVIDER
  666clouds:
    type: inline
    payload:
      - name: 666clouds-relay
        type: vless
        server: <私有地址>
        port: <私有端口>
        uuid: <私有身份>
        network: tcp
        tls: true
        servername: <SNI>
        client-fingerprint: chrome
        udp: true
        reality-opts:
          public-key: <Reality公钥>
          short-id: <短ID字符串>
  # <<< RULEMESH_DESKTOP_666CLOUDS_PROVIDER
proxy-groups:
  # >>> RULEMESH_DESKTOP_666CLOUDS_GROUP
  - name: 666clouds
    type: select
    hidden: true
    use:
      - 666clouds
  # <<< RULEMESH_DESKTOP_666CLOUDS_GROUP
rules:
  - IN-PORT,7898,666clouds
  # 下方原有业务规则顺序保持，AI 仍为第一条业务规则。
```

复用 FlClash 已设置的 SOCKS5 7898，不新建同端口 `listeners`。第一条有效 `IN-PORT` 匹配代理入站端口，让通过 7898 接入的连接固定使用单一中继；不包含 DIRECT、机场候选或自动回退。中继故障时应报告故障。普通系统代理/TUN 入站继续按原有业务规则分流。

“隐式”通过 `hidden: true` 策略组与独立 inline provider 实现：节点不放入顶层 `proxies`，不加入任何机场/地区/业务菜单。隐藏组是客户端展示提示，不是保密或权限机制；provider 管理页、控制器仍可能看到已加载节点。不得使用 `include-all` 等方式把它重新混入普通组。

`666clouds` 是用户命名的本地静态 provider，没有订阅 URL、更新下载或机场健康检查。本仓库的机场订阅清单比对、业务逐机场覆盖和美国机场检查，只排除经过完整桌面入口校验的这一项；其他 HTTP 订阅继续逐项 DIRECT 下载检查，任意其他 inline provider 不获得豁免。此前检查器把全部 provider 都视为机场，新增本地中继会误报业务候选遗漏；现已用窄范围验证及回归覆盖这一边界。

## 接入与 DNS

在 AdsPower「个人设置 → 本地设置」开启「使用系统代理连接代理」，选择「手动配置 SOCKS」，地址 `127.0.0.1`，端口 `7898`，保存后关闭并重新打开环境以建立新连接。全局上游只设置一次，无需逐个登记环境远程代理地址和规则。

路径为：AdsPower → 本机 SOCKS5 7898 → 666clouds 中继 → 环境配置的远程代理 → 目标网站。系统代理检测预期显示中继的出口 IP/地区；浏览器最终 IP 通常仍是环境远程代理的出口。检测不保证显示配置中的节点名称。未配置远程代理的环境、不同协议和 UDP 另行实测，不能由一次 IP 检测推断全部环境已经接管。

Windows 的普通系统代理端口保持原用途。AdsPower 使用全局手动 SOCKS 接入 7898；自动检测到其他规则分流入口时，检测请求仍可能命中 DIRECT。

用户连接信息附带 `dns=8.8.8.8`，但 Mihomo VLESS 节点没有这种节点级 `dns` 配置语义。本次保留该信息为备注，不新增无效字段，也不把普通 DNS 全局切到 Google：中继 server 是 IP，无服务器域名 bootstrap；SNI 是 TLS 身份，不需要为了连接该 IP 额外解析。若 AdsPower 将域名直接交给远程代理，最终解析由相应远端实现；若先在本地解析，则继续使用当前国内双 DoH/AI 专用解析基线。配置文件不能证明远端已使用 8.8.8.8，指定远端解析器需要另行维护相应服务端。

原始 URI 的 fragment 中含 SSH 管理信息，它不是 VLESS 参数，严禁复制到配置、注释、日志、文档或测试。TCP、Reality、SNI、指纹及身份采用 Mihomo 原生字段；未指定额外 flow。URI 的 `encryption=none` 使用 VLESS 默认无额外加密语义，`spx` 不伪造为 Mihomo 未支持的节点字段。

## 验证与维护

- 静态检查保护端口唯一、本机访问、首条固定出口、单节点、隐藏组及业务隔离；旧 AdsPower 域名、进程和 DNS 专用规则仍不得恢复。
- inline provider 与隐藏组使用唯一成对标记。iOS 派生前先验证完整桌面结构，再精确剥离这两块、SOCKS 端口与 IN-PORT；标记越界或吞掉其他内容直接失败。安卓、iOS、Surge 和公开通用模板不新增入口或节点。
- 文件头入口说明放在原头部后，保留性能基线标记位于前三行。
- 构建入口 `tools/build_rules.ps1`；完整检查 `tools/check.ps1`，含在线订阅闸门。原生语法校验使用官方 Mihomo CLI 的 `-t -d <任务专用临时目录> -f <配置文件>`。FlClashCore.exe 是 IPC 服务入口，不支持这些标准 CLI 参数。
- 更换此中继时只修改私人桌面 provider 的身份/连接参数；固定目标名、端口、隐藏及隔离约束保留。改变设计应同步配置备注、本页、AGENTS、检查器和测试，再确认其他配置未改变。
- 构建/语法通过与运行验收分开。用户自行导入测试；检查系统代理出口、至少两个不同环境的完整链路及 DNS 实际出口。节点名称、HTTP 204 和静态检查不能替代链路/DNS 验收。

## 2026-11-21 连接修复记录

现象：AdsPower 显示未检测到系统代理，FlClash 日志却已记录 `InPort/7898 → 666clouds`，随后拨号超时。该证据说明本机 SOCKS 接入及规则已命中，不能据此恢复逐个代理端点规则，也不能把 TCP 超时直接归为 Reality 认证失败。

服务端核对发现：用户新提供的管理服务器上 Xray 正常运行，代理端口对公网监听，UUID 与 SNI 匹配；桌面配置的 server、Reality 公钥和 short-id 则仍属于旧连接信息。修复仅将这三个字段与当前 Xray 入站对齐，没有修改正常运行的服务器服务或防火墙。服务器 Reality 私钥只用于内存中派生公钥并比对，SSH 密码与私钥均不写入仓库或日志。

验证使用无 TUN、无系统代理覆写、无订阅的独立 Mihomo 临时进程，仅监听随机本机 SOCKS 端口，结束后关闭。修正参数后 HTTP/HTTPS 均成功，出口匹配用户指定服务器，三个 AdsPower 检测域名 `check.myclientip.com`、`check.adspower.com`、`ip-scan.adspower.net` 均返回 HTTP 200。首轮个别检测请求曾超时，服务端 DNS/TCP/HTTPS 与随后重试均成功，保留为该轮探测限制，不解释为永久封锁。服务器系统解析器包含 Google 与 Cloudflare DNS；未验证每次实际选择哪一个，不声称专用使用 8.8.8.8。本次没有操作 FlClash 导入界面或 AdsPower 环境，因此应用验收仍由用户执行。

防复发：更换服务器、重装代理或重新生成 Reality 密钥后，必须从同一个当前入站同时核对 server、公钥、short-id、UUID、SNI 与 flow；不只更新 IP，也不从历史 URI 的 SSH fragment 推断当前代理身份。TCP 监听、普通进程的 TCP 可达和原生 `-t` 只覆盖各自阶段，不能证明整条链可用。没有日志时先核对客户端日志采集开关与级别，再重现；空日志不证明请求未进入代理。

参考：[AdsPower 系统代理配置](https://help.adspower.com/docs/Network-Diagnostics-System-Proxy-Supports-Customization)、[Mihomo 入站](https://wiki.metacubex.one/en/config/inbound/)、[inline provider](https://wiki.metacubex.one/en/config/proxy-providers/)、[策略组 hidden](https://wiki.metacubex.one/en/config/proxy-groups/)、[VLESS](https://wiki.metacubex.one/en/config/proxies/vless/)。
