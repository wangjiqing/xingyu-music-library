"""One-time, loss-aware import. Runtime: Python standard library only.

Identical source rows share a record. Conflicting rows keep distinct IDs.
Reimporting the same snapshot is a no-op; a changed workbook requires review.
"""
import argparse
import hashlib
import json
import re
import uuid
import zipfile
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
REL = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
PRIVATE = re.compile(r'用户|本地歌单|本地无损|NAS\b|/Users/|/Volumes/|[A-Za-z]:\\', re.I)

def read_xlsx(path):
    with zipfile.ZipFile(path) as z:
        shared = []
        if 'xl/sharedStrings.xml' in z.namelist():
            shared = [''.join(t.itertext()) for t in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        rels = {r.attrib['Id']: r.attrib['Target'] for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        result = {}
        for sheet in ET.fromstring(z.read('xl/workbook.xml')).find('m:sheets', NS):
            target = rels[sheet.attrib[REL]]
            target = target.lstrip('/') if target.startswith('/') else 'xl/' + target
            rows = []
            for row in ET.fromstring(z.read(target)).findall('m:sheetData/m:row', NS):
                cells = []
                for cell in row:
                    column = re.match('[A-Z]+', cell.attrib['r']).group()
                    index = 0
                    for char in column:
                        index = index * 26 + ord(char) - 64
                    while len(cells) < index:
                        cells.append('')
                    value = cell.find('m:v', NS)
                    if cell.attrib.get('t') == 'inlineStr':
                        text = ''.join(cell.find('m:is', NS).itertext())
                    elif cell.attrib.get('t') == 's':
                        text = shared[int(value.text)]
                    else:
                        text = value.text if value is not None else ''
                    cells[index - 1] = text.strip()
                while len(rows) < int(row.attrib['r']) - 1:
                    rows.append([])
                rows.append(cells)
            result[sheet.attrib['name']] = rows
        return result

def split_terms(text):
    return list(dict.fromkeys(t.strip() for t in re.split(r'[/、｜|，,]', text) if t.strip() and t.strip() != '—'))

def public_text(text):
    return '；'.join(part for part in re.split(r'[；;。]', text) if part and not PRIVATE.search(part))

def urls(text):
    return list(dict.fromkeys(re.findall(r'https?://[^\s；;，<>"\u3002]+', text)))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('workbook', type=Path)
    args = parser.parse_args()
    digest = hashlib.sha256(args.workbook.read_bytes()).hexdigest()
    manifest_path = ROOT / 'data/catalog.json'
    if manifest_path.exists():
        current = json.loads(manifest_path.read_text())
        if current['source']['sha256'] == digest:
            print('This snapshot is already imported. Canonical edits and IDs are preserved.')
            return
        raise SystemExit('Changed workbook: import into a separate review branch; existing entries will not be overwritten.')
    sheets = read_xlsx(args.workbook)
    standard_header = sheets['歌曲总表'][0]
    entries = {}
    collections = []
    private_rows = []
    record_count = 0
    for sheet_name, rows in sheets.items():
        kind = 'bgm' if sheet_name == '声音记忆_BGM' else 'song'
        if not rows or (rows[0] != standard_header and kind != 'bgm'):
            continue
        collection_id = 'col-' + uuid.uuid4().hex[:12]
        member_ids = []
        for row_number, raw in enumerate(rows[1:], 2):
            if not any(raw):
                continue
            record_count += 1
            values = (raw + [''] * 12)[:12]
            key = (kind, tuple(values))
            if key not in entries:
                if kind == 'bgm':
                    year, title, context, artist, subtype, scene, carriers, language, grade, note, source = values[:11]
                    album, composer = '', artist
                    tags = split_terms(subtype) + split_terms(scene)
                else:
                    year, title, artist, album, composer, tags_raw, carriers, context, language, grade, note, source = values
                    tags = split_terms(tags_raw)
                issues = []
                year_value = int(year) if re.fullmatch(r'\d{4}', year) and int(year) > 0 else None
                if year_value is None:
                    issues.append('year_uncertain')
                if any('待核' in x for x in [artist, composer, note]):
                    issues.append('credit_or_detail_pending')
                if grade not in ['S', 'A', 'B']:
                    issues.append('grade_invalid')
                references = urls(source) + urls(note)
                if not references:
                    issues.append('public_source_missing')
                aliases = [t.strip() for t in title.split(' / ') if t.strip() != title]
                alias_match = re.search('常俗称“([^”]+)”', note)
                if alias_match:
                    aliases.extend(split_terms(alias_match.group(1)))
                entry = {
                    'schema_version': 1, 'id': 'snd-' + uuid.uuid4().hex[:16],
                    'title': title, 'aliases': list(dict.fromkeys(aliases)), 'kind': kind,
                    'artist_credit': artist, 'composer_credit': composer,
                    'year': year_value, 'year_label': year if year not in ['0', '待核', ''] else '年代待核',
                    'year_basis': '原表记载，首发、传播或版本日期的含义待核',
                    'album': album, 'context': context if context != '—' else '',
                    'language': language, 'editorial_grade': grade if grade in ['S', 'A', 'B'] else None,
                    'tags': list(dict.fromkeys(tags)), 'carriers': split_terms(carriers),
                    'notes': public_text(note) if not urls(note) else '',
                    'sources': [{'url': url, 'verification': 'unreviewed'} for url in dict.fromkeys(references)],
                    'review_status': 'unreviewed', 'issues': issues,
                    'collection_ids': [], 'provenance': [], 'related_entry_ids': [],
                    'audio_refs': [], 'revision': 1,
                }
                entries[key] = entry
            entry = entries[key]
            entry['provenance'].append({'source_id': 'excel-v40', 'sheet': sheet_name, 'row': row_number})
            if sheet_name != '歌曲总表' and collection_id not in entry['collection_ids']:
                entry['collection_ids'].append(collection_id)
            if entry['id'] not in member_ids:
                member_ids.append(entry['id'])
            if PRIVATE.search(' '.join(values)):
                private_rows.append({'entry_id': entry['id'], 'sheet': sheet_name, 'row': row_number, 'values': values})
        if sheet_name != '歌曲总表':
            collections.append({'id': collection_id, 'title': re.sub(r'_v\d+$', '', sheet_name),
                                'source_sheet': sheet_name, 'entry_ids': member_ids})
    by_identity = defaultdict(list)
    for entry in entries.values():
        by_identity[(entry['title'].casefold(), entry['artist_credit'].casefold())].append(entry)
    for group in by_identity.values():
        if len(group) > 1:
            for entry in group:
                entry['issues'].append('possible_duplicate_or_variant')
                entry['related_entry_ids'] = [x['id'] for x in group if x != entry]
    output = ROOT / 'data/entries'
    output.mkdir(parents=True, exist_ok=True)
    for entry in entries.values():
        (output / (entry['id'] + '.json')).write_text(json.dumps(entry, ensure_ascii=False, indent=2) + '\n')
    manifest = {
        'schema_version': 1, 'title': '星屿声音记忆库',
        'description': '收藏声音，也留下版本、出处与记忆。',
        'source': {'id': 'excel-v40', 'label': '视听资料整理表 v40', 'sha256': digest,
                   'sheet_count': len(sheets), 'imported_source_rows': record_count},
        'import_policy': '只合并内容完全一致的来源行；差异记录分别保留，全部标记为未逐项核验。',
        'imported_entry_count': len(entries), 'collections': collections,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    private_path = ROOT / 'private'
    private_path.mkdir(exist_ok=True)
    (private_path / 'import-private-notes.json').write_text(json.dumps(private_rows, ensure_ascii=False, indent=2))
    print(json.dumps({'entries': len(entries), 'source_rows': record_count, 'collections': len(collections),
                      'private_rows_excluded_from_public_notes': len(private_rows)}, ensure_ascii=False))

if __name__ == '__main__':
    main()
