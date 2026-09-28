# 第三版第三步：证据与可复现评估

日期：2026-09-27。目标是把项目推进到可解释、可检查的个人研究工程作品；不宣称达到生产级、具备生态预测能力或已获得准确率提升。

## 本次功能

1. 主张必须分为source_fact（来源事实）与project_inference（项目推断）。这是模型分类、程序校验结构，不保证类型语义完全正确。
2. 每条主张附知识卡片段：card_id、field、quote。程序检查片段是否出现在对应卡片字段，不能伪造摘录。
3. 来源事实只能锚定claim字段；项目推断可使用claim/application_note，但必须说明caveat。
4. 最多两条主张，保留条件，不为填满条数强答。继续沿用原接口的1200输出token预算。
5. 保存模型返回的原始文本（包括格式/证据校验失败的文本）、完整本轮检索证据与使用量。传输层已拒绝的截断/非文本响应仍不能完整保存；未改造底层HTTP客户端。
6. review_runs.py从v0.2或v0.3运行记录创建人工评分JSON，并按版本汇总评分覆盖率、支持程度、失败状态与已知token用量。
7. 原始记录哈希验证、评分条目完整性检查，防止改过结果后继续套用旧评分；拒绝重复输入相同文件内容。

## 不等于事实核查

知识卡是对网页资料的整理，不是网页原文。界面写“知识卡摘录”，不能把它宣传成逐字网页引文。来源、适用条件仍须回查。

真实摘录也可能伴随错误推论，例如“水温影响生物活动”不能自动支持“所有情况都必须精确测温”。测试特意保留这种能通过形式校验的反例。语义支持仍由人工评价；普通同学可复核来源支持关系，不代表生态专家真值。

## 安装

这是依赖第二版的增量包；包含第三版第二步的新入口与状态核心更新，所以即使未装第二步，也可在第二版上安装本包。第一步代码可保留。

覆盖：agent_v03.py、context_agent.py、tests/test_context_agent.py。
新增：grounding.py、review_runs.py、tests/test_grounding_review.py、本说明和REVIEW_RUBRIC.md。

请先提交第二步已完成的本地工作，再覆盖上述同名文件，不删除任何旧运行JSON。app.py、rag.py、retriever.py、llm.py与data/不变，第二版基线仍可运行。

```bash
cd "/Users/zhangyuhang/Desktop/LureSense/LureSense/luresense-agent"
python3 -m unittest discover -s tests -v
mkdir -p runs
python3 agent_v03.py --mode mock --query "大口黑鲈吃什么？"
```

保留第一步时共66项测试；没有第一步的8项测试则为58项。mock不产生模型主张，仅展示候选资料，不能用于评价新主张格式的真实生成质量。

## 真实调用

```bash
python3 agent_v03.py --mode rag --base-url "https://api.openai.com/v1" --model "gpt-4.1-mini" --api-key-prompt --query "气温能直接代替水温吗？" --save runs/v03_step3_temperature_01.json
```

输入API Key后等待，看到答案或错误后输入/exit保存。若已存在同名文件，改用02；程序会在调用前拒绝重名路径。本步使用了更严格的新输出格式，旧模型响应可能被拒绝，这属于需要记录的格式失败，不应悄悄切回旧模式。未自动修复或重试。

预期的显示形式是类型标签、主张、知识卡摘录、推断限制和来源。例子只是结构：

```text
【来源事实（待核对）】…… [Kxxx]
知识卡摘录 Kxxx/claim：……
【项目推断】…… [Kyyy]
限制：……
```

## 生成并填写评分表

```bash
python3 review_runs.py prepare --run runs/v03_step3_temperature_01.json --out runs/review_temperature_01.json
open -e runs/review_temperature_01.json
```

填写reviewer（可用昵称），只修改各item的answerable、useful、condition_correct、abstention_appropriate、note，以及claim_reviews内的support和note。评分含义见REVIEW_RUBRIC.md。

不要修改id、question、version、result、sources、index。各条支持判断需有文字理由。不会自动给分，也不调用额外模型。

```bash
python3 review_runs.py summarize --review runs/review_temperature_01.json --out runs/summary_temperature_01.json
```

先不填任何评分也能汇总，此时覆盖率为0，相关比例为null；null表示无有效分母，不是0%错误率。

可同时放入两版记录：

```bash
python3 review_runs.py prepare --run runs/openai_temperature_01.json runs/v03_step3_temperature_01.json --out runs/review_comparison_01.json
```

它会按app_version分组。只有文件存在时才执行；旧版顶层记录和第三版sessions记录均支持。表里保存原始文件绝对路径，移动文件后须重新生成评分表并有记录地迁移评分；不能绕过哈希检查。

## 评估注意点

- 统计单位是response turn，同一会话多次修改并非独立样本，不能把这些数量当作独立测试题数。
- synthetic=true或未标明synthetic=false的条目不进入真实指标；仍显示排除数量。
- 状态失败、拒答与预算耗尽保留，不因没有主张就当作正确回答。
- supported/partial/unsupported进入已决分母；pending和unresolved不算正确，也不进入该分母，必须同时报告覆盖率。
- partial与unsupported分别报告。not_fully_supported合并两者，避免把“半对”算作完全支持。
- useful指标只覆盖人工判断answerable=yes且useful为yes/no的条目，分母明确显示；未评分不能自动记有效。
- token未知记null而非0，不推算美元费用。不同模型、知识版本、提示词混跑时，不能仅凭同一app_version分组直接比较。
- 这是开发阶段自评。先用相同问题和条件比较，不在看过答案后改评分规则或移除失败题。正式评估应冻结场景并尽量让第二位评审复核。

## 本次验证

66项软件测试通过（第二版24+第一步8+第二步17+本步17）；底层模型集成使用模拟客户端。新增测试覆盖摘录伪造、推断冒充事实、推断缺少限制、真实摘录不保证蕴含、评分覆盖、重复/缺失条目、原始证据修改、旧版本兼容、模拟记录排除。

另执行模拟客户端的生成→保存→创建评分→人工标签示例→汇总的完整工具流程，以及mock CLI退出保存。本次未进行真实付费调用，未宣称新提示词已在真实模型上稳定。

## 提交main

确认git branch --show-current输出main，再执行：

```bash
git add agent_v03.py context_agent.py grounding.py review_runs.py tests/test_context_agent.py tests/test_grounding_review.py docs/V03_STEP3_GUIDE.md docs/REVIEW_RUBRIC.md
git diff --cached --stat
git commit -m "feat: add claim provenance validation and human evaluation workflow"
git push origin main
```

下一阶段优先级：先获得5～10个真实开发场景的评分和失败分析，再决定修复路由、改用语义检索、增加会话持久化或做展示界面。工业部署、硬件、多Agent不是当前目标。
