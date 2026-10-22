"""Rule-routed weather + existing RAG entry. One weather request per invocation."""
import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
from context_agent import ContextSession, QUESTIONS, respond, render, session_record
from retriever import KnowledgeBase
from llm import ChatClient
from weather_tool import coordinates, query_weather, render_weather


def plan(question, force=False):
    if not isinstance(question, str) or not 0 < len(question.strip()) <= 1000:
        raise ValueError('问题须为1～1000字符')
    weather = bool(re.search(r'天气|气温|风速|降水|下雨', question))
    current = bool(re.search(r'现在|当前|今天|此刻|查一下|查询|查查', question))
    conceptual = bool(re.search(r'是什么|为什么|区别|代替|原理', question))
    requested = force or (weather and current and not conceptual)
    unsupported = requested and bool(re.search(r'明天|后天|昨天|未来|下周|过去|\d{4}[-年]', question))
    if unsupported:
        return {'weather': False, 'knowledge': False, 'reason': '首版只查询当前天气，不支持指定日期或历史查询。'}
    session = ContextSession(question)
    return {'weather': requested, 'knowledge': not requested or session.task=='site',
            'reason': '显式天气请求' if requested else '复用原知识与观察流程'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--query', required=True)
    parser.add_argument('--weather-mode', choices=['mock', 'live'], default='mock')
    parser.add_argument('--with-weather', action='store_true')
    parser.add_argument('--latitude', type=float)
    parser.add_argument('--longitude', type=float)
    parser.add_argument('--mode', choices=['mock', 'rag'], default='mock')
    parser.add_argument('--model', default=os.getenv('MODEL_NAME',''))
    parser.add_argument('--base-url', default=os.getenv('MODEL_BASE_URL','https://api.openai.com/v1'))
    parser.add_argument('--api-key-prompt', action='store_true')
    parser.add_argument('--save', required=True)
    args = parser.parse_args()
    destination = Path(args.save)
    if destination.exists() or not destination.parent.is_dir():
        parser.error('输出文件须不存在，且父目录须存在')
    try:
        decision = plan(args.query, args.with_weather)
        record = dict(schema_version='tool-workflow-1', question=args.query,
                      planner='bounded_rules_v1', plan=decision, tool_events=[], sessions=[],
                      note='天气结果单独保存；未注入旧知识卡提示，不将气温写入水温状态。',
                      code_sha256={name: hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest()
                                   for name in ('agent_tools.py','weather_tool.py')})
        print('路由：', decision['reason'])
        if decision['weather']:
            lat, lon = args.latitude, args.longitude
            if lat is None:
                lat = input('请输入查询纬度（不知道可输入 q 退出）：').strip()
            if lon is None:
                lon = input('请输入查询经度（不知道可输入 q 退出）：').strip()
            lat, lon = coordinates(lat, lon)
            if args.weather_mode=='live':
                print('将向 Open-Meteo 发送所提供坐标；天气请求最多1次。')
            result = query_weather(lat, lon, mode=args.weather_mode)
            record['tool_events'].append(result)
            print(render_weather(result))
        if decision['knowledge']:
            session, kb = ContextSession(args.query), KnowledgeBase()
            while True:
                slot = session.next_question()
                if slot is None:
                    break
                while True:
                    try:
                        session.choose(slot, input(QUESTIONS[slot]+'\n> ').strip())
                        break
                    except ValueError as error:
                        print(error)
            def factory():
                key = getpass.getpass('API Key（隐藏输入）：') if args.api_key_prompt else os.getenv('MODEL_API_KEY','')
                return ChatClient(args.model, key, args.base_url)
            print(render(respond(session, kb, args.mode, factory)))
            record['sessions'].append(session_record(session, kb))
        with destination.open('x', encoding='utf-8') as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
            f.write('\n')
        print('记录已保存：', destination)
    except (ValueError, OSError, EOFError, KeyboardInterrupt) as error:
        parser.exit(1, f'未完成：{error}\n')


if __name__=='__main__':
    main()
