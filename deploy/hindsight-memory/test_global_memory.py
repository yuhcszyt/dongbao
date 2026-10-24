import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('gm', Path(__file__).with_name('global_memory.py'))
gm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gm)


def lesson(**kw):
    return dict(key='docker-dns-resolution', existing_id=None, symptom='Docker DNS failure',
                cause='Container resolver configuration', solution='Check resolver in container',
                conditions='Docker bridge network', **kw)


class GlobalMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.prev = gm.DB
        gm.DB = str(Path(self.tmp.name) / 'state.sqlite')
        gm.connect().close()

    def tearDown(self):
        gm.DB = self.prev
        self.tmp.cleanup()

    def count(self, table):
        with gm.connect() as c:
            return c.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0]

    def test_outbox_ignores_fallback_and_global_and_deduplicates(self):
        gm.enqueue('default', 'd')
        gm.enqueue('global', 'd')
        gm.enqueue('a', 'd')
        gm.enqueue('a', 'd')
        self.assertEqual(self.count('sources'), 1)

    def test_repeated_evidence_one_lesson(self):
        gm.enqueue('a', 'd')
        for _ in range(3):
            gm.replace_evidence('a', 'd', [lesson()], 'hash')
        self.assertEqual(self.count('evidence'), 1)
        self.assertEqual(self.count('lessons'), 1)

    def test_cross_project_dedup_and_provenance(self):
        for bank in ('a', 'b'):
            gm.enqueue(bank, 'd')
            gm.replace_evidence(bank, 'd', [lesson()], 'hash')
        self.assertEqual(self.count('lessons'), 1)
        with patch.object(gm, 'request', return_value={'success': True}) as req:
            gm.publish()
        self.assertIn('/banks/global/', req.call_args.args[1])
        item = req.call_args.args[2]['items'][0]
        self.assertEqual(json.loads(item['metadata']['sources']), [['a', 'd'], ['b', 'd']])

    def test_no_republish_unchanged(self):
        gm.enqueue('a', 'd')
        gm.replace_evidence('a', 'd', [lesson()], 'hash')
        with patch.object(gm, 'request', return_value={'success': True}) as req:
            gm.publish()
            gm.replace_evidence('a', 'd', [lesson()], 'hash')
            gm.publish()
            self.assertEqual(req.call_count, 1)

    def test_retract_deleted_source(self):
        gm.enqueue('a', 'd')
        gm.replace_evidence('a', 'd', [lesson()], 'hash')
        with gm.connect() as c:
            row = c.execute('SELECT * FROM sources').fetchone()
        with patch.object(gm, 'request', return_value=None):
            gm.process_source(row)
        self.assertEqual(self.count('evidence'), 0)
        with patch.object(gm, 'request', return_value=None) as req:
            gm.publish()
            self.assertEqual(req.call_args.args[0], 'DELETE')
            self.assertIn('/banks/global/', req.call_args.args[1])

    def test_partial_invalidation_retracts_conservatively(self):
        gm.enqueue('a', 'd')
        gm.replace_evidence('a', 'd', [lesson()], 'hash')
        with gm.connect() as c:
            row = c.execute('SELECT * FROM sources').fetchone()
        with patch.object(gm, 'request', side_effect=[{'original_text': 'new'}, {'total': 1}]):
            gm.process_source(row)
        self.assertEqual(self.count('evidence'), 0)

    def test_publication_failure_remains_dirty(self):
        gm.enqueue('a', 'd')
        gm.replace_evidence('a', 'd', [lesson()], 'hash')
        with patch.object(gm, 'request', side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):
                gm.publish()
        with gm.connect() as c:
            self.assertEqual(c.execute('SELECT dirty FROM lessons').fetchone()[0], 1)

    def test_sensitive_data_redaction(self):
        text = 'password=not-real api_key=demo-value 13812345678 person@example.com 192.0.2.1 /Users/alice/app'
        clean = gm.redact(text)
        for sensitive in ['not-real', 'demo-value', '13812345678', 'person@example.com', '192.0.2.1', 'alice']:
            self.assertNotIn(sensitive, clean)

    def test_merge_keeps_origin_and_partial_error(self):
        value = gm.merged([('a', {'results': [{'id': '1', 'text': 'one'}]}), ('default', {'error': 'timeout'})])
        self.assertEqual(value['results'][0]['source_bank'], 'a')
        self.assertIn('default', value['errors'])

    def test_fallback_bounded_relevant_only(self):
        for bank in ('a', 'b', 'c', 'd'):
            gm.enqueue(bank, 'doc')
            gm.replace_evidence(bank, 'doc', [lesson()], 'hash')
        self.assertEqual(len(gm.related_banks('Docker DNS', {'a'})), 2)
        self.assertEqual(gm.related_banks('unrelated bananas', set()), [])

    def test_source_changed_during_extraction_is_not_published(self):
        gm.enqueue('a', 'd')
        with gm.connect() as c:
            row = c.execute('SELECT * FROM sources').fetchone()
        with patch.object(gm, 'request', side_effect=[{'original_text': 'first'}, {'total': 0}, {'original_text': 'second'}]), patch.object(gm, 'candidates_for', return_value=[]), patch.object(gm, 'extract', return_value=[lesson()]):
            with self.assertRaises(RuntimeError):
                gm.process_source(row)
        self.assertEqual(self.count('evidence'), 0)

if __name__ == '__main__':
    unittest.main()
