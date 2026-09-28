"""Check provenance anchors, not semantic entailment or ecological truth."""
import json
import re
from llm import ModelError

OUTPUT_INSTRUCTION = '''
输出契约（本契约替代先前的claims结构）：只输出JSON对象，恰好包含status、claims、followup_question。
status只能是answered或insufficient_evidence；followup_question必须是null。
answered时claims为1至2条；insufficient_evidence时claims为空。
每条claim恰好包含：
{"kind":"source_fact或project_inference","text":"简短主张","evidence_ids":["K003"],
 "anchors":[{"card_id":"K003","field":"claim或application_note","quote":"从该卡相应字段逐字摘录的片段"}],
 "caveat":null或"推断的限制或需要验证的条件"}
source_fact的anchors只允许引用卡片claim字段，不能把application_note包装为来源事实。
project_inference必须提供非空caveat；它仍需要证据锚点，但锚点存在不代表推理成立。
quote是知识卡片段，不是网页原文引语；逐字复制4至180字符，不可改写或添加省略号。
每条1至3个锚点，evidence_ids须与锚点中的card_id集合一致。text限300字符，caveat限200字符。
保留已知/未知条件及地区限制。不在输出中添加URL。宁可一条充分支持的说明，不凑条数。
'''


def _text(value, lower, upper):
    return isinstance(value, str) and lower <= len(value.strip()) <= upper


def validate_grounded(raw, cards):
    try:
        obj = json.loads(raw)
    except (ValueError, TypeError):
        raise ModelError('回答不是有效JSON') from None
    if not isinstance(obj, dict) or set(obj) != {'status', 'claims', 'followup_question'}:
        raise ModelError('回答字段不符合证据契约')
    if obj['status'] not in ('answered', 'insufficient_evidence') or obj['followup_question'] is not None:
        raise ModelError('状态不合法或模型越过流程自行追问')
    claims = obj['claims']
    if not isinstance(claims, list) or len(claims) > 2 or (obj['status'] == 'answered') != bool(claims):
        raise ModelError('主张数量与状态不一致')
    lookup = {card['id']: card for card in cards}
    for claim in claims:
        if not isinstance(claim, dict) or set(claim) != {'kind', 'text', 'evidence_ids', 'anchors', 'caveat'}:
            raise ModelError('每条主张须包含类型、内容、引用、证据片段与限制')
        if claim['kind'] not in ('source_fact', 'project_inference') or not _text(claim['text'], 1, 300):
            raise ModelError('主张类型或长度不合法')
        caveat = claim['caveat']
        if caveat is not None and not _text(caveat, 1, 200):
            raise ModelError('限制说明长度不合法')
        if claim['kind'] == 'project_inference' and caveat is None:
            raise ModelError('项目推断必须说明限制')
        if re.search(r'https?://', claim['text'] + (caveat or '')):
            raise ModelError('来源链接应由程序生成')
        refs = claim['evidence_ids']
        if not isinstance(refs, list) or not refs or not all(isinstance(r, str) for r in refs):
            raise ModelError('引用列表不合法')
        if len(refs) != len(set(refs)) or not set(refs) <= set(lookup):
            raise ModelError('引用重复或不在本次检索证据中')
        anchors = claim['anchors']
        if not isinstance(anchors, list) or not 1 <= len(anchors) <= 3:
            raise ModelError('需要1至3个证据锚点')
        anchored = set()
        for anchor in anchors:
            if not isinstance(anchor, dict) or set(anchor) != {'card_id', 'field', 'quote'}:
                raise ModelError('锚点结构不合法')
            cid, field, quote = anchor['card_id'], anchor['field'], anchor['quote']
            if not isinstance(cid, str) or cid not in refs or field not in ('claim', 'application_note'):
                raise ModelError('锚点卡片或字段不合法')
            if claim['kind'] == 'source_fact' and field != 'claim':
                raise ModelError('项目推断字段不能作为来源事实的锚点')
            if not _text(quote, 4, 180):
                raise ModelError('证据片段须为4至180字符')
            normalize = lambda s: re.sub(r'\s+', '', s)
            if normalize(quote) not in normalize(lookup[cid][field]):
                raise ModelError('证据片段并非指定知识卡字段中的摘录')
            anchored.add(cid)
        if anchored != set(refs):
            raise ModelError('每个引用编号都需要对应证据锚点')
    return obj
