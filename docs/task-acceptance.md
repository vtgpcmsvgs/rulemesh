# 任务收尾验收

本仓库每次任务结束前执行一次本轮收尾入口。单元测试保护检查器行为，真实订阅和手机探测验证当前状态；两者缺一不可。设备或控制器不可读时记录未验收并返回非零，不能用上次报告、节点名称、204 测速或静态 YAML 替代。

```powershell
.\.venv\Scripts\python.exe tools/check_task_acceptance.py --settings "$env:LOCALAPPDATA\RuleMesh\android-acceptance.json" --output "$env:TEMP\rulemesh-acceptance.json"
```

入口先串行运行完整 `tools/check.ps1`，其中包括构建、结构/DNS/路由/完整性、全部回归与私人订阅在线闸门。完整退出后，才采集设备证据；不与构建并发读取产物。最后检查两份私人源的 SHA-256 未在验收期间变化。报告携带本次运行 ID 和起止时间，不提供跳过基本检查或导入旧证据的参数。

| 必检项目 | 通过条件 | 不能代替的证据 |
| --- | --- | --- |
| 基本检查 | 完整 check.ps1 成功；对应源码与检查器回归成功 | 只跑一个测试文件 |
| 订阅 | 两份清单一致；相同 UA、DIRECT 下载；有效非空 Clash YAML；无明确过期或流量耗尽 | 旧缓存或网页 200 |
| 运行节点 | 设备当前 provider 非空，至少一个 alive 且最新有效延迟在实际检查周期内 | alive=true 但历史为空、过旧 |
| Google | 活动唯一 FlClash VPN 无残留系统 HTTP 代理；实际 Google 选择香港；移动首页及手机 Chrome 实际首页/搜索为未缓存受信 HTTPS 200、Google.com 搜索框 | 桌面 UA、204、/ncr Cookie、仅有 JS 启用提示的 HTML |
| DNS | 正常域名解析成功；唯一测试查询后，Google/AI 的 DoH 活动连接出现新返回字节，链分别经过 Google 香港与 AI 美国组 | 只看 nameserver-policy 或查询命中缓存 |
| 美国五出口 | 逐一通过实际 AI 域名读取公网出口；选中与活动节点相符；连接链含指定落地和 AI；结束恢复测试前 fixed 状态 | 查 IP 网站默认 DIRECT、前置机场 IP、端口能连 |
| IP 身份 | 用户明确授权信任给定五 IP；本轮验证五个实际美国出口和链路 | 不运行纯净度检测，也不生成风险评分 |

入口同时执行移动 curl 首页和前台 Chrome 首页/真实搜索：Chrome 在执行 JS 后核对最终域名、路径、搜索框、当前文档响应和证书，并在 finally 恢复缓存。Chrome 调试页面须唯一，无法唯一定位则失败。完整配置导入、VPN 或客户端行为变更后，还须完整重启客户端与核对官方备份和源文件一致性；Wi-Fi 与移动数据分别报告。实际应用的账号、消息、媒体和大文件业务按本次变更范围另行验收。

重复发布同名源时，导入提示不替代字节校验；出现旧组型时用唯一辅助文件名导入并登记媒体索引，最终确认当前选中 profile 的源字节。冷启动后 Chrome 调试服务存在就绪窗口，检查器只对建立连接做有界等待，不重放已经执行的浏览器导航。

## 本机设置

设置文件必须位于公开仓库外，不提交控制器密钥或本机运行时路径。示意字段：

```json
{
  "device_python": "C:/path/to/python.exe",
  "usb_api_directory": "C:/path/to/explicit/AdbWinApi-directory",
  "controller": {"port": 9090, "secret": "PRIVATE"},
  "exit_identity_policy": "user-provided-trusted"
}
```

常规 ADB 可将 `usb_api_directory` 替换为 `adb` 的真实路径。只能选择一个传输，不猜测设备或端口。直接 USB 后备使用 `tools/android_usb_transport.py`，Python 与 AdbWinApi 必须同位数；依赖持久放在 `%LocalAppData%/RuleMesh/android-adb`，不依赖临时任务目录。使用已有 `.android/adbkey`，不重置密钥或系统网络。所有 USB 操作由同一互斥串行执行；只重试建立连接，不重放已执行的操作。

控制器由操作者在 FlClash 中临时启用，确认实际回环端口与当前密钥后填入设置；测试不会自动启用或猜测控制器。诊断完成关闭控制器并核对官方备份。密钥改变后旧设置应失败，需要重新读取，不能关闭鉴权绕过。测试五出口时会短暂切换美国组，不切换 Google 香港；在 finally 中恢复原 fixed 状态，原先自动则调用内核 DELETE 取消固定。若设备断开或进程被强制终止导致恢复未确认，整体失败，必须核对并恢复后才能收尾。

用户于 2026-10-24 明确取消纯净度检测，无条件信任其提供的五 IP。设置使用 `exit_identity_policy: user-provided-trusted`；不查询风险数据库，不将出口 IP 发送到第三方风险服务。美国地区和完整链路仍逐个实测。

## 安卓美国链式例外

2026-10-24 用户重新明确授权：仅私人安卓配置使用五条 SOCKS5 最终落地，前置为机场手动选择组。普通 Google 默认香港及已知故障节点隔离继续生效。AI、Microsoft 的美国代理候选与美国地区组接入五出口；Microsoft 的既有 DIRECT 选项保留。其他客户端不改变，旧 AWS/链式 IP 规则资产不恢复。

同日冷启动复测发现香港 url-test 的 fixed 不能阻止健康失败后的回退；私人安卓共享香港地区组最终改为可见 select，保留历史组名兼容，移除组级测速字段并保存实测线路。共享该香港选择的业务同时固定；其他五地区仍自动测速。验收检查运行时组型与保存选择，禁止将临时测速失败后的陌生节点当作已验证香港出口。

五个落地节点通过 Mihomo `dialer-proxy` 拨号前置机场；前置只引用机场 provider，使用 select 固定已验证线路；204 健康状态不能触发自动回退。前置不能引用五出口或美国业务组形成环。私人 `x-rulemesh-android-us-chain` 登记明确结构，检查器拒绝额外出口、缺失认证、错端口、DIRECT 拨号、机场最终落地回退和跨客户端扩散。源文件不能静态证明真实出口地区，因此仍需设备探测。

SOCKS5 最终出口暂按 TCP 能力配置 `udp: false`，不向客户端虚报 UDP 支持。普通 Google 香港继续保留 QUIC；美国候选或美国应用的 UDP 能力需供应商协议支持与独立实测后才能启用。前置健康不代表它能连接最终 SOCKS5，必须测试完整链路并在客户端保存已验证的前置选择。
