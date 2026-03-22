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
  - `C:\Users\zaife\AppData\Local\Programs\Python\Python314\python.exe`
  - `python`
  - `py -3`

## Codex 注意事项

- 在 Codex Windows 沙箱里，`python` / `py -3` 可能不可用，即使 Python 已安装
- 当前机器已确认存在的解释器路径是：
  - `C:\Users\zaife\AppData\Local\Programs\Python\Python314\python.exe`
- 如果直接执行该解释器出现 `Access is denied`（访问被拒绝），这是沙箱限制，不是仓库问题；需要申请提升权限后再运行

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
- 如果看到首行注释被构建脚本误报为 `unrecognized plain rule`，先检查 BOM
- 不要手改 `dist/`；一律改 `rules/` 或构建脚本后重建
- 提交前若新增或修改注释，先确认是否为中文表达，而不是英文占位说明
