"""Recheck final inference against preserved raw V2 results; no retraining/test tuning."""
import argparse
import json
from pathlib import Path

from auditforge.env import Session
from auditforge.efficient_training import load_trainer
from auditforge.sequential_policy import investigate
from auditforge.training import episode_seed

ROOT=Path(__file__).resolve().parents[1]


def verify():
    raw=json.loads((ROOT/'reports/final-sequential-v2-test-raw.json').read_text(encoding='utf8'))
    models=[load_trainer(json.loads((ROOT/f'reports/final-sequential-selected-{i}.json').read_text(encoding='utf8'))) for i in range(3)]
    fixtures={row['company']:row for row in raw['fixtures']}
    count=0
    for row in raw['rows']:
        if row['company'] not in (0,1,7,13):continue
        fixture=fixtures[row['company']]
        session=Session();initial,_=session.reset(fixture['seed'],fixture['config'],'evaluation')
        investigate(session.step,initial,policy=row['policy'],budget=row['budget'],weights=models[row['checkpoint']].weights)
        assert session.steps==row['steps']
        assert all(abs(session.report[key]-row[key])<1e-12 for key in ('reward','f1','precision','recall','tp','fp','fn'))
        count+=1
    return dict(passed=True,policy_reproductions=count,independent_companies=4,
                scope='Deterministic final inference matches stored V2 metrics after the decoder-only refactor; not a new independent benchmark.')


if __name__=='__main__':print(json.dumps(verify()))
