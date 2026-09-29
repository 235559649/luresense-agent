# v0.5 增量安装与提交

这轮新增实验和工程文档，复用已有 v03 step3 核心与 v04 Web。没有新增 Python 第三方依赖，不重写旧入口和 README。

## 安装

将 LureSense_eval_v05.zip 下载到 Downloads，然后：

```bash
cd "/Users/zhangyuhang/Desktop/LureSense/LureSense/luresense-agent"
python3 -c "import context_agent, grounding, review_runs, web_app"
unzip -o "$HOME/Downloads/LureSense_eval_v05.zip" -d "$HOME/Downloads"
cp -R "$HOME/Downloads/LureSense_eval_v05/." .
python3 -m unittest discover -s tests -v
```

若 import 失败，先补装上一轮增量模块。完整历史合并后本次共有 86 项单元/接口测试；你自己新增测试会改变总数。

## 运行实验

```bash
python3 benchmark_v05.py --split dev --out runs/eval_v05_dev_01
python3 benchmark_v05.py --split challenge --out runs/eval_v05_challenge_01
```

输出目录必须尚不存在。运行第二次请把后缀改为 02。默认只跑 dev；`--split all` 跑全部 30 条。此脚本不提供 rag 模式，不需要 Key，不会调用任何模型。

每个输出目录包含：

- REPORT.md：三组结果、适用分母与失败列表。
- results.json：数据快照、哈希、逐情景结果和按类别汇总。
- agent_runs/：每条情景的 mock 会话，用于检查状态和证据。

随包 reports/v05_baseline/ 是本次实际执行的全量基线结果，不是预测数值。机器时间戳不同，且今后改动核心会改变指标；比较前检查版本和哈希。

## 先读哪些结果

1. 读 docs/EXPERIMENT_DESIGN_V05.md，理解什么能比较、什么不能比较。
2. 打开 REPORT.md，看每项 n；不要只看最高分。
3. 找 S10：拼接“结构：未知”依然可能匹配结构类知识，检查查询可解释该失败。
4. 找 S30：“不是在海边”被关键词范围判断拦截，是现有实现的缺陷。
5. 找 S08、S13：相关卡未完全召回，检查检索词表与知识卡标签。

标注由本项目拟定，尚未经钓鱼专家验证。先理解和复核，再扩展案例。

## 自动测试

新增 .github/workflows/luresense-ci.yml：在 main push 和 pull_request 时，使用 Python 3.11/3.12 跑测试和 dev 离线实验，把报告写入 Actions 的运行摘要。不读取模型密钥、不执行付费模型调用，不部署网页。

配置参考官方 actions/checkout 与 actions/setup-python 文档：
- https://github.com/actions/checkout
- https://github.com/actions/setup-python

本地已验证 Python 3.12；GitHub 托管工作流尚未实际运行，上传后到 Actions 查看首次结果。实验分数低不会单独令 CI 失败：单元测试与运行错误是失败条件，质量指标用于审查。后续建立稳定、独立的标准后再设置质量门槛。

## 按你的要求提交 main

```bash
git branch --show-current
git status --short
```

确认当前是 main，再提交本轮文件：

```bash
git add benchmark_v05.py data/scenarios_v05.json tests/test_benchmark_v05.py .github/workflows/luresense-ci.yml docs/V05_INSTALL.md docs/EXPERIMENT_DESIGN_V05.md docs/PROJECT_OVERVIEW_V05.md docs/adr/0001-bounded-agent-and-evaluation.md reports/v05_baseline
git diff --cached --stat
git commit -m "feat: add scenario benchmark, design rationale and offline CI"
git push origin main
```

没有对你的远程仓库自动执行提交。README 可根据 docs/PROJECT_OVERVIEW_V05.md 手工补充，并沿用原有安装说明；不要把它当作已验证的真实模型效果声明。
