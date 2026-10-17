"""Offline provenance audit. Counts processing events, never semantic accuracy."""
import argparse
from collections import Counter
import json
from pathlib import Path
from review_runs import prepare, write_new


def original_answer(result):
    for key in ('model_answer_before_guard', 'model_answer_before_policy'):
        value = result.get(key)
        if isinstance(value, dict):
            return value, key
    raw = result.get('raw_response')
    if isinstance(raw, str):
        try:
            value = json.loads(raw)
        except ValueError:
            return None, 'unparseable_raw'
        if isinstance(value, dict):
            return value, 'raw_response'
    return None, 'not_recorded'


def build_audit(paths):
    prepared = prepare(paths)  # Keeps SHA256 identity and rejects duplicate files.
    rows = []
    origins, final_statuses, original_statuses = Counter(), Counter(), Counter()
    attempted = received = intercepted = rewritten = token_sum = known_tokens = 0
    nonreal = 0
    for item in prepared['items']:
        r = item['result']
        real = r.get('synthetic') is False
        original, source = original_answer(r)
        raw_status = original.get('status') if original else None
        if not isinstance(raw_status, str):
            raw_status = 'unknown'
        origin = r.get('answer_origin') or 'not_recorded'
        status = r.get('status') or 'unknown'
        is_attempt = r.get('request_attempted') is True
        is_received = r.get('model_response_received') is True
        is_guard = origin == 'context_guard_v1' and bool(r.get('context_guard_conflicts'))
        is_policy = origin == 'reviewed_observation_policy_v1'
        usage = r.get('usage') or {}
        tokens = usage.get('total_tokens') if isinstance(usage, dict) else None
        if not isinstance(tokens, int) or isinstance(tokens, bool) or tokens < 0:
            tokens = None
        if real:
            origins[origin] += 1
            final_statuses[status] += 1
            original_statuses[raw_status] += 1
            attempted += is_attempt
            received += is_received
            intercepted += is_guard
            rewritten += is_policy
            if tokens is not None:
                known_tokens += 1
                token_sum += tokens
        else:
            nonreal += 1
        rows.append({'id': item['id'], 'real_record': real,
                     'final_status': status, 'answer_origin': origin,
                     'request_attempted': is_attempt, 'model_response_received': is_received,
                     'original_declared_status': raw_status, 'original_source': source,
                     'original_claim_count': len(original['claims']) if original and isinstance(original.get('claims'), list) else None,
                     'final_claim_count': len(r.get('claims', [])),
                     'guard_rules': sorted({c.get('rule','unknown') for c in r.get('context_guard_conflicts', [])}),
                     'total_tokens': tokens})
    real_count = len(rows) - nonreal
    return {'schema_version':'1', 'unit':'response turn, not independent scenario',
            'warning':'处理过程审计，不是准确率。原始status只是模型声明；规则拦截不自动证明其语义判断正确。无调用或缺失原始输出记unknown；模拟/未知来源不计入真实记录汇总。',
            'sources': prepared['sources'],
            'summary': {'all_rows':len(rows),'real_rows':real_count,
                        'synthetic_or_unknown_rows':nonreal,
                        'attempted_requests':attempted,'received_model_responses':received,
                        'final_status_counts':dict(final_statuses),
                        'original_declared_status_counts':dict(original_statuses),
                        'answer_origin_counts':dict(origins),
                        'guard_interceptions':intercepted,'policy_rewrites':rewritten,
                        'interception_rate_on_received':intercepted/received if received else None,
                        'known_total_tokens_sum':token_sum,
                        'rows_with_known_tokens':known_tokens,
                        'rows_without_known_tokens':real_count-known_tokens},
            'rows':rows}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',nargs='+',required=True)
    parser.add_argument('--out',required=True)
    args=parser.parse_args()
    try:
        report=build_audit(args.run)
        write_new(args.out,report)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        parser.exit(1, '审计失败：'+str(error)+'\n')
    print(json.dumps(report['summary'],ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
