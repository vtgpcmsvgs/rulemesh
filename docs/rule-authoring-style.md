# 源规则编排与维护风格

这份文档专门记录 `rules/{reject,direct,proxy,region}/` 下源规则文件的编排约定，用来把已经验证过的维护经验沉淀成仓库内的长期记忆，降低后续返工、回滚到“一坨兜底规则”的概率。

## 适用范围

- 适用于所有参与构建的 `.list` 源规则文件
- 尤其适用于同时包含上游 `INCLUDE`、显式域名、关键词兜底的中大型规则文件
- 例如：
  - `rules/region/tw/ai_tw.list`
  - `rules/direct/ai_cn_direct.list`
  - `rules/direct/bytedance_direct.list`
  - `rules/region/tw/google_tw.list`
  - `rules/region/tw/crypto_tw.list`
  - `rules/region/hk/global_media.list`

## 总体原则

- 先保证语义稳定，再追求可读性
- 同一平台、同一服务、同一类基础设施尽量放在同一小节
- 上游精细规则优先，本地只做高价值兜底
- 文件头先写清“它负责什么、不负责什么、顺序上放在哪里”
- 自写注释统一用中文，不混入英文占位说明

## 先分类，再编辑

对中大型规则或维护约定的修改，默认先把本次任务分到这些类别里，再开始改文件：

- 源规则
- 上游登记
- 公开说明或公开模板
- 构建与检查脚本
- 私有同步项

这么做的目的不是增加仪式感，而是提前暴露“这次会不会顺手漏改别处”。

配套的硬闸门已经接入 `powershell -ExecutionPolicy Bypass -File tools/check.ps1`：

- `tools/check_change_guardrails.py` 会先根据当前工作区变更给出分类
- 对已经能机械判断的强关联项直接失败
- 对还不适合硬编码的高风险联动给出显式提醒

当前明确做成硬失败的主要有两类：

- `rules/{reject,direct,proxy,region}/` 下 `.list` 源规则文件新增、删除或重命名，但没有同步修改 `rules/upstream/sources.yaml` 与 `rules/upstream/merge.yaml`
- `docs/rule-authoring-style.md` 已修改，但没有同步更新 `AGENTS.md` 与 `README.md`

这意味着“我知道这次顺手不用改别的”不能只停留在口头判断，至少要先过一遍默认闸门。

## 推荐结构

一个典型的源规则文件，默认按这四层组织：

1. 文件头说明
2. 维护约束
3. 按平台或按服务分组的小节
4. 需要时补充“边界说明”或“不要并入什么”

推荐模板：

```text
# 规则集定位：按“上游主体 + 本地兜底”维护。
# 维护约束：
# 1) ...
# 2) ...
# 3) ...

# 平台 / 服务 A：说明。
INCLUDE,upstream/...
DOMAIN-SUFFIX,...
DOMAIN,...
DOMAIN-KEYWORD,...

# 平台 / 服务 B：说明。
...
```

## 小节粒度

默认优先按“人能直观看懂”的维度分组，而不是只按规则类型分组。

优先级通常是：

1. 平台 / 产品
2. 服务类型
3. 共享基础设施

例如：

- `ai_tw.list` 适合按 `ChatGPT / OpenAI`、`Claude / Anthropic`、`Gemini / Google AI`、`Perplexity` 这类平台分组
- `google_tw.list` 适合按 `Google FCM`、`YouTube`、`Google 通用服务`、`Gemini / Google AI` 这类服务分组
- `crypto_tw.list` 适合按 `交易所 / 接入基础设施`、`链上数据 / 区块浏览器`、`预测市场` 这类类别分组
- `bytedance_direct.list` 适合按 `字节跳动 / ByteDance` 与 `抖音 / Douyin` 分组
- `global_media.list` 适合按 `上游 GlobalMedia 主体`、`X / Twitter 网页补站`、`Polymarket 香港解锁补站` 这类服务小节分组

不要默认把所有显式域名堆成一段、所有关键词再堆成另一段；这样后续找某个平台时要来回跳，不利于维护。

## 小节内部顺序

同一小节里，默认按这个顺序排列：

1. 小节说明注释
2. `INCLUDE,upstream/...`
3. 显式入口
4. 兜底入口

其中“显式入口”通常包括：

- `DOMAIN`
- `DOMAIN-SUFFIX`
- `DOMAIN-WILDCARD`
- `IP-CIDR`

“兜底入口”通常包括：

- `DOMAIN-KEYWORD`
- 少量高价值、长期稳定的广覆盖规则

这样做的目标是让维护者先看到“精细来源”，再看到“本地补站”，最后看到“更宽泛的兜底”。

## 什么时候按平台分组，什么时候保持简单

不是每个文件都要强行拆成很多小节。

适合按平台 / 服务细分的小节：

- 一个文件承接多个平台、多个品牌、多个产品入口
- 文件里既有多个 `INCLUDE`，又有多组显式域名与关键词兜底
- 维护者需要经常按平台查找和补规则

适合保持“上游主体 + 本地最高优先级兜底”的简单结构：

- `cn_direct.list` 这种宽泛基础兜底文件
- `telegram.list` 这种上游主体很明确、手写入口很少的入口型文件
- 只有一两个本地补站的小文件

简化版仍建议写清楚边界，例如：

- 这个文件是“最宽泛的基础兜底”，顺序应放在细分规则之后
- 这个文件只保留“官方域名 / 短链 / 客户端入口”，不承接通用广覆盖

## 上游与本地规则的边界

默认采用“上游优先 + 本地兜底”的写法：

- 上游负责持续维护的精细规则
- 本地只保留你真实需要、上游暂未稳定覆盖、或者需要更激进兜底的部分

本地兜底不应膨胀成上游镜像。只有满足下面至少一条时，才值得补本地规则：

- 这是你真实命中过、且经常用到的入口
- 这是高频品牌词，漏掉后很容易回退到错误出口
- 这是上游更新慢、但你需要更激进覆盖的类别
- 这是你有意保留的“观察兜底”

## 文件头必须写清楚的内容

每个中大型源规则文件，头部至少回答这几个问题：

- 这份规则负责什么
- 它默认绑定哪个区域 / 动作
- 它不负责什么
- 它和相邻规则文件的边界是什么
- 客户端顺序上应放在谁前面或后面

例如：

- `ai_tw.list` 要明确“只负责海外 AI，不负责国内 AI”
- `ai_cn_direct.list` 要明确“显式国内 AI 在前，字节共享基础设施仍交给 bytedance_direct”
- `google_tw.list` 要明确“Gemini 允许在 ai_tw 交叉兜底，但 google_tw 必须排在 ai_tw 前”
- `cn_direct.list` 要明确“它是最宽泛的大陆通用兜底，应放在更细分规则之后”

## 文件边界补充

- 单一区域的公有云前缀继续放在对应地区目录，例如 `rules/region/jp/tokyo_aws_ipv4.list`
- 多地区链式代理 / 多地区 SOCKS5 端点不要因为历史来源继续挂在单一国家目录；应按当前语义放到类似 `rules/region/multi/` 的路径
- 这类文件的头注释要明确写清：它不是某个国家地区入口，客户端默认应接到链式代理 / 自动选择 / 负载均衡组，而不是固定地区组

## 只改源文件、不改 dist 的情况

如果本次修改只涉及：

- 注释重写
- 小节重排
- 说明增强

且构建后确认 `dist/` 内容没有变化，那么允许最终只提交源文件本身。

但即使预期 `dist` 不变，也仍然必须执行：

- `powershell -ExecutionPolicy Bypass -File tools/build_rules.ps1`
- `powershell -ExecutionPolicy Bypass -File tools/check.ps1`

不能因为“只是注释调整”就跳过验证。

## 何时同步文档与仓库约定

当你修改的是“规则内容”时，未必需要更新维护文档。

但当你修改的是下面这些内容时，必须同步更新仓库内的经验沉淀：

- 规则编排方式
- 文件边界
- 维护方法论
- 默认排序原则
- 上游与本地兜底的分工

最低要求是同步更新：

- `AGENTS.md`
- `README.md`
- 这份文档 `docs/rule-authoring-style.md`

反过来说，只要你已经改了 `docs/rule-authoring-style.md`，就不要把它当成“只补一份说明文档”；默认还要同步把同一套约束写回 `AGENTS.md` 与 `README.md`。

## 当前已标准化的参考文件

下面这些文件现在已经按这套风格整理过，可以作为后续修改时的直接参考：

- `rules/region/tw/ai_tw.list`
- `rules/direct/ai_cn_direct.list`
- `rules/direct/bytedance_direct.list`
- `rules/region/tw/google_tw.list`
- `rules/region/tw/crypto_tw.list`
- `rules/region/hk/global_media.list`
- `rules/region/hk/telegram.list`
- `rules/direct/cn_direct.list`

后续新增或重构类似规则时，优先向这些文件的组织方式看齐，而不是重新发明一套新的注释风格。
