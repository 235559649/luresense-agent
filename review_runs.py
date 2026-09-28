"""Prepare human JSON review sheets and summarize grades without model calls."""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path

SUPPORT = {'pending', 'supported', 'partial', 'unsupported', 'unresolved'}
YESNO = {'pending', 'yes', 'no', 'unknown'}


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_new(path, data):
    with Path(path).open('x', encoding='utf-8') as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def prepare(paths):
    review = {'schema_version': '1', 'reviewer': '', 'sources': [], 'items': []}
    seen = set()
    for file_number, path in enumerate(paths):
        path = Path(path).resolve()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in seen:
            raise ValueError('重复输入同一运行记录，已拒绝以避免重复计数')
        seen.add(digest)
        review['sources'].append({'path': str(path), 'sha256': digest})
        data = read_json(path)
        if not isinstance(data, dict):
            raise ValueError('运行记录须为JSON对象')
        if 'sessions' in data:
            sessions = data['sessions']
        elif 'events' in data:
            sessions = [data]
        elif 'claims' in data:
            sessions = [{'app_version': data.get('app_version', 'unknown'),
                         'question': data.get('query', ''), 'events': [{'event': 'response', 'result': data}]}]
        else:
            raise ValueError('不支持的运行记录；需要v0.2回答或v0.3会话JSON')
        if not isinstance(sessions, list):
            raise ValueError('sessions须为数组')
        for sn, session in enumerate(sessions):
            responses = [e['result'] for e in session.get('events', []) if e.get('event') == 'response']
            # Incomplete sessions are visible, not silently dropped.
            if not responses:
                responses = [{'status': 'incomplete', 'claims': [], 'synthetic': True,
                              'current_context': session.get('context', {})}]
            for rn, result in enumerate(responses):
                item = {'id': f'f{file_number}-s{sn}-r{rn}',
                        'version': session.get('app_version', data.get('app_version', 'unknown')),
                        'question': result.get('original_question', result.get('query', session.get('question', ''))),
                        'result': deepcopy(result), 'answerable': 'pending', 'useful': 'pending',
                        'condition_correct': 'pending', 'abstention_appropriate': 'pending', 'note': '',
                        'claim_reviews': [{'index': i, 'support': 'pending', 'note': ''}
                                          for i, _ in enumerate(result.get('claims', []))]}
                review['items'].append(item)
    return review


def summarize(review):
    # Regenerate immutable evidence from the original records. Grade edits only.
    if not isinstance(review.get('reviewer'), str):
        raise ValueError('reviewer须为文字')
    expected = prepare([s['path'] for s in review['sources']])
    if review['schema_version'] != expected['schema_version'] or review['sources'] != expected['sources']:
        raise ValueError('原始记录发生变化，不能把旧评分套到新结果')
    if len(review['items']) != len(expected['items']):
        raise ValueError('评审条目缺失或重复')
    groups = defaultdict(list)
    for item, original in zip(review['items'], expected['items']):
        mutable = {'answerable', 'useful', 'condition_correct', 'abstention_appropriate', 'note', 'claim_reviews'}
        if {k: v for k, v in item.items() if k not in mutable} != {k: v for k, v in original.items() if k not in mutable}:
            raise ValueError('不可修改原始问题、证据、结果或条目标识')
        for name in ('answerable', 'useful', 'condition_correct', 'abstention_appropriate'):
            if item.get(name) not in YESNO:
                raise ValueError('回答级评分须为pending/yes/no/unknown')
        if not isinstance(item.get('note'), str):
            raise ValueError('note须为文字')
        grades = item['claim_reviews']
        if len(grades) != len(original['claim_reviews']):
            raise ValueError('每条主张必须保留一个评分位置')
        for index, grade in enumerate(grades):
            if set(grade) != {'index', 'support', 'note'} or grade['index'] != index or grade['support'] not in SUPPORT:
                raise ValueError('主张评分无效或顺序改变')
            if not isinstance(grade['note'], str) or grade['support'] != 'pending' and not grade['note'].strip():
                raise ValueError('已评分主张须填写证据支持判断理由')
        groups[item['version']].append(item)
    output = {'reviewer': review['reviewer'], 'unit': 'response turn, not independent scenario',
              'warning': '人工来源支持评估；不是生态真值或自动事实核查。未评分/未决不计为正确。', 'groups': {}}
    ratio = lambda numerator, denominator: numerator / denominator if denominator else None
    for version, items in groups.items():
        real = [i for i in items if i['result'].get('synthetic') is False]
        labels = Counter(g['support'] for i in real for g in i['claim_reviews'])
        decided = sum(labels[k] for k in ('supported', 'partial', 'unsupported'))
        total = sum(labels.values())
        answerable = [i for i in real if i['answerable'] == 'yes']
        useful_decided = [i for i in answerable if i['useful'] in ('yes', 'no')]
        tokens = [i['result'].get('usage', {}).get('total_tokens') for i in real]
        known_tokens = [t for t in tokens if isinstance(t, int) and not isinstance(t, bool) and t >= 0]
        output['groups'][version] = {
            'all_response_rows': len(items), 'real_response_rows': len(real),
            'synthetic_or_unknown_rows_excluded': len(items) - len(real),
            'real_status_counts': dict(Counter(i['result']['status'] for i in real)),
            'claim_label_counts': dict(labels), 'claim_count': total, 'decided_claim_count': decided,
            'decided_coverage': ratio(decided, total),
            'unsupported_rate_among_decided': ratio(labels['unsupported'], decided),
            'not_fully_supported_rate_among_decided': ratio(labels['unsupported'] + labels['partial'], decided),
            'answerable_yes_rows': len(answerable), 'usefulness_decided_rows': len(useful_decided),
            'useful_rate_on_graded_answerable_rows': ratio(sum(i['useful'] == 'yes' for i in useful_decided), len(useful_decided)),
            'condition_grade_counts': dict(Counter(i['condition_correct'] for i in real)),
            'abstention_grade_counts': dict(Counter(i['abstention_appropriate'] for i in real)),
            'known_total_tokens_sum': sum(known_tokens) if known_tokens else None,
            'rows_with_known_tokens': len(known_tokens), 'rows_without_known_tokens': len(real)-len(known_tokens)}
    return output


def main():
    parser = argparse.ArgumentParser(description='离线人工证据评分，不自动打分')
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--run', nargs='+', required=True)
    p.add_argument('--out', required=True)
    p = sub.add_parser('summarize')
    p.add_argument('--review', required=True)
    p.add_argument('--out')
    args = parser.parse_args()
    if args.action == 'prepare':
        write_new(args.out, prepare(args.run))
        print('已生成待人工填写的评分JSON：' + args.out)
    else:
        result = summarize(read_json(args.review))
        if args.out:
            write_new(args.out, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit('评分处理失败：' + str(error))
