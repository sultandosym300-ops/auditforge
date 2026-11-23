"""Untrusted document-policy inference, supplied public parameters only."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
from auditforge.document_policy import Network, investigate

model=Network(os.environ['AUDITFORGE_POLICY_ARCHITECTURE'],
              parameters=json.loads(os.environ['AUDITFORGE_POLICY_WEIGHTS']))
budget=int(os.environ['AUDITFORGE_POLICY_BUDGET'])
initial=json.loads(sys.stdin.readline())


def step(action):
    print(json.dumps(action),flush=True)
    response=json.loads(sys.stdin.readline())
    return response['observation'],response['reward'],response['terminated'],response['truncated'],response['info']


investigate(step,initial,model=model,budget=budget)
