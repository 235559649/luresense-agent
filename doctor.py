"""Offline startup checks. Never contact the provider or print credentials."""
import argparse
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
REQUIRED = ('agent_v03.py', 'web_app.py', 'context_agent.py', 'context_guard.py',
            'observation_policy.py', 'llm.py', 'grounding.py', 'retriever.py',
            'web/index.html', 'web/app.js', 'web/style.css',
            'data/knowledge_cards.json', 'data/sources.json')


def checks(root=ROOT, mode='mock', env=None, model=None, base_url=None, prompt=False):
    env = os.environ if env is None else env
    rows = []
    def add(name, ok, detail):
        rows.append({'check': name, 'ok': bool(ok), 'detail': detail})
    add('python', sys.version_info >= (3, 11), '需要 Python 3.11 或以上')
    missing = [name for name in REQUIRED if not (root / name).is_file()]
    add('files', not missing, '关键文件齐全' if not missing else '缺少：' + ', '.join(missing))
    for name in ('knowledge_cards', 'sources'):
        try:
            json.loads((root / 'data' / (name + '.json')).read_text(encoding='utf-8'))
            add(name, True, 'JSON 可读取；不代表内容已完成事实核查')
        except (OSError, ValueError):
            add(name, False, 'JSON 缺失、不可读或格式错误')
    if mode == 'rag':
        selected_model = model if model is not None else env.get('MODEL_NAME', '')
        endpoint = base_url if base_url is not None else env.get('MODEL_BASE_URL', 'https://api.openai.com/v1')
        try:
            u = urlsplit(endpoint)
            valid = u.scheme == 'https' and u.hostname and not (u.username or u.password or u.query or u.fragment)
        except ValueError:
            valid = False
        add('model', bool(selected_model.strip()), '需要模型名称；本检查不验证服务商是否支持该模型')
        add('endpoint', valid, '需要无凭据、无查询参数的 HTTPS 基础地址；不输出配置值')
        add('credential', prompt or bool(env.get('MODEL_API_KEY', '').strip()),
            '将在启动命令中隐藏输入密钥' if prompt else '只检查 MODEL_API_KEY 是否非空，不验证有效性、不输出密钥')
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode', choices=('mock', 'rag'), default='mock')
    p.add_argument('--model')
    p.add_argument('--base-url')
    p.add_argument('--api-key-prompt', action='store_true', help='声明启动时隐藏输入；本检查不会索取密钥')
    a = p.parse_args()
    rows = checks(mode=a.mode, model=a.model, base_url=a.base_url, prompt=a.api_key_prompt)
    for row in rows:
        print(('PASS' if row['ok'] else 'FAIL') + ' ' + row['check'] + '：' + row['detail'])
    print('仅完成离线启动前检查；未访问网络、未调用模型、未验证账户权限或余额。')
    return 0 if all(r['ok'] for r in rows) else 1


if __name__ == '__main__':
    raise SystemExit(main())
