# LureSense

淡水大口黑鲈知识问答与现场观察助手。结合知识卡检索、有限条件澄清、引用结构校验和上下文规则检查，提供带来源与限制的回答。

这是可在本机运行的个人项目原型。不会预测鱼存在概率或保证中鱼率；没有接入图像识别、实时天气或可穿戴设备。

## 快速启动

需要 Python 3.11 或以上，无需安装第三方 Python 依赖。

### 1. 进入程序目录

在终端进入包含 `doctor.py`、`web_app.py` 和 `data/` 的目录。

例如，如果当前目录下的程序位于 `LureSense/luresense-agent/`：

```bash
cd LureSense/luresense-agent
```

如果已经位于该目录，无需再次执行 `cd`。

确认文件存在：

```bash
ls doctor.py web_app.py
```

后续命令均在此目录执行。

### 2. 检查环境

```bash
python3 doctor.py
```

### 3. 启动网页

```bash
python3 web_app.py --mode mock --port 8765
```

浏览器打开 http://127.0.0.1:8765 。

停止服务：在终端按 `Ctrl+C`。

> 使用 IDE 的 Markdown 快捷运行时，请将工作目录设置为仓库根目录。
> README 所在位置不会自动成为命令的工作目录。
## 真实模型模式

先做离线配置检查，再启动：

```bash
python3 doctor.py --mode rag --model gpt-4.1-mini --api-key-prompt
python3 web_app.py --mode rag --model gpt-4.1-mini --base-url "https://api.openai.com/v1" --api-key-prompt --port 8765
```

示例模型来自本项目已有运行记录，不保证所有账户可用。doctor 不联网、不验证密钥有效性或余额。模型服务必须兼容本项目使用的 Chat Completions JSON 请求。使用其他服务时须同时替换配套地址和模型名称。

密钥在终端隐藏输入，仅后端内存使用。问题和检索卡片会发送到配置的模型服务。支持 MODEL_NAME、MODEL_API_KEY、MODEL_BASE_URL 环境变量；不会自动读取 .env 文件。请勿把实际密钥提交到仓库。

## CLI 与评分

```bash
mkdir -p runs/demo
python3 agent_v03.py --mode rag --model gpt-4.1-mini --api-key-prompt --query "我在湖泊岸边，看到倒木，应该先观察哪里？" --save runs/demo/session_01.json
```

通过 /water、/cover、/temperature 修改条件，/new 开始新问题，/exit 保存退出。每个会话最多两项自动追问、三次模型请求（失败也计入）。已有保存文件不会覆盖。

```bash
python3 review_runs.py prepare --run runs/demo/session_01.json --out runs/demo/review_01.json
```

人工填写 reviewer、回答评分、claim_reviews 的 support 和理由；不改原回答、证据、编号和源日志。完成后：

```bash
python3 review_runs.py summarize --review runs/demo/review_01.json --out runs/demo/summary_01.json
```

网页导出的运行 JSON 也可作为 --run 输入。未评分或没有有效分母时不能解释为准确率。

## 测试与评估

```bash
python3 -m unittest discover -s tests -v
python3 benchmark_v05.py --split all --out runs/benchmark_checkpoint_01
```

基准输出目录须不存在。离线基准比较 direct、append_context、agent_state 的检索与状态指标，不调用真实模型，不能代替回答质量评估。测试数量与结果以当前版本的测试输出和 CI 记录为准。

真实开发案例及已知失败见 [评估检查点](docs/VALIDATION_CHECKPOINT.md)。这些是参与开发的少量案例，不是独立盲测。模型原始回答与规则处理后的最终回答必须区分：answer_origin、model_answer_before_policy、model_answer_before_guard 保留处理来源。

## 主要模块

| 文件 | 职责 |
|---|---|
| web_app.py / web/ | 本地Web服务和交互界面 |
| agent_v03.py / context_agent.py | CLI、路由、有限澄清和条件更新 |
| retriever.py / data/ | 关键词检索、知识卡及来源元数据 |
| llm.py / grounding.py | 模型接口及JSON、引用编号、知识卡摘录校验 |
| observation_policy.py / context_guard.py | 有限观察建议规范与条件冲突检查 |
| review_runs.py / benchmark_v05.py | 人工评分汇总和离线基准 |
| doctor.py | 不联网的启动前环境与配置检查 |
| audit_runs.py | 审计原始模型输出、规则拦截、策略改写与 Token 用量 |

## 已知局限

- 引用合法与摘录匹配不代表结论一定获得支持；仍需人工核查。
- 有限中文规则可能漏拦或误拦，不是通用语义验证。
- 地域、物种和生态适用范围可能在生成中遗漏；K005地域范围是已知改进项。
- 用户自述未经实测验证；观察候选不证明鱼存在。
- Web仅监听127.0.0.1，是本机演示，不是已完成公网部署的服务。
- 请求失败不伪装正常回答，不自动重试；费用和用量以服务商实际记录为准。

完整手工验收与Git提交步骤见 [Web收尾指南](docs/WEB_HANDOFF.md)。


### 上下文规则评估

使用固定的人工开发案例，评估上下文检查的正确拦截、
误拦与漏拦。无需联网，不调用模型。

```bash
mkdir -p runs/guard_eval
python3 evaluate_guard.py --out runs/guard_eval/dev_01.json
```

结果包含混淆矩阵、指标分母、失败案例，以及规则和数据集
的 SHA256。已有输出文件不会覆盖。

这些案例用于开发与回归检查，不是独立盲测；
指标不代表真实模型准确率或完整系统的回答质量。


## 架构、实验与演示

详见 [项目架构与实验说明](docs/PORTFOLIO_RELEASE.md)。

项目采用显式会话状态、有限澄清、知识卡检索、
引用结构校验和上下文规则，保留模型原始输出与规则处理记录。

支持离线模拟演示、人工评分、处理过程审计，
以及固定开发集上的规则版本比较。
开发集指标不代表真实模型准确率或独立盲测表现。