"""Frozen financial-structure transfer panel, without learning or model selection."""
import json,argparse,hashlib
from pathlib import Path

from auditforge.efficient_training import load_trainer
from auditforge.generator import generate
from auditforge.reconcile import validate
from auditforge.financial_audit import audit_episode
from auditforge.training import episode_seed
from scripts.sequential_benchmark import run_panel,save

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--audit-only',action='store_true');args=parser.parse_args()
    spec=json.loads((ROOT/'configs/sequential-batch-holdout.json').read_text(encoding='utf8'))
    models=[load_trainer(json.loads((ROOT/f'reports/final-sequential-selected-{i}.json').read_text(encoding='utf8'))) for i in range(3)]
    financial=[]
    for index in range(spec['companies']):
        config=models[0].config(index,spec['family'])
        episode=generate(episode_seed(spec['root'],'frozen-company',index),config)
        assert validate(episode)
        independent=audit_episode(episode)
        assert independent['valid'],independent['errors']
        payments=episode['public']['payments']
        financial.append(dict(company=index,valid=True,independent_rational_valid=independent['valid'],truth_count=len(episode['truth']),
                              multi_obligation_payments=sum(len(p['invoice_refs'])>1 for p in payments),
                              refund_documents=sum(p['amount_minor']<0 for p in payments)))
    save(ROOT/'reports/final-sequential-batch-financial-audit.json',dict(passed=True,companies=financial,
         source_sha256={name:hashlib.sha256((ROOT/'auditforge'/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
                        for name in ('batch_settlement.py','investigation_world.py','financial_audit.py')}))
    if args.audit_only:return
    summary=run_panel(spec,models,spec['root'],spec['companies'],spec['family'],ROOT/'reports/final-sequential-batch-raw.json')
    save(ROOT/'reports/final-sequential-batch-summary.json',dict(specification=spec,financial=financial,results=summary))


if __name__=='__main__':main()
