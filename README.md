# LureSense RAG v0.2

日期：2026-09-22。沿用22张知识卡和8个来源，增加固定RAG、引用检查和可配置模型接口。

**新用户先运行mock模式，再配置真实模型。** 模拟模式只摘录资料，绝不代表真实大模型效果。当前还没有动态Agent、天气、图片或多轮记忆。

## 1. 解压与运行

需要Python 3.11或以上，没有第三方依赖。打开终端，输入 `cd `，将解压的 `LureSense_RAG_v02` 文件夹拖入终端后回车。

```bash
python3 --version
python3 app.py --mode mock --query "大口黑鲈吃什么？"
```

应该显示“模拟模式：规则摘录，未调用大模型”，随后是带K编号的资料和来源。

保留原来的纯检索方式：

```bash
python3 app.py --mode retrieve --query "水草附近可以先了解什么？"
```

## 2. 接入真实模型

准备支持Chat Completions接口、JSON object模式及max_completion_tokens参数的模型账户。填写你账户中真实可用的模型ID，不能照抄占位词。默认基础URL为OpenAI API；如使用其他兼容服务，先根据该服务官方文档核实地址与参数支持，兼容性尚未逐家验证。

```bash
python3 app.py --mode rag --model "填写实际模型ID" --api-key-prompt --query "大口黑鲈吃什么？"
```

命令会在本机隐藏询问API Key；输入后不显示字符属于正常现象。不要把密钥发到聊天中。真实请求会把你的问题和命中卡片发送给配置的模型服务。不要在--model中放密钥。

其他基础URL示例结构（占位地址不可直接使用）：

```bash
python3 app.py --mode rag --base-url "https://你的服务域名/v1" --model "实际模型ID" --api-key-prompt --query "水草附近可以先了解什么？"
```

也支持环境变量MODEL_NAME、MODEL_API_KEY、MODEL_BASE_URL；不会自动读取.env文件。凭据不保存到结果文件。

本次没有用户的模型账户，因此**真实付费接口尚未联调**。HTTP400可能是服务不支持当前参数；401通常需要核对认证；429需要核对限流或配额。错误仅显示状态，不回显服务错误正文。请求不自动重试，避免重复付费。

## 3. 保存第一条实验记录

```bash
python3 app.py --mode mock --query "气温能代替水温吗？" --save first_mock_run.json
```

真实模式同样加--save，建议每题用不同文件名。记录包含问题、回答、检索ID、来源、模式标志、模型名称、用量（如果返回）、耗时、提示词/知识/源码哈希。已有文件不会覆盖。API失败或输出校验失败不会生成成功记录，须将失败另外记入实验总数，不能从分母悄悄删除。

## 4. 这版增加什么

| 文件 | 作用 |
| --- | --- |
| retriever.py | 原关键词检索 |
| llm.py | HTTPS模型请求、超时和错误处理 |
| rag.py | 组织证据、校验JSON和引用、渲染来源、保存运行记录 |
| app.py | retrieve/mock/rag三个模式 |
| evaluate_retrieval.py | 开发题的参考卡片覆盖检查 |
| tests/test_rag.py | 模拟响应和校验测试 |
| RESEARCH_ROADMAP.md | 如何形成研究问题、基线、消融和报告 |

## 5. 测试与小型检索检查

```bash
python3 -m unittest discover -s tests -v
python3 evaluate_retrieval.py
```

24项软件测试通过。覆盖模型响应格式错误、伪造引用、未检索卡片、接口错误、缺失配置、截断、来源保留、记录防覆盖等。模型请求测试使用模拟响应，并未调用真实模型。

6个有参考卡片的开发题中，参考覆盖均值83.3%；详细结果见eval/retrieval_pilot.json。不能称为RAG准确率或生态预测准确率。其余4题无参考卡，不纳入此检索指标。

## 6. 必须理解的限制

- 引用ID合法检查不会判断“这条资料是否真的支持这句话”；保留了测试来明确这一盲区。
- 某些OpenAI兼容服务的参数不同，首次真实调用才可核实该服务兼容性。
- 单轮RAG没有多轮事实状态，即使模型返回追问，后续回答也不会自动合并上下文；这是下一阶段任务。
- 真实模式出错不会静默切成mock伪装成功。
- 关键词检索不理解复杂否定和比较，照片/天气没有接入。

## 7. 接下来一周

1. 运行retrieve和mock，各保存一条记录。
2. 读WALKTHROUGH，能解释每个模块的职责。
3. 配置模型，跑5个开发题，并手工核对引用和结论。
4. 保留成功、拒答、失败，别只截图最好的回答。
5. 真实基线稳定后，再实现RESEARCH_ROADMAP中的主动澄清机制。

接口依据：https://developers.openai.com/api/reference/resources/chat 。当前适配限定Chat Completions请求格式，不保证所有模型供应商支持。
