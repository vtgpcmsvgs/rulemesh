# RuleMesh

这个仓库现在按“一份源规则，多端产物输出”的思路维护：

- `rules/` 是源规则层，只放你自己审阅后的规则素材与维护元数据
- `dist/` 是构建产物层，客户端只引用这里
- `Surge` 使用 `dist/surge/rules/`
- `Clash Verge Rev` 与 `Clash Meta for Android` 使用 `dist/mihomo/classical/`

这样做的目标是把“怎么维护规则”与“客户端怎么接入规则”分开，避免客户端继续直接引用第三方上游仓库，也避免源规则和客户端格式绑死。

## 目录说明

```text
rules/
  reject/      # 拒绝类源规则
  direct/      # 直连类源规则
  proxy/       # 代理类源规则
  region/      # 区域策略类源规则
  upstream/    # 上游来源登记与未来合并模板

dist/
  surge/
    rules/     # Surge RULE-SET 使用的显式规则产物
  mihomo/
    classical/ # Mihomo 的 behavior: classical 使用的显式规则产物

tools/
  build_rules.ps1
  build_rules.py
```

说明：

- `rules/` 下参与构建的源规则文件统一使用 `.list` 命名
- 例如 `rules/region/tw/google_tw.list` 会生成 `dist/surge/rules/region/tw/google_tw.list` 与 `dist/mihomo/classical/region/tw/google_tw.yaml`
- `dist/build-report.json` 会记录每个源文件被识别为 `domain-only`、`ipcidr-only` 或 `classical/mixed`，以及构建警告
- 这些分类结果只用于维护诊断，不再对应额外的 `domainset` / `domain` / `ipcidr` 产物目录

## 如何构建

Windows 本地与 Codex 会话统一优先使用包装脚本：

```bash
powershell -ExecutionPolicy Bypass -File tools/build_rules.ps1
```

日常开发自检可直接运行：

```bash
powershell -ExecutionPolicy Bypass -File tools/check.ps1
```

这个脚本会串行执行构建、单元测试、`dist/` 目录结构校验、`dist/build-report.json` warning 校验，并在最后输出 `git status --short`。

CI 或其他非 Windows 环境如果已经确认本机 `python` 可用，也可以直接执行：

```bash
python tools/build_rules.py
```

构建脚本会：

- 从 `rules/` 读取源规则
- 自动生成 `dist/surge/rules/` 与 `dist/mihomo/classical/`
- 将纯域名规则规范化成显式规则行，例如 `.example.com` 会输出成 `DOMAIN-SUFFIX,example.com`
- 尝试识别 `domain-only`、`ipcidr-only`、`classical/mixed`
- 强制校验 `rules/{reject,direct,proxy,region}/` 中的自写注释为中文；若出现纯英文注释会直接失败
- 对不能安全转换到目标客户端格式的行输出 warning，而不是静默吞掉
- 保证重复执行结果一致

## 如何发布

最小发布流程：

1. 修改 `rules/` 源规则
2. 运行 `powershell -ExecutionPolicy Bypass -File tools/build_rules.ps1`
3. 检查 `dist/` 与 `dist/build-report.json`
4. 提交 `rules/`、`dist/`、文档与 CI 改动

仓库已新增最小 GitHub Actions 工作流：

- push 到 `main` 时会运行单元测试、重建 `dist/`，并校验已提交的 `rules/upstream` 与 `dist/` 是否和仓库源码一致
- `pull request` 到 `main` 时会校验单元测试、构建流程，以及 `rules/upstream` 与 `dist/` 是否已经提交最新结果
- 每天 `09:30 Asia/Shanghai` 的上游同步、重建与自动回写由 [`.github/workflows/sync-upstream-rules.yml`](.github/workflows/sync-upstream-rules.yml) 单独负责
- 支持手动触发
- [`.github/workflows/build-dist.yml`](.github/workflows/build-dist.yml) 不再自动拉上游或自动修复提交；如果网页端直接编辑 `main` 却漏提 `dist/`，工作流会明确报错提醒补齐

## 客户端如何使用

请只引用 `dist/`，不要直接引用：

- `rules/`
- 第三方原始规则库 URL
- `rules/upstream/` 下的登记文件

接入示例见：

- [docs/usage-surge.md](docs/usage-surge.md)
- [docs/usage-mihomo.md](docs/usage-mihomo.md)
- [docs/examples/surge-public.conf](docs/examples/surge-public.conf)
- [docs/examples/mihomo-public.yaml](docs/examples/mihomo-public.yaml)
- [docs/aws-region-rules.md](docs/aws-region-rules.md)
- [docs/alicloud-direct-rules.md](docs/alicloud-direct-rules.md)
- [docs/github-ssh-direct-rules.md](docs/github-ssh-direct-rules.md)

其中 Surge 当前建议明确区分两种使用版本：

- 软路由集群版
  - 只在本地私有环境维护，用于工作电脑集群接入软路由 Surge。
  - 允许包含按局域网源 IP 的设备分流、私有 `policy-path`、`[MITM]` 与证书参数。
- 个人终端版
  - 对应仓库里的公开参考模板 [`docs/examples/surge-public.conf`](docs/examples/surge-public.conf)。
  - 保留通用的 `General + Proxy Group + Rule` 结构，但移除设备分流、私有订阅地址与 `[MITM]`。

其中两份公开参考模板已经做过脱敏处理，适合直接上传到公开仓库给他人参考：

- `docs/examples/surge-public.conf`
  - 对应 Surge 的“个人终端版”
  - 保留完整 `General + Proxy Group + Rule` 结构
  - 已移除设备分流、私有订阅地址与 `[MITM]`
  - 默认接入 1 条 `DOMAIN-KEYWORD,adspower` 内联规则与 `proxy/gfw` 广谱代理规则
- `docs/examples/mihomo-public.yaml`
  - 保留完整 `dns + proxy-providers + proxy-groups + rule-providers + rules` 结构
  - 已移除真实机场订阅链接、供应商命名与控制面参数
  - 默认接入 1 条 `DOMAIN-KEYWORD,adspower` 内联规则与 `proxy/gfw` 广谱代理规则

## 当前设计原则

- 源规则尽量保持小而清晰，优先你自己的审阅结果
- 上游来源只作为参考素材，不直接暴露给客户端
- 统一输出显式规则行，不再生成额外的客户端专用精简产物
- 域名规则、CIDR 规则与大多数关键词规则都通过 `RULE-SET` / `behavior: classical` 接入
- 少量必须内联的关键词规则应先于广谱代理规则；例如 `DOMAIN-KEYWORD,adspower` 应放在 `proxy/gfw` 前，避免被更广的代理规则吞没

## Google 路由强约束

- Google 相关（含 Google Play / Gemini / YouTube / FCM）只在 `rules/region/tw/google_tw.list` 维护
- 客户端应接入 `dist/surge/rules/region/tw/google_tw.list` 或 `dist/mihomo/classical/region/tw/google_tw.yaml`
- Google 规则必须绑定 `TW-AUTO`（或等价台湾策略组），不再提供 `proxy/google` 双入口
- 规则顺序必须先放 Google TW 规则，再放 `region/hk/global_media` 等广谱区域规则，确保优先命中台湾策略
- 新增或调整 Google 规则时，先改该源文件，再执行构建同步 `dist/`

## 上游维护方式

当前仓库只先落两类维护元数据：

- `rules/upstream/sources.yaml`
  - 记录每个主要源文件建议参考哪些上游
- `rules/upstream/merge.yaml`
  - 记录未来如何把上游素材并回本仓库源规则

这两个文件当前不参与自动构建，只负责把维护策略写清楚，避免后续继续依赖口头约定。

## 本地私有配置

仓库提供 [`.rulemesh.local.example.json`](.rulemesh.local.example.json) 作为本地私有配置模板。复制为 `.rulemesh.local.json` 后，可给 `tools/sync_upstream_rules.py` 提供本地告警配置；当前支持：

- `upstream_alert.feishu_webhook_url`
- `upstream_alert.feishu_secret`

约定如下：

- `.rulemesh.local.json` 只用于本地私有环境，已经被 `.gitignore` 忽略，不应提交到公开仓库
- 缺少本地配置时，不影响构建与上游同步主流程，只会跳过 Feishu 告警发送
- 真实 Webhook、密钥、私有订阅地址、MITM 参数与本地长期使用配置应继续保留在公开仓库外部，例如 `%USERPROFILE%\Desktop\rulemesh-local\current`
- 若私有配置结构发生变化，必须同步更新 `.rulemesh.local.example.json` 与相关文档，但只能提交脱敏占位值

## 维护建议

- 优先改 `rules/`，不要直接手改 `dist/`
- 新增规则前，先想清楚它是 `reject`、`direct`、`proxy` 还是 `region`
- 新增、删除或重命名 `rules/{reject,direct,proxy,region}/` 下的 `.list` 源规则文件时，同步更新 `rules/upstream/sources.yaml` 与 `rules/upstream/merge.yaml`
- 新增或调整默认对外使用的规则入口、顺序、策略含义时，同步更新 `README.md`、`docs/usage-surge.md`、`docs/usage-mihomo.md` 与两份公开模板
- 如果一个源文件开始变得很大，优先补 `sources.yaml` 与 `merge.yaml`，再考虑引入更多上游素材
- 提交前优先运行 `powershell -ExecutionPolicy Bypass -File tools/check.ps1`
- 提交前看一眼 `dist/build-report.json` 的 warnings，特别是 Mihomo 不支持的规则类型
- 自写注释、生成说明、文档说明默认统一写中文，不要再放英文占位注释

## 规则方法论：上游优先 + 本地兜底

本仓库统一采用“上游优先精准匹配 + 本地规则兜底覆盖”的编排方式：

- 先写 `INCLUDE,upstream/...`，优先命中第三方持续维护的精细规则。
- 再写本地兜底规则，优先使用 `DOMAIN-KEYWORD` 与 `DOMAIN-SUFFIX` 提升覆盖韧性。
- 兜底规则只补“高频且长期稳定”的关键词/后缀，避免把本地规则膨胀成上游镜像。
- 当某类规则暂无可靠上游时，可先保留手写规则；一旦有稳定上游，再迁移到“上游优先”结构。
- 目标是同时兼顾：上游的精准全面 + 本地兜底的抗失效能力。
