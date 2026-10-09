# 第二轮：有限观察建议

基线：第一轮修复包；用户已推送main f610e81并通过CI。本轮仅修改context_agent.py，新增observation_policy.py与10项测试。

## 行为与边界

上一轮提示词已经限制措辞，但P12仍只有一般知识，P14仍出现“应重点观察”。本轮加强提示词，并为简单观察问题加入可审计的规则输出。

触发条件全部满足才应用：site任务；末句为有限白名单中的“应该先观察什么／哪里”等表达；结构是用户报告的水草、倒木、岩石或水草和倒木；本次确实检索到K003且claim和application_note与已核对版本相同；模型返回通过原证据契约校验的answered答案。

应用后输出两条主张：K003一般来源事实，以及“项目推断（规则生成）：根据你报告的X，可以把X作为观察候选”。建议只使用已确认结构，并说明自述未实测、结构不证明鱼存在、不支持位置排序或效果保证。

模型原始返回保留raw_response，解析后的原答额外存为model_answer_before_policy；answer_origin=reviewed_observation_policy_v1标识规则输出。无规则时answer_origin=model。模型仍只请求一次。错误、非法输出、拒答不会被规则伪装成成功；mock仍仅展示证据。用户撤回结构后规则不触发。

这是受限的混合工作流，不是通用语义核查，也不能宣称模型自身能力提高。统计最终显示答案时，要同时报告规则应用情况，并保留模型原答分析。一般来源事实可以列出其他结构，不表示现场存在；规则建议只列用户报告结构。

本轮不增加新生态来源、不修改知识库、检索、旧评估日志或评分。复杂问题继续原流程。规则白名单可能漏掉合理表达；超出范围不能承诺同样效果。

## 验证

124项单元测试通过，新增10项涵盖：事实-only转为建议、过强原答保留、四种结构、撤回、未知/否定、非观察任务、来源修改、拒答与错误、非法输出、mock及代码哈希。
30情景×3组离线基准汇总与基线一致，模型调用0次。完整前后报告位于包内reports。这些测试验证流程与规则行为，不等于真实模型评估；本轮未调用付费API。

## 安装

停止正在运行的CLI或Web。将包解压至Downloads，在项目根目录执行：

```bash
python3 ~/Downloads/LureSense_observation_fix/apply_fix.py
python3 -m unittest discover -s tests -v
```

安装脚本先校验旧版本、备份到runs/phase1_fix_backup_时间戳，再复制四个文件。冲突时停止，不强制覆盖。回滚时将备份里的context_agent.py复制回原位置，新增模块/测试/指南可移出项目；先保存后来进行的其他编辑。

## 复测：已见问题回归，不是盲测

```bash
mkdir -p runs/phase2_01
python3 agent_v03.py --mode rag --base-url "https://api.openai.com/v1" --model "gpt-4.1-mini" --api-key-prompt --query "我在水库岸边，看到一片倒木，应该先观察什么？" --save runs/phase2_01/observation_01.json
```

1. 首题应给倒木观察候选，显示规则生成；日志保留模型原答。
2. /new：我在湖泊岸边，看到水草，应该先观察哪里？建议不扩展到倒木、岩石，不出现观察排序。
3. /cover选择0：撤回后无规则候选，不恢复水草条件。
4. /new：我在湖泊岸边，没有观察到水草、倒木或岩石，应该先看什么？不应用规则，不假设结构存在。
5. /new：大口黑鲈幼鱼和成鱼吃的东西一样吗？保持知识问题流程，不应用观察规则。
6. /exit保存，然后：

```bash
python3 review_runs.py prepare --run runs/phase2_01/observation_01.json --out runs/phase2_01/review_observation_01.json
```

请上传两个JSON进行检查，不修改旧日志。完成后再追加未用于修复的新表达测试，单独记录。记录规则输出成功不等于原模型生成正确。

## 提交（本地复测后）

```bash
git diff --check
git add context_agent.py observation_policy.py tests/test_observation_policy.py docs/OBSERVATION_FIX_GUIDE.md
git diff --cached --stat
git commit -m "fix: add bounded and auditable observation suggestions"
git push origin main
```

提交前确认当前分支为main，暂存文件不包含runs。
