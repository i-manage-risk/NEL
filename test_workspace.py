import unittest
import json
from pathlib import Path
from positioning import range_index
from site_chrome import apply_chrome

class WorkspaceTests(unittest.TestCase):
    def test_index_boundaries(self):
        self.assertIsNone(range_index(list(range(155))))
        self.assertIsNone(range_index([1]*156))
        self.assertEqual(range_index(list(range(156))), 100)
        self.assertEqual(range_index(list(range(155,-1,-1))), 0)

    def test_all_scans_preserved_in_workspace(self):
        payload=json.loads(Path('outputs/workspace.json').read_text())
        expected={p.stem.replace('filtered_universe_', '') for p in Path('outputs').glob('filtered_universe_*.csv')}
        self.assertEqual({s['date'] for s in payload['snapshots']},expected)
        self.assertTrue(all(s['closeDate'] < s['date'] for s in payload['snapshots']))

    def test_chrome_idempotent(self):
        page=apply_chrome('<html><head></head><body></body></html>','liquid')
        self.assertEqual(apply_chrome(page,'liquid'),page)

if __name__=='__main__':
    unittest.main()
