"""Regression checks for migration completeness and version boundaries."""
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('catalog_build', ROOT/'scripts/build.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog, cls.entries = build.load_catalog()

    def test_every_imported_row_has_a_destination(self):
        source = self.catalog['source']
        imported = [p for e in self.entries for p in e['provenance'] if p['source_id'] == source['id']]
        self.assertEqual(len(imported), source['imported_source_rows'])
        positions = {(p['sheet'],p['row']) for p in imported}
        self.assertEqual(len(positions),len(imported))

    def test_topic_only_records_and_bgm_are_preserved(self):
        self.assertTrue(any(e['title']=='上海滩' and e['artist_credit']=='叶丽仪' for e in self.entries))
        self.assertTrue(any(e['kind']=='bgm' and '光芒与希望' in e['aliases'] for e in self.entries))

    def test_same_title_different_works_remain_distinct(self):
        versions = [e for e in self.entries if e['title']=='神的传说']
        self.assertGreaterEqual(len(versions),2)
        self.assertGreaterEqual(len({e['composer_credit'] for e in versions}),2)

    def test_initial_year_conflict_has_not_disappeared(self):
        versions = [e for e in self.entries if e['title']=='江南' and e['artist_credit']=='林俊杰']
        # Once the discrepancy is resolved, reviewed records should explain that status.
        self.assertTrue({2003,2004}.issubset({e['year'] for e in versions}) or any(e['review_status']=='reviewed' for e in versions))

    def test_rejects_private_audio_location(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'data/entries').mkdir(parents=True)
            entry = copy.deepcopy(self.entries[0])
            entry['audio_refs']=['https://private-bucket.example/file.mp3?signature=secret']
            entry['collection_ids']=[]
            entry['related_entry_ids']=[]
            (root/'data/catalog.json').write_text(json.dumps({'collections':[]}))
            (root/'data/site.json').write_text(json.dumps({'repository_url':None}))
            (root/'data/entries'/f"{entry['id']}.json").write_text(json.dumps(entry))
            with patch.object(build,'ROOT',root):
                with self.assertRaisesRegex(ValueError,'opaque resource IDs'):
                    build.load_catalog()

if __name__ == '__main__':
    unittest.main()
