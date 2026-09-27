# 第三版第二步：条件进入检索与模型回答

日期：2026-09-27。增量开发包，依赖第二版的retriever.py、rag.py、llm.py、data/。不需要第一步代码才能运行；如果已经安装第一步，也可同时保留。

## 本次交付

- agent_v03.py：新的交互入口，默认mock；rag显式调用模型。
- context_agent.py：任务规则路由、有限条件提取、状态、检索、模型消息、预算、日志。
- tests/test_context_agent.py：17项新增离线测试。
- 本说明与V03_STEP2_ACCEPTANCE.md：安装、验收和对照步骤。

原app.py保持第二版流程；agent_cli.py保持第三版第一步流程。请使用新的agent_v03.py运行这一步，不要混淆入口。

## 安装

解压后将两个根目录Python文件放到现有app.py旁；将新增测试放入tests/；将两份说明放入docs/。合并目录内容，不替换整个tests/或docs/。无新增第三方依赖。

```bash
cd "/Users/zhangyuhang/Desktop/LureSense/LureSense/luresense-agent"
python3 -m unittest discover -s tests -v
mkdir -p runs
python3 agent_v03.py --mode mock --save runs/v03_step2_mock_01.json
```

如果已经安装第一步，共49项测试；只在第二版上加本包则为41项。两种情况都应显示OK。

## 离线体验

默认模糊问题先选1湖泊，再选4水草和倒木，显示候选资料。/cover后选5，检索关键词删除旧的水草/倒木。/water修改水域；/temperature修改温度来源；/new新问题；/exit退出。

初始条件完整时跳过追问：

```bash
python3 agent_v03.py --mode mock --query "我在湖泊，看到水草和倒木，应该先看哪里？"
```

简单知识题不要求现场条件：

```bash
python3 agent_v03.py --mode mock --query "大口黑鲈吃什么？"
```

mock仅展示资料，claims为空、synthetic=true。不是模拟出一条大模型回答，更不能作真实效果数据。

## 接入已在第二版跑通的模型

```bash
python3 agent_v03.py --mode rag --base-url "https://api.openai.com/v1" --model "gpt-4.1-mini" --api-key-prompt --query "我在淡水边，应该先看哪里？" --save runs/v03_step2_real_01.json
```

先完成条件选择。有证据时才隐藏询问API Key；没有证据时不读取密钥也不请求模型。同一进程复用客户端，密钥不写入日志。支持MODEL_NAME、MODEL_BASE_URL、MODEL_API_KEY，不自动读取.env。

每个会话最多2项自动追问、3次模型请求（含网络/格式失败）；手动修改和/retry可触发新请求，占同一预算。/new创建新会话并重置该会话预算，因此一个进程总调用数可能超过3。配置缺失发生在请求前，不计模型请求。不会自动重试。

退出时保存本次进程的所有会话，包含未完成状态、每次条件变更、各次回答/失败、引用证据、使用量、延迟及代码/知识/提示词哈希。路径存在时在任何请求前拒绝，不覆盖原结果。须正常退出才能保存；不是崩溃恢复或持久会话续接。

## 输出与日志含义

日志顶层是sessions数组，不再直接在顶层读取mode/model_called。每个会话events中event=response的result记录一次处理。

- request_attempted：客户端是否已发起调用尝试；不证明模型服务完成推理或计费。
- model_response_received：客户端是否获得完整文本响应。
- status=answered：结构和引用编号检查通过，语义支持仍需人工核对。
- status=error：接口或格式失败；返回的usage若可用仍保留。
- status=budget_exhausted：预算耗尽，本次没有请求。
- status=evidence_only：mock候选资料。
- status=insufficient_evidence：无资料、范围不适用或模型判断不足；结合request_attempted区别。
- model_latency_seconds：模型客户端调用耗时，不包括手动输入密钥；elapsed_seconds首轮可能包括输入密钥的等待，不适合直接比较模型延迟。

兼容字段model_called等同本次请求尝试，失败时也可能true。判断成功不能只看这个字段。日志不保存供应商原始错误正文或未通过校验的原始生成文本，因此还不是完整的所有响应存档。

## 条件提取与纠错的实际边界

本次采用中文关键词白名单和简单规则，不是通用语言理解。能识别湖泊/湖边/湖岸、水库、河流/河边、池塘，以及水草、倒木、岩石/石块等明确表述。含否定、可能、如果、或者的相关片段保守地不提取，请用户确认；复杂跨句假设、比较和范围表达仍可能误判。

界面会展示条件，误判时用编号修改。新自由文本问题用/new；暂不支持直接说“刚才说错了”来自动改口。

温度目前只追踪气温/水温/两者/未知；可以识别部分带标签数字表述，但不结构化保存或校验温度数值、单位、测量深度与时间，不计算最佳温度。数字仍作为原问题文本传给模型。

现场建议的检索查询由主题与当前已知条件构建，旧条件不会作为检索词回流；原始问题仍单独传给模型作为历史输入，并通过提示词要求以最新状态为准。这个优先级不是语义保证，需要检查实际输出。

现场问题的查询重构会损失某些细节（例如复杂钓饵偏好），路由也可能把不在白名单里的现场问法归为知识题。范围检查仍很保守，例如包含被否定的海水词也可能拒绝。地区与现场鱼种没有新验证机制。

## 与事实核查的区别

本次加强提示词：未知不能补造、用户自述不是实测、项目推断应标明、不要夸大资料强度。仍沿用第二版JSON与引用ID检查；它不能自动检验结论蕴含关系、生态正确性或地理可迁移性。结构化事实/推断输出和逐条证据评分留给第三步。

## 验证记录

合并第二版与第一步后，49项单元测试通过（24+8+17）。另验证5个CLI场景：知识直答、模糊补全并改口、条件完整、全部未知、/new多会话；均检查保存和重名拒绝。模型集成采用FakeClient，测试消息传递、引用拒绝、失败预算和用量保留。本次没有执行真实付费模型调用；第二版的成功调用不能代替本步提示词与流程的真实验收。

接口参考：https://developers.openai.com/api/docs/guides/structured-outputs 。仍使用JSON object模式和应用层校验，并未宣称已切换为严格JSON Schema或语义校验。

## 提交

按你的选择，直接提交到main。先执行git branch --show-current确认当前为main；如在其他分支，先检查git status并保留工作，再切换，不使用强制切换。不要覆盖或移动v0.2.0标签。

```bash
git branch --show-current
git add agent_v03.py context_agent.py tests/test_context_agent.py docs/V03_STEP2_GUIDE.md docs/V03_STEP2_ACCEPTANCE.md
git diff --cached --stat
git commit -m "feat: add context-aware generation with bounded clarification"
git push -u origin main
```

runs/继续忽略。第三版还没有完成科学评估，暂不打最终v0.3.0标签。
