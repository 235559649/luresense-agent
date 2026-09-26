# v0.2代码阅读顺序

1. data/knowledge_cards.json：每张卡是原材料。source_ids指向sources.json。
2. retriever.py：问题匹配到最多4张卡片。它可能漏检，命中也不等于回答正确。
3. rag.py中的generate：先检索；无资料就返回，不进行无依据的生成。mock只摘录；rag才调用模型。
4. llm.py：把messages发送到配置的HTTPS接口；接收模型文本和token用量。不能把API Key写进源码。
5. validate_answer：检查JSON结构、每条主张是否有引用、引用是否属于本次检索。它不理解主张真假。
6. format_answer：按真实来源映射展示证据，URL由程序产生。
7. save_run：明确要求保存时写实验记录；synthetic区分模拟与真实模式。
8. app.py：把上述模块连接到命令行。

练习：运行mock模式并查看JSON，找到retrieved_ids、claims和evidence，解释三者如何关联。再运行“火星钓鱼”，确认不会生成答案。最后读test_id_validation_is_not_entailment，理解为何有引用的答案也可能错误。

当前是固定检索流程。后续让系统识别缺失条件、追问、更新状态并选择是否再检索，才进入Agent阶段。研究重点不在于多装几个框架，而在于这些额外决策是否带来可测量的改善。
