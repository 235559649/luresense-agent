# 第四轮：部分确认与否定表达回归

基线为第三轮 context_guard 补丁。真实运行的代码哈希已经与基线核对。

## 修改
- context_agent.py：只对混合否定语句中的独立、明确“看到/观察到”分句保留确认结构。例如看到倒木但不知道水草，保留倒木。同一结构既肯定又不确定时继续要求确认。
- context_guard.py：缩小免责声明匹配；“无法观察水底所以这里没有水草”不再因“无法”而被放过。“不能断定没有水草”仍放行。
- tests/test_context_variants.py：新增6个测试方法（包含多个措辞子案例）。

范围仍是有限中文规则，不保证识别任意自然语言。没有新增鱼类知识、没有调用付费模型，也没有把规则表现算作模型准确率。

## 安装
退出CLI/Web，在项目根目录执行：

```bash
python3 ~/Downloads/LureSense_context_variants_fix/apply_fix.py
python3 -m unittest discover -s tests -v
```

预期140个测试通过。安装器先核对所有文件，再备份和更新；本地文件不同会停止，不要强制覆盖。

## 本地真实模型检查

```bash
mkdir -p runs/phase4_01
python3 agent_v03.py --mode rag --base-url "https://api.openai.com/v1" --model "gpt-4.1-mini" --api-key-prompt --query "我在湖泊岸边，我看到倒木，但不知道有没有水草，应该先观察哪里？" --save runs/phase4_01/variants_01.json
```

1. 首问预期保留倒木，不因水草未知重复询问已看到的结构；不给水草存在的结论。
2. /new 输入“我在湖泊岸边，水太浑，我看不清有没有水草，应该先观察哪里？”；如果出现结构选项，选0；不应自动识别为已确认水草。
3. /new 输入“我在湖泊岸边，看到水草，应该先观察哪里？”；回答后 /cover 选0；后续不再采用水草。
4. /exit 保存。保留首次结果，不为获得通过反复重试。

```bash
python3 review_runs.py prepare --run runs/phase4_01/variants_01.json --out runs/phase4_01/review_variants_01.json
```

评分针对最终输出；另外查看 answer_origin、model_answer_before_policy、model_answer_before_guard。未触发拦截不等于证明拦截能力。离线构造失败文本可验证拦截逻辑，但不是模型真实犯错频率。

## 验证结果
本轮140个离线单元测试通过。离线benchmark为30情景×3组，模型调用0次；详见包内REPORT.md。新增案例已参与开发，不是盲测集。

## 个人项目收尾范围（规划估算）
以每天1–2小时为假设，形成可演示、可复现的求职作品预计还需3–5周：
1. 可靠性收尾：3–5天，完成本补丁真实检查，冻结一组新措辞验收样本，记录失败。
2. 产品流程：5–8天，Web完整流程、错误提示、结果导出、配置说明；不只测CLI。
3. 发布准备：4–7天，部署方式、密钥隔离、调用预算、超时处理、安装验证。
4. 展示材料：3–5天，README、架构图、带分母的评估表、演示录像、已知局限。

以上可以部分重叠，不含野外生态验证、可穿戴设备、图像识别、多鱼种扩展。
完成标准：新人能按README启动；Web从提问到导出可走通；异常可解释且不伪装正常回答；离线与真实评估分开；演示和局限清楚。满足后标记作品版本，不无限追加局部规则。
