# v0.3-step1 安装与运行

这是增量包，需复制到已经跑通的第二版仓库。只新增4个代码/文档类别，不替换app.py、rag.py、llm.py或retriever.py。完整功能计划见V03_PLAN.md。

1. 在现有仓库运行git status。先提交第二版未保存的工作，保留其基线。
2. 解压本包；把agent_cli.py、clarification.py放到与app.py同级；把tests中的test_clarification.py放到现有tests；把docs中的两个文档放到现有docs。合并目录，不要把整个现有tests文件夹替换掉。
3. 可建立开发分支：git switch -c feature/v03-clarification。
4. 运行：

```bash
python3 -m unittest discover -s tests -v
mkdir -p runs
python3 agent_cli.py --save runs/v03_clarification_01.json
```

默认问题是“我在淡水边，应该先看哪里？”。输入1回车选择湖泊，输入4回车选择水草和倒木（演示假设，不是确认真实现场）。程序会显示状态和重新检索到的卡片。

然后输入/cover，再输入5，验证可修改为“未观察到上述结构”。输入/exit保存最后的完整会话。保存路径不能已存在；换新文件名即可。Ctrl+C或EOF退出时，条件完整也会尝试保存。

本次两项都填0不会反复追问。/new开始新的问题并清除旧会话状态；--save只保存最后一个完整会话，要保留多个案例请分别运行并使用不同文件名。

程序会确认两项条件，即使你已在原问题里说过，这是本阶段的已知限制。结构化修改不会删除原问题中的旧描述；原问题本身有错误时用/new重新输入。

5. 完成验收后，只提交本次新增文件：

```bash
git add agent_cli.py clarification.py tests/test_clarification.py docs/V03_PLAN.md docs/V03_INSTALL.md
git diff --cached --stat
git commit -m "feat: add bounded clarification state and offline retrieval flow"
git push -u origin feature/v03-clarification
```

这只是第三版第一步，暂不打最终v0.3.0标签。runs/保持忽略，不将API密钥放入任何文件。原第二版依然通过python3 app.py运行。
