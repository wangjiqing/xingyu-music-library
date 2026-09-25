"""Check versioned files, not the user's private working directory."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIO = {'.mp3','.flac','.wav','.m4a','.ogg','.aac','.opus','.aiff','.aif','.wma','.mp4','.ape','.dsf','.dff'}

def check():
    result = subprocess.run(['git','ls-files','-z'], cwd=ROOT, capture_output=True, check=True)
    failures = []
    for raw in result.stdout.decode().split('\0'):
        if not raw:
            continue
        path = Path(raw)
        if path.suffix.lower() in AUDIO | {'.xlsx','.xls','.sqlite','.db'} or raw.startswith(('private/','.env')) or raw == 'PROJECT_PROPOSAL.md':
            failures.append(raw)
        if raw.startswith('data/') and path.suffix == '.json':
            content = (ROOT / path).read_text()
            if re.search(r'/Users/|/Volumes/|X-Amz-Signature=|AKIA[A-Z0-9]{16}|-----BEGIN .*PRIVATE KEY-----', content):
                failures.append(raw + ': private field or credential')
    if failures:
        raise SystemExit('Files not permitted for publication:\n' + '\n'.join(failures))
    print('Publication boundary passed: no tracked audio, raw workbook, private database or private paths.')

if __name__ == '__main__':
    check()
