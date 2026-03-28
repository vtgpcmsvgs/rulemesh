# AGENTS.md

## 仓库重点

- 源规则只维护在 `rules/`
- 构建产物只发布两条线：
  - `dist/surge/rules/`
  - `dist/mihomo/classical/`
- 不要重新引入这些已废弃目录：
  - `dist/surge/domainset/`
  - `dist/mihomo/domain/`
  - `dist/mihomo/ipcidr/`

## 构建入口

- Windows 本地与 Codex 会话统一优先使用 `tools/build_rules.ps1`
- 不要默认直接跑 `python tools/build_rules.py`
- 这个包装脚本会优先探测：
  - `$env:RULEMESH_PYTHON`
  - 仓库内 `.venv\Scripts\python.exe`
  - `%LocalAppData%\Programs\Python\Python314\python.exe`
  - `python`
  - `py -3`

## Codex 注意事项

- 在 Codex Windows 沙箱里，`python` / `py -3` 可能不可用，即使 Python 已安装
- 当前机器已确认存在的解释器路径是：
  - `%LocalAppData%\Programs\Python\Python314\python.exe`
- 如果直接执行该解释器出现 `Access is denied`（访问被拒绝），这是沙箱限制，不是仓库问题；需要申请提升权限后再运行

## 仓库默认流程

- 对本仓库的任何实际修改，默认同时同步更新 `%USERPROFILE%\Desktop\rulemesh-local\current` 中对应文件；除非用户明确说明不要同步
- 修改前后都要判断 `%USERPROFILE%\Desktop\rulemesh-local\current` 是否存在对应文件；只有存在对应关系时才同步；若本次没有对应同步项，最终回复中必须明确写出“本次无对应同步项”
- 修改完成后，必须检查整个仓库中同类问题是否仍然存在，并检查是否有耦合项、重复项、残留项；发现后应一并处理或明确报告
- 提交前默认运行 `powershell -ExecutionPolicy Bypass -File tools/check.ps1`；若因为环境或权限限制无法执行，必须在最终回复中明确说明
- 新增、删除或重命名 `rules/{reject,direct,proxy,region}/` 下的 `.list` 源规则文件时，必须同步更新 `rules/upstream/sources.yaml` 与 `rules/upstream/merge.yaml`
- 新增或调整默认对外使用的规则入口、规则顺序、策略含义或公开模板行为时，必须同步更新 `README.md`、`docs/usage-surge.md`、`docs/usage-mihomo.md`、`docs/examples/surge-public.conf`、`docs/examples/mihomo-public.yaml`
- 若本次修改影响使用方式、规则组织、构建方式、产物结构或维护约定，必须同步更新相关文档
- 私有 `rulemesh-substore-surge-work-whitelist.conf` 属于长期特化的工作路由白名单配置；它与 `rulemesh-substore-surge-personal.conf`、`rulemesh-substore-mihomo-clash-verge.yaml`、`rulemesh-substore-mihomo-clash-meta.yaml` 从现在起允许永久不一致，不得因为“统一模板”或“对齐 personal 配置”而回滚
- 维护 `rulemesh-substore-surge-work-whitelist.conf` 时，默认应维持“仅放行明确白名单入口，其余流量对工作电脑统一 REJECT”的原则；若要恢复广谱放行（如 `proxy/gfw`、广谱 `direct`、`FINAL` 兜底放行），必须得到用户明确确认
- 当前该工作路由白名单默认允许入口包括：设备分流、区域精确规则、GitHub SSH、GitHub Raw 下载入口、GitHub 广覆盖观察兜底、私有订阅更新直连、1Password、AdsPower、Polygon RPC、BSC RPC、Google Public DNS 主 IPv4 端点、Cloudflare DNS、`LAN,DIRECT`、`direct/os_time_direct`、`direct/microsoft_direct`、`direct/macos_update_direct`、阿里云指定直连与 `direct/bytedance_direct`；其中只有 2.1 设备分流保留 `SRC-IP + AWS 区域` 约束，2.2-2.10 不再额外限制 `SRC-IP`，原独立 IP 规则段已删除；未命中上述入口的流量最终 `FINAL,REJECT`
- GitHub 在该工作路由文件中除 `github_ssh_direct` 外，还允许紧随其后保留 `DOMAIN,raw.githubusercontent.com` 下载入口与一条广覆盖 `DOMAIN-KEYWORD,github` 观察兜底；它们用于显式放行 GitHub Raw 规则产物下载，并发现 SSH / Raw 之外的漏网之鱼，不得被“去重”或“收敛”掉
- GitHub Raw 下载链路默认还应保留 `raw.githubusercontent.com = server:system` 与 `dns-server = system, ...` 这组解析兜底，用于降低 Surge 外部资源偶发超时；除非用户明确要求，不要顺手删掉
- AdsPower 在该工作路由文件中除精细 `adspower_direct` / `adspower_proxy` 外，还允许紧随其后保留一条广覆盖 `DOMAIN-KEYWORD,adspower` 观察兜底；它是故意用于发现细分规则漏网之鱼的，不得被“去重”或“收敛”掉
- 上述工作路由白名单特化只适用于工作路由文件本身，不自动扩散到两个 `personal` 配置，也不要把 `personal` 配置的通用结构反向覆盖到该工作路由文件
- 只要工作路由白名单逻辑、适用范围、维护边界发生变化，必须同步更新 `docs/surge-work-cluster-whitelist.md`、`README.md` 与相关使用说明，避免后续失忆式回滚
- 若本次任务产生了实际文件变更，且用户没有明确禁止提交，则默认在验证完成后提交 git commit
- 如果上述任一步无法执行，不得静默跳过；必须在最终回复中明确说明未完成项、原因以及阻塞点
- 最终回复默认应包含：同步状态、全仓检查结果、文档更新情况、验证结果、提交状态

## 私有配置与脱敏

- `.rulemesh.local.json`、`%USERPROFILE%\Desktop\rulemesh-local\current`、私有 `policy-path`、真实机场订阅地址、Webhook、AccessKey、STS、`[MITM]` 证书参数、局域网设备分流规则都视为私有内容
- 默认不要把私有文件内容或敏感值写回公开仓库，也不要在回复中完整回显真实密钥、签名、订阅 URL 或其他敏感参数
- 即使需要在公开仓库里记录工作路由白名单维护约定，也只允许写“固定工作电脑”“白名单模式”“与 personal 永久不一致”这类抽象说明；不要把真实 `SRC-IP` 范围、私有设备标识、订阅地址或本地策略分组细节写回公开仓库
- 若本地私有配置结构发生变化，必须同步更新 `.rulemesh.local.example.json` 与相关文档，但只允许写入脱敏占位值
- 若任务需要参考私有配置，默认只说明字段名、用途与是否生效，不直接暴露真实值

## 验证步骤

- 修改 `rules/`、`tools/build_rules.py`、文档或产物结构后，运行：
  - `powershell -ExecutionPolicy Bypass -File tools/build_rules.ps1`
- 提交前检查：
  - `dist/` 目录树是否仍然只有 `surge/rules` 与 `mihomo/classical`
  - `dist/build-report.json`
  - `git status`

## 警告约定

- 当前构建预期应为 `0` 条 warning
- 如果构建 warning 数量增加，先检查是否引入了：
  - BOM 字符
  - 不受支持的 Mihomo 规则
  - 被误判为普通文本的注释行

## 语言约束

- 仓库自写内容默认工作语言统一为中文
- `rules/{reject,direct,proxy,region}/` 中的自写注释必须使用中文；纯英文注释视为构建错误，不允许提交
- `tools/` 中生成 `rules/upstream/` 的头部说明、`dist/` 的生成头部说明统一使用中文
- 第三方原样同步的上游快照内容可保留原始语言，但不要在本仓库自写说明里继续追加英文注释

## 文件规范

- 规则与文档统一使用 UTF-8 无 BOM
- 新增或修改文本文件后，提交前要顺手检查是否意外写入 BOM；尤其是 `rules/`、`docs/`、`README.md`、`AGENTS.md`、`.github/`、`tools/`、`tests/`
- 如果看到首行注释被构建脚本误报为 `unrecognized plain rule`，先检查 BOM
- 不要手改 `dist/`；一律改 `rules/` 或构建脚本后重建
- 提交前若新增或修改注释，先确认是否为中文表达，而不是英文占位说明
