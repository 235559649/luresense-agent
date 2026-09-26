"""仅检查开发题的参考卡片覆盖，不运行模型，也不评分生态正确性。"""
import argparse
import json
from pathlib import Path
from retriever import KnowledgeBase


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--cases', default=str(Path(__file__).parent/'eval/development.jsonl'))
    args=parser.parse_args()
    cases=[json.loads(line) for line in Path(args.cases).read_text(encoding='utf-8').splitlines() if line.strip()]
    kb=KnowledgeBase()
    rows=[]
    for case in cases:
        if not case['reference_card_ids']:
            continue
        retrieved=kb.search(case['user_message'])
        got={r['card']['id'] for r in retrieved['results']}
        expected=set(case['reference_card_ids'])
        rows.append({'id':case['id'],'expected':sorted(expected),'retrieved':sorted(got),
                     'reference_coverage_at_4':len(got & expected)/len(expected)})
    print(json.dumps({'kind':'retrieval_only_development_pilot','not_model_or_field_evaluation':True,
                      'evaluated_cases':len(rows),'skipped_cases':len(cases)-len(rows),
                      'mean_reference_coverage_at_4':sum(r['reference_coverage_at_4'] for r in rows)/len(rows) if rows else None,
                      'rows':rows},ensure_ascii=False,indent=2))


if __name__=='__main__': main()
