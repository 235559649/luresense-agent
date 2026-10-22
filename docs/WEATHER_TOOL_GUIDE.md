# 天气工具与知识流程集成（第一版）

## 新增能力

agent_tools.py 是新的单次 CLI 入口；通过有限规则判断是否查询当前天气，缺少经纬度时询问用户。普通知识问题和观察问题复用 ContextSession、检索、模型请求与输出检查。天气和知识结果分开显示、分开记录。

weather_tool.py 调用固定 Open-Meteo HTTPS 端点，最多尝试一次、不重试。显式请求摄氏度、km/h、mm 和 UTC 时间戳，校验字段、单位和时效（最多允许3小时陈旧、30分钟超前，这是项目阈值）。拒绝重定向、过大响应与非法坐标。mock 不联网，live 失败不使用模拟数值冒充成功。

天气是模型资料，不是现场实测；2米气温不是水温，10米风速不是岸边测得风速。返回网格坐标可能与请求坐标不同。区间降水不是全天降水。工具数据不能证明鱼存在或决定最佳钓位。

本版采用规则路由，不是模型 function calling，也没有自主多步规划。暂未改动网页；从 agent_tools.py 演示。天气结果尚未注入旧知识卡生成提示，静态证据与动态工具结果分别展示，不宣称天气提高了建议质量。

## 安装与验证

在原项目根目录运行安装器。安装器只增加文件，同名异内容会停止，不覆盖已有改动。

```bash
python3 ~/Downloads/LureSense_weather_tool/apply_weather.py
python3 -m unittest discover -s tests -v
mkdir -p runs/weather
```

如果此前168项测试均已安装，本轮预期总数184。也可单独运行：

```bash
python3 -m unittest discover -s tests -p 'test_weather_tool.py' -v
```

## 不联网演示

```bash
python3 agent_tools.py --query "查询当前天气和风速" --weather-mode mock --latitude 1.3521 --longitude 103.8198 --save runs/weather/mock_01.json
```

默认两种模式都是mock。上面的经纬度仅为新加坡区域演示坐标，不代表用户所在位置或钓点；模拟数值也是人工样例。

## 真实天气查询

```bash
python3 agent_tools.py --query "查询当前天气和风速" --weather-mode live --latitude 1.3521 --longitude 103.8198 --save runs/weather/live_01.json
```

该命令只调用天气服务，不调用LLM，不需要模型API密钥。live 会向Open-Meteo发送指定坐标；日志也保存坐标，公开日志前需检查隐私。访问受网络和服务状态影响；个人演示使用公共端点，扩大流量或商业化前应核对服务条款。

缺少坐标时会询问；没有地名解析，不推测所在地。输入非法值时停止。首版不支持明日、历史或指定日期天气；不会把当前值冒充未来预报。

## 天气＋已有观察流程

```bash
python3 agent_tools.py --query "我在湖泊看到倒木，应该先看哪里？" --with-weather --weather-mode live --latitude 1.3521 --longitude 103.8198 --mode mock --save runs/weather/combined_01.json
```

先输出真实天气，再展示观察问题的候选资料。水温仍未知；模型请求为0。

若要同时调用模型生成观察回答：

```bash
python3 agent_tools.py --query "我在湖泊看到倒木，应该先看哪里？" --with-weather --weather-mode live --latitude 1.3521 --longitude 103.8198 --mode rag --model gpt-4.1-mini --api-key-prompt --save runs/weather/combined_rag_01.json
```

此命令可能产生模型费用。天气结果没有发送给模型，模型仍仅依据原有知识卡和用户条件。普通知识问题如“大口黑鲈吃什么？”不会调用天气；“气温能代替水温吗？”走知识流程。

## 日志与评估

顶层 schema_version=tool-workflow-1；tool_events 保存工具状态，sessions 保存原有知识流程记录。

- request_attempted / response_received：请求是否尝试、是否收到可处理对象。
- synthetic：是否模拟数据。
- requested_location / grid_location：用户请求点与天气模型网格点。
- retrieved_at_utc / valid_at_utc：查询时刻与数据时刻。
- provider_payload / payload_sha256：服务响应与内容指纹。
- status=error 时 data=null，不把错误当零气温或零降水。

纯天气日志 sessions 为空，不能拿旧 review_runs.py 或 audit_runs.py 的知识回答指标来解释天气质量。混合日志的旧评分工具只能评价 sessions 中的知识回答，不能自动评价工具结果。工具可靠性由本轮单元测试和真实联通记录检查，尚无端到端质量提升实验。

## 本轮验证记录

- 新增16项离线测试通过，覆盖参数、模式、路由、错误、单位和时效。
- 在开发环境实际调用Open-Meteo成功一次；这是连通性验证，不证明长期可用。
- 模拟天气CLI和混合观察CLI已运行成功；未调用付费模型。
- 原网页保持原入口；本轮没有浏览器天气组件。

## 下一阶段

先确认用户环境中的真实天气查询可用，再考虑网页工具卡、模型提出调用且程序校验的function-calling流程，以及有工具/无工具的任务对照。避免在未验证数据契约前将天气值注入旧知识卡契约。

## 来源

Open-Meteo Weather Forecast API: https://open-meteo.com/en/docs
Open-Meteo: https://open-meteo.com/
文档核对日期：2026-10-18。官方文档说明current conditions基于15分钟天气模型数据。
