"""Container-side agent. This image has no generator, evaluator, seed or private files."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from reconcile import reconcile

initial=json.loads(sys.stdin.readline())
public=dict(manifest=initial['manifest'],policy=initial['policy'])
for table in ('ledger','invoices','payments','fx'):
    public[table]=[]
    cursor=None
    while True:
        print(json.dumps(dict(tool='list_records',table=table,cursor=cursor,limit=50)),flush=True)
        result=json.loads(sys.stdin.readline())
        if result['terminated'] or result['truncated']: raise SystemExit(0)
        response=result['observation']['result']
        public[table].extend(response['records']); cursor=response['next_cursor']
        if cursor is None: break
print(json.dumps(dict(tool='submit',findings=dict(episode_id=initial['manifest']['episode_id'],findings=reconcile(public)))),flush=True)
sys.stdin.readline()
