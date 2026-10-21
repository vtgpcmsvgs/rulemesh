# AI 中转站分类与域名边界

核对日期：2026-10-12。用户另行指定的 `easyapis.cc`、`ccapi.us` 已加入 `region/multi/ai_relay`；官网分别标注 AI API Gateway、AI API 中转站。

两张截图共 59 个平台条目。本次将其中 51 个第三方中转或模型聚合网关纳入中转规则，包含此前已收录的 6 个；其余 8 个按目前证据属于原生平台、模型社区或推理/算力服务，不作为中转站加入。新增官网、API 与备用主机共 53 条规则，含 OpenRouter 从美国规则迁入；中转规则合计 79 条。

这里的中转包括转发其他厂商 API、汇聚多个上游模型并统一路由/计费的网关。单纯提供 OpenAI/Anthropic 兼容协议，或在工具中被标为 aggregator，不能证明它转发其他厂商 API。目录只用于核对候选及实际请求主机；是否属于纯推理平台仍需结合官网、模型目录和产品性质判断。收录不代表服务质量、价格、模型真实性或可用性认证。

## CC Switch 赞助页补充（2026-10-21）

核对用户指定的 [CC Switch 中文赞助页](https://ccswitch.io/zh/sponsors)及其公开赞助数据，并与当前 [Claude](https://github.com/farion1231/cc-switch/blob/main/src/config/claudeProviderPresets.ts)、[Codex](https://github.com/farion1231/cc-switch/blob/main/src/config/codexProviderPresets.ts)、[Gemini](https://github.com/farion1231/cc-switch/blob/main/src/config/geminiProviderPresets.ts) 预设交叉确认。原有服务不重复登记，本次补充 11 条官网/API/备用域名规则，中转规则从上次的 79 条增至 90 条。

| 服务 | 新增域名或主机 | 依据与本次访问限制 |
| --- | --- | --- |
| AIGoCode | `aigocode.net`，精确 `api.aigocode.dev` | 赞助页链接新官网；官网 HTTP 200，预设确认 `.dev` 实际 API 和已覆盖的 `api.aigocode.app` 备用入口；`.dev` 本次连接失败，仅登记确认的 API 主机 |
| ClaudeCN | `claudecn.ai` | 赞助页当前链接及预设注册入口；官网 HTTP 200，提供 Claude/GPT/Gemini 等模型，保留既有 `.top` API |
| GrooRoute Pro | `grooroute.pro`、`grooroute.xyz` | 赞助页明确写 AI API 中转；官网 HTTP 200，预设确认 `.xyz` 备用 API，本次备用入口连接失败 |
| SudoCode.us | `sudocode.us`、`sudocode.run` | 赞助页描述 Claude/Codex/Gemini 接入及 `.run` 备用地址，三类预设一致；本次两入口 HTTP 451，未据此声称可用或与 `.chat` 合并 |
| XycAi | `xyc.ai` | 赞助页说明官方域名；三类预设确认 `apicdn.xyc.ai`，与既有 `apicdn.xycai.us` 并存；本次根域连接失败 |
| EveryAPI | `everyapi.ai` | 官网 HTTP 200，提供多厂商模型统一 API；赞助页使用 `app.everyapi.ai` 控制台，预设确认 `api.everyapi.ai` 和 `api-cn.everyapi.ai` |
| AllTokens / AllTokens SI | `alltokens.cc`、`alltokens.si` | 两官网均 HTTP 200，个人及企业多模型中转；赞助说明和三类预设均确认官网/API 共用主机 |

赞助类别不直接决定收录：胜算云虽标为 native-platform，具体说明有第三方模型聚合，沿用既有规则；Kimi、PPIO、火山方舟、硅基流动、优云智算、七牛云仍属本规则排除范围；new-api 的 `newapi.ai` 是开源基础设施项目官网，未证明该官网运营托管中转服务，不因 aggregator 标签而加入。CC Switch 本身的 `ccswitch.io` 也不作为中转域名。

新增域名均沿用全地区自动选择和默认国内 DNS，检查实际私有配置中的调用、目标组及 DNS 遮蔽。私人配置已通过远程规则引用关联本规则，无需重复内联新域名；iOS 仍从桌面版和当前构建资产重新派生核对。静态通过与设备更新资源、真实 DNS/出口及模型调用验收分别报告。

## 收录的截图条目

表内主域默认使用 `DOMAIN-SUFFIX`；“精确”表示只匹配列出的主机。官网证据为本次读取的公开页面标题、描述或产品文档；[CC Switch 公开预设](https://github.com/farion1231/cc-switch/blob/main/src/config/claudeProviderPresets.ts)用于交叉核对官网、API 地址和第三方模型接入配置，不自动整包导入。

| 截图平台 | 收录域名或主机 | 依据与备注 |
| --- | --- | --- |
| 88API | `88api.ai` | [官网](https://88api.ai/)明确写 AI API 中转、Claude/GPT/Gemini 统一接入；与 `88code.org` 不同 |
| 9527CODE | `9527.codes` | [官网](https://9527.codes/)明确写企业级 AI 中转与模型聚合 |
| A6API | `a6api.com` | [官网](https://a6api.com/)写多商家供货渠道、统一 API 调度与比价 |
| AICodeMirror | `aicodemirror.ai` | [官网](https://www.aicodemirror.ai/)提供 Claude Code、Codex 等共享接入与计费 |
| AICodeWith | `aicodewith.ai` | [官网](https://aicodewith.ai/zh)提供多模型统一接入、预付费额度与统一计费 |
| AICoding | `aicoding.inc` | 公开预设登记第三方 `api.aicoding.inc`；官网返回 HTTP 451，未取得官网正文 |
| AIGoCode | `aigocode.app` | 公开预设登记第三方 `api.aigocode.app`；官网本次 TLS 连接失败 |
| AiHubMix | `aihubmix.com` | 公开预设登记 Anthropic API 接入及 `api.aihubmix.com`；官网/文档本次 TLS 连接失败 |
| Amux | `amux.ai` | [官网](https://amux.ai/)写一个 API、多个模型供应商与自动故障转移 |
| APIKEY.FUN | `apikey.fan` | [官网](https://apikey.fan/)标题为 APIKEY.FAN AI 中转；截图品牌写 FUN，仅收录实际域名 FAN |
| APINebula | `apinebula.ai` | [官网](https://apinebula.ai/)描述多模型聚合与协议转换；原规则已覆盖 |
| AtlasCloud | 精确 `atlascloud.ai`、`www.atlascloud.ai`、`api.atlascloud.ai` | [官网](https://www.atlascloud.ai/)列出 GPT Image、Gemini 等第三方模型；[文档](https://www.atlascloud.ai/docs)明确为 API 聚合平台，仅登记网站/API 主机 |
| BotCF | `botcf.com` | [官网](https://botcf.com/)描述 AI 模型聚合与分发网关 |
| CCSub | `ccsub.net` | [官网](https://www.ccsub.net/zh)明确写 Claude Code 中转、多个厂商模型统一接入 |
| CherryIN | 精确 `open.cherryin.ai`、`open.cherryin.net` | [官网入口](https://open.cherryin.ai/)描述模型聚合网关；公开预设确认 Claude 接入及备用主机 |
| ClaudeAPI | `apito.ai` | [官网](https://apito.ai/)明确写 Anthropic API 国内代理 |
| ClaudeCN | `claudecn.top` | [官网](https://claudecn.top/)明确写 Claude API 中转及多厂商 API |
| Code0 | `code0.ai` | [官网](https://code0.ai/zh)提供一个 Key 接入多个厂商模型、统一计费及路由 |
| CrazyRouter | `crazyrouter.com` | [公开文档](https://crazyrouter.com/docs)介绍 API 接入与路由；预设登记第三方 `cn.crazyrouter.com`，主页首次返回 HTTP 403 |
| Cubence | `cubence.com` | 原公开评测规则已覆盖；公开预设交叉登记，官网本次 TLS 连接失败 |
| DMXAPI | `dmxapi.cn` | [官网](https://dmxapi.cn/)明确写 API 聚合中转，支持 OpenAI/Claude/Gemini 等 |
| E-FlowCode | `e-flowcode.cc` | [官网](https://e-flowcode.cc/)为 API 网关；公开预设登记第三方 Anthropic 接入 |
| FennoAI | 精确 `api.fenno.ai` | [官网入口](https://api.fenno.ai/)明确写路由 GPT、Claude 等模型并统一额度/账单 |
| FluxA Token Plan | 精确 `agentmarket.fluxapay.xyz` | [模型市场](https://agentmarket.fluxapay.xyz/)展示第三方模型统一接口和按量计费；不扩大到支付母域或千帆原生 API |
| IKunCode | `ikuncode.ai` | 公开预设登记 `api.ikuncode.ai` 和原 `.cc` 备用入口；API 根页返回 HTTP 401，保留原 `ikuncode.cc` |
| JieKou AI | `jiekou.ai` | 公开预设登记 `/anthropic`、`/openai/v1` 及 Claude 模型；官网/文档本次 TLS 连接失败 |
| Micu | `micuapi.ai` | [官网](https://micuapi.ai/)为模型 API 网关；原规则已覆盖 |
| OpenCode Go | 精确 `opencode.ai` | [Go](https://opencode.ai/go)页面列出 Claude、GPT 等模型，[Zen](https://opencode.ai/zen)为第三方模型精选接入；两者共用主机，域名规则无法区分 URL 路径 |
| OpenModel | `openmodel.ai` | [官网](https://openmodel.ai/)明确为托管多模型网关，提供路由、重试、日志与统一计费 |
| OpenRouter | `openrouter.ai` | [公开文档](https://openrouter.ai/docs/quickstart)说明统一 API 和供应商路由；从 `ai_us` 迁入，解除美国规则及 DNS 遮蔽 |
| PackyCode | `packyapi.ai` | [官网](https://packyapi.ai/)明确为全球模型 API 聚合平台；原规则已覆盖 |
| PatewayAI | `pateway.ai` | [官网](https://pateway.ai/)明确为 Claude/Codex API 中转与代理接入 |
| PIPELLM | 精确 `code.pipellm.ai`、`cc-api.pipellm.ai` | [网站](https://code.pipellm.ai/)与公开预设交叉核对；预设登记 Claude 模型及实际请求主机 |
| RelaxyCode | `relaxycode.com` | 公开预设登记第三方 Anthropic 接口；官网根域证书过期，www 入口返回 HTTP 400，未关闭 TLS 验证 |
| RightCode | `rightapi.ai` | [官网](https://rightapi.ai/)说明统一 Claude Code、Codex 等接入；原规则已覆盖 |
| RunAPI | `runapi.host` | [官网](https://runapi.host/)明确写多模型聚合及供应商智能路由 |
| RunToken | `runtoken.ai` | [官网](https://runtoken.ai/)为模型 API 网关；公开预设登记 Anthropic 接入 |
| 胜算云 | `shengsuanyun.com` | [官网](https://www.shengsuanyun.com/)说明全球模型接入与企业网关；公开预设登记 Claude 和 `router.shengsuanyun.com` |
| SoleAPI | `soleapi.com` | [官网](https://soleapi.com/)明确写一个 Key 使用 Claude/GPT/Gemini，自动路由与故障转移 |
| SoruxGPT | 精确 `ai.soruxgpt.com` | [官网入口](https://ai.soruxgpt.com/)描述模型聚合与分发网关 |
| Soshow | 精确 `aimarket.so-show.com`、`maas.so-show.com` | [模型市场](https://aimarket.so-show.com/)与公开预设交叉确认 Claude 及实际 API；API 根页 HTTP 404 不等于接口路径无效 |
| SSSAiCode | `sssaicodeapi.com`，另精确 `node-hk.sssaiapi.com` | [官网](https://sssaicodeapi.com/)明确为独立第三方网关；公开预设确认备用 API，不替换原 `sssaicode.com` |
| SubRouter | `subrouter.ai` | [官网](https://subrouter.ai/)明确写 GPT/Claude/Gemini 多厂商网关 |
| SudoCode | `sudocode.chat` | 用户此前明确指定且原规则已覆盖；本次官网响应不完整，未据此删除原规则 |
| 兔子 API | 精确 `api.tu-zi.com` | [官网入口](https://api.tu-zi.com/)说明全球模型 API 聚合 |
| TeamoRouter | `teamorouter.cn` | [官网](https://teamorouter.cn/)描述 Claude Code、Codex 统一 API Key 和计费；页面标题为 DeepSeek，不以标题单独判断 |
| TheRouter | `therouter.ai` | [官网](https://therouter.ai/)提供跨供应商路由、故障转移、计费与治理 |
| TokenFlux | `tokenflux.dev` | [官网](https://tokenflux.dev/)标题明确为 AI API Gateway；公开预设确认 Anthropic 接入 |
| XycAi | `xycai.us` | [官网](https://xycai.us/)明确为中转站，一个 API 接入多个厂商模型 |
| YYLX | `yylx.io` | [官网](https://yylx.io/)明确为 Claude/GPT/Gemini 中转与按量计费网关 |
| ZetaAPI | `zetaapi.ai` | 公开预设登记第三方 `api.zetaapi.ai`；官网本次 TLS 连接失败 |

## 本次不作为中转站收录

| 截图条目 | 域名 | 本次分类依据 |
| --- | --- | --- |
| Gemini Native | `ai.google.dev` | [Google 原生模型 API](https://ai.google.dev/)，保持既有 `ai_us` 美国及专用 DNS |
| Nvidia | `build.nvidia.com` | [NVIDIA NIM 原生推理入口](https://build.nvidia.com/)，不是第三方 Claude/GPT 中转 |
| ModelScope | `modelscope.cn` | [开源模型社区](https://modelscope.cn/)，提供模型、数据集和在线服务 |
| Novita AI | `novita.ai` | [LLM 目录](https://novita.ai/models/llm)明确为开源模型推理，OpenAI 项是 GPT OSS；[模型文档](https://docs.novita.ai/guides/model-apis-overview.md)及预设主要为托管模型、GPU 与沙箱，兼容协议不足以确认为闭源模型中转 |
| PPIO | `ppio.com` | [官网模型产品](https://ppio.com/model-api)强调自有推理引擎与自定义模型托管 |
| 七牛云 | `s.qiniu.com` | 该主机是[云厂商官网](https://www.qiniu.com/)的跳转入口；AI 推理与音视频/存储共用厂商品牌，不扩大云母域 |
| SiliconFlow | `siliconflow.cn` | [公开模型目录](https://siliconflow.cn/models)及预设主要是国内/开源模型推理与 MaaS，不因 Anthropic 兼容而归为 Claude 中转 |
| 优云智算 | `compshare.cn` | [官网](https://compshare.cn/)与[模型 API](https://www.compshare.cn/model-api)强调 GPU 云和自有推理能力；不扩大云根域或 `modelverse.cn` |

以上仅是本次中转规则的范围判断，不替这些平台另行指定新出口，也不否定未来可能新增的转发产品。后续若官方文档证明存在第三方模型转发，应按具体产品/API 主机重新核实。

## 路由、DNS 与同步边界

- OpenRouter 从 `ai_us` 删除后，既有 Surge `[Host]` 和 Mihomo `rule-set:us_ai` DNS policy 随规则资产收敛，不再对它使用 AI 美国专项；中转规则沿用默认国内 DNS。
- 中转入口在既有规则位置使用全地区自动选择。源规则和构建产物均只包含显式域名，没有关键词、IP/ASN 或共享云根域。
- 诊断须从规则解析实际目标组及其类型：现有 Surge 全地区入口是直接节点 `smart`，Mihomo 是 `url-test`，不能把某一客户端的类型断言套用到另一客户端；固定地区业务的嵌套子组约束仍按各自基线检查。
- 公开模板、三份私人 Surge、桌面/安卓/iOS Mihomo 已有中转规则引用。新增域名由远程规则资源承接，配置本身没有新增引用需求；设备需成功更新资源后才使用新内容。
- 单元测试保护中转与美国规则互斥、官网/API 正例、共享母域及官方/推理平台负例；常用路由数据补充新入口的 TCP/UDP 首条命中用例。
- 官网访问和公开目录能支持域名归属分类，不能替代设备上的实际 DNS、出口、认证请求与模型调用验收。TLS/HTTP 限制已逐项注明，没有关闭 TLS 校验或使用私人 API Key。
