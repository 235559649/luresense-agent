"""Offline retrieval/state benchmark: no model calls, no answer-quality claims."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
from statistics import mean

from context_agent import ContextSession, OPTIONS, respond, session_record
from retriever import KnowledgeBase

ROOT = Path(__file__).resolve().parent
ARMS = ('direct', 'append_context', 'agent_state')


def digest(data):
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')


def load_cases(path, kb):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('schema_version') != 1 or not isinstance(data.get('cases'), list) or not data['cases']:
        raise ValueError('情景文件须为 schema_version=1 且包含非空 cases')
    ids, known = set(), {c['id'] for c in kb.cards}
    for c in data['cases']:
        required = {'id','split','category','question','answers','corrections','relevant_ids',
                    'expect_no_evidence','expected_context','forbidden_query_terms'}
        if not isinstance(c, dict) or set(c) != required:
            raise ValueError('情景字段缺失或多余')
        if not isinstance(c['id'], str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', c['id']) or c['id'] in ids:
            raise ValueError('情景ID须唯一且为安全文件名')
        ids.add(c['id'])
        if c['split'] not in ('dev','challenge') or not isinstance(c['category'], str) or not c['category']:
            raise ValueError('split/category不合法')
        ContextSession(c['question'])
        if not isinstance(c['answers'], dict) or not isinstance(c['corrections'], list):
            raise ValueError('补充与修正格式错误')
        selections = list(c['answers'].items())
        for edit in c['corrections']:
            if not isinstance(edit, list) or len(edit) != 2:
                raise ValueError('修正须为[slot, choice]')
            selections.append(edit)
        for slot, choice in selections:
            if not isinstance(slot, str) or slot not in OPTIONS or not isinstance(choice, str) or choice not in OPTIONS[slot]:
                raise ValueError('选项不合法')
        rel = c['relevant_ids']
        if not isinstance(rel, list) or not all(isinstance(i,str) and i in known for i in rel) or len(set(rel)) != len(rel):
            raise ValueError('相关卡片ID不存在或重复')
        if type(c['expect_no_evidence']) is not bool or c['expect_no_evidence'] != (not bool(rel)):
            raise ValueError('相关卡标注与无证据预期矛盾')
        if not isinstance(c['expected_context'], dict) or any(k not in OPTIONS or v not in OPTIONS[k].values() for k,v in c['expected_context'].items()):
            raise ValueError('预期上下文不合法')
        if not isinstance(c['forbidden_query_terms'], list) or not all(isinstance(t,str) and t for t in c['forbidden_query_terms']):
            raise ValueError('失效关键词须为非空字符串数组')
    return data


def replay(case):
    session = ContextSession(case['question'])
    while True:
        slot = session.next_question()
        if slot is None:
            break
        if slot not in case['answers']:
            raise ValueError(f"{case['id']} 缺少脚本回答：{slot}；不得自动补成未知")
        session.choose(slot, case['answers'][slot])
    for slot, choice in case['corrections']:
        session.choose(slot, choice)
    return session


def score(case, ids, query, context=None):
    relevant = set(case['relevant_ids'])
    hit = bool(relevant.intersection(ids))
    first = next((i for i, key in enumerate(ids, 1) if key in relevant), None)
    expected = case['expected_context']
    return {'hit_at_4': hit if relevant else None,
            'recall_at_4': len(relevant.intersection(ids))/len(relevant) if relevant else None,
            'reciprocal_rank_at_4': (1/first if first else 0) if relevant else None,
            'empty_on_negative': not ids if case['expect_no_evidence'] else None,
            'stale_query_clean': not any(t in query for t in case['forbidden_query_terms']) if case['forbidden_query_terms'] else None,
            'context_exact': all(context[k]['value'] == v and context[k]['status'] != 'unanswered' for k,v in expected.items()) if expected and context is not None else None}


def run_case(case, kb):
    session = replay(case)
    # Same final facts as the agent arm; original wording remains in this naive baseline.
    labels = {'waterbody':'水域','cover':'可见结构','temperature_source':'温度来源'}
    additions = [f"{labels[k]}：{v['value'] if v['value'] is not None else '未知'}"
                 for k,v in session.context().items() if v['status'] != 'unanswered']
    queries = {'direct':case['question'], 'append_context':case['question']+'；当前补充条件：'+'；'.join(additions)}
    results = []
    for arm in ARMS:
        if arm == 'agent_state':
            answer = respond(session, kb, mode='mock')
            ids, query, status = answer['retrieved_ids'], answer['retrieval_query'], answer['status']
        else:
            query = queries[arm]
            r = kb.search(query, limit=4)
            ids, status = [v['card']['id'] for v in r['results']], r['status']
        results.append({'case_id':case['id'],'split':case['split'],'category':case['category'],
                        'arm':arm,'query':query,'retrieved_ids':ids,'status':status,
                        'metrics':score(case,ids,query,session.context() if arm == 'agent_state' else None)})
    return results, session_record(session,kb)


def rate(values):
    values = [v for v in values if v is not None]
    return {'n':len(values),'mean':mean(values) if values else None}


def summarize(rows):
    groups = {}
    keys = ('hit_at_4','recall_at_4','reciprocal_rank_at_4','empty_on_negative','stale_query_clean','context_exact')
    for arm in ARMS:
        subset = [r for r in rows if r['arm'] == arm]
        groups[arm] = {'cases':len(subset), **{key:rate([r['metrics'][key] for r in subset]) for key in keys}}
    return groups


def format_rate(value):
    return '— (n=0)' if value['mean'] is None else f"{value['mean']:.3f} (n={value['n']})"


def report_text(result):
    lines = ['# LureSense 检索与状态实验', '',
             '**离线结果；没有调用模型，不表示回答正确率或钓鱼效果。**', '',
             f"情景数：{result['scenario_count']}；划分：{result['split']}；数据哈希：`{result['dataset_sha256']}`。", '',
             '标注为项目作者拟定的待复核卡片集合；challenge 是压力测试，不是独立盲测。', '',
             '| 方法 | Hit@4 | Recall@4 | MRR@4 | 负例空检索率 | 失效词移除率 | 状态匹配率 |',
             '| --- | --- | --- | --- | --- | --- | --- |']
    for arm,g in result['summary'].items():
        keys = ('hit_at_4','recall_at_4','reciprocal_rank_at_4','empty_on_negative','stale_query_clean','context_exact')
        lines.append('| '+arm+' | '+' | '.join(format_rate(g[k]) for k in keys)+' |')
    lines += ['', '## 如何解释', '',
              '- direct 只获得原问题；其他两组获得补充条件。与 direct 的差异同时包含信息增益，不能单独归因于算法。',
              '- append_context 将原问题与最终条件拼接；agent_state 按状态重写查询。此对照用于观察原问题失效词的影响。',
              '- 拼接基线中的字段名本身也可能命中检索词；差异包含序列化方式的影响，不是独立因果实验。',
              '- 状态匹配只对 agent_state 适用；没有状态的基线不计零分。所有指标只用适用案例作分母。',
              '- Recall@4 只对已标注相关卡计算；卡片集合不是穷尽标注，因此不计算 Precision。',
              '- 负例空检索率衡量检索门控，不衡量模型是否恰当拒答。相关主题卡片存在也不保证具体结论可回答。',
              '- 仅评估修正后的最终状态；原有单元测试另覆盖多轮历史。离线运行无网络耗时和模型费用指标。',
              '', '## 失败与部分召回（全部保留）', '',
              '| 案例 | 方法 | 类别 | 问题 | 召回 ID | 未满足项 |', '| --- | --- | --- | --- | --- | --- |']
    failed = 0
    for r in result['rows']:
        misses = [k for k,v in r['metrics'].items() if (isinstance(v,bool) and not v) or (k == 'recall_at_4' and v is not None and v < 1)]
        if misses:
            failed += 1
            question = result['questions'][r['case_id']].replace('|','/').replace('\n',' ')
            lines.append(f"| {r['case_id']} | {r['arm']} | {r['category']} | {question} | {', '.join(r['retrieved_ids']) or '空'} | {', '.join(misses)} |")
    if not failed:
        lines.append('| — | — | — | — | — | 本集合无上述失败；不能据此推断泛化 |')
    lines += ['', '## 可追溯信息', '', '```json',json.dumps(result['provenance'],ensure_ascii=False,indent=2),'```','']
    return '\n'.join(lines)


def run_benchmark(dataset_path, split, out):
    kb = KnowledgeBase()
    data = load_cases(dataset_path,kb)
    selected = [c for c in data['cases'] if split == 'all' or c['split'] == split]
    if not selected:
        raise ValueError('所选划分没有案例')
    # All replay scripts are validated before creating output.
    for case in selected:
        replay(case)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    (out/'agent_runs').mkdir()
    rows=[]
    for c in selected:
        results, record = run_case(c,kb)
        rows.extend(results)
        write_json(out/'agent_runs'/f"{c['id']}.json",record)
    names = ('benchmark_v05.py','retriever.py','context_agent.py','grounding.py','llm.py','agent_v03.py')
    result = {'schema_version':1,'experiment':'offline_retrieval_state','model_called':False,
              'recorded_at_utc':datetime.now(timezone.utc).isoformat(), 'split':split,
              'scenario_count':len(selected),'category_counts':dict(Counter(c['category'] for c in selected)),
              'dataset_sha256':digest(data),'dataset_snapshot':data,
              'questions':{c['id']:c['question'] for c in selected},
              'provenance':{'python':platform.python_version(),'knowledge_sha256':digest(kb.cards),
                            'sources_sha256':digest(kb.sources),'label_status':data.get('label_status','unknown'),
                            'code_sha256':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}},
              'summary':summarize(rows),'by_category':{},'rows':rows}
    for category in result['category_counts']:
        result['by_category'][category] = summarize([r for r in rows if r['category'] == category])
    write_json(out/'results.json',result)
    (out/'REPORT.md').write_text(report_text(result),encoding='utf-8')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases',type=Path,default=ROOT/'data/scenarios_v05.json')
    parser.add_argument('--split',choices=('dev','challenge','all'),default='dev')
    parser.add_argument('--out',type=Path,required=True,help='必须是尚不存在的目录；避免覆盖实验记录')
    args=parser.parse_args()
    result=run_benchmark(args.cases,args.split,args.out)
    print(f"完成 {result['scenario_count']} 个情景 × 3 组；模型调用 0 次。报告：{args.out/'REPORT.md'}")
    print('指标差或未通过案例保留在报告中，不作为程序执行失败。')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError) as error:
        raise SystemExit(str(error))
