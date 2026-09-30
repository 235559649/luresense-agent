# Phase 1 修复与复测指南

基于 source_before_fix_20260929_180909.zip。此包包含两个运行文件的替换、12项新增回归测试及本说明。旧日志与知识卡不修改。

## 修改内容

- context_agent.py：识别“先观察／先留意”；knowledge任务也保存明确的现场自述，概念提问不自动变成现场事实。
- 新增effective_question：保留原问题于日志，向模型发送屏蔽已修改条件词及旧温度读数的问题。knowledge路由的检索也使用更新后的问题和当前条件。
- 明确的“没有观察到水草、倒木或岩石”记录为未观察到。混合、假设、复杂否定继续保守处理，不声称通用自然语言理解。
- 提示词要求比较问题只回答证据覆盖的部分，说明缺口，避免将观察候选升级为排序或强制要求。
- 拒答增加现场数据缺口或证据不足说明；不在缺少资料时强制调用模型。
- retriever.py：补充“吃的东西／吃些什么／以什么为食”以及“越深”等概念表达。成鱼食性资料不代表已有幼鱼比较证据。

## 验证结果与限制

修改前102项、修改后114项单元测试通过（Python 3.12）。新增测试使用本地模拟客户端验证请求内容，不是实际模型生成结果。
30情景×3组基准的summary指标完全一致。旧数据未覆盖本次新表达，因此无指标提升不等于修复无效。完整修改前后报告在压缩包reports目录。

| 方法 | Hit@4 n=19 | Recall@4 n=19 | MRR@4 n=19 | 负例空检索率 n=11 | 失效词移除率 n=6 | 状态匹配率 |
| --- | --- | --- | --- | --- | --- | --- |
| direct | .737 | .684 | .535 | .818 | .000 | null, n=0 |
| append_context | 1.000 | .947 | .877 | .636 | .000 | null, n=0 |
| agent_state | 1.000 | 1.000 | .842 | 1.000 | 1.000 | 1.000, n=16 |

没有发起真实模型调用，没有重新核验网页来源，没有新增幼鱼知识；来源锚点校验仍不等于语义支持校验。P12/P14生成措辞和P11部分回答能力必须实际复测。P13弱相关资料排序没有在本次重构；复杂否定仍可能需要选择确认。原app_version保持0.3-step3，版本比较应使用代码和提示词哈希。

## 安装

退出正在运行的CLI/Web进程。下载ZIP至Downloads并解压，保持目录名称LureSense_phase1_fix。
在项目根目录执行：

```bash
python3 ~/Downloads/LureSense_phase1_fix/apply_fix.py
python3 -m unittest discover -s tests -v
```

脚本先核对当前文件是否与上传版本相同；有冲突会在写入前停止。备份位于runs/phase1_fix_backup_时间戳。不会修改旧评分记录或自动提交Git。

## 离线验证

```bash
python3 benchmark_v05.py --split dev --out runs/phase1_fix_01/eval_dev
python3 benchmark_v05.py --split challenge --out runs/phase1_fix_01/eval_challenge
```

输出目录已存在时改用新后缀，不覆盖旧结果。两个基准都应显示模型调用0次。

## 真实复测

```bash
mkdir -p runs/phase1_fix_01
python3 agent_v03.py --mode rag --base-url "https://api.openai.com/v1" --model "gpt-4.1-mini" --api-key-prompt --query "大口黑鲈幼鱼和成鱼吃的东西一样吗？" --save runs/phase1_fix_01/batch03_after.json
```

保留第一次结果。每题之间输入/new，不要为了通过反复/retry。

1. P11：上面的食性问题应召回K004，并在配置正常时尝试模型请求；只凭成鱼资料不能完整比较幼鱼。
2. P12：我在水库岸边，看到一片倒木，应该先观察什么？——检查site路由及水库、倒木状态。
3. P13：我在湖泊岸边，没有观察到水草、倒木或岩石，应该先看什么？——检查未观察到状态，不应把这些结构视为存在。
4. P14：我在湖泊岸边，看到水草，应该先观察哪里？——首次回答后/cover选择0。检查cover=unknown、检索不含水草、effective_question中旧词被屏蔽。回答也必须承认未知；若仍假定水草存在，保留为生成失败。
5. P15：我在一个没有名字的池塘边，你能告诉我此刻水下两米处的准确水温吗？——检查池塘记录、拒绝编造数值、说明测量数据缺口。
6. /exit保存。然后生成评分文件：

```bash
python3 review_runs.py prepare --run runs/phase1_fix_01/batch03_after.json --out runs/phase1_fix_01/review_batch03_after.json
```

上传这两个JSON继续人工评分。不要将建议答案写进原始日志。

## 提交

本地验证和人工复测完成后，检查diff，再仅提交本次4个文件：

```bash
git diff --check
git diff -- context_agent.py retriever.py
git add context_agent.py retriever.py tests/test_phase1_repairs.py docs/PHASE1_FIX_GUIDE.md
git diff --cached --stat
git commit -m "fix: preserve current context and improve retrieval paraphrases"
git push origin main
```

使用main前确认当前分支确实为main。不要把runs备份和模型日志提交到仓库。

## 回滚

备份目录中context_agent.py与retriever.py是原文件。需要回滚时，停止服务，将它们复制回项目根目录。新增测试与文档没有覆盖旧文件，可移出项目。随后运行原102项测试。若修复后又做了其他编辑，先保存这些新修改。
