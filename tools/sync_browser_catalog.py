"""Refresh the browser's offline catalog after editing folio_catalog.py."""
import json
from pathlib import Path
import re
import sys
sys.dont_write_bytecode = True
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from folio_catalog import PROFILES, FIELDS, EXTRA_BACKUP_FIELDS, ACCESS_EXTRA, ACCESS_DIRECT
path = root / 'browser-edition/index.html'
text = path.read_text()
for name, value in [('PROFILES', PROFILES), ('RECORD_FIELDS', FIELDS),
                    ('EXTRA_BACKUP_FIELDS', EXTRA_BACKUP_FIELDS),
                    ('ACCESS_EXTRA', ACCESS_EXTRA), ('ACCESS_DIRECT', ACCESS_DIRECT)]:
    text, count = re.subn(r'^const ' + name + r' = .*?;$',
                          lambda _: 'const ' + name + ' = ' + json.dumps(value, ensure_ascii=False) + ';',
                          text, flags=re.M)
    if count != 1:
        raise SystemExit(f'Expected exactly one embedded {name}')
path.write_text(text)
