"""运行：python3 app.py --query '水草附近可以先了解什么？'"""
import argparse
import json
from retriever import KnowledgeBase, format_result


def main():
    parser = argparse.ArgumentParser(description="LureSense 本地知识检索原型")
    parser.add_argument("--query", "-q", help="只查询一次；不提供则进入交互模式")
    parser.add_argument("--limit", type=int, default=4, choices=range(1, 5))
    parser.add_argument("--json", action="store_true", help="输出结构化 JSON")
    args = parser.parse_args()
    try:
        kb = KnowledgeBase()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"资料加载失败：{exc}\n")

    def run(query):
        result = kb.search(query, args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else format_result(result))

    if args.query is not None:
        try:
            run(args.query)
        except ValueError as exc:
            parser.exit(2, f"输入错误：{exc}\n")
        return
    print(f"LureSense 已载入 {len(kb.cards)} 张卡片。输入问题，输入 exit 退出。")
    print("这是无模型的资料检索版本，不是完整的 AI Agent。")
    while True:
        try:
            query = input("\n你的问题：")
            if query.strip().casefold() in {"exit", "quit", "退出"}:
                break
            run(query)
        except ValueError as exc:
            print(f"输入错误：{exc}")
        except (EOFError, KeyboardInterrupt):
            print("\n已退出。")
            break


if __name__ == "__main__":
    main()
