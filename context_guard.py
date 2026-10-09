"""Bounded Chinese checks for upgrading missing observations to presence or absence.

Not a semantic verifier. Only explicit patterns are covered. Preserve raw model
answers in the caller; do not automatically retry or claim the model is correct.
"""
import re

STRUCTURES = r'(?:水草|倒木|岩石(?:台阶)?|植被|掩护(?:结构)?|藏匿结构|覆盖|结构)'
ABSENCE = re.compile(
    r'(?:没有|不存在|缺乏|缺少|无)(?:任何|这些|上述|常见的|常见|可供鱼类使用的|鱼类)*' + STRUCTURES
    + r'|(?:水草|倒木|岩石|植被|掩护结构)(?:均|都|全部)?不存在')
PRESENCE = re.compile(
    r'(?:已知|已确认|已经确认)(?:的|有|存在)?' + STRUCTURES
    + r'|(?:现场|这里|附近|岸边)(?:已经确认|已确认|已知)?(?:有|存在)' + STRUCTURES)
DISCLAIMER = re.compile(
    r'不代表|不等于|不意味着|不证明|并非|不是'
    r'|(?:不能|无法|尚不能|不足以)(?:据此)?(?:断定|认定|判断|确定|确认|证明|说明|说)')


def context_conflicts(answer, context):
    cover = context.get('cover', {})
    if not (cover.get('status') in ('unknown', 'unanswered') or
            cover.get('value') == '未观察到上述结构'):
        return []
    conflicts = []
    for index, claim in enumerate(answer['claims']):
        # A caveat in another sentence must not erase an unsupported premise.
        for field in ('text', 'caveat'):
            for clause in re.split(r'[，,。；;！？!?\n]', claim.get(field) or ''):
                for rule, pattern in (('unobserved_to_absent', ABSENCE),
                                      ('unobserved_to_present', PRESENCE)):
                    for match in pattern.finditer(clause):
                        prefix = clause[:match.start()]
                        # A new causal assertion is not covered by an earlier disclaimer.
                        local_prefix = re.split(r'所以|因此|故而|于是', prefix)[-1]
                        if DISCLAIMER.search(local_prefix):
                            continue
                        # "如果现场没有..." is hypothetical, not a current observation.
                        # "没有...时，现场缺乏..." is still caught by the second clause.
                        if re.match(r'\s*(?:如果|假如|假设|若)', clause):
                            continue
                        conflicts.append({'claim_index': index, 'field': field,
                                          'rule': rule, 'matched_text': match.group()})
    return conflicts
