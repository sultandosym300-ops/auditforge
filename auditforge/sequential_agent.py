"""Untrusted-container inference: public decoder + weights, no evaluator code."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
from auditforge.sequential_policy import investigate

initial=json.loads(sys.stdin.readline())
weights=json.loads(os.environ['AUDITFORGE_POLICY_WEIGHTS'])
budget=int(os.environ['AUDITFORGE_POLICY_BUDGET'])


def step(action):
    print(json.dumps(action),flush=True)
    value=json.loads(sys.stdin.readline())
    return value['observation'],value['reward'],value['terminated'],value['truncated'],value['info']


investigate(step,initial,weights=weights,budget=budget)
