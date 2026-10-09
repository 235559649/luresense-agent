# 第三轮：未观察到不等于不存在

基于第二轮observation修复包，包含context_agent.py替换、新增context_guard.py、10项回归测试和本指南。

## 为什么修改

本轮人工评分5条响应、7个主张：supported 5、partial 1、unsupported 1。2条已判可回答的有用率为2/2，不代表整体正确率。未观察到结构这一题的状态正确，模型却生成“现场缺乏常见的鱼类藏匿结构”。

## 行为

在原JSON/引用契约校验之后、观察规则之前检查模型输出。当cover为unknown、unanswered或未观察到上述结构时，识别明确的“没有水草”“缺乏结构”“倒木不存在”等表述。当前实现检查text与caveat。明确“不能断定／不代表……”以及以“如果／假如／假设／若”开头的假设句不拦截；后一句的免责声明不会取消前一句的冲突。

命中时整条响应的claims和展示证据为空，状态为insufficient_evidence，显示条件限制说明；answer_origin=context_guard_v1。保留raw_response、model_answer_before_guard和context_guard_conflicts，同时保留检索证据、token及调用记录。没有额外请求或重试，不把接口失败伪装成拒答。

这是有限的中文模式检测，不是语义验证器，有误报/漏报可能。含混复杂句仍需要人工复核。整条答案停止展示是保守策略，可能丢弃其中有依据的部分；不代表知识库整体不可回答。

另加强K005提示：保留密苏里语境，不能把“溪流常年水潭”的“常年”扩大到所有水域。这一项仅是提示词改进，尚无自动语义保证，必须真实复测。

## 验证

Python 3.12环境134项单元测试通过（原124+新增10）。包括失败表述、同类表达、unknown/unanswered、合法未观察到说明、免责声明、假设句、caveat冲突、已确认状态，以及从请求到日志的端到端模拟测试。
30情景×3组离线基准汇总保持不变。基准不评估模型措辞，不能据此宣称真实回答已全部修复。没有付费模型调用。原始失败记录和评分不修改。

## 安装

解压至Downloads，停止CLI/Web，在luresense-agent根目录执行：

```bash
python3 ~/Downloads/LureSense_context_guard_fix/apply_fix.py
python3 -m unittest discover -s tests -v
```

脚本校验第二轮基线并备份到runs/phase1_fix_backup_时间戳；冲突时不要强制覆盖。依赖第二轮的observation_policy.py，不能跳过第二轮直接安装本包。

## 真实复测

```bash
mkdir -p runs/phase3_01
python3 agent_v03.py --mode rag --base-url "https://api.openai.com/v1" --model "gpt-4.1-mini" --api-key-prompt --query "我在湖泊岸边，没有观察到水草、倒木或岩石，应该先看什么？" --save runs/phase3_01/context_guard_01.json
```

依次/new输入：
1. 我在水库岸边，看到一片倒木，应该先观察什么？——确认上一轮规则仍有效。
2. 我在湖泊岸边，看到水草，应该先观察哪里？——回答后/cover选0，检查撤回。
3. 大口黑鲈幼鱼和成鱼吃的东西一样吗？——保留成鱼适用条件与幼鱼缺口。
最后/exit。

首题允许模型直接给出合理拒答或谨慎有据回答；若生成冲突被拦截，必须记录为系统拦截成功、模型原答失败，不能记作模型答对。若模型本次没有冲突，不能由此证明拦截已在真实调用中触发。

```bash
python3 review_runs.py prepare --run runs/phase3_01/context_guard_01.json --out runs/phase3_01/review_context_guard_01.json
```

上传两个JSON继续评分。不为得到“通过”而重复请求。评分沿用原口径，同时在note区分模型输出、观察规则和冲突拦截。

## 回滚与提交

回滚前保存安装后的其他编辑，将备份context_agent.py恢复；新增文件可移出项目。
完成验证后只提交本轮文件：

```bash
git diff --check
git add context_agent.py context_guard.py tests/test_context_guard.py docs/CONTEXT_GUARD_GUIDE.md
git diff --cached --stat
git commit -m "fix: guard against unsupported absence of observed structures"
git push origin main
```

先确认当前分支main，不提交runs目录。
