"""Create a catalog entry with a permanent ID and conservative defaults."""
import argparse
import json
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--title', required=True)
    parser.add_argument('--artist', default='待核')
    parser.add_argument('--kind', choices=['song','bgm'], default='song')
    args = parser.parse_args()
    entry = {'schema_version':1, 'id':'snd-'+uuid.uuid4().hex[:16], 'title':args.title,
             'aliases':[], 'kind':args.kind, 'artist_credit':args.artist, 'composer_credit':'待核',
             'year':None, 'year_label':'年代待核', 'year_basis':'尚未核实', 'album':'', 'context':'',
             'language':'待核', 'editorial_grade':None, 'tags':[], 'carriers':[], 'notes':'',
             'sources':[], 'review_status':'unreviewed', 'issues':['public_source_missing','year_uncertain'],
             'collection_ids':[], 'provenance':[], 'related_entry_ids':[], 'audio_refs':[], 'revision':1}
    path = ROOT / 'data/entries' / (entry['id']+'.json')
    path.write_text(json.dumps(entry,ensure_ascii=False,indent=2)+'\n')
    print(path.relative_to(ROOT))

if __name__ == '__main__':
    main()
