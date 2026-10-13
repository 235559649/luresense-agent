# 首次启动检查点

安装后执行：
```bash
python3 doctor.py
python3 -m unittest discover -s tests -v
python3 web_app.py --mode mock --port 8765
```
预期doctor全部PASS，153个测试通过；网页 http://127.0.0.1:8765 可打开。

配置真实模式前可运行：
```bash
python3 doctor.py --mode rag --model gpt-4.1-mini --api-key-prompt
```
doctor不调用API，不检查账户额度或模型权限，也不会读取.env文件。通过只意味着本地必要文件和配置形式符合要求，不保证运行时一定成功。

本轮修改：README.md更新为当前项目说明；新增doctor.py和5个测试方法。原模型调用、知识卡、评分和上下文算法不变。

提交：
```bash
git add -- README.md doctor.py tests/test_doctor.py docs/STARTUP_CHECKPOINT.md
git diff --cached --stat
git diff --cached --check
git commit -m "docs: refresh quickstart and add offline startup checks"
git push origin main
```
执行前确认当前分支main，检查全部暂存文件符合预期；推送被拒绝不要force。

后续：在单独新目录从GitHub克隆并按README启动；固定演示脚本和验收清单；准备录像和架构说明；达到标准后发布作品版本。
