# 2026-09-16 出口修订与防误伤

本修订按业务目的保留地区出口，并收敛无必要的代理和解析绕行。它优先于较早文档中 WPS/Store 自动择优、Surge 阿里设备代理和 AI 激进关键词的描述。

| 业务 | 当前原则 | 边界 |
| --- | --- | --- |
| 海外 AI | 美国出口及独立海外解析 | 只匹配审核过的产品域名和租户入口；不按子串、共享云根域或 IP/ASN 扩围 |
| WPS / 金山文档 | 香港出口 | 用于公开文档地区展示；保留既有 WPS 业务范围及默认国内 DNS |
| Microsoft Store | 美国出口 | 用于美国地区应用下载的 IP 条件；通用 Microsoft（含中国业务）保留代理，不改为直连 |
| Crypto、日本入口、香港券商 | 保留既定地区 | 精确例外优先，不能被全地区测速组替代 |
| 国内 DNS / 新华三 | 紧随 AI 的精选直连 | 只覆盖 `cn_services_direct` 明确列出的域名与自举地址 |
| 爱思 / Apple | 保持既有业务直连，DNS 改用国内默认 | 删除 Personal 遗留海外 Host 项；不扩展工作配置的 Apple/爱思权限 |
| 阿里日常业务 | 取消强制代理 | Surge 同时撤销阿里设备条件和整设备代理；工作白名单中未明确放行的请求仍 REJECT |

WPS 香港和 Store 美国是用户明确的业务例外，不能因为目标在国内或使用 `.cn` 域名就改直连。IP 出口本身不保证平台地区展示、账户地区或商店资格立即改变；对应业务状态要另行验收。

## 规则与 DNS

AI 旧规则的 `xai` 会匹配 `gxairlines.com`、`auxair.com`，`poe`、`suno` 等也会匹配无关域名；上游 OpenAI/Gemini/Copilot 还会重新带入关键词、共享云与 IP/ASN。现在保持上游原始快照供审核，但不直接整包 INCLUDE；`ai_us` 仅用 DOMAIN/DOMAIN-SUFFIX，按平台保留真实服务及已确认的租户入口。`www.bing.com` 是 Copilot 与普通搜索共用的明确主机例外，仍使用美国；不扩大整个 Bing。

国内 DNS 保护不能只验证后面“存在 DIRECT”。七份配置的第二条有效规则统一为 `cn_services_direct,DIRECT`，早于 Google IP、设备、拒绝与其他代理。Surge 移除 DOH/DOH3/DOQ 通用代理规则，海外解析器继续按已登记主机/IP 分流；工作模式未放行的未知解析器仍 REJECT。

普通默认国内双 DoH、节点国内 bootstrap、AI 美国解析、安卓 Google 独立稳定出口和解析、GitHub Raw 专项解析均保留。没有为 WPS 或 Store 新增海外 DNS 镜像。

两份 Personal 保持路由和 DNS 一致；工作白名单仍独立。Store 在公开模板和 Personal 保留原有优先顺序；新增到工作与两份 FlClash 时放在既有更新拒绝后、通用 Microsoft 前，避免以地区修订解除更新禁令。

## 防复发与验收

`test_scoped_egress.py` 同时检查真实产品正例、名称相似反例、共享平台反例、DNS 前置遮蔽和地区出口漂移。`check_common_routes.py` 增加本次反例、国内 DNS、新华三、WPS 与 Store 样本；性能检查验证真实地区过滤条件、国内服务第二条、停用阿里与设备广谱、允许的海外 Host 例外。

静态检查不提供真实目的 IP 或运行态，不能替代客户端验收。部署时要分别比较源文件、选中 profile、生成配置与实际加载结果，避免只更新私人仓库却仍使用旧缓存。

排错经验：补丁出现同文件 Delete/Add 或缺失锚点时，先确认未落盘，再改为唯一锚点/原子替换。PowerShell 不展开传给 rg 的路径通配符，须使用真实目录和 `--glob`；命令失败不能由后续成功掩盖。上述经验已同步到 AGENTS.md。

首次全量检查还发现旧回归断言仍要求 WPS 自动择优、新华三留在代理清单。已按新的业务目的更新断言，并保留“新华三必须在直连清单”和实际香港出口检查；测试不能继续固化已被用户修订的策略。

手机运行验收进一步发现：Store 原生目录和授权接口已经绑定美国，网页入口 `apps.microsoft.com` 却遗漏在专项清单外，命中了通用 Microsoft。现以精确 DOMAIN 补齐，并同时检查网页、原生目录、授权接口与 Microsoft 根域反例；不能仅凭代表性 API 已走美国就认定整个商店入口都一致。

桌面浏览器验收发现：`notebooklm.google` 已重定向到 Gemini Notebook 的 `notebook.google`，页面产品入口为 `notebook.google.com`。两者补入 AI 的 DOMAIN-SUFFIX 清单，让新入口继续使用美国出口和 AI 专用 DNS；不扩大 Google 根域。正例、伪后缀反例、Mihomo 常用业务首条命中与七份配置的 AI 优先检查覆盖这次变更。以后验收产品入口时应同时检查重定向目标，旧域名规则正确不代表最终页面仍采用同一策略。完整方法与未通过项见[桌面实测](flclash-desktop-validation-20260916.md)。
