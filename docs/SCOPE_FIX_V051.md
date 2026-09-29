# v0.5.1 范围否定修复：安装与验收

## 改动

覆盖 retriever.py、context_agent.py，新增 tests/test_scope_negation.py。
路由和检索共用 has_out_of_scope；仅完整、明确的否定分句可排除范围外词。
例如“我不是在海边，我在湖泊，看到水草，应该先看哪里？”现在按现场问题处理。
逐分句检查，因此否定一个词不会掩盖另一个肯定的范围外条件。
疑问、双重否定、假设、比较、复杂嵌套仍保守拦截；本补丁不是通用中文语义理解。
不修改知识库、检索排序、场景标注或模型提示词。

## 安装

适用于已合并 v03 step3、v04、v05 的项目。本补丁基于用户报告中的代码哈希。
若自行修改过这两个文件，先比较差异，勿直接覆盖个人改动。
在项目中运行 git status --short，保存未提交代码后安装。

```bash
cd "/Users/zhangyuhang/Desktop/LureSense/LureSense/luresense-agent"
unzip -o "$HOME/Downloads/LureSense_scope_fix_v051.zip" -d "$HOME/Downloads"
cp -R "$HOME/Downloads/LureSense_scope_fix_v051/." .
python3 -m unittest discover -s tests -v
python3 benchmark_v05.py --split dev --out runs/eval_v051_dev_01
python3 benchmark_v05.py --split challenge --out runs/eval_v051_challenge_01
```

输出目录须不存在；重复执行时换后缀。完整历史版本预期94项测试通过。
本次在 Python 3.12 本地验证，未运行远程 GitHub Actions、浏览器点击或真实模型调用。

## 前后实验

包内 reports/scope_fix_v051 保留 before_all、after_all、after_dev、after_challenge。
每份含 REPORT.md 和 results.json；后者保存场景快照、逐案例结果、代码及数据哈希。
30个场景中仅S30三组结果变化，其他29个场景逐行结果不变。
共享检索器修复同时作用于direct和append_context，不能把提升全归因于Agent。

| 全量指标 | direct 修复前→后 | append_context 修复前→后 | agent_state 修复前→后 | n |
|---|---|---|---|---|
| Hit@4 | .684→.737 | .947→1.000 | .947→1.000 | 19 |
| Recall@4 | .605→.658 | .868→.921 | .895→.947 | 19 |
| MRR@4 | .509→.535 | .825→.877 | .816→.842 | 19 |
| 负例空检索率 | .818→.818 | .636→.636 | 1.000→1.000 | 11 |
| 失效词移除率 | 0→0 | 0→0 | 1.000→1.000 | 6 |
| 状态匹配率 | 不适用 | 不适用 | .938→1.000 | 16（仅Agent） |

仅适用于人工构造的离线场景，不代表模型回答正确率。开发集不变。
S10的agent_state原本已通过；拼接基线的未知字段误命中仍保留。
S08、S13在最终“河流、岩石”条件下均找到K003、K011，漏标注相关卡K005。
它们属于后续检索及标注复核任务，本补丁不为了提高分数添加无差别检索词。

## 网页验收

停止旧服务，重新运行 python3 web_app.py，刷新网页并开始新会话。
1. 输入S30原问题：应识别湖泊、水草，进入候选证据流程，不再判范围外。
2. 输入“我在海边，怎么钓？”：仍应提示范围不适用。
3. 输入“我不在海边，应该先看哪里？”：应询问水域，不把否定海边等同于确认湖泊。
4. 输入“我不在海边，但是这里是海水，怎么钓？”：仍应提示范围不适用。

## 提交 main

确认 git branch --show-current 为 main，检查暂存差异后提交。

```bash
git add retriever.py context_agent.py tests/test_scope_negation.py docs/SCOPE_FIX_V051.md reports/scope_fix_v051
git diff --cached --stat
git commit -m "fix: share conservative negation-aware scope checks"
git push origin main
```
