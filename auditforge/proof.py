"""Trusted demonstration proofs; never part of the agent-facing reset/step API.

Standalone fixtures expose their own answers for inspection. Active-episode private
explanations require both an explicit demo request and a completed submission.
"""
import copy
import hashlib
import json
import random
import time
from datetime import datetime

from .env import Session
from .financial_audit import audit_episode, converted_minor
from .generator import GENERATOR_VERSION, TYPES, generate
from .matcher import evaluate, oracle
from .policies import run_policy

PROOF_VERSION = 'proof_v1'
HISTORICAL_CI = dict(
    commit='bd202ffc8d4e2a43d9a6c2d2b8ed5d98956c7d03',
    url='https://github.com/sultandosym300-ops/geneziz/actions/runs/44938007968',
    command='python -m scripts.ultimate_verify --seed 801973140685',
    tests=132, limits=dict(cpus=2,memory_bytes=4294967296,network='none'),
    peak_memory_bytes=482353152,
    scope='Confirmed historical CI for the cited commit. This browser did not execute Docker; these are not current-commit CI claims.')


def _canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf8')


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _records(public):
    return {r.get('row_id',r.get('doc_id')):r for table in ('ledger','invoices','payments','fx') for r in public[table]}


def transform_for_proof(episode, seed, *, return_mapping=False):
    """Portable copy of verify.transform, with native parity regression coverage.

    Keeping the pure JSON operation here allows Pyodide to run it without importing
    verify's subprocess/multiprocessing command-line harness.
    """
    rng=random.Random(seed)
    ids=set()
    def collect(value,key=''):
        if isinstance(value,dict):
            for k,v in value.items():collect(v,k)
        elif isinstance(value,list):
            for v in value:collect(v,key)
        elif isinstance(value,str) and (key.endswith('_id') or key.endswith('_ids') or key=='evidence_sets'):
            ids.add(value)
    collect(episode)
    mapping={v:'mapped-'+format(rng.getrandbits(96),'024x') for v in sorted(ids)}
    def replace(value):
        if isinstance(value,dict):return {k:replace(v) for k,v in value.items()}
        if isinstance(value,list):return [replace(v) for v in value]
        if isinstance(value,str):return mapping.get(value,value)
        return value
    transformed=replace(episode)
    for branch in ('public','pristine'):
        transformed[branch]['manifest']['company']='Renamed Fictional Company'
        for table in ('ledger','invoices','payments','fx'):rng.shuffle(transformed[branch][table])
    return (transformed,mapping) if return_mapping else transformed


def public_story(public):
    """Read only publicly available documents; no truth/provenance argument exists."""
    manifest=public['manifest']
    chains=[]
    invoices=sorted(public['invoices'],key=lambda r:r['invoice_id'])[:3]
    for invoice in invoices:
        iid=invoice['invoice_id']
        payments=[p for p in public['payments'] if any(r['invoice_id']==iid for r in p['invoice_refs'])]
        ledger=[r for r in public['ledger'] if r['invoice_id']==iid]
        payable=[r for r in ledger if r['account']=='payable']
        chains.append(dict(chain_id=iid,invoice=copy.deepcopy(invoice),payments=copy.deepcopy(payments),
                           ledger=copy.deepcopy(ledger),currency=manifest['base_currency'],
                           book_balance_minor=sum(r['credit_minor']-r['debit_minor'] for r in payable),
                           document_ids=[invoice['doc_id']]+[p['doc_id'] for p in payments],
                           ledger_ids=[r['row_id'] for r in ledger],
                           description_key='invoice_settlement_chain'))
    business=public.get('business')
    result=dict(format='auditforge-public-story',version=1,
                profile=business.get('profile','compact') if business else 'compact',
                manifest=copy.deepcopy(manifest),
                summary=dict(invoices=len(public['invoices']),payments=len(public['payments']),
                             ledger=len(public['ledger']),suppliers=len({r['entity_id'] for r in public['invoices']}),
                             currencies=sorted({r['currency'] for r in public['invoices']+public['payments']})),
                chains=chains,source_records={table:copy.deepcopy(public[table]) for table in ('ledger','invoices','payments','fx')},scope='Public company history. Book balances may contain the controlled accounting errors; no hidden answer is consulted.')
    if business:
        result['business']=copy.deepcopy(business)
    return result


def receipt_scenario(public, event_id, amount_minor):
    """A public, immutable financial what-if, separate from official RL actions."""
    from .realistic import change_customer_receipt
    world = public.get('business')
    if not isinstance(world, dict) or world.get('version') != 'realistic_v1':
        raise ValueError('Create a realistic company first')
    changed = change_customer_receipt(world, event_id, amount_minor)
    def values(current):
        event = next(e for e in current['events'] if e['event_id'] == event_id)
        accounts = current['state']['accounts']
        return dict(amount_minor=event['amount_minor'], cash_minor=accounts.get('cash', 0),
                    receivable_minor=accounts.get('receivable', 0))
    return dict(before=values(world), after=values(changed), business=changed,
                scope='Public causal what-if. The active episode, labels and reward are unchanged.')


def _session_for(episode):
    session=Session()
    session.episode=copy.deepcopy(episode)
    session.public=session.episode['public']
    session.mode='evaluation'
    session.steps,session.done,session.done_flags=0,False,(False,False)
    session.report,session.started,session.seconds,session.final=None,time.monotonic(),60,[]
    initial=dict(task='Audit the company for four documented financial issue types; submit evidence-backed findings.',
                 manifest=copy.deepcopy(session.public['manifest']),policy=copy.deepcopy(session.public['policy']),steps_remaining=100)
    return session,initial


def _reproducibility(seed, config):
    first=Session();initial,_=first.reset(seed,config,'evaluation')
    log=[]
    run_policy(first,initial,'reconciliation',log)
    second=Session();initial2,_=second.reset(seed,config,'evaluation')
    repeated=[]
    for row in log:
        observation,reward,terminated,truncated,info=second.step(copy.deepcopy(row['action']))
        repeated.append(dict(episode_id=initial2['manifest']['episode_id'],step=len(repeated)+1,
                             action=copy.deepcopy(row['action']),observation=observation,reward=reward,
                             terminated=terminated,truncated=truncated))
    left=dict(initial=initial,public=first.public,trajectory=log,report=first.report)
    right=dict(initial=initial2,public=second.public,trajectory=repeated,report=second.report)
    transformed,mapping=transform_for_proof(first.episode,seed+1,return_mapping=True)
    changed,changed_initial=_session_for(transformed)
    changed_log=[]
    run_policy(changed,changed_initial,'reconciliation',changed_log)
    old_order=[mapping[r['row_id']] for r in first.public['ledger']]
    new_order=[r['row_id'] for r in changed.public['ledger']]
    return dict(first_hash=_digest(left),second_hash=_digest(right),
                observations_equal=log==repeated and initial==initial2,
                report_equal=first.report==second.report,
                first_run=dict(initial=initial,trajectory=log,report=first.report,public_hash=_digest(first.public)),
                second_run=dict(initial=initial2,trajectory=repeated,report=second.report,public_hash=_digest(second.public)),
                renaming=dict(source_hash=_digest(first.public),changed_hash=_digest(changed.public),
                              report_equal=first.report==changed.report,ids_changed=all(k!=v for k,v in mapping.items()),
                              order_changed=old_order!=new_order,mapping=mapping,
                              source_sample=first.public['ledger'][:3],changed_sample=changed.public['ledger'][:3],
                              source_report=first.report,changed_report=changed.report,
                              changed_trajectory=changed_log,
                              command='python -m auditforge.metamorphic --count 100 --seed '+str(seed)))


def _financial_fixture(episode,clean):
    public=episode['public'];pristine=episode['pristine']
    audit=audit_episode(episode);clean_audit=audit_episode(clean)
    totals={}
    for row in pristine['ledger']:
        totals[row['currency']]=totals.get(row['currency'],0)+row['debit_minor']-row['credit_minor']
    available=set(_records(public))
    missing=sorted({i for t in episode['truth'] for evidence in t['evidence_sets'] for i in evidence}-available)
    checks=[dict(id='balanced_pristine_journal',passed=all(n==0 for n in totals.values()),actual=totals,expected='zero debit-minus-credit in every currency'),
            dict(id='independent_financial_reconstruction',passed=audit['valid'],actual=audit,expected='exact rational reconstruction agrees with controlled discrepancies'),
            dict(id='public_documentary_sufficiency',passed=not missing,actual=dict(missing_ids=missing),expected='all required evidence IDs exist in the public documents'),
            dict(id='clean_company',passed=clean_audit['valid'] and not clean['truth'],actual=clean_audit,expected='independent audit finds no hidden discrepancy')]
    story=public_story(pristine)
    return dict(valid=all(c['passed'] for c in checks),checks=checks,example=story['chains'][0],
                scope='Financial checks are computed on these local demonstration fixtures, not an official jury score.')


def proof_suite(seed=2026112204):
    """Live standalone trusted fixtures. Never inserted into an active RL observation."""
    if type(seed) is not int:
        raise ValueError('seed must be an integer')
    config=dict(invoices=40,counts={kind:int(kind=='payment_allocation') for kind in TYPES})
    episode=generate(seed,config)
    clean=dict(public=copy.deepcopy(episode['pristine']),pristine=copy.deepcopy(episode['pristine']),truth=[],provenance=[])
    full=oracle(episode)
    missing=copy.deepcopy(full);missing['findings'][0]['evidence_ids']=[]
    wrong=copy.deepcopy(full);wrong['findings'][0]['claimed_amount_minor']+=1
    duplicate=copy.deepcopy(full);duplicate['findings'].append(copy.deepcopy(full['findings'][0]))
    empty=dict(episode_id=full['episode_id'],findings=[])
    fixtures=[('correct',episode,full,(1,0,0)),('missing_evidence',episode,missing,(0,1,1)),
              ('wrong_amount',episode,wrong,(0,1,1)),('duplicate_finding',episode,duplicate,(1,1,0)),
              ('false_positive',clean,full,(0,1,0)),('clean_silence',clean,empty,(0,0,0))]
    cases=[]
    records=_records(episode['public'])
    for name,fixture,submission,expected_counts in fixtures:
        report=evaluate(full['episode_id'],fixture['truth'],submission,4)
        actual=(report['tp'],report['fp'],report['fn'])
        evidence=sorted({i for f in submission['findings'] for i in f['evidence_ids']})
        cases.append(dict(id=name,description_key=name,submission=submission,report=report,
                          expected=dict(zip(('tp','fp','fn'),expected_counts)),passed=actual==expected_counts,
                          inspection_steps=4,evidence_records=[copy.deepcopy(records[i]) for i in evidence if i in records]))
    return dict(format='auditforge-proof-suite',version=PROOF_VERSION,seed=seed,generator_version=GENERATOR_VERSION,
                matcher_cases=cases,financial=_financial_fixture(episode,clean),
                reproducibility=_reproducibility(seed,config),historical_ci=copy.deepcopy(HISTORICAL_CI),
                scope='Fresh local demonstration fixtures; real matcher and public-action replay. This is separate from the active agent and is not an official hackathon score.')


def _calculation(episode, truth, mutation):
    kind=truth['type'];before=mutation.get('before',[]);after=mutation.get('after',[])
    relevant='expense' if kind in ('duplicate_invoice','accounting_period') else 'payable'
    before_rows=[r for r in before if r['account']==relevant]
    after_rows=[r for r in after if r['account']==relevant]
    sum_before=sum(r['debit_minor'] for r in before_rows)
    sum_after=sum(r['debit_minor'] for r in after_rows)
    operands=dict(stage_before_minor=sum_before,stage_after_minor=sum_after)
    if kind=='duplicate_invoice':
        measured=abs(sum_after-sum_before)
        equation=f'{sum_after} - {sum_before} = {sum_after-sum_before}'
    elif kind=='payment_allocation':
        public=episode['public'];row=after_rows[0]
        payment=next(p for p in public['payments'] if p['payment_id']==row['payment_id'])
        date=datetime.fromisoformat(payment['timestamp']).astimezone(datetime.fromisoformat(public['manifest']['period_start']).tzinfo).date().isoformat()
        fx=next((f for f in public['fx'] if f['date']==date and f['source_currency']==payment['currency'] and f['target_currency']==public['manifest']['base_currency']),None)
        rate=fx['rate'] if fx else '1'
        declared=sum(r['allocated_minor'] for r in payment['invoice_refs'] if r['invoice_id']==row['invoice_id'])
        declared_base=converted_minor(declared,payment['currency'],public['manifest']['base_currency'],rate,public['manifest']['currency_exponents'])
        recorded_base=converted_minor(row['allocation_source_minor'],payment['currency'],public['manifest']['base_currency'],rate,public['manifest']['currency_exponents'])
        operands.update(source_document_id=payment['doc_id'],source_currency=payment['currency'],declared_allocation_minor=declared,recorded_allocation_minor=row['allocation_source_minor'],declared_fx_rate=rate,expected_settlement_minor=declared_base,recorded_at_declared_rate_minor=recorded_base)
        measured=abs(declared_base-recorded_base)
        equation=f'{declared_base} - {recorded_base} = {declared_base-recorded_base}'
    elif kind=='fx_conversion':
        public=episode['public'];row=after_rows[0]
        payment=next(p for p in public['payments'] if p['payment_id']==row['payment_id'])
        date=datetime.fromisoformat(payment['timestamp']).astimezone(datetime.fromisoformat(public['manifest']['period_start']).tzinfo).date().isoformat()
        fx=next(f for f in public['fx'] if f['date']==date and f['source_currency']==payment['currency'] and f['target_currency']==public['manifest']['base_currency'])
        expected=converted_minor(row['allocation_source_minor'],payment['currency'],public['manifest']['base_currency'],fx['rate'],public['manifest']['currency_exponents'])
        operands.update(source_document_id=payment['doc_id'],fx_record_id=fx['row_id'],source_currency=payment['currency'],source_amount_minor=row['allocation_source_minor'],declared_fx_rate=fx['rate'],recorded_fx_rate=row['fx_rate'],expected_conversion_minor=expected)
        measured=abs(sum_after-expected)
        equation=f'{sum_after} - {expected} = {sum_after-expected}'
    else:
        public=episode['public'];row=after_rows[0]
        invoice=next(i for i in public['invoices'] if i['invoice_id']==row['invoice_id'])
        start,end=(datetime.fromisoformat(public['manifest'][k]) for k in ('period_start','period_end'))
        source_inside=start<=datetime.fromisoformat(invoice['issued_at'])<end
        book_inside=start<=datetime.fromisoformat(row['timestamp'])<end
        measured=invoice['total_minor'] if source_inside!=book_inside else 0
        operands.update(source_timestamp=invoice['issued_at'],recorded_timestamp=row['timestamp'],
                        source_inside_period=source_inside,recorded_inside_period=book_inside,
                        invoice_total_minor=invoice['total_minor'])
        equation=f'{invoice["issued_at"]} / {row["timestamp"]}: period disagreement = {measured}'
    return dict(operands=operands,equation=equation,calculated_discrepancy_minor=measured,
                matches_declared_discrepancy=measured==truth['expected_amount_minor'],
                scope='Causal mutation stage, before subsequent interacting changes. Current book rows are shown separately.')


def _assigned_findings(episode_id, truth, findings):
    """Resolve support with the real matcher, then preserve its one-to-one rule."""
    graph=[];eligible=[];seen=set()
    for index,finding in enumerate(findings):
        edges=[];supported=set()
        for j,target in enumerate(truth):
            payload=dict(episode_id=episode_id,findings=[finding])
            if evaluate(episode_id,[target],payload,0)['tp']:
                edges.append(j)
                evidence=set(finding['evidence_ids'])
                supported.update(frozenset(ids) for ids in target['evidence_sets'] if evidence.issuperset(ids))
        graph.append(edges)
        key=(finding['type'],tuple(sorted(finding['affected_ids'])),finding['currency'],finding['claimed_amount_minor'],frozenset(supported))
        if key not in seen:
            eligible.append(index);seen.add(key)
    assigned={}
    def augment(index,visited):
        for target in graph[index]:
            if target in visited:continue
            visited.add(target)
            if target not in assigned or augment(assigned[target],visited):
                assigned[target]=index;return True
        return False
    for index in eligible:augment(index,set())
    expected=evaluate(episode_id,truth,dict(episode_id=episode_id,findings=findings),0)['tp']
    if len(assigned)!=expected:raise ValueError('Explainer assignment differs from evaluator')
    return assigned,graph


def explain_completed(session, *, demo=False):
    """Private evaluator view; explicit demo=True and terminal session are required."""
    if demo is not True or not getattr(session,'done',False) or getattr(session,'mode',None) not in ('train','demo'):
        raise ValueError('Private explanations require an explicit completed demo')
    episode=session.episode
    public=episode['public'];records=_records(public)
    payload=session.final if isinstance(session.final,dict) else dict(episode_id=public['manifest']['episode_id'],findings=[])
    findings=payload.get('findings',[])
    issues=[]
    mutations={r['issue_id']:r for r in episode['provenance']}
    assignment,support=_assigned_findings(public['manifest']['episode_id'],episode['truth'],findings)
    for truth_index,truth in enumerate(episode['truth']):
        mutation=mutations.get(truth['issue_id'])
        if mutation is None:
            # A future profile must provide its own causal stage. Never invent it.
            calculation=dict(operands={},equation='',calculated_discrepancy_minor=None,
                             matches_declared_discrepancy=False,scope='No causal stage is available for this profile.')
            mutation={}
        else:
            calculation=_calculation(episode,truth,mutation)
        scores=[assignment[truth_index]] if truth_index in assignment else []
        supported=[i for i,edges in enumerate(support) if truth_index in edges]
        expected_ids=set(truth['affected_ids'])
        candidates=[f for f in findings if set(f.get('affected_ids',[]))==expected_ids]
        if scores:reason='matched'
        elif supported:reason='matching_conflict'
        elif not candidates:reason='missing_finding'
        elif not any(f['type']==truth['type'] for f in candidates):reason='wrong_type'
        elif not any(f['claimed_amount_minor']==truth['expected_amount_minor'] for f in candidates):reason='wrong_amount'
        elif not any(f['currency']==truth['currency'] for f in candidates):reason='wrong_currency'
        else:reason='insufficient_evidence'
        evidence=sorted(set(i for group in truth['evidence_sets'] for i in group))
        issues.append(dict(type=truth['type'],affected_ids=copy.deepcopy(truth['affected_ids']),
                           expected_amount_minor=truth['expected_amount_minor'],currency=truth['currency'],
                           before_rows=copy.deepcopy(mutation.get('before',[])),after_rows=copy.deepcopy(mutation.get('after',[])),
                           current_rows=[copy.deepcopy(records[i]) for i in truth['affected_ids'] if i in records],
                           evidence_records=[copy.deepcopy(records[i]) for i in evidence if i in records],
                           calculation=calculation,matched=bool(scores),matched_finding_indices=scores,candidate_finding_indices=supported,diagnosis=reason))
    if 'business' in public:
        from .realistic_audit import audit_realistic
        financial=audit_realistic(episode)
    else:
        financial=audit_episode(episode)
    result=dict(format='auditforge-completed-demo',version=PROOF_VERSION,episode_id=public['manifest']['episode_id'],
                report=copy.deepcopy(session.report),submission=copy.deepcopy(payload),issues=issues,financial=financial,
                scope='Trusted explanation after termination. Hidden answers and causal before/after must never be sent through the agent-facing RL tools.')
    return result
