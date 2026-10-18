"""Offline paired guard experiments; authored data, not model accuracy."""
import argparse
import hashlib
import inspect
import json
from pathlib import Path
import context_guard


def digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(raw.encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')


def validate(data):
    if data.get('schema_version') != 'guard-dataset-1':
        raise ValueError('评估集版本无效')
    if data.get('split') not in ('dev', 'holdout'):
        raise ValueError('split 必须为 dev 或 holdout')
    if not isinstance(data.get('cases'), list) or not data['cases']:
        raise ValueError('cases 必须为非空列表')
    ids = set()
    for case in data['cases']:
        case_id = case.get('id')
        if not isinstance(case_id, str) or not case_id.strip() or case_id in ids:
            raise ValueError('案例编号为空或重复')
        ids.add(case_id)
        if type(case.get('expected_block')) is not bool:
            raise ValueError('expected_block 必须为布尔值')
        if not isinstance(case.get('label_reason'), str) or not case['label_reason'].strip():
            raise ValueError('每条案例须填写标注理由')
        cover = case['context']['cover']
        if cover.get('status') not in ('unknown', 'unanswered', 'user_reported'):
            raise ValueError('cover 状态无效')
        if 'value' not in cover or (cover['value'] is not None and not isinstance(cover['value'], str)):
            raise ValueError('cover 值无效')
        claims = case['answer']['claims']
        if not isinstance(claims, list) or not claims:
            raise ValueError('claims 必须为非空列表')
        for claim in claims:
            if not isinstance(claim.get('text'), str) or not claim['text'].strip():
                raise ValueError('主张文本不能为空')
            if claim.get('caveat') is not None and not isinstance(claim['caveat'], str):
                raise ValueError('caveat 必须为文字或 null')
    return data


def export_dataset(report):
    if report.get('dataset') != 'context_guard_dev_v1':
        raise ValueError('仅支持从原 context_guard_dev_v1 报告导出开发集')
    keys = ('id', 'context', 'answer', 'expected_block', 'label_reason')
    data = dict(schema_version='guard-dataset-1', name='context_guard_dev_v1',
                split='dev', provenance='AI-authored development examples; not a blind test',
                cases=[{k: row[k] for k in keys} for row in report['rows']])
    return validate(data)


def evaluate(data):
    validate(data)
    rows, counts = [], dict(tp=0, fp=0, tn=0, fn=0)
    for case in data['cases']:
        conflicts = context_guard.context_conflicts(case['answer'], case['context'])
        predicted, expected = bool(conflicts), case['expected_block']
        outcome = ('tp' if predicted else 'fn') if expected else ('fp' if predicted else 'tn')
        counts[outcome] += 1
        rows.append(dict(id=case['id'], expected_block=expected,
                         predicted_block=predicted, outcome=outcome, conflicts=conflicts))
    def metric(a, b):
        return dict(numerator=a, n=b, value=a / b if b else None)
    tp, fp, tn, fn = (counts[k] for k in ('tp', 'fp', 'tn', 'fn'))
    return dict(schema_version='guard-run-1', dataset=data,
                dataset_sha256=digest(data),
                guard_sha256=hashlib.sha256(Path(inspect.getfile(context_guard)).read_bytes()).hexdigest(),
                model_calls=0, warning='规则开发评估；不是模型准确率或独立盲测证明。',
                summary=dict(**counts, precision=metric(tp, tp+fp), recall=metric(tp, tp+fn),
                             false_positive_rate=metric(fp, fp+tn),
                             failure_ids=[r['id'] for r in rows if r['outcome'] in ('fp', 'fn')]),
                rows=rows)


def checked_rows(report):
    if report.get('schema_version') != 'guard-run-1':
        raise ValueError('请使用本工具生成的评估结果进行比较')
    data = validate(report['dataset'])
    if digest(data) != report['dataset_sha256']:
        raise ValueError('评估集指纹不匹配')
    cases, rows = data['cases'], report['rows']
    if len(cases) != len(rows):
        raise ValueError('结果条数不匹配')
    for case, row in zip(cases, rows):
        if row['id'] != case['id'] or row['expected_block'] is not case['expected_block']:
            raise ValueError('结果编号或标签不匹配')
        if type(row['predicted_block']) is not bool:
            raise ValueError('预测值无效')
    return {r['id']: r for r in rows}


def compare(before, after):
    a, b = checked_rows(before), checked_rows(after)
    if before['dataset_sha256'] != after['dataset_sha256']:
        raise ValueError('案例、标签或元数据发生改变，不能进行配对比较')
    fixed, regressed = [], []
    for key in a:
        old = a[key]['predicted_block'] == a[key]['expected_block']
        new = b[key]['predicted_block'] == b[key]['expected_block']
        if not old and new:
            fixed.append(key)
        if old and not new:
            regressed.append(key)
    return dict(dataset_sha256=before['dataset_sha256'],
                before_guard=before['guard_sha256'], after_guard=after['guard_sha256'],
                same_guard=before['guard_sha256'] == after['guard_sha256'],
                fixed_ids=fixed, regressed_ids=regressed,
                unchanged_count=len(a)-len(fixed)-len(regressed),
                warning='只比较相同案例的规则判断，不代表端到端质量提升。')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    for command, inputs in [('export', ['report']), ('run', ['dataset']), ('compare', ['before', 'after'])]:
        p = sub.add_parser(command)
        for name in inputs:
            p.add_argument('--'+name, required=True)
        p.add_argument('--out', required=True)
    args = parser.parse_args()
    try:
        if args.action == 'export':
            result = export_dataset(read(args.report))
        elif args.action == 'run':
            result = evaluate(read(args.dataset))
        else:
            result = compare(read(args.before), read(args.after))
        write(args.out, result)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        parser.exit(1, f'处理失败：{error}\n')
    print(json.dumps(result.get('summary', {'saved': args.out}), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
