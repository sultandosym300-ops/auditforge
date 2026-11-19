import random
from .reconcile import reconcile
from .generator import TYPES


def run_policy(env, initial, name='reconciliation', log=None):
    manifest = initial['manifest']
    public = dict(manifest=manifest, policy=initial['policy'])
    step = len(log) if log is not None else 0
    ended = False
    def act(action):
        nonlocal step, ended
        result = env.step(action)
        step += 1
        if log is not None:
            log.append(dict(episode_id=manifest['episode_id'], step=step, action=action, observation=result[0], reward=result[1], terminated=result[2], truncated=result[3]))
        ended = result[2] or result[3]
        return result
    rng = random.Random(2026)
    if name == 'random':
        for _ in range(8):
            act(dict(tool='list_records', table=rng.choice(['ledger','payments','invoices','fx']), limit=50))
        findings = []
    else:
        for table in ('ledger','invoices','payments','fx'):
            public[table] = []
            cursor = None
            while not ended:
                result = act(dict(tool='list_records', table=table, cursor=cursor, limit=50))[0]
                if 'error' in result: break
                public[table].extend(result['result']['records'])
                cursor = result['result']['next_cursor']
                if cursor is None: break
        if ended: return None
        if name == 'reconciliation':
            findings = reconcile(public)
        elif name == 'mark_all':
            findings = [dict(type=kind, affected_ids=[r['row_id']], claimed_amount_minor=abs(r['debit_minor']-r['credit_minor']), currency=r['currency'], evidence_ids=[r['row_id']], explanation='Attack: flag every inspected posting.') for r in public['ledger'] for kind in TYPES][:30]
        else:
            raise ValueError('Unknown agent policy')
    return act(dict(tool='submit', findings=dict(episode_id=manifest['episode_id'], findings=findings)))
