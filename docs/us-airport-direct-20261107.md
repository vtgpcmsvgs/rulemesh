# 美国机场节点方案（2026-11-07）

用户撤销六份私人配置的美国 SOCKS5 链式出口。美国业务直接使用机场节点，取消固定购买 IP 身份对比。公开模板已有机场方案，不添加私人资产。

AI 在 Mihomo/iOS 中使用 select，在 Surge 中继续使用 url-test；候选均为美国-724、美国-kuibenvpn 等逐机场 url-test 子组。低调机场显示美国-didiao，实际 provider id 保持 diidao。每个子组只绑定一个现有机场并过滤美国节点，排除套餐占位项，容差 100；桌面/Surge 300 秒，安卓/iOS 600 秒，实际业务子组主动检测。AI 不提供 DIRECT。Microsoft 共享这些子组并追加 DIRECT；Store 与普通六地区菜单使用美国机场地区自动组。

删除本地 SOCKS5 节点、单成员 load-balance、美国线路入口、六个地区接入组、dialer-proxy/underlying-proxy、专用 UDP 拒绝和 x-rulemesh-us-chain 登记。不得仅移除登记来绕过静态检查；六份私人配置必须通过机场方案闸门，链式模块只保留历史夹具兼容。

本次出口例外保持：Crypto 台湾、香港券商香港、Google/YouTube/Telegram/Apple/Notion 的既有香港及六地区候选、日本精确入口、国内直连与工作最终 REJECT。DNS 继续默认国内、AI 跟随 AI、安卓 Google/YouTube 各自跟随业务组。

手机保持用户指定的直连 Wi-Fi。导入后核对源字节、重启持久性、唯一 FlClash VPN 无系统 HTTP 代理、实际 AI 美国机场节点和新的连接返回字节、Google 普通首页/搜索与 DoH 出口。订阅下载、静态规则和设备验收分开；缺 Chrome、控制器或 Wi-Fi 证据必须标记未验收，不切移动网络掩盖失败。

设备设置使用 exit_identity_policy: airport-region-observation 和 required_transport: wifi；不查询 IP 纯净度，不要求旧固定 IP。check_us_airport.py 保护当前配置；既有 DNS、业务顺序、配额和有效期闸门继续执行。

2026-11-07 本轮记录：完整检查 425 项回归及全部订阅在线闸门通过。六份配置已完成结构检查，DNS、订阅、非美国业务组及业务规则与变更前一致。安卓在用户指定的直连 Wi-Fi 下确认唯一 FlClash VPN、无系统 HTTP 代理、七个机场美国子组和近期存活历史；AI 业务观测到美国实际出口与新返回字节，普通香港机场路径也观测到香港出口。移动 Google 初次线路发生 google.cn 跳转，改在客户端保存另一条香港线路后，普通移动首页受信 HTTPS 200、搜索框存在且无跳转；保留初次失败，不据此扩大 provider 隔离。冷启动后手动选择保留，官方备份与最终源文件逐字节一致。Google 香港和 AI 美国的 DoH 均观察到新返回字节；国内 DoH 的实际出口未独立验收。

这台手机缺少 Chrome，本轮完整设备验收仍返回失败，不能声称浏览器首页/真实搜索或完整业务均已通过。采集器在 Chrome 不可用时继续保留独立 DNS 与美国出口证据，整体仍失败；相关负例已纳入回归。配置迁移插入标记后须检查文件尾，避免追加空行；保留未修改行既有换行并执行 git diff --check。
