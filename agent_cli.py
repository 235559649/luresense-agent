"""Run beside v0.2 app.py: python3 agent_cli.py. Offline only."""
import argparse
from pathlib import Path
from clarification import ClarificationSession, QUESTIONS, save_session
from retriever import KnowledgeBase, format_result


def main():
    parser = argparse.ArgumentParser(description='LureSense v0.3-step1 引导式澄清（离线）')
    parser.add_argument('--query', default='我在淡水边，应该先看哪里？')
    parser.add_argument('--save', help='退出时保存最后一个会话；不覆盖已有文件')
    args = parser.parse_args()
    if args.save and (Path(args.save).exists() or not Path(args.save).parent.is_dir()):
        parser.error('保存文件已存在或父目录不存在，请更换路径或先创建目录')
    kb = KnowledgeBase()
    session = ClarificationSession(args.query)
    initial = kb.search(session.question)
    if initial['status'] == 'out_of_scope':
        print(initial['message'])
        return
    print('【离线澄清原型：不调用模型】范围暂定淡水大口黑鲈，不确认现场有鱼。')
    print('这一阶段不自动理解条件，请用编号确认。不确定选0。')
    print('输入 /exit 退出，/new 开始新问题。完成后可用 /water 或 /cover 修改条件。')
    last_record = None
    try:
        while True:
            slot = session.next_slot()
            if slot:
                raw = input(QUESTIONS[slot] + '\n> ').strip()
            else:
                query = session.retrieval_query()
                result = kb.search(query)
                last_record = session.record(result)
                print('\n当前条件：', session.context())
                print('重检索问题：', query)
                print(format_result(result))
                print('这里只展示候选资料，不是已经检查适用性的现场建议。')
                raw = input('\n/water 修改水域；/cover 修改结构；/new 新问题；/exit 结束\n> ').strip()
            if raw == '/exit':
                break
            if raw == '/new':
                new_session = ClarificationSession(input('新的问题：').strip())
                check = kb.search(new_session.question)
                if check['status'] == 'out_of_scope':
                    print(check['message'])
                    continue
                session, last_record = new_session, None
                continue
            if raw in ('/water', '/cover'):
                selected = 'waterbody' if raw == '/water' else 'cover'
                choice = input(QUESTIONS[selected] + '\n> ').strip()
                try:
                    session.choose(selected, choice)
                    last_record = None
                except ValueError as error:
                    print(error)
                continue
            if slot:
                try:
                    session.choose(slot, raw)
                    last_record = None
                except ValueError as error:
                    print(error)
            else:
                print('请选择列出的命令；自然语言条件识别尚未实现。')
    except (EOFError, KeyboardInterrupt):
        print('\n结束会话。')
    # Save current state, never a stale result from before a correction.
    if args.save:
        if session.next_slot() is None:
            last_record = session.record(kb.search(session.retrieval_query()))
            save_session(last_record, args.save)
            print('已保存：' + args.save)
        else:
            print('会话尚未完成两项选择，本次未保存。')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        raise SystemExit('运行失败：' + str(error))
