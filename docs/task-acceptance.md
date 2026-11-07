# 任务收尾验收

每次任务结束前执行本轮收尾入口。入口先串行完成构建、全部回归、结构/DNS/路由/完整性检查和私人订阅在线闸门，再采集手机证据，最后确认六份私人源 SHA-256 未变化。报告包含本次运行 ID 与起止时间，不提供跳过基本检查或导入历史证据的参数。设备或控制器不可读即记录未验收并返回非零。

```powershell
.\.venv\Scripts\python.exe -B -X utf8 tools/check_task_acceptance.py --settings "$env:LOCALAPPDATA\RuleMesh\android-acceptance.json" --output "$env:LOCALAPPDATA\RuleMesh\airport-acceptance.json"
```

2026-11-07 起，六份私人配置取消美国链式代理，使用机场美国节点。当前结构见 [美国机场节点方案](us-airport-direct-20261107.md)；旧链式模块只兼容历史回归，不代表现行配置。

| 必检项目 | 通过条件 | 不能代替的证据 |
| --- | --- | --- |
| 基本检查 | 完整 check.ps1 和相关回归成功 | 只跑一个测试文件 |
| 订阅 | 两份清单一致；相同 UA、DIRECT 下载；正式 YAML 非空；无明确过期或耗尽 | 缓存、网页 200、未提供到期时间 |
| 运行节点 | 各 provider 已加载；alive=true；按可解析时间取最新 history，该条 delay>0 且在 max(2×实际 interval,600秒) 内 | 空、过旧、未来或不可解析的历史 |
| Wi-Fi VPN | 唯一活动 FlClash VPN，Wi-Fi 承载，无残留系统 HTTP 代理 | 保存的开关或仅有 VPN 图标 |
| 美国业务 | AI 候选为逐机场美国子组；子组只引用本 provider 美国节点；实际 AI trace 返回公网地址、US 地区及同请求的新连接字节 | 节点名称、旧固定购买 IP、测速 204、默认 DIRECT 的 IP 网站 |
| Google 香港 | 实际 Google 选择香港；移动 curl 首页与前台 Chrome 首页/搜索受信 HTTPS 200，有搜索框、无 google.cn 跳转 | 桌面 UA、/ncr Cookie、仅有 JS 提示的 HTML |
| DNS | 正常域名解析成功；唯一查询后 Google/AI 的 DoH 连接出现新返回字节，分别经过 Google 香港和 AI 美国机场子组 | 静态 policy、缓存命中、订阅下载成功 |
| 持久性 | 完整停止 VPN、结束 FlClash、重开并重新启动后复测；官方备份中当前 profile 与源文件逐字节一致 | 同名 profile、导入成功提示、临时控制器选择 |

保持用户指定的直连 Wi-Fi，不切移动数据掩盖失败。美国业务不再比较已撤销的固定 IP，不查询纯净度。Crypto 台湾、香港券商、日本入口、默认国内 DNS 与工作最终 REJECT 均保持。各平台静态通过不代表桌面、Mac 或 iPhone 已加载；账号、消息、媒体等业务按任务范围另验。国内 DoH 内部直连若未实测出口，仍标记未验收。

Chrome 通过唯一调试页面禁用测试缓存，验证当前文档、证书与 DOM，并在 finally 恢复缓存。冷启动时仅对连接建立做有界等待，不重放已执行的浏览器导航。UI 变化或动画可能使控件树不可读；点击必须先核对前台包、控件身份和可见边界，并等待目标页面出现。不能把一次 Back 当作已返回目标页。备份文件名必须验证输入已提交且为精确 ASCII；输入法改写时保留应用生成的默认名，保存前确认不存在同名文件，再从新文件集合确认导出成功。仪表盘包含出口 IP，截图必须在工具输出前遮蔽地址及其他私人字段，不能直接展示整页。

## 本机设置

设置必须位于公开仓库外，不提交密钥或本机路径：

```json
{
  "device_python": "C:/path/to/python.exe",
  "usb_api_directory": "C:/path/to/explicit/AdbWinApi-directory",
  "controller": {"port": 9090, "secret": "PRIVATE"},
  "exit_identity_policy": "airport-region-observation",
  "required_transport": "wifi"
}
```

常规 ADB 可将 usb_api_directory 替换为 adb 的真实路径。只选择一种传输；不猜设备、端口或密钥。直接 USB 使用 tools/android_usb_transport.py，Python 与 AdbWinApi 必须同位数，设备脚本明确使用设置中的 device_python。依赖持久放在 %LocalAppData%/RuleMesh/android-adb，沿用已有 adbkey，不重置密钥或网络。USB 操作由同一互斥串行执行，只重试建立连接，不重放已执行操作。

导入与测试准备阶段由操作者在 FlClash 界面临时启用回环控制器；验收器只读取已启用的控制器，不自动启用、不猜端口。端口和密钥从当前生成配置或官方备份获取，重新导入后重新核对；401 即停止依赖探测，不能关闭鉴权绕过。测试只读观测业务路由，测试前后选择必须相同。结束关闭临时控制器，另导出官方备份核对配置和设置。原始正文、连接、IP 和凭据只在内存解析，报告仅保存脱敏证据。

历史香港隔离继续由私人登记与 provider 精确排除保护，运行态确认已排除节点不在实际 provider 中。超时不能冒充已证实跳转，少量节点样本不能推断整家质量。检查器回归保留短连接、旧返回字节、空 provider、错误地区及缺少 Wi-Fi 的负例。
