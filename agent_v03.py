"""v0.3-step3 entry, additive to the v0.2 project; no third-party packages."""
import argparse
import getpass
import json
import os
from pathlib import Path

from context_agent import ContextSession, QUESTIONS, respond, render, session_record
from llm import ChatClient
from retriever import KnowledgeBase


def main():
    parser = argparse.ArgumentParser(description='LureSense 条件化回答 v0.3-step3')
    parser.add_argument('--mode', choices=('mock', 'rag'), default='mock')
    parser.add_argument('--query', default='我在淡水边，应该先看哪里？')
    parser.add_argument('--model', default=os.getenv('MODEL_NAME', ''))
    parser.add_argument('--base-url', default=os.getenv('MODEL_BASE_URL', 'https://api.openai.com/v1'))
    parser.add_argument('--api-key-prompt', action='store_true')
    parser.add_argument('--save', help='退出时保存本次进程中的所有会话，拒绝覆盖')
    args = parser.parse_args()
    destination = Path(args.save) if args.save else None
    if destination and (destination.exists() or not destination.parent.is_dir()):
        parser.error('保存文件已存在或父目录不存在；请更换路径或创建目录')
    if args.mode == 'rag' and not args.model.strip():
        parser.error('rag模式请填写--model；密钥只在需要调用时读取')
    kb = KnowledgeBase()
    sessions = []
    current = ContextSession(args.query)
    client = None

    def get_client():
        nonlocal client
        if client is None:
            key = getpass.getpass('API Key（隐藏输入）：') if args.api_key_prompt else os.getenv('MODEL_API_KEY', '')
            client = ChatClient(args.model, key, args.base_url)
        return client

    print('【v0.3-step3】规则路由与有限澄清；自然语言识别有边界。用户信息未经实测验证。')
    print('条件有误时可修改；两项自动追问上限，每个会话最多3次模型请求（含失败）。')
    dirty = True
    try:
        while True:
            slot = current.next_question()
            if slot:
                text = input(QUESTIONS[slot] + '\n> ').strip()
            else:
                if dirty:
                    print(render(respond(current, kb, args.mode, get_client)))
                    dirty = False
                text = input('\n/water /cover /temperature 修改；/retry 重试；/new 新问题；/exit 退出\n> ').strip()
            if text == '/exit':
                break
            if text == '/new':
                try:
                    replacement = ContextSession(input('新问题：').strip())
                except ValueError as error:
                    print(error)
                    continue
                sessions.append(session_record(current, kb))
                current, dirty = replacement, True
                continue
            controls = {'/water': 'waterbody', '/cover': 'cover', '/temperature': 'temperature_source'}
            if text in controls:
                target = controls[text]
                choice = input(QUESTIONS[target] + '\n> ').strip()
                try:
                    current.choose(target, choice)
                    dirty = True
                except ValueError as error:
                    print(error)
                continue
            if text == '/retry' and slot is None:
                dirty = True
                continue
            if slot:
                try:
                    current.choose(slot, text)
                    dirty = True
                except ValueError as error:
                    print(error)
            else:
                print('请输入列出的命令；新的自由文本问题请用/new。')
    except (EOFError, KeyboardInterrupt):
        print('\n已结束。')
    finally:
        if destination:
            sessions.append(session_record(current, kb))
            with destination.open('x', encoding='utf-8') as handle:
                json.dump({'app_version': '0.3-step3', 'sessions': sessions}, handle, ensure_ascii=False, indent=2)
            print('会话记录已保存：' + str(destination))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        raise SystemExit('运行失败：' + str(error))
