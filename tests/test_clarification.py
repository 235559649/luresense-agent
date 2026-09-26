import json
from pathlib import Path
import tempfile
import unittest
from clarification import ClarificationSession, save_session
from retriever import KnowledgeBase


class ClarificationTests(unittest.TestCase):
    def test_vague_question_then_context_retrieves(self):
        kb = KnowledgeBase()
        s = ClarificationSession('我在淡水边，应该先看哪里？')
        self.assertEqual(kb.search(s.question)['status'], 'empty')
        s.choose('waterbody', '1')
        s.choose('cover', '4')
        self.assertEqual(kb.search(s.retrieval_query())['status'], 'ok')

    def test_unknown_finishes_without_reasking(self):
        s = ClarificationSession('我在淡水边，应该先看哪里？')
        s.choose('waterbody', '0')
        self.assertEqual(s.next_slot(), 'cover')
        s.choose('cover', '0')
        self.assertIsNone(s.next_slot())
        self.assertEqual(s.context()['cover']['status'], 'unknown')
        self.assertEqual(s.retrieval_query(), s.question)

    def test_correction_removes_old_keywords(self):
        s = ClarificationSession('先看哪里？')
        s.choose('waterbody', '1')
        s.choose('cover', '4')
        s.choose('cover', '5')
        self.assertNotIn('水草', s.retrieval_query())
        self.assertNotIn('倒木', s.retrieval_query())
        self.assertEqual(s.events[-1]['event'], 'correct')

    def test_new_session_does_not_share_state(self):
        first = ClarificationSession('先看哪里？')
        first.choose('waterbody', '1')
        second = ClarificationSession('其他问题')
        self.assertEqual(second.facts, {})
        self.assertEqual(second.events, [])

    def test_invalid_option_does_not_change_state(self):
        s = ClarificationSession('先看哪里？')
        with self.assertRaises(ValueError):
            s.choose('waterbody', '湖泊或河流')
        self.assertEqual(s.facts, {})

    def test_partial_context_cannot_retrieve(self):
        with self.assertRaises(ValueError):
            ClarificationSession('先看哪里？').retrieval_query()

    def test_claimed_conditions_are_not_verified(self):
        s = ClarificationSession('先看哪里？')
        s.choose('waterbody', '1')
        self.assertFalse(s.context()['waterbody']['verified'])

    def test_record_and_no_overwrite(self):
        s = ClarificationSession('先看哪里？')
        s.choose('waterbody', '0')
        s.choose('cover', '0')
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'record.json'
            save_session(s.record({'status': 'empty'}), file)
            self.assertFalse(json.loads(file.read_text())['model_called'])
            with self.assertRaises(FileExistsError):
                save_session({}, file)


if __name__ == '__main__':
    unittest.main()
