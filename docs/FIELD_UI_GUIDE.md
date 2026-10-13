# 页面视觉与使用引导更新

## 本轮内容
- 首页增加本地内嵌SVG湖岸示意插画，明确标注非现场照片或检测结果。没有外链图片、字体或新依赖。
- 调整桌面双栏与手机单栏布局，提问区和回答区使用不同视觉强调。
- 增加三步引导、回答等待区和模拟/规则规范输出说明。
- 不新增照片上传入口，不改变模型、状态管理、检索或评分逻辑。

## 安装
在项目根目录执行：
```bash
python3 ~/Downloads/LureSense_field_ui/apply_fix.py
python3 -m unittest discover -s tests -v
python3 web_app.py --mode mock --port 8765
```
打开 http://127.0.0.1:8765 ，如样式未更新使用Cmd+Shift+R刷新。

## 浏览器验收
- 首屏显示湖岸插画和“非现场照片或检测结果”说明；不是照片识别功能。
- 提交“我在淡水边，应该先看哪里？”，选择湖泊、水草，再将结构改为不知道。
- 检查条件、回答与证据面板更新，导出JSON可以下载。
- 缩窄到约390px宽，检查内容单栏显示，没有横向溢出。
- 用Tab键检查输入框、按钮和条件下拉框可操作且焦点可见。
- 真实模式继续沿用原启动命令，不必为了本次视觉修改重复付费评估。

## 验证边界
153个Python测试通过（包括原Web服务/HTTP测试），JavaScript语法检查通过。本环境没有可用浏览器二进制，下载也未成功，因此未完成实际浏览器截图与交互验收。响应式样式已实现，但需按上述清单本地确认。

## 提交
```bash
git add -- web/index.html web/style.css web/app.js docs/FIELD_UI_GUIDE.md
git diff --cached --stat
git diff --cached --check
git commit -m "feat: refine field notebook UI and onboarding"
git push origin main
```
先确认main分支、暂存内容符合预期；不强制推送。

后续优先从新目录克隆验证README，再制作演示录像与架构说明。增加真实照片需明确授权及来源，且标注示例；当前插画只作视觉说明。
