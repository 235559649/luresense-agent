# LureSense Web v0.4：安装、验证与演示

这是 v3 核心之上的增量模块，不是整仓替换。目标是让面试官看到“提问—补充条件—检索—回答与证据—修改条件—导出评估”的完整流程。

## 1. 安装到现有仓库

需要 Python 3.10+（推荐继续使用你已有的 Python 3.11 环境），没有新增第三方运行依赖。必须已安装 v03 step3；根目录应包含 context_agent.py、agent_v03.py、grounding.py、review_runs.py、retriever.py、llm.py，以及 data/knowledge_cards.json 和 data/sources.json。

将下载的 LureSense_web_v04.zip 放到 Downloads，在终端执行：

```bash
cd "/Users/zhangyuhang/Desktop/LureSense/LureSense/luresense-agent"
python3 -c "from context_agent import ContextSession, respond, session_record; import grounding, review_runs"
unzip -o "$HOME/Downloads/LureSense_web_v04.zip" -d "$HOME/Downloads"
cp -R "$HOME/Downloads/LureSense_web_v04/." .
python3 -m unittest discover -s tests -v
python3 web_app.py
```

如果第一条 Python 检查失败，先安装上次的 v03 step3 增量包，不要用 v02 的旧核心替代。完整历史测试集合应为 76 项（原有 66 项，新增 Web 测试 10 项）；你自己新增的测试会改变总数。

浏览器打开 http://127.0.0.1:8765 。模拟模式只展示候选证据，不生成模型建议。按 Ctrl+C 停止服务；端口占用可运行 `python3 web_app.py --port 8766`。

## 2. 接入已经用过的模型

先停止模拟服务，再运行：

```bash
python3 web_app.py --mode rag --model gpt-4.1-mini --api-key-prompt
```

这沿用你此前成功运行的模型名称；是否仍可用取决于你的账号与服务端。默认地址为 https://api.openai.com/v1 。也可通过 `--base-url` 指定兼容地址，必须使用普通 URL，不要粘贴 Markdown 链接格式。

Key 在终端隐藏输入，仅存在后端进程内存，不放入网页、导出文件或仓库。也支持既有 MODEL_NAME、MODEL_BASE_URL、MODEL_API_KEY 环境变量；不自动读取 .env。真实模式启动时检查配置，但只有满足条件的回答请求才调用模型。

每个会话最多 3 次模型请求，失败也计数；修改条件可能触发新请求。新问题创建新会话，预算重新计数，因此这不是整个进程的费用上限。

## 3. 三个演示场景

| 操作 | 应看到什么 | 可解释的工程点 |
| --- | --- | --- |
| 问“我在淡水边，应该先看哪里？”，选择湖泊、水草和倒木 | 两项追问结束，出现候选资料或真实回答 | 规则控制澄清，区分未知与已提供条件 |
| 把右侧可见结构改为“未观察到上述结构” | 条件标记已修改，旧答案替换，处理过程追加一条记录 | 状态更新影响重新检索，避免沿用旧条件 |
| 开新问题，同样模糊提问，两项均选“不知道” | 证据不足，不请求模型 | 证据门控与有限调用预算 |

另可演示“气温能直接代替水温吗？”：知识问答不强制补齐现场条件。

右侧处理过程展示程序事件，不是模型隐含思维链。真实输出中的“来源事实”是模型声明的类别，不代表自动核验通过；引用检查只验证编号、字段与卡片摘录，结论是否被证据支持仍需人工判断。

## 4. 导出与评估

点击“导出 JSON”，浏览器下载当前会话完整记录，包括每次回答和证据。复制到仓库 runs/ 后，可以沿用 v3 评估工具：

```bash
mkdir -p runs
# 将下载记录复制到 runs/web_demo_01.json 后执行
python3 review_runs.py prepare --run runs/web_demo_01.json --out runs/web_review_01.json
# 按 docs/REVIEW_RUBRIC.md 人工填写评审字段后
python3 review_runs.py summarize --review runs/web_review_01.json
```

评估源文件须留在原位置且不修改，因为评审文件记录绝对路径及哈希。模拟记录不能作为真实模型质量指标。

当前会话只在服务器内存；最多 20 个会话。刷新页面会丢失页面当前会话入口，重启服务会清空全部会话。需要保留的记录先导出。文件中会有用户问题、条件与模型响应，提交样例前检查内容。

## 5. 文件职责

| 文件 | 职责 |
| --- | --- |
| web_app.py | 本机 HTTP 服务、会话生命周期、串行状态更新、调用已有核心、JSON 导出 |
| web/index.html | 问题、追问、答案、来源、当前条件、事件区 |
| web/app.js | 页面交互与纯文本渲染；不存 API Key |
| web/style.css | 桌面/窄屏布局 |
| tests/test_web_app.py | 10 项服务和 HTTP 回归测试 |
| docs/PORTFOLIO_DEMO.md | 面试讲解要点与下一阶段实验 |

API：GET /api/config；POST /api/start {question}；POST /api/choose {session_id,slot,choice}；POST /api/export {session_id}。POST 使用配置接口返回的本机请求令牌。服务仅绑定 127.0.0.1，静态资源使用允许列表，输出按文本渲染。

它是单用户本地演示服务，没有账号、持久化数据库或生产部署设计；不要直接改成公网监听。

## 6. 提交到 main

先停止服务，确认当前分支和变更：

```bash
git branch --show-current
git status --short
git diff --stat
```

确认是你指定的 main 分支后，仅提交本轮新增文件：

```bash
git add web_app.py web/index.html web/app.js web/style.css tests/test_web_app.py docs/WEB_DEMO_GUIDE.md docs/PORTFOLIO_DEMO.md
git diff --cached --stat
git commit -m "feat: add local web demo for contextual RAG and evidence review"
git push origin main
```

不要使用 git add . 把个人运行记录、密钥或其他课程作业一并提交。

## 本次验证范围

在 Python 3.12 环境下合并既有 v02、v03 step1、v03 step3 与本轮文件，76 项 unittest 全部通过；JavaScript 通过 Node 语法检查。测试包含真实本机 HTTP 请求，模型交互测试使用替身。

本次未调用真实付费模型，也未完成浏览器视觉验收：执行环境没有可运行的 Chromium，下载失败。因此请在你的 Mac 上按第 3 节检查页面、下拉修正和下载按钮；这轮测试结果不包含浏览器交互通过的声明。
