# LureSense 检索与状态实验

**离线结果；没有调用模型，不表示回答正确率或钓鱼效果。**

情景数：10；划分：challenge；数据哈希：`f8f22c345b24e7bbb6ca043dcbbf52fd02f57796305aaa12c69221feb32d53fc`。

标注为项目作者拟定的待复核卡片集合；challenge 是压力测试，不是独立盲测。

| 方法 | Hit@4 | Recall@4 | MRR@4 | 负例空检索率 | 失效词移除率 | 状态匹配率 |
| --- | --- | --- | --- | --- | --- | --- |
| direct | 0.714 (n=7) | 0.595 (n=7) | 0.548 (n=7) | 0.667 (n=3) | 0.000 (n=3) | — (n=0) |
| append_context | 0.857 (n=7) | 0.810 (n=7) | 0.762 (n=7) | 0.667 (n=3) | 0.000 (n=3) | — (n=0) |
| agent_state | 0.857 (n=7) | 0.857 (n=7) | 0.786 (n=7) | 1.000 (n=3) | 1.000 (n=3) | 0.833 (n=6) |

## 如何解释

- direct 只获得原问题；其他两组获得补充条件。与 direct 的差异同时包含信息增益，不能单独归因于算法。
- append_context 将原问题与最终条件拼接；agent_state 按状态重写查询。此对照用于观察原问题失效词的影响。
- 拼接基线中的字段名本身也可能命中检索词；差异包含序列化方式的影响，不是独立因果实验。
- 状态匹配只对 agent_state 适用；没有状态的基线不计零分。所有指标只用适用案例作分母。
- Recall@4 只对已标注相关卡计算；卡片集合不是穷尽标注，因此不计算 Precision。
- 负例空检索率衡量检索门控，不衡量模型是否恰当拒答。相关主题卡片存在也不保证具体结论可回答。
- 仅评估修正后的最终状态；原有单元测试另覆盖多轮历史。离线运行无网络耗时和模型费用指标。

## 失败与部分召回（全部保留）

| 案例 | 方法 | 类别 | 问题 | 召回 ID | 未满足项 |
| --- | --- | --- | --- | --- | --- |
| S23 | direct | vague | 我在池塘，应该优先观察哪里？ | K005, K010, K016, K019 | hit_at_4, recall_at_4 |
| S24 | direct | negation | 如果在湖泊有水草，怎么钓？ | K010, K003, K005, K016 | empty_on_negative, stale_query_clean |
| S24 | append_context | negation | 如果在湖泊有水草，怎么钓？ | K003, K010, K005, K011 | empty_on_negative, stale_query_clean |
| S25 | direct | negation | 我在湖泊，没看到水草，怎么钓？ | K010, K003, K005, K016 | stale_query_clean |
| S25 | append_context | negation | 我在湖泊，没看到水草，怎么钓？ | K003, K010, K005, K011 | stale_query_clean |
| S26 | direct | correction | 我在河流，看到岩石，应该先找哪里？ | K003, K011 | recall_at_4, stale_query_clean |
| S26 | append_context | correction | 我在河流，看到岩石，应该先找哪里？ | K003, K005, K010, K011 | stale_query_clean |
| S28 | direct | temperature | 现在水温22度。 | K008, K018, K019 | recall_at_4 |
| S28 | append_context | temperature | 现在水温22度。 | K018, K008, K019 | recall_at_4 |
| S30 | direct | negated_scope | 我不是在海边，我在湖泊，看到水草，应该先看哪里？ | 空 | hit_at_4, recall_at_4 |
| S30 | append_context | negated_scope | 我不是在海边，我在湖泊，看到水草，应该先看哪里？ | 空 | hit_at_4, recall_at_4 |
| S30 | agent_state | negated_scope | 我不是在海边，我在湖泊，看到水草，应该先看哪里？ | 空 | hit_at_4, recall_at_4, context_exact |

## 可追溯信息

```json
{
  "python": "3.11.5",
  "knowledge_sha256": "76435a1dc22a59dc53acf5b0e4235ffb24c97a5d6008a9960d17b9d3fef1f909",
  "sources_sha256": "811324daa5a4e538d83a8668ac1df924b6b538811aedcc33723cd4d07921a652",
  "label_status": "draft_author_labels_not_expert_validated",
  "code_sha256": {
    "benchmark_v05.py": "1497d57dc0c704d2e3e3b39843d1ea38cb09ee21e71b1f038e022c188995dbec",
    "retriever.py": "6fc312d4ec7f0df638547c17fe05f1c26894447d22a6e156b16f4824d1c4b435",
    "context_agent.py": "585cc32f1c5899c4dbdcd8bad2dc92450d6f451941df905ada3802848c395db1",
    "grounding.py": "0c63ce217fcf5bd9a1b90a02436f4aa62267df1bcbfcae25905afe97ffc82e81",
    "llm.py": "2a26cd3e7a472c2abc78abd657334b422b3529f97d31b8de13863f85de30182e",
    "agent_v03.py": "54ec1c48e0892ed9a39f1c53688e20c5a394666b6502c6b4add55a7c4ec5a934"
  }
}
```
