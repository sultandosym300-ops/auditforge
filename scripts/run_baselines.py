"""Four explicit adapters; the oracle is evaluator-only, never an agent RPC."""
import argparse
import json
from pathlib import Path

from auditforge.env import Session
from auditforge.matcher import oracle
from auditforge.policies import run_policy

POLICIES = ('random', 'reconciliation', 'mark_all', 'oracle')


def evaluate_baseline(seed, config, policy, *, allow_evaluator_oracle=False, mode='evaluation'):
    if policy not in POLICIES:
        raise ValueError('Unknown baseline')
    if policy == 'oracle' and not allow_evaluator_oracle:
        raise ValueError('The oracle requires explicit trusted-evaluator authorization')
    session = Session()
    initial, _ = session.reset(seed, config, mode)
    log = []
    if policy != 'oracle':
        class Actions:
            def step(self, action):
                return session.step(action)
        run_policy(Actions(), initial, policy, log)
    else:
        answer = oracle(session.episode)
        # Query the actual evidence through official tools before the trusted
        # adapter submits. Ordinary policies never receive the episode object.
        required = sorted({identifier for finding in answer['findings'] for identifier in finding['evidence_ids']})
        for identifier in required:
            table = next(table for table in ('ledger','invoices','payments','fx')
                         if any(identifier == row.get('row_id', row.get('doc_id')) for row in session.public[table]))
            action = dict(tool='get_record', table=table, id=identifier)
            result = session.step(action)
            log.append(dict(episode_id=initial['manifest']['episode_id'],step=len(log)+1,action=action,
                            observation=result[0],reward=result[1],terminated=result[2],truncated=result[3]))
        action = dict(tool='submit', findings=answer)
        result = session.step(action)
        log.append(dict(episode_id=initial['manifest']['episode_id'],step=len(log)+1,action=action,
                        observation=result[0],reward=result[1],terminated=result[2],truncated=result[3]))
    if not session.done or session.steps > 100:
        raise RuntimeError('Baseline did not finish within the official action budget')
    return dict(policy=policy, evaluator_only=policy=='oracle', report=session.report,
                steps=session.steps, trajectory=log)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=2026112204)
    parser.add_argument('--policy', choices=POLICIES+('all',), default='reconciliation')
    parser.add_argument('--allow-evaluator-oracle', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    policies = POLICIES if args.policy=='all' else (args.policy,)
    if 'oracle' in policies and not args.allow_evaluator_oracle:
        parser.error('Oracle is evaluator-only; pass --allow-evaluator-oracle on a trusted host')
    result = [evaluate_baseline(args.seed,{},policy,allow_evaluator_oracle=args.allow_evaluator_oracle) for policy in policies]
    text = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text+'\n',encoding='utf8')
    print(json.dumps([dict(policy=r['policy'],steps=r['steps'],**r['report']) for r in result]))


if __name__=='__main__':
    main()
