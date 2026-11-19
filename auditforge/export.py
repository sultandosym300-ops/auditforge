import csv
import json
from pathlib import Path


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2), encoding='utf-8')


def export_episode(episode, root):
    root = Path(root)
    public = episode['public']
    eid = public['manifest']['episode_id']
    folder = root / 'public' / eid
    folder.mkdir(parents=True, exist_ok=True)
    for name in ('manifest','policy'):
        write_json(folder / (name+'.json'), public[name])
    for table in ('invoices','payments'):
        (folder/(table+'.jsonl')).write_text(''.join(json.dumps(r, sort_keys=True)+'\n' for r in public[table]), encoding='utf-8')
    for table in ('ledger','fx'):
        with (folder/(table+'.csv')).open('w', newline='', encoding='utf-8') as stream:
            fields = list(dict.fromkeys(k for row in public[table] for k in row))
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            # CSV nulls are explicit literal null; JSON fields remain actual null.
            writer.writerows({k: 'null' if row.get(k) is None else row[k] for k in fields} for row in public[table])
    for name in ('truth','provenance'):
        write_json(root/'evaluator_private'/eid/(name+'.json'), episode[name])
