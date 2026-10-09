# Web收尾与GitHub提交

## 本轮修改和验证
- 拦截回答已有原因说明时，不再叠加通用证据不足长提示；保留条件修改提示。
- Web显示中文结果状态，明确区分回答、证据不足、条件冲突拦截和请求失败；失败时提示导出记录。
- 148个Python测试通过（含Web服务与HTTP测试），node --check web/app.js通过。
- 未执行浏览器视觉验收，未调用真实模型；没有部署到公网。

## 安装
在项目根目录执行：
```bash
python3 ~/Downloads/LureSense_web_handoff/apply_fix.py
python3 -m unittest discover -s tests -v
```
若安装器报告文件不同，保留本地修改，不要强制覆盖。

## Web验收
```bash
python3 web_app.py --mode mock --port 8765
```
打开 http://127.0.0.1:8765 。mock只验证交互，不评价模型回答质量。
- 输入“我在淡水边，应该先看哪里？”；确认追问可选择，页面没有卡死。
- 选择湖泊和水草，检查条件面板与结果更新。
- 将可见结构改为不知道，检查条件更新。
- 导出JSON；确认有sessions及事件记录。
- 重新提交新问题，确认没有继承上一问题的现场条件。

停止服务后，可启动真实模式：
```bash
python3 web_app.py --mode rag --model gpt-4.1-mini --base-url https://api.openai.com/v1 --api-key-prompt --port 8765
```
密钥只在终端隐藏输入。仅本机访问；关闭前导出。真实模型有调用成本，不要求反复测试。

## Git提交前检查
本包无法操作你的Mac仓库；以下命令在本地项目根目录运行。
```bash
git status --short --branch
git branch --show-current
git diff --stat
git remote -v
```
如果当前不是main且有未提交修改，先保留现状并提供输出，不要强行切分支。

将下列规则合并进已有.gitignore，不覆盖原规则：
```gitignore
.idea/
runs/
__pycache__/
*.py[cod]
.venv/
venv/
.env
.env.*
!.env.example
.DS_Store
```
.env.example只能放占位值。测试fixture应提交，不要全局忽略所有JSON或ZIP。

检查已被追踪的本地目录：
```bash
git ls-files -- .idea runs
```
只有确实不应入库时执行（保留磁盘文件）：
```bash
git rm -r --cached --ignore-unmatch -- .idea runs
```
忽略规则不会删除Git历史；若历史曾包含真实密钥，应另行处理泄露密钥。不要上传.env内容。

明确暂存这几轮修改：
```bash
git add -- .gitignore context_agent.py context_guard.py observation_policy.py retriever.py web/app.js tests/test_phase1_repairs.py tests/test_observation_policy.py tests/test_context_guard.py tests/test_context_variants.py tests/test_presence_guard.py tests/fixtures/unknown_cover_presence.json docs/PHASE1_FIX_GUIDE.md docs/OBSERVATION_FIX_GUIDE.md docs/CONTEXT_GUARD_GUIDE.md docs/CONTEXT_VARIANTS_GUIDE.md docs/PRESENCE_GUARD_GUIDE.md docs/WEB_HANDOFF.md docs/VALIDATION_CHECKPOINT.md
git diff --cached --stat
git diff --cached --name-only
git diff --cached --check
git diff --cached
```
文件路径不存在时停止，检查实际安装情况。确认暂存列表只包含代码、测试、文档和忽略规则；runs/.idea如出现只能是预期的删除记录。已有其他暂存内容也要检查。

在main上提交：
```bash
git commit -m "feat: harden context checks and clarify web results"
git push origin main
```
不要使用force。如果远端领先导致拒绝，保留错误输出后再处理。推送成功后到GitHub确认提交及已有CI检查结果。

## 本阶段退出条件
- 上述Web流程完成，导出可以进入review_runs.py prepare。
- 真实模型、规则输出、模拟测试明确区分。
- README可指导别人启动，GitHub源码与本地一致，CI结果可见。
下一轮补配置与启动文档、演示材料；有限规则和地域适用范围保留为已知局限。
