"""Bounded observation wording, not a semantic verifier or a model retry.

Only a narrowly recognized observation request with a confirmed supported cover
and the reviewed K003 card is eligible. Original model text stays in raw_response.
"""
import re

COVER_TERMS = {'水草': '水草', '倒木': '倒木', '岩石': '岩石', '水草和倒木': '水草和倒木'}
REVIEWED_CLAIM = '大口黑鲈会利用倒木、岩石台阶、植被及人工结构等掩护。'
REVIEWED_NOTE = '用户确认的结构可列为观察候选；结构存在不证明鱼存在。'


def observation_answer(question, task, context, cards, answer):
    """Return a controlled answer only after a valid answered model response."""
    if task != 'site' or answer['status'] != 'answered':
        return None
    clauses = [s.strip() for s in re.split(r'[，,。；;！？!?]', question) if s.strip()]
    if not clauses or not re.fullmatch(
            r'(?:我|我们)?(?:应该|可以|该|要)?(?:先|优先)?(?:观察|看|留意|找)'
            r'(?:什么|哪里|哪儿|哪些地方|哪些位置)', clauses[-1]):
        return None
    if any(t in question for t in ('概率', '中鱼率', '保证', '一定', '水温', '气温', '温度', '装备', '饵', '比较', '最好')):
        return None
    cover = context['cover']
    value = cover.get('value')
    if cover.get('status') != 'user_reported' or value not in COVER_TERMS:
        return None
    card = next((c for c in cards if c['id'] == 'K003'), None)
    # Do not silently reuse the policy after a card's reviewed content changes.
    if not card or card['claim'] != REVIEWED_CLAIM or card['application_note'] != REVIEWED_NOTE:
        return None
    return {
        'status': 'answered', 'followup_question': None,
        'claims': [
            {'kind': 'source_fact', 'text': card['claim'], 'evidence_ids': ['K003'],
             'anchors': [{'card_id': 'K003', 'field': 'claim', 'quote': card['claim']}], 'caveat': None},
            {'kind': 'project_inference',
             'text': f'项目推断（规则生成）：根据你报告的{value}，可以把{value}作为观察候选。',
             'evidence_ids': ['K003'],
             'anchors': [{'card_id': 'K003', 'field': 'claim', 'quote': card['claim']},
                         {'card_id': 'K003', 'field': 'application_note', 'quote': card['application_note']}],
             'caveat': '现场结构来自用户自述，未经实测验证；结构存在不证明有鱼，现有资料不支持位置优先级或效果保证。'}]
    }
