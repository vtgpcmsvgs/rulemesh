# 任务收尾验收

本仓库每次任务结束前执行一次本轮收尾入口。单元测试保护检查器行为，真实订阅和手机探测验证当前状态；两者缺一不可。设备或控制器不可读时记录未验收并返回非零，不能用上次报告、节点名称、204 测速或静态 YAML 替代。

```powershell
.\.venv\Scripts\python.exe tools/check_task_acceptance.py --settings "$env:LOCALAPPDATA\RuleMesh\android-acceptance.json" --output "$env:TEMP\rulemesh-acceptance.json"
```

入口先串行运行完整 `tools/check.ps1`，其中包括构建、结构/DNS/路由/完整性、全部回归与私人订阅在线闸门。完整退出后，才采集设备证据；不与构建并发读取产物。最后检查六份私人源的 SHA-256 未在验收期间变化。报告携带本次运行 ID 和起止时间，不提供跳过基本检查或导入旧证据的参数。

| 必检项目 | 通过条件 | 不能代替的证据 |
| --- | --- | --- |
| 基本检查 | 完整 check.ps1 成功；对应源码与检查器回归成功 | 只跑一个测试文件 |
| 订阅 | 两份清单一致；相同 UA、DIRECT 下载；有效非空 Clash YAML；无明确过期或流量耗尽 | 旧缓存或网页 200 |
| 运行节点 | 设备当前 provider 非空，至少一个 alive 且最新有效延迟在实际检查周期内 | alive=true 但历史为空、过旧 |
| Google | 活动唯一 FlClash VPN 无残留系统 HTTP 代理；实际 Google 选择香港；移动首页及手机 Chrome 实际首页/搜索为未缓存受信 HTTPS 200、Google.com 搜索框 | 桌面 UA、204、/ncr Cookie、仅有 JS 启用提示的 HTML |
| DNS | 正常域名解析成功；唯一测试查询后，Google/AI 的 DoH 活动连接出现新返回字节，链分别经过 Google 香港与 AI 美国组 | 只看 nameserver-policy 或查询命中缓存 |
| 区域链式出口 | 验证唯一美国链式出口，经实际 AI trace；必须获得实际公网 IP、地区及同请求的新连接字节；测试前后策略配置一致 | 查 IP 网站默认 DIRECT、前置机场 IP、端口能连 |
| IP 身份 | 用户明确授权信任登记的单个美国 IP；核对实际地区和 IP；登记身份不能补足缺失的观测 | 不运行纯净度检测，也不生成风险评分 |

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

控制器由操作者在 FlClash 中临时启用，确认实际回环端口与当前密钥后填入设置；测试不会自动启用或猜测控制器。诊断完成关闭控制器并核对官方备份。重新导入或再次启用控制器后，必须从当前界面重新读取密钥并验证鉴权，不能假定上次保存值仍有效；旧设置返回 401 时停止依赖探测，不能关闭鉴权绕过。出口测试只读观测实际 AI 路由，验证唯一美国落地的 IP、地区与新连接字节；不对 LoadBalance 发 PUT/DELETE。未观测到出口、链未命中或前后选择变化都明确未验收。香港按普通机场路径验移动首页/搜索与 DNS，不再要求匹配已撤销的香港购买 IP。

沿用不检测纯净度约定，设置使用 `exit_identity_policy: user-provided-trusted`。六份源配置静态检查与设备验收分开；Windows 桌面、macOS Surge、iOS 的运行态另报，安卓入口通过也不能证明其他设备已加载。


## 六份私人配置单美国链式结构

2026-10-31 当前修订：全部六份私人配置统一单个美国 SOCKS5 落地；香港业务使用普通机场线路，撤销此前两个 Comcast 与一个 Lumen 方案。美国仅显示一个 `美国线路入口`，按香港、台湾、新加坡、日本、美国、韩国的顺序选择 `经香港接入`、`经台湾接入`、`经新加坡接入`、`经日本接入`、`经美国接入`、`经韩国接入`，默认香港。六个辅助组隐藏且仅从全部机场 provider 中自动选择对应地区节点；切换接入地区不改变最终美国 IP，不复用业务地区组。美国最终组仍隐藏，不创建 `RM-HK-Front`。美国没有多节点负载均衡；Mihomo 保留单成员 load-balance 防止 TCP-only UDP 跳过规则，Surge 使用 underlying-proxy 与 UDP REJECT。登记升级为 `x-rulemesh-us-chain` 版本 6（front-mode: regional-airport-select），真实端点和认证仅在私人仓库。

Mihomo 美国最终组显式 hidden: true，仅包含 RM-US-Exit；AI/Microsoft 的代理候选只引用它，Microsoft 保留 DIRECT。Surge 美国最终组为隐藏的单成员 select，AI 自动组复用该组。唯一可见前置 `美国线路入口` 必须按约定顺序包含六个隐藏地区入口，且当前选择属于其中之一。运行态须逐个核对六个 URLTest 的完整候选与当前选择：候选非空、全部来自实际 provider 节点集合、全部具有对应地区标签。未知节点、错地区标签、业务组、DIRECT、最终出口、入口间递归，以及旧 RM-US-Front 或前置组残留均失败。前置香港与业务香港组分离；改名后必须确认客户端实际加载新配置并重新保存地区选择。

安卓香港恢复可见 select，保留全部 provider 和历史精确隔离；其余客户端香港保持自动机场选择。香港券商恢复香港-provider 子组。源文件静态通过后仍须在界面核对加载的当前 profile、完整成员和保存选择。工作白名单最终 REJECT 不变。

线路删除依据单独校验：私人 `x-rulemesh-android-provider-quarantine` 登记 provider、精确名称、原因和受信跳转证据；provider 排除表达式须与登记完全一致，不得宽匹配或用超时冒充跳转。报告区分历史样本与本轮复测；同一 provider 的通过样本不能被省略，不能把少量香港样本推断为整家质量。

SOCKS5 最终出口暂按 TCP 能力配置 `udp: false`，不向客户端虚报 UDP 支持。因此新的美国链不承诺 UDP/QUIC；香港使用原机场能力；既有无全局 UDP 拒绝规则保持，但 Google/Cronet 的 TCP 回退与语音视频需实机验证。不得把“规则未拒绝 QUIC”写成“SOCKS5 已支持 QUIC”。前置健康不代表它能连接最终 SOCKS5，必须测试完整链路并在客户端保存已验证的前置选择。


2026-10-24 运行态复核补充：provider 的 exclude-filter 先于 override.additional-prefix / additional-suffix 生效，必须把界面显示名称还原为订阅原始名称后精确匹配，再从设备 provider 列表确认消失；正式 YAML 正则与文本检查器的反斜杠层级须分别校验。五出口探测在请求进行中采样活动连接并验证新返回字节，结束后连接消失不能被误判为业务链未命中；原始连接与出口 IP 只留在内存。对应负例覆盖名称前后缀和短连接，失败轮次保留。
