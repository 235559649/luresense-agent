"""python3 app.py --mode mock --query '大口黑鲈吃什么？'"""
import argparse
import getpass
import json
import os
from llm import ChatClient, ModelError
from rag import generate, format_answer, save_run
from retriever import KnowledgeBase, format_result


def main():
    parser = argparse.ArgumentParser(description='LureSense v0.2：检索与带引用RAG')
    parser.add_argument('--mode', choices=('retrieve', 'mock', 'rag'), default='retrieve')
    parser.add_argument('--query', '-q')
    parser.add_argument('--limit', type=int, choices=range(1, 5), default=4)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--model', default=os.getenv('MODEL_NAME', ''))
    parser.add_argument('--base-url', default=os.getenv('MODEL_BASE_URL', 'https://api.openai.com/v1'))
    parser.add_argument('--api-key-prompt', action='store_true', help='在本机隐藏输入密钥')
    parser.add_argument('--save', help='保存JSON；仅支持--query；不覆盖已有文件')
    args = parser.parse_args()
    if args.save and args.query is None:
        parser.error('--save需要--query，避免多轮覆盖')
    if args.save and args.mode == 'retrieve':
        parser.error('--save用于mock或rag；纯检索可用--json')
    try:
        kb = KnowledgeBase()
        client = None
        if args.mode == 'rag':
            key = getpass.getpass('API Key（输入不显示，仅用于本次进程）：') if args.api_key_prompt else os.getenv('MODEL_API_KEY', '')
            client = ChatClient(args.model, key, args.base_url)

        def run(q):
            result = kb.search(q, args.limit) if args.mode == 'retrieve' else generate(kb, q, args.mode, client, args.limit)
            if args.save:
                save_run(result, args.save, kb)
            formatter = format_result if args.mode == 'retrieve' else format_answer
            print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else formatter(result))

        if args.query is not None:
            run(args.query)
        else:
            print(f'LureSense {args.mode}模式；输入exit退出。各问题独立处理，尚无多轮记忆。')
            while True:
                try:
                    q = input('\n问题：')
                    if q.strip().casefold() in ('exit', 'quit', '退出'):
                        break
                    run(q)
                except (ValueError, ModelError) as exc:
                    print('未生成有效答案：' + str(exc))
                except (EOFError, KeyboardInterrupt):
                    break
    except (OSError, ValueError, ModelError, KeyError, TypeError) as exc:
        parser.exit(1, '运行失败：' + str(exc) + '\n')


if __name__ == '__main__':
    main()
