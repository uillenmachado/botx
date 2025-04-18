
#!/usr/bin/env python3
import gzip, shutil, datetime, pathlib, os

DB = 'bot.db'
DIR = pathlib.Path('backups')
DIR.mkdir(exist_ok=True)

ts = datetime.datetime.now().strftime('%Y%m%d_%H%M')
gz = DIR / f'{ts}.db.gz'

with open(DB, 'rb') as fin, gzip.open(gz, 'wb') as fout:
    shutil.copyfileobj(fin, fout)

# keep only last 10 backups
backups = sorted(DIR.glob('*.gz'))
for old in backups[:-10]:
    old.unlink()
