# v0.5.2 河流表达召回与检索解释

## 前提与改动

先安装并验收 v0.5.1。本包覆盖 retriever.py，新增 tests/test_retrieval_explanations.py。
若有个人修改，先保存并比较差异。本包不修改 context_agent.py、知识卡、场景标注或模型提示词。

S08/S13最终状态都是河流、岩石；原检索器只认识岩石，漏掉K005。
K005已有“溪流常年水潭及大河静水回湾”表述，故增加river_habitat概念映射：
河流、河边、河岸、溪流、大河、回湾。只根据现有卡片匹配，不把河流查询扩展成所有湖泊主题。
这些词用于检索关联，不表示它们具有完全相同的生态条件。
K005仍保留常年水潭、静水回湾等限定，不能据此认定任意河流存在目标鱼。

## 新增可解释字段

每条检索结果新增 retrieval_score 与 score_components。
score_components区分exact_id、exact_tag、concept，保存points、query_terms、card_terms。
各组件分数之和等于retrieval_score；重复查询词不重复加分。
原分数权重、4条返回上限和相同分数按卡片ID排序的规则保持不变。
这些是规则匹配分数，不是置信度、相关概率或事实正确程度。
字段保存在检索JSON与会话导出的证据中；本轮没有新增网页评分面板。

## 安装与测试

```bash
cd "/Users/zhangyuhang/Desktop/LureSense/LureSense/luresense-agent"
git status --short
unzip -o "$HOME/Downloads/LureSense_retrieval_v052.zip" -d "$HOME/Downloads"
cp -R "$HOME/Downloads/LureSense_retrieval_v052/." .
python3 -m unittest discover -s tests -v
python3 benchmark_v05.py --split dev --out runs/eval_v052_dev_01
python3 benchmark_v05.py --split challenge --out runs/eval_v052_challenge_01
```

完整历史代码预期102项测试通过；新输出目录不能已存在。所有实验不需要Key。
本次验证环境Python 3.12，尚未执行用户Mac浏览器操作、真实模型或远程Actions。

## 查看匹配解释

```bash
python3 app.py --query "河流 岩石" --json
```

在K005结果中查找concept=river_habitat，查看query_terms和card_terms的关系。
河流岩石查询现在召回K003、K005、K011；这只是候选资料，不是现场结论。

## 实测结果

相同数据与标注，全量Recall@4（n=19）：
- direct：0.658 → 0.684
- append_context：0.921 → 0.947
- agent_state：0.947 → 1.000

Agent的Hit@4、MRR@4、负例空检索率、失效词移除率、状态匹配率不变。
S08/S13的Agent Recall@4均从0.5变为1；S26的direct召回也改善。
90条方法结果中5条变化，其余85条不变；详情见reports/retrieval_v052/COMPARISON.md。
已有标签用于开发，不是盲测；下一轮应增加未用于调试的表达和实际使用问题。
S10/S11的拼接组失败继续保留，避免改写基线以隐藏其局限。

## 网页验收

停止旧服务并运行python3 web_app.py，刷新网页，开始新会话。
1. 输入“我在河流，看到岩石，应该先找哪里？”：候选资料应包括K003和K005。
2. 输入“我在湖泊，看到水草，怎么选钓位？”后把条件改成河流、岩石：新检索应包括K005，查询不再保留旧湖泊、水草条件。
3. 模糊问题两项都选不知道：仍保留未知，不猜测河流或岩石。
4. 导出JSON：检索证据中的score_components应保留匹配解释。

## 提交main

确认当前分支为main，检查差异后提交；本包未替用户推送。

```bash
git branch --show-current
git add retriever.py tests/test_retrieval_explanations.py docs/V052_GUIDE.md reports/retrieval_v052
git diff --cached --stat
git commit -m "feat: add river habitat retrieval and scoring explanations"
git push origin main
```
