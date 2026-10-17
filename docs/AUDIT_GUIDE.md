# 原始模型与最终输出审计

## 用途
补充人工评分：review_runs.py判断主张是否获支持；audit_runs.py只统计处理来源、状态转换和用量，不自动判定语义正确。原始模型声明answered不是准确率；拦截次数也不是拦截正确率。

## 安装与使用
在项目根目录：
```bash
python3 ~/Downloads/LureSense_audit_fix/apply_fix.py
python3 -m unittest discover -s tests -v
python3 audit_runs.py --run runs/phase5_01/presence_01.json --out runs/phase5_01/audit_presence_01.json
```
预期161个测试通过。输出已存在时不会覆盖，换新文件名即可，不用重跑模型。

也可输入多个日志：
```bash
python3 audit_runs.py --run runs/phase4_01/variants_01.json runs/phase5_01/presence_01.json --out runs/audit_development_01.json
```
不同轮次不是独立随机样本，不可拿混合比例当模型整体能力。重复文件按内容哈希拒绝；不能识别不同导出文件中部分重复的会话，使用者应避免重复纳入。

## 字段说明
- attempted_requests：真实记录中明确标记的请求尝试数；包含失败尝试。
- received_model_responses：明确收到模型文本的记录数；不代表JSON或证据校验通过。
- original_declared_status_counts：优先使用拦截或规范前保留的回答，否则解析raw_response；没有可读原始回答记unknown，不用最终结果推测。
- final_status_counts：实际输出状态，error与insufficient_evidence分别统计。
- guard_interceptions：存在context_guard_v1标记及冲突记录的次数。
- policy_rewrites：reviewed_observation_policy_v1规范表达次数。
- interception_rate_on_received：拦截数/收到模型响应数，分母0时null；是处理比例，不是准确率。
- rows_without_known_tokens：用量缺失的记录数，不擅自填0；known_total_tokens_sum只求和已知用量。
- synthetic_or_unknown_rows：模拟或没有明确真实来源的记录，保留明细但不计入真实汇总。

## 已有记录验证
presence_01：2次尝试、2次响应；原始声明answered两条；最终answered一条、insufficient_evidence一条；规则拦截一条、观察规范一条；已知tokens4159。无需重新调用模型。

## 面试定位
建议名称：LureSense：带有限澄清与证据约束的状态化RAG助手。

已实现：规则路由、条件槽位及修改、有限追问/请求预算、检索、引用结构检查、有限上下文冲突规则、Web/CLI、日志、人工评分和过程审计。
尚未实现：模型自主任务分解、动态工具选择、多工具执行规划、长期记忆、现场视觉或生态预测。适合讨论Agent工程基础，不应声称通用自主Agent。

演示顺序：
1. 提问并澄清，显示条件状态。
2. 修改/撤回条件，展示旧条件失效。
3. 解释来源事实、项目推断及适用限制。
4. 用保存的presence_01展示一次真实模型错误和规则拦截，不反复调用模型碰结果。
5. 对照人工评分与过程审计，说明不能把规则改写效果算成模型提升。

后续先完成全新目录克隆与README验收、浏览器视觉验收、演示录像。若进一步扩展Agent能力，再单独设计一个有明确价值、失败处理和评估的真实工具任务。

## Git提交
```bash
git add -- audit_runs.py tests/test_audit_runs.py docs/AUDIT_GUIDE.md
git diff --cached --stat
git diff --cached --check
git commit -m "feat: audit model outputs and rule interventions"
git push origin main
```
确认当前main及暂存内容。不要暂存runs审计输出或密钥。
