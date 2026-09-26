"""Build only allowlisted static assets and catalog data for GitHub Pages."""
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {'schema_version', 'id', 'title', 'aliases', 'kind', 'artist_credit', 'composer_credit',
            'year', 'year_label', 'year_basis', 'album', 'context', 'language', 'editorial_grade',
            'tags', 'carriers', 'notes', 'sources', 'review_status', 'issues', 'collection_ids',
            'provenance', 'related_entry_ids', 'audio_refs', 'revision'}

def load_catalog():
    catalog = json.loads((ROOT / 'data/catalog.json').read_text())
    site = json.loads((ROOT / 'data/site.json').read_text())
    repository_url = site.get('repository_url')
    if repository_url and not re.fullmatch(r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository_url):
        raise ValueError('Invalid repository URL')
    catalog['repository_url'] = repository_url
    entries = []
    for path in sorted((ROOT / 'data/entries').glob('*.json')):
        entry = json.loads(path.read_text())
        if set(entry) != REQUIRED:
            raise ValueError(f'{path.name}: unsupported or missing fields: {set(entry) ^ REQUIRED}')
        if entry['id'] != path.stem or not re.fullmatch(r'snd-[0-9a-f]{16}', entry['id']):
            raise ValueError(f'{path.name}: invalid stable ID')
        if not isinstance(entry['title'], str) or not entry['title'].strip():
            raise ValueError(f'{path.name}: empty title')
        if entry['kind'] not in ['song', 'bgm'] or entry['review_status'] not in ['unreviewed', 'in_review', 'reviewed', 'disputed']:
            raise ValueError(f'{path.name}: invalid enum')
        if entry['year'] is not None and (type(entry['year']) is not int or not 1000 <= entry['year'] <= 2100):
            raise ValueError(f'{path.name}: invalid year')
        if entry['editorial_grade'] not in [None, 'S', 'A', 'B']:
            raise ValueError(f'{path.name}: invalid grade')
        text_fields = ['artist_credit', 'composer_credit', 'year_label', 'year_basis', 'album', 'context', 'language', 'notes']
        if any(not isinstance(entry[field], str) for field in text_fields):
            raise ValueError(f'{path.name}: invalid text field')
        for field in ['aliases', 'tags', 'carriers', 'issues', 'collection_ids', 'related_entry_ids', 'audio_refs']:
            if not isinstance(entry[field], list) or any(not isinstance(value, str) for value in entry[field]):
                raise ValueError(f'{path.name}: invalid list field {field}')
        if type(entry['revision']) is not int or entry['revision'] < 1 or entry['schema_version'] != 1:
            raise ValueError(f'{path.name}: invalid revision or schema version')
        if not isinstance(entry['sources'], list) or not isinstance(entry['provenance'], list):
            raise ValueError(f'{path.name}: invalid source/provenance list')
        for source in entry['sources']:
            if set(source) != {'url', 'verification'} or source['verification'] not in ['unreviewed', 'supported', 'contradicted', 'unavailable']:
                raise ValueError(f'{path.name}: invalid source fields')
            parsed = urlparse(source['url'])
            if parsed.scheme not in ['http', 'https'] or not parsed.netloc or parsed.username or parsed.password:
                raise ValueError(f'{path.name}: invalid source URL')
        for provenance in entry['provenance']:
            if set(provenance) != {'source_id', 'sheet', 'row'} or type(provenance['row']) is not int or provenance['row'] < 2:
                raise ValueError(f'{path.name}: invalid provenance')
        # Public audio references contain opaque IDs only. Never publish storage keys or credentials.
        if any(not isinstance(ref, str) or not re.fullmatch(r'aud-[0-9a-f]{16,32}', ref) for ref in entry['audio_refs']):
            raise ValueError(f'{path.name}: audio_refs must contain opaque resource IDs only')
        if re.search(r'/Users/|/Volumes/|(?:localhost|127\.0\.0\.1)|AKIA[A-Z0-9]{16}|X-Amz-Signature=', json.dumps(entry)):
            raise ValueError(f'{path.name}: private data in public entry')
        entries.append(entry)
    ids = {e['id'] for e in entries}
    collections = {c['id'] for c in catalog['collections']}
    if len(ids) != len(entries):
        raise ValueError('Duplicate IDs')
    for entry in entries:
        if not set(entry['related_entry_ids']) <= ids or not set(entry['collection_ids']) <= collections:
            raise ValueError(f"{entry['id']}: dangling reference")
    for collection in catalog['collections']:
        if not set(collection['entry_ids']) <= ids:
            raise ValueError('Collection has missing entries')
        actual = {e['id'] for e in entries if collection['id'] in e['collection_ids']}
        if actual != set(collection['entry_ids']):
            raise ValueError(f"{collection['id']}: collection membership is inconsistent")
    return catalog, entries

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    catalog, entries = load_catalog()
    if not args.check:
        output = ROOT / 'dist'
        output.mkdir(exist_ok=True)
        allowed = ['index.html', 'style.css', 'app.js', 'favicon.svg']
        for name in allowed:
            shutil.copy2(ROOT / 'web' / name, output / name)
        # GitHub Pages may continue serving a cached app.js at an unchanged URL.
        # Fingerprint the static assets in the generated HTML so deployments load
        # the matching code and styles immediately after each content change.
        index_path = output / 'index.html'
        index_html = index_path.read_text()
        for attribute, name in [('href', 'style.css'), ('src', 'app.js')]:
            source = (ROOT / 'web' / name).read_bytes()
            version = hashlib.sha256(source).hexdigest()[:12]
            old_reference = f'{attribute}="./{name}"'
            new_reference = f'{attribute}="./{name}?v={version}"'
            if index_html.count(old_reference) != 1:
                raise ValueError(f'Expected exactly one {old_reference} in web/index.html')
            index_html = index_html.replace(old_reference, new_reference)
        index_path.write_text(index_html)
        catalog['entries'] = entries
        catalog['stats'] = {'entries': len(entries), 'bgm': sum(e['kind'] == 'bgm' for e in entries),
                            'needs_review': sum(bool(e['issues']) for e in entries),
                            'source_rows': sum(len(e['provenance']) for e in entries)}
        (output / 'catalog.json').write_text(json.dumps(catalog, ensure_ascii=False, separators=(',', ':')))
        (output / '.nojekyll').write_text('')
        for path in output.iterdir():
            if path.name not in allowed + ['catalog.json', '.nojekyll']:
                raise ValueError(f'Unexpected publish artifact: {path.name}')
    print(f"Validated {len(entries)} entries and {len(catalog['collections'])} collections" + ('' if args.check else '; built dist/'))

if __name__ == '__main__':
    main()
