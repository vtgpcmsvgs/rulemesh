# 代理组过滤维护方法论

本文用于沉淀 RuleMesh 在私有 Mihomo / Surge 配置中的代理组过滤维护约定，重点避免把独立占位项或供应商名前缀误写成宽匹配。

## 先说结论

- `剩余流量`、`套餐到期`、`距离下次重置`、`过滤掉`、`Expire Date`、`Traffic Reset` 这类状态/提示项，继续按前缀匹配过滤。
- `直接连接` 这类独立占位项，必须按“整行精确匹配”过滤，不能按任意位置命中过滤。
- `联系我们` 继续按专项子串匹配。
- `1.2 GB | 50 GB` 这类流量统计提示，继续按数值模式匹配。

## 供应商名前缀风险

- 某些 provider 可能会给真实节点追加统一前缀，或把供应商名注入到节点显示名里。
- 这类情况下，不要把供应商名或独立占位项写成普通子串、负向前瞻宽匹配或其他会命中整行任意位置的表达式。
- 修改前先检查相关 provider 是否存在 `additional-prefix` 或等价的节点名前缀注入机制。

## 当前推荐写法

- Mihomo `exclude-filter`：

```yaml
exclude-filter: "(?i)^(剩余流量|套餐到期|距离下次重置|过滤掉|expire date|traffic reset)|^(直接连接)$|联系我们|\\d+(?:\\.\\d+)?\\s*(?:[kmgt]b?|b)\\s*\\|\\s*\\d+(?:\\.\\d+)?\\s*(?:[kmgt]b?|b)"
```

- Surge `policy-regex-filter`：

```ini
policy-regex-filter=^(?!剩余流量)(?!(直接连接)$)(?!套餐到期)(?!距离下次重置)(?!.*联系我们)(?!过滤掉)(?!Expire Date)(?!Traffic Reset)(?!.*\d+(?:\.\d+)?\s*(?:[KMGT]B?|B)\s*\|\s*\d+(?:\.\d+)?\s*(?:[KMGT]B?|B)).*$
```

## 明确禁止的错误写法

- 不要把 Mihomo 写成：

```yaml
exclude-filter: "(?i)剩余流量|直接连接|供应商名|套餐到期|距离下次重置|..."
```

- 不要把 Surge 写成：

```ini
policy-regex-filter=^(?!.*剩余流量)(?!.*直接连接)(?!.*供应商名)...
```

- 上面两种写法都可能把真实节点误当成提示词或占位项过滤掉。

## 修改时必须做的验证

1. 先确认相关 provider 是否存在统一前缀或统一命名注入。
2. 至少拿 1 条真实节点名做正例验证，确认不会被误过滤。
3. 至少拿 1 条独立占位项做反例验证，确认仍会被过滤。
4. 至少拿 2 到 3 条状态提示做反例验证，例如 `剩余流量 88 GB`、`套餐到期 2026-05-01`、`Traffic Reset in 3 days` 必须过滤。
5. 搜索全仓与私有目录里的同类表达式，避免只修一处、下一次又被别的文件覆盖回去。

## 同步范围

- `%USERPROFILE%\\Desktop\\rulemesh-local\\current\\rulemesh-substore-mihomo-clash-verge.yaml`
- `%USERPROFILE%\\Desktop\\rulemesh-local\\current\\rulemesh-substore-mihomo-clash-meta.yaml`
- `%USERPROFILE%\\Desktop\\rulemesh-local\\current\\rulemesh-substore-surge-personal.conf`
- `%USERPROFILE%\\Desktop\\rulemesh-local\\current\\rulemesh-substore-surge-work-whitelist.conf`
- `docs/examples/mihomo-public.yaml`
- `docs/examples/surge-public.conf`
- `docs/usage-mihomo.md`
- `docs/usage-surge.md`
- `README.md`

## 执行顺序

1. 先改 4 份私有配置里的实际过滤表达式。
2. 再改公开示例，避免文档继续教错。
3. 再改 `README.md`、`docs/usage-surge.md`、`docs/usage-mihomo.md` 与本文。
4. 最后搜索全仓与私有目录确认没有旧表达式残留。

## 维护目标

- 手动切换、自动组和地区组应尽量只展示真实节点。
- 过滤规则的维护目标不是“写法看起来统一”，而是“既能过滤占位项，又不误伤真实节点”。
- 只要存在 provider 前缀注入或统一命名机制，就把它当成改动前必查项，而不是普通样式调整。