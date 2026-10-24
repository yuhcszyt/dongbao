import importlib.util
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('gm', Path(__file__).with_name('global_memory.py'))
gm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gm)

ENV = {'HINDSIGHT_API_LLM_MODEL': 'test-model',
       'HINDSIGHT_API_LLM_BASE_URL': 'https://llm.invalid/v1',
       'HINDSIGHT_API_LLM_API_KEY': 'test-key'}

GOOD = {'topic': 'docker-dns', 'text': '容器内 DNS 解析失败时先检查 /etc/resolv.conf 是否被宿主机覆盖，适用 Docker 桥接网络'}


class FakeResp:
    def __init__(self, payload):
        self.buf = json.dumps(payload).encode()

    def read(self):
        return self.buf

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def chat(items):
    return {'choices': [{'message': {'content': json.dumps({'lessons': items}, ensure_ascii=False)}}]}


class GlobalMemoryTests(unittest.TestCase):
    def promote(self, items, document=None, invalid=None, recall=None, docs=None):
        """Run promote() with Hindsight REST stubbed; return the request mock."""
        responses = [document if document is not None else {'original_text': 'some text'},
                     invalid if invalid is not None else {'total': 0},
                     recall if recall is not None else {'chunks': {}},
                     docs if docs is not None else {'items': []}]
        responses += [{'success': True}] * len(items)
        with patch.dict(os.environ, ENV), patch.object(gm, 'urlopen') as opened, \
                patch.object(gm, 'request', side_effect=responses) as req:
            opened.side_effect = [FakeResp(chat(items))]
            gm.promote('proj', 'doc')
        return req

    def test_promote_ignores_fallback_and_global_banks(self):
        with patch.object(gm, 'request') as req, patch.object(gm, 'urlopen') as opened:
            gm.promote('default', 'doc')
            gm.promote('global', 'doc')
            gm.promote('proj', '')
        req.assert_not_called()
        opened.assert_not_called()

    def test_promote_skips_missing_and_retired_documents(self):
        cases = ((None, {'total': 1}, 1), ({'original_text': 'x'}, {'total': 1}, 2),
                 ({'original_text': ''}, {'total': 0}, 2))
        for document, invalid, calls in cases:
            with patch.object(gm, 'request', side_effect=[document, invalid]) as req, \
                    patch.object(gm, 'urlopen') as opened:
                gm.promote('proj', 'doc')
            self.assertEqual(req.call_count, calls, document)
            opened.assert_not_called()

    def test_promote_retains_lesson_into_global_bank(self):
        req = self.promote([GOOD])
        calls = [c for c in req.call_args_list if c.args[1].endswith('/memories')]
        self.assertEqual(len(calls), 1)
        self.assertIn('/banks/global/', calls[0].args[1])
        item = calls[0].args[2]['items'][0]
        self.assertEqual(item['content'], GOOD['text'])
        self.assertIn('global-experience', item['tags'])
        self.assertEqual(item['metadata']['source_bank'], 'proj')

    def test_promote_without_lesson_never_retains(self):
        req = self.promote([])
        self.assertFalse(any(c.args[1].endswith('/memories') for c in req.call_args_list))

    def test_llm_output_rejects_bad_topic(self):
        with patch.dict(os.environ, ENV), patch.object(gm, 'urlopen') as opened:
            opened.side_effect = [FakeResp(chat([{'topic': 'Bad Topic!', 'text': 'x' * 40}]))]
            with self.assertRaises(ValueError):
                gm.llm_lessons('source', [], [])

    def test_llm_output_rejects_secrets_and_short_text(self):
        for item in ({'topic': 'ok', 'text': 'password=hunter2 ' + 'x' * 40}, {'topic': 'ok', 'text': 'short'}):
            with patch.dict(os.environ, ENV), patch.object(gm, 'urlopen') as opened:
                opened.side_effect = [FakeResp(chat([item]))]
                with self.assertRaises(ValueError):
                    gm.llm_lessons('source', [], [])

    def test_llm_output_rejects_too_many_lessons(self):
        with patch.dict(os.environ, ENV), patch.object(gm, 'urlopen') as opened:
            opened.side_effect = [FakeResp(chat([GOOD, GOOD, GOOD]))]
            with self.assertRaises(ValueError):
                gm.llm_lessons('source', [], [])

    def test_sensitive_data_redaction(self):
        text = 'password=not-real api_key=demo-value 13812345678 person@example.com 192.0.2.1 /Users/alice/app'
        clean = gm.redact(text)
        for sensitive in ['not-real', 'demo-value', '13812345678', 'person@example.com', '192.0.2.1', 'alice']:
            self.assertNotIn(sensitive, clean)

    def test_existing_lessons_reads_chunks_and_topics(self):
        with patch.object(gm, 'request', side_effect=[{'chunks': {'a': {'text': 'old lesson'}}},
                                                      {'items': [{'tags': ['global-experience', 'topic:docker-dns']}]}]):
            chunks, topics = gm.existing_lessons('text')
        self.assertEqual(chunks, ['old lesson'])
        self.assertEqual(topics, ['docker-dns'])

    def test_promote_reuses_topic_so_same_lesson_is_replaced(self):
        req = self.promote([GOOD], docs={'items': [{'tags': ['topic:' + GOOD['topic']]}]})
        item = [c for c in req.call_args_list if c.args[1].endswith('/memories')][0].args[2]['items'][0]
        self.assertEqual(item['update_mode'], 'replace')
        self.assertEqual(item['document_id'], 'gm-' + gm.digest(GOOD['topic'])[:24])


if __name__ == '__main__':
    unittest.main()
