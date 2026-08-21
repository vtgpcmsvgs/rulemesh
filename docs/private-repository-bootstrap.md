# 私有配置仓库发现与恢复

## 目的

公开仓库只保存规则源、构建产物和脱敏说明，真实客户端配置保存在 GitHub 私人仓库 `vtgpcmsvgs/rulemesh-local`。根目录的 [`private-repository.json`](../private-repository.json) 是这项对应关系的机器可读登记，也是跨机器恢复时的单一发现入口。

仅在另一台机器登录相同 GitHub 账号，不会自动创建本地目录，也不会让 Codex 自动知道私人仓库与本地路径的对应关系。新的 Codex 会话应先读取公开仓库的 `AGENTS.md` 与 `private-repository.json`，再检查或恢复私人仓库；不得因为 `%USERPROFILE%\Desktop\rulemesh-local` 不存在就断言私人配置不存在，也不得擅自创建同名空仓库。

## Windows 恢复流程

1. 确认 GitHub CLI 使用能够访问私人仓库的账号：

   ```powershell
   gh auth status
   gh repo view vtgpcmsvgs/rulemesh-local --json nameWithOwner,visibility,defaultBranchRef,url
   ```

2. 确认目标目录。默认工作副本固定为：

   ```text
   %USERPROFILE%\Desktop\rulemesh-local
   ```

3. 目标目录不存在时，从已登记的私人仓库克隆：

   ```powershell
   $target = Join-Path $env:USERPROFILE "Desktop\rulemesh-local"
   gh repo clone vtgpcmsvgs/rulemesh-local $target
   ```

   目标目录已经存在时，不要覆盖或再次克隆；先检查其 `origin`、工作区与分支状态。

4. 校验本地工作副本与远程默认分支：

   ```powershell
   $target = Join-Path $env:USERPROFILE "Desktop\rulemesh-local"
   git -C $target remote get-url origin
   git -C $target fetch origin main
   git -C $target status -sb
   git -C $target rev-list --left-right --count origin/main...main
   ```

   正常结果应满足：`origin` 指向登记的私人仓库、当前分支为 `main`、工作区无意外变更、领先与落后均为 `0`。

   Codex 沙箱若报告 `detected dubious ownership`，不要修改全局 Git 配置；只给当前命令附加已经核对过的绝对路径：

   ```powershell
   git -c "safe.directory=$target" -C $target status -sb
   git -c "safe.directory=$target" -C $target rev-list --left-right --count 'HEAD...@{upstream}'
   ```

   PowerShell 会把未加引号的 `@{...}` 当作哈希表语法，因此包含 `@{upstream}` 的 revision 必须整体使用单引号。只应把实际登记的私人仓库路径传给 `safe.directory`，不得用 `*` 或写入全局配置。

5. 解析当前配置目录时以实际布局为准：优先使用 `rulemesh-local/current`；若没有 `current`，但主配置与同步脚本直接位于仓库根目录，则使用根目录。不得为适配旧说明凭空创建 `current`。当前根目录包含家庭与公司两份 Surge Personal：`rulemesh-substore-surge-personal.conf` 和 `rulemesh-substore-surge-personal-company.conf`；两者除用途标识与 MITM 外应保持同构。

## Codex 行为边界

- GitHub 登录状态只能证明账号身份，不能替代仓库发现、克隆与本地路径登记。
- 在声明“私人配置不存在”之前，必须先读取 `private-repository.json`，并通过 GitHub 检查登记的私人仓库是否可访问。
- 不要把私人仓库克隆到公开 `rulemesh` 仓库内部，也不要把两者合并为同一个 Git 工作区。
- 检查私人仓库时，只输出仓库地址、分支、提交号、同步计数、文件计数或脱敏后的字段；不得输出真实订阅 URL、密钥、签名或证书参数。
- 私人配置修改只有在提交、推送成功，并确认本地相对 `origin/main` 领先与落后均为 `0` 后才算完成。

## 防回归检查

`tools/check_private_repository_registration.py` 会校验登记文件结构，以及 `AGENTS.md`、`README.md` 和本文之间的关键引用关系；`tools/check.ps1` 默认执行该检查。若私人仓库重命名、转移所有者、修改默认分支或改变本地布局，必须同时更新登记文件和相关说明。
