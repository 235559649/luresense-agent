"""Loopback-only, single-user demonstration UI. Run beside agent_v03.py."""
import argparse
from collections import OrderedDict
from copy import deepcopy
import getpass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import threading
from urllib.parse import urlsplit

from context_agent import ContextSession, QUESTIONS, OPTIONS, respond, session_record
from llm import ChatClient
from retriever import KnowledgeBase

WEB_ROOT = Path(__file__).resolve().parent / 'web'


class DemoService:
    """Bounded session state; each session serializes edits and generation."""
    def __init__(self, mode='mock', factory=None):
        if mode not in ('mock', 'rag'):
            raise ValueError('模式必须为mock或rag')
        self.mode, self.factory = mode, factory
        self.kb = KnowledgeBase()
        self.sessions = OrderedDict()
        self.lock = threading.Lock()

    def _view(self, sid, entry):
        session = entry['session']
        slot = session.next_question()
        if slot is None and entry['dirty']:
            entry['result'] = respond(session, self.kb, self.mode, self.factory)
            entry['dirty'] = False
        question = None if slot is None else {
            'slot': slot, 'text': QUESTIONS[slot],
            'options': [{'value': value, 'label': label if label is not None else '不知道'}
                        for value, label in OPTIONS[slot].items()]}
        return {'session_id': sid, 'mode': self.mode, 'question': session.question,
                'task': session.task, 'context': session.context(), 'followup': question,
                'questions_asked': session.questions_asked, 'model_requests': session.attempts,
                'result': entry['result'], 'events': session.events,
                'choices': {slot: [{'value': value, 'label': label if label is not None else '不知道'}
                                  for value, label in choices.items()] for slot, choices in OPTIONS.items()}}

    def start(self, question):
        session = ContextSession(question)
        sid = secrets.token_urlsafe(24)
        entry = {'session': session, 'lock': threading.Lock(), 'dirty': True, 'result': None}
        with self.lock:
            if len(self.sessions) >= 20:
                raise ValueError('已达到20个会话上限；请先导出需要的记录，再重启本地服务')
            self.sessions[sid] = entry
        with entry['lock']:
            return deepcopy(self._view(sid, entry))

    def get_entry(self, sid):
        if not isinstance(sid, str):
            raise ValueError('缺少会话ID')
        with self.lock:
            entry = self.sessions.get(sid)
        if entry is None:
            raise ValueError('会话已不存在；服务重启后需要重新开始')
        return entry

    def choose(self, sid, slot, choice):
        entry = self.get_entry(sid)
        with entry['lock']:
            entry['session'].choose(slot, choice)
            entry['dirty'] = True
            # Clear stale answer while awaiting any remaining required condition.
            entry['result'] = None
            return deepcopy(self._view(sid, entry))

    def export(self, sid):
        entry = self.get_entry(sid)
        with entry['lock']:
            return {'app_version': 'web-0.4', 'sessions': [session_record(entry['session'], self.kb)]}


def make_handler(service, token, port):
    allowed_hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            # Do not write questions, request bodies or API credentials to console logs.
            pass

        def send(self, status, body, content_type='application/json; charset=utf-8'):
            raw = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(raw)

        def trusted_host(self):
            return self.headers.get('Host') in allowed_hosts

        def do_GET(self):
            if not self.trusted_host():
                return self.send(403, {'error': '只接受本机地址'})
            path = urlsplit(self.path).path
            files = {'/': ('index.html', 'text/html; charset=utf-8'),
                     '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                     '/style.css': ('style.css', 'text/css; charset=utf-8')}
            if path == '/api/config':
                return self.send(200, {'csrf_token': token, 'mode': service.mode})
            if path not in files:
                return self.send(404, {'error': '页面不存在'})
            name, mime = files[path]
            return self.send(200, (WEB_ROOT / name).read_bytes(), mime)

        def do_POST(self):
            if not self.trusted_host() or not secrets.compare_digest(self.headers.get('X-LureSense-Token', ''), token):
                return self.send(403, {'error': '请求验证失败，请刷新页面'})
            origin = self.headers.get('Origin')
            if origin and origin not in {f'http://{host}' for host in allowed_hosts}:
                return self.send(403, {'error': '拒绝跨站请求'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 8192:
                    return self.send(413, {'error': '请求大小不合法'})
                if self.headers.get_content_type() != 'application/json':
                    return self.send(415, {'error': '请求须为JSON'})
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError('请求须为JSON对象')
                path = urlsplit(self.path).path
                if path == '/api/start':
                    result = service.start(data.get('question'))
                elif path == '/api/choose':
                    result = service.choose(data.get('session_id'), data.get('slot'), data.get('choice'))
                elif path == '/api/export':
                    result = service.export(data.get('session_id'))
                else:
                    return self.send(404, {'error': '接口不存在'})
                self.send(200, result)
            except (ValueError, TypeError, KeyError) as error:
                self.send(400, {'error': str(error)})
            except Exception:
                self.send(500, {'error': '本地服务发生异常，请保留已导出的记录并检查终端环境'})

    return Handler


def main():
    parser = argparse.ArgumentParser(description='LureSense 本地求职演示界面')
    parser.add_argument('--mode', choices=('mock', 'rag'), default='mock')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--model', default=os.getenv('MODEL_NAME', ''))
    parser.add_argument('--base-url', default=os.getenv('MODEL_BASE_URL', 'https://api.openai.com/v1'))
    parser.add_argument('--api-key-prompt', action='store_true')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('端口范围为1024～65535')
    client = None
    if args.mode == 'rag':
        if not args.model.strip():
            parser.error('真实模式需要--model')
        key = getpass.getpass('API Key（仅后端内存，输入不显示）：') if args.api_key_prompt else os.getenv('MODEL_API_KEY', '')
        client = ChatClient(args.model, key, args.base_url)
    service = DemoService(args.mode, (lambda: client) if client else None)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(service, secrets.token_urlsafe(32), args.port))
    server.daemon_threads = True
    print(f'LureSense 已启动：http://127.0.0.1:{args.port} / 模式：{args.mode}')
    print('仅本机可访问。退出前请在页面导出记录；Ctrl+C停止服务。')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        raise SystemExit('启动失败：' + str(error))
