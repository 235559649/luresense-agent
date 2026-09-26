"""v0.3-step1: bounded, offline, structured clarification; no model calls."""
from dataclasses import dataclass, field
import json
from pathlib import Path

OPTIONS = {
    'waterbody': {'1': '湖泊', '2': '水库', '3': '河流', '4': '池塘', '0': None},
    'cover': {'1': '水草', '2': '倒木', '3': '岩石', '4': '水草和倒木',
              '5': '未观察到上述结构', '0': None},
}
QUESTIONS = {
    'waterbody': '水域类型？1 湖泊 / 2 水库 / 3 河流 / 4 池塘 / 0 不知道',
    'cover': '你确认看到了什么？1 水草 / 2 倒木 / 3 岩石 / 4 水草和倒木 / 5 未观察到上述结构 / 0 不知道',
}


@dataclass
class ClarificationSession:
    question: str
    facts: dict = field(default_factory=dict)
    events: list = field(default_factory=list)

    def __post_init__(self):
        if not isinstance(self.question, str) or not self.question.strip() or len(self.question) > 1000:
            raise ValueError('初始问题须为1～1000字符')
        self.question = self.question.strip()

    def next_slot(self):
        # A recorded None is an explicit unknown, not an unanswered question.
        return next((key for key in OPTIONS if key not in self.facts), None)

    def choose(self, slot, choice):
        if slot not in OPTIONS or choice not in OPTIONS[slot]:
            raise ValueError('请选择该项列出的编号；不知道请选择0')
        previous = self.facts.get(slot)
        value = OPTIONS[slot][choice]
        self.events.append({'event': 'correct' if slot in self.facts else 'answer',
                            'slot': slot, 'previous': previous, 'value': value,
                            'source': 'user_selection'})
        self.facts[slot] = value

    def context(self):
        return {key: {'value': self.facts.get(key),
                      'status': ('unanswered' if key not in self.facts else
                                 'unknown' if self.facts[key] is None else 'user_reported'),
                      'verified': False} for key in OPTIONS}

    def retrieval_query(self):
        if self.next_slot() is not None:
            raise ValueError('请先完成两项选择，也可以选择不知道')
        # Keep negatives/unknowns in the state, not as positive retrieval keywords.
        terms = [value for key, value in self.facts.items()
                 if value is not None and not (key == 'cover' and value == '未观察到上述结构')]
        return self.question + ('；用户补充：' + '、'.join(terms) if terms else '')

    def record(self, retrieval):
        return {'app_version': '0.3-step1', 'workflow': 'guided_clarification',
                'question': self.question, 'scope_assumption': '淡水大口黑鲈；并非确认现场有鱼',
                'context': self.context(), 'events': self.events,
                'retrieval_query': self.retrieval_query(), 'retrieval': retrieval,
                'model_called': False,
                'limitations': ['用户自述未经现场验证', '尚未检查资料与条件的语义一致性',
                                '不自动解析初始问题中的条件，可能重复确认']}


def save_session(record, filename):
    with Path(filename).open('x', encoding='utf-8') as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)
