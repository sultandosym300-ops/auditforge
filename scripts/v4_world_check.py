"""Offline held-out verification of realistic_v1 economics and public tools."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import time
from auditforge.realistic import generate_realistic,BUSINESS_TYPES,replay_business,change_customer_receipt
from auditforge.realistic_audit import audit_realistic
from auditforge.env import Session
from auditforge.policies import run_policy


def run(seed=2026112204):
    source_hashes={name:hashlib.sha256((Path(__file__).resolve().parents[1]/'auditforge'/name).read_bytes()).hexdigest() for name in ('realistic.py','realistic_audit.py')}
    started=time.perf_counter();rows=[];index=0
    for business in BUSINESS_TYPES:
        for size in (40,84,200):
            for clean,interaction in ((True,0),(False,0),(False,1),(False,2)):
                root=int.from_bytes(hashlib.sha256(f'world-holdout:{seed}:{index}'.encode()).digest()[:8],'big')
                config=dict(profile='realistic_v1',business_type=business,invoices=size,clean=clean,interaction=interaction,timezone=('+05:45','-03:30','+14:00')[index%3],period_month=('2040-02','2000-01','2099-12')[(index//3)%3])
                start=time.perf_counter();ep=generate_realistic(root,config);generation=time.perf_counter()-start
                result=audit_realistic(ep)
                assert result['valid'] and result['pristine_valid'],(index,result['errors'])
                session=Session();initial,_=session.reset(root,config,'evaluation')
                assert session.public==ep['public']
                run_policy(session,initial,'reconciliation')
                assert session.report['f1']==1 and session.report['fp']==0 and session.steps<=100
                documents=ep['public']['business']['source_documents'];access=Session();access.reset(root,config,'evaluation')
                for doc in (documents[0],documents[len(documents)//2],documents[-1]):
                    observation,reward,terminated,truncated,info=access.step(dict(tool='get_document',doc_id=doc['doc_id']))
                    assert observation['result']==doc and not reward and not terminated and not truncated and not info
                rows.append(dict(index=index,seed=root,config=config,valid=result['valid'],pristine_valid=result['pristine_valid'],event_count=result['event_count'],journal_count=result['journal_count'],source_document_count=result['source_document_count'],generation_seconds=generation,source_access_checks=3,tax_accrued_minor=ep['public']['business']['state']['tax']['accrued_minor'],steps=session.steps,**session.report));index+=1
    assert any(r['tax_accrued_minor']>0 for r in rows) and any(r['tax_accrued_minor']==0 for r in rows)
    sample=generate_realistic(2026112298,dict(profile='realistic_v1',business_type='manufacturing',invoices=40,clean=True))
    mutations=[]
    for name in ('context_posting_amount','cached_private_cash','cached_inventory_quantity','source_bank_line','cached_trial_balance','missing_source_document','cached_interest_paid','cached_tax_rate','cached_employee_count','cached_depreciation','cached_disposal_status'):
        bad=copy.deepcopy(sample);world=bad['public']['business']
        if name=='context_posting_amount':world['journal'][-1]['debit_minor']+=1
        elif name=='cached_private_cash':bad['pristine']['business']['state']['accounts']['cash']+=1
        elif name=='cached_inventory_quantity':world['state']['inventory']['raw_quantity']+=1
        elif name=='source_bank_line':
            for key in ('documents','source_documents'):next(d for d in world[key] if d['type']=='bank_statement')['cash_delta_minor']+=1
        elif name=='cached_trial_balance':world['reports']['trial_balance'][0]['closing_minor']+=1
        elif name=='missing_source_document':
            world['source_documents'].pop();world['documents'].pop()
        elif name=='cached_interest_paid':world['state']['loan']['interest_paid_minor']+=1
        elif name=='cached_tax_rate':world['state']['tax']['rate_basis_points']+=1
        elif name=='cached_employee_count':world['state']['payroll']['employees']+=1
        elif name=='cached_depreciation':world['state']['assets'][0]['accumulated_depreciation_minor']+=1
        elif name=='cached_disposal_status':world['state']['assets'][0]['disposed']=not world['state']['assets'][0]['disposed']
        check=audit_realistic(bad);assert not check['valid'],name
        mutations.append(dict(name=name,detected=True,errors=check['errors']))
    world=sample['public']['business'];receipt=next(e for e in world['events'] if e['type']=='customer_receipt')
    changed=change_customer_receipt(world,receipt['event_id'],receipt['amount_minor']-100)
    before=replay_business(world['events'],world['journal'],world['as_of'],world['period_start']);after=replay_business(changed['events'],changed['journal'],changed['as_of'],changed['period_start'])
    counterfactual=copy.deepcopy(sample);counterfactual['public']['business']=changed
    assert audit_realistic(counterfactual)['valid']
    causal=dict(payment_change_minor=-100,cash_change_minor=after['accounts']['cash']-before['accounts']['cash'],receivable_change_minor=after['accounts']['receivable']-before['accounts']['receivable'],balanced=after['reports']['balance_sheet']['balanced'])
    assert causal['cash_change_minor']==-100 and causal['receivable_change_minor']==100 and causal['balanced']
    return dict(study='realistic-v1-independent-world-check',source_sha256=source_hashes,root_seed=seed,count=len(rows),passed=len(rows),pristine_worlds_checked=len(rows),profiles={b:sum(r['config']['business_type']==b for r in rows) for b in BUSINESS_TYPES},clean_companies=sum(r['config']['clean'] for r in rows),positive_tax_companies=sum(r['tax_accrued_minor']>0 for r in rows),zero_tax_companies=sum(r['tax_accrued_minor']==0 for r in rows),mean_f1=sum(r['f1'] for r in rows)/len(rows),false_positives=sum(r['fp'] for r in rows),maximum_steps=max(r['steps'] for r in rows),source_access_checks=sum(r['source_access_checks'] for r in rows),mutations=mutations,causal_payment_replay=causal,seconds=time.perf_counter()-started,rows=rows,limitations=['Four official anomaly classes remain procurement scope. Other economically active modules are financial context, not new supervised anomaly labels.','Toy profit tax and straight-line depreciation are declared simulation conventions, not country legislation or financial reporting standard compliance.','All holdout companies come from the same procedural generator family. No external-domain transfer claimed.'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--seed',type=int,default=2026112204);p.add_argument('--output',type=Path,default=Path('reports/v4-world-check.json'));p.add_argument('--export-example',type=Path);a=p.parse_args()
    if a.export_example:
        from auditforge.generator import generate
        from auditforge.export import export_episode
        export_episode(generate(a.seed,dict(profile='realistic_v1',business_type='logistics',invoices=40)),a.export_example)
    result=run(a.seed);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
