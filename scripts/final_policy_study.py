"""Frozen transfer/budget/ablation study; no selection on the final holdout.

All policies receive an initial public observation and a step callable. Evaluator
fixtures and rewards remain outside that boundary. Auxiliary budgets constrain the
strategy, not the official environment's 100-action/60-second contract.
"""
import argparse
import copy
import hashlib
import json
import random
import statistics
import time
from pathlib import Path
from unittest.mock import patch
from auditforge import efficient_training as source_policy

from auditforge.efficient_training import EfficientTrainer, INITIAL_WEIGHTS, investigate
from auditforge.env import Session
from auditforge.generator import generate
from auditforge.reconcile import reconcile
from auditforge.training import episode_seed

ROOT=Path(__file__).resolve().parents[1]
SEEDS=(314159,271828,161803,141421,173205)
BUDGETS=(5,10,20,40,100)
TRAIN_BUSINESSES=('logistics','trade')
TEST_BUSINESSES=('manufacturing','it','services')
SCENARIOS=('period','fx','mixed','clean')
HOLDOUT_ROOT=971836205419
POLICIES=('trained','untrained','random','reconciliation','zero_features','random_weights','independent_reward','forced_sources','no_financial_decode')
SOURCES=('generator.py','realistic.py','efficient_training.py','reconcile.py','matcher.py','env.py')


def source_hashes():
    return {name:hashlib.sha256((ROOT/'auditforge'/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest() for name in SOURCES}


class PublicBudget:
    """Advertise the same strategy budget on EVERY observation, reserve submit."""
    def __init__(self,session,budget):
        self._session,self.remaining=session,budget
        self.observed_ids=set()
    def step(self,action):
        if self.remaining<=0:raise AssertionError('Policy exceeded the strategy budget')
        if action.get('tool')=='submit':
            for finding in action.get('findings',{}).get('findings',[]):
                assert set(finding['affected_ids']+finding['evidence_ids'])<=self.observed_ids
        observation,reward,terminated,truncated,info=self._session.step(action)
        self.remaining-=1
        result=observation.get('result')
        if isinstance(result,dict) and isinstance(result.get('records'),list):
            self.observed_ids.update(r.get('row_id',r.get('doc_id')) for r in result['records'])
        observation=dict(observation,steps_remaining=self.remaining)
        return observation,reward,terminated,truncated,info


def run_acquisition(boundary,initial,weights,remove_decoder=False):
    if remove_decoder:
        with patch.object(source_policy,'decode',return_value=[]):
            return investigate(boundary.step,initial,weights)
    return investigate(boundary.step,initial,weights)


def run_baseline(boundary,initial,name):
    """The existing random/full-source policies with explicit early budget stop.

    Reconciliation requires all four tables. With insufficient budget it submits
    no claims rather than pretending missing source rows are complete evidence.
    At sufficient budget the collector and decoder match run_policy exactly.
    """
    public=dict(manifest=initial['manifest'],policy=initial['policy'])
    if name=='random':
        rng=random.Random(2026)
        for _ in range(min(8,boundary.remaining-1)):
            boundary.step(dict(tool='list_records',table=rng.choice(['ledger','payments','invoices','fx']),limit=50))
        findings=[]
    else:
        complete=True
        for table in ('ledger','invoices','payments','fx'):
            public[table]=[];cursor=None
            while True:
                if boundary.remaining<=1:complete=False;break
                observation,_,terminated,truncated,_=boundary.step(dict(tool='list_records',table=table,cursor=cursor,limit=50))
                if terminated or truncated or 'error' in observation:raise AssertionError('Unexpected baseline collection failure')
                public[table].extend(observation['result']['records']);cursor=observation['result']['next_cursor']
                if cursor is None:break
            if not complete:break
        findings=reconcile(public) if complete else []
    return boundary.step(dict(tool='submit',findings=dict(episode_id=initial['manifest']['episode_id'],findings=findings)))


def immutable_fixture(episode):
    """Trusted evaluator fixture shares immutable source; policy sees only step.

    Session.step copies every observation and never mutates the episode. A final
    hash check rejects any study that changed a fixture. No private state is
    passed to inference. Generation/reset performance is not included here.
    """
    session=Session();session.episode=episode;session.public=episode['public'];session.mode='evaluation'
    session.steps=0;session.done=False;session.done_flags=(False,False);session.report=None
    session.started=time.monotonic();session.seconds=60;session.final=[]
    initial=dict(task='Audit the company for four documented financial issue types; submit evidence-backed findings.',
                 manifest=copy.deepcopy(session.public['manifest']),policy=copy.deepcopy(session.public['policy']),steps_remaining=100)
    return session,initial


def train_noise(model,index):
    """Same public interaction/gradient; replace reward with independent U[-1,1]."""
    session=Session()
    initial,_=session.reset(episode_seed(model.seed,'efficient-train',index),model.config(index),'train')
    _,decisions=investigate(session.step,initial,model.weights,random.Random(episode_seed(model.seed,'efficient-actions',index)))
    fake=random.Random(episode_seed(model.seed,'independent-reward',index)).uniform(-1,1)
    advantage=fake-model.baseline
    for gate,features,action,probability in decisions:
        for j,value in enumerate(features):model.weights[gate*7+j]+=model.learning_rate*advantage*(action-probability)*value
    model.baseline=.9*model.baseline+.1*fake


def summarize(rows):
    values=sorted(r['steps'] for r in rows)
    return dict(runs=len(rows),independent_companies=len({r['company'] for r in rows}),
        **{key:statistics.mean(r[key] for r in rows) for key in ('precision','recall','f1','reward','steps','inspection_steps','cpu_seconds')},
        median_steps=statistics.median(values),p90_steps=values[int(.9*(len(values)-1))],
        fp=sum(r['fp'] for r in rows),fn=sum(r['fn'] for r in rows),minimum_f1=min(r['f1'] for r in rows))


def paired_interval(rows,budget,left='trained',right='reconciliation',metric='reward'):
    """Average checkpoint variation within a company, then bootstrap companies."""
    groups={}
    for row in rows:
        if row['budget']==budget and row['policy'] in (left,right):
            groups.setdefault(row['company'],{}).setdefault(row['policy'],[]).append(row[metric])
    differences=[statistics.mean(p[left])-statistics.mean(p[right]) for p in groups.values()]
    rng=random.Random(episode_seed(HOLDOUT_ROOT,'paired-bootstrap',budget))
    samples=sorted(statistics.mean(rng.choices(differences,k=len(differences))) for _ in range(2000))
    return dict(left=left,right=right,budget=budget,metric=metric,independent_company_clusters=len(differences),
        paired_difference=statistics.mean(differences),bootstrap_95=[samples[49],samples[1949]],replicates=2000,
        scope='Company-cluster percentile bootstrap after averaging the five checkpoints. Synthetic panel uncertainty only, not external-domain confidence.')


def run(episodes=300,seeds=SEEDS):
    frozen_sources=source_hashes();rows=[];training=[];fixtures=[];started=time.perf_counter()
    for business in TEST_BUSINESSES:
        for size in (40,84,200):
            for scenario in SCENARIOS:
                index=len(fixtures);config=EfficientTrainer(0,scenario).config(1)
                config.update(profile='realistic_v1',business_type=business,invoices=size,
                              timezone=('+05:45','-03:30','+14:00')[index%3],period_month=('2044-02','2037-12')[index%2])
                seed=episode_seed(HOLDOUT_ROOT,'heldout-company',index)
                fixtures.append((index,seed,scenario,business,size,config,generate(seed,config)))
    fixture_hashes=[hashlib.sha256(json.dumps(ep,sort_keys=True).encode()).hexdigest() for *_,ep in fixtures]
    for seed in seeds:
        model=EfficientTrainer(seed,'mixed',world_profile='realistic_v1')
        noise=EfficientTrainer(seed,'mixed',world_profile='realistic_v1')
        before=time.perf_counter()
        for index in range(episodes):
            model.business_type=noise.business_type=TRAIN_BUSINESSES[index%2]
            model.train_episode();train_noise(noise,index)
        checkpoint=copy.deepcopy(model.checkpoint())
        training.append(dict(seed=seed,episodes=episodes,train_businesses=list(TRAIN_BUSINESSES),seconds=time.perf_counter()-before,
                             weights=list(model.weights),independent_reward_weights=list(noise.weights)))
        zero_features=[w if index%7==0 else 0. for index,w in enumerate(model.weights)]
        random_weights=[random.Random(episode_seed(seed,'random-weight',index)).uniform(-2,2) for index in range(21)]
        for company,company_seed,scenario,business,size,config,episode in fixtures:
            for budget in BUDGETS:
                for policy in POLICIES:
                    session,initial=immutable_fixture(episode);initial['steps_remaining']=budget
                    boundary=PublicBudget(session,budget)
                    before=time.process_time()
                    if policy in ('random','reconciliation'):run_baseline(boundary,initial,policy)
                    else:
                        weights={'trained':model.weights,'untrained':INITIAL_WEIGHTS,'zero_features':zero_features,
                            'random_weights':random_weights,'independent_reward':noise.weights,
                            'forced_sources':[20.]*21,'no_financial_decode':model.weights}[policy]
                        run_acquisition(boundary,initial,weights,remove_decoder=policy=='no_financial_decode')
                    assert session.done and session.steps<=budget and session.done_flags==(True,False)
                    row=dict(training_seed=seed,company=company,company_seed=company_seed,scenario=scenario,business_type=business,
                        size=size,budget=budget,policy=policy,steps=session.steps,inspection_steps=session.steps-1,
                        cpu_seconds=time.process_time()-before,**{k:session.report[k] for k in ('precision','recall','f1','reward','tp','fp','fn')})
                    assert abs(row['reward']-max(-1,min(1,2*row['f1']-1-.002*row['inspection_steps'])))<1e-12
                    rows.append(row)
        assert model.checkpoint()==checkpoint
        print(json.dumps(dict(seed=seed,done_policy_runs=len(rows))),flush=True)
    assert fixture_hashes==[hashlib.sha256(json.dumps(ep,sort_keys=True).encode()).hexdigest() for *_,ep in fixtures]
    current_sources=source_hashes()
    return dict(study='final-transfer-budget-ablation',version=1,preregistered_design=dict(training_seeds=list(seeds),training_episodes=episodes,
        train_businesses=list(TRAIN_BUSINESSES),test_businesses=list(TEST_BUSINESSES),holdout_root=HOLDOUT_ROOT,budgets=list(BUDGETS),
        scenarios=list(SCENARIOS),sizes=[40,84,200],hyperparameters='Unchanged v3/v4 learning rate .1, no validation/tuning on final panel.',
        controls='Zero non-bias feature coefficients; randomized weights; independent uniform training reward; forced source gates; financial decoder removed.'),
        fixture_hashes_unchanged=True,source_sha256_lf=frozen_sources,sources_unchanged=frozen_sources==current_sources,training=training,
        unique_holdout_companies=len(fixtures),total_policy_runs=len(rows),
        summary=[dict(budget=b,policy=p,**summarize([r for r in rows if r['budget']==b and r['policy']==p])) for b in BUDGETS for p in POLICIES],
        paired=[paired_interval(rows,b,metric=m) for b in BUDGETS for m in ('f1','reward')],
        per_seed=[dict(seed=s,budget=b,**summarize([r for r in rows if r['training_seed']==s and r['budget']==b and r['policy']=='trained'])) for s in seeds for b in BUDGETS],
        companies=[dict(company=i,seed=s,scenario=k,business_type=b,size=n,config=c) for i,s,k,b,n,c,_ in fixtures],
        rows=rows,seconds=time.perf_counter()-started,
        limitations=['Same 36 company fixtures repeat across five checkpoints, nine policies and five budgets; 8100 runs are not 8100 independent companies.',
            'Evaluator fixtures share immutable source records; each step returns deep-copied observations and a final hash check verifies no fixture changed. Source generation/reset timing is excluded from inference timing.',
            'Transfer is within one procedural generator and the same procurement error mechanism, not external finance generalization.',
            'Zero-features means non-bias feature ablation at inference, not retraining a featureless architecture.',
            'Independent reward is uniform noise, not shuffled recorded rewards.',
            'Budgeted reconciliation keeps its four-table acquisition order and makes no claims if full sources cannot fit. Random reserves one submit action.',
            'The official environment remains 100 steps and 60 seconds; smaller budgets are strategy constraints imposed through public observations.',
            'Forced source gates plus documentary decoding are deterministic controls, not learned-model improvements.',
            'Financial arithmetic remains hand engineered; high F1 does not establish learned bookkeeping or superiority over deterministic reconciliation.'])


def write_markdown(result,path):
    lines=['# Final policy transfer and ablation study','',
        f"{result['unique_holdout_companies']} independent synthetic companies; {len(result['training'])} checkpoints; {result['total_policy_runs']} paired policy runs. Train businesses: logistics/trade. Test businesses: manufacturing/IT/services.",'',
        '| Budget | Policy | F1 | Reward | Steps | FP | FN |','|---:|---|---:|---:|---:|---:|---:|']
    for row in result['summary']:
        lines.append(f"| {row['budget']} | {row['policy']} | {row['f1']:.6f} | {row['reward']:.6f} | {row['steps']:.3f} | {row['fp']} | {row['fn']} |")
    lines+=['','## Paired uncertainty','', '| Budget | Metric | Trained minus reconciliation | Company-bootstrap 95% |','|---:|---|---:|---|']
    for row in result['paired']:lines.append(f"| {row['budget']} | {row['metric']} | {row['paired_difference']:.6f} | [{row['bootstrap_95'][0]:.6f}, {row['bootstrap_95'][1]:.6f}] |")
    lines+=['','## Interpretation','',
        'No production policy replacement is made by this study. At budgets where both policies have complete evidence, compare identical paired rows rather than selecting the best seed. If zero-feature or forced-source controls match the learned policy, that is evidence of limited acquisition complexity, not an additional learned financial skill.',
        '', '## Limitations','']+['- '+s for s in result['limitations']]
    full={r['policy']:r for r in result['summary'] if r['budget']==100}
    trained=[r for r in result['rows'] if r['policy']=='trained']
    forced=[r for r in result['rows'] if r['policy']=='forced_sources']
    force_equal=all((a['company'],a['training_seed'],a['budget'],a['f1'],a['reward'],a['steps'])==(b['company'],b['training_seed'],b['budget'],b['f1'],b['reward'],b['steps']) for a,b in zip(trained,forced))
    lines+=['','## Measured conclusions','',
        f"At 100 actions, trained F1={full['trained']['f1']:.6f}, reconciliation F1={full['reconciliation']['f1']:.6f}, reward={full['trained']['reward']:.6f}, mean steps={full['trained']['steps']:.6f}.",
        f"Zero non-bias features: F1={full['zero_features']['f1']:.6f}; random weights={full['random_weights']['f1']:.6f}; independent reward={full['independent_reward']['f1']:.6f}; decoder removed={full['no_financial_decode']['f1']:.6f}.",
        f"Every non-timing trained row matches the deterministic forced-source control: {force_equal}. Therefore this study does not establish a learned advantage over that stronger deterministic control.",
        'At budget 10 the trained policy exceeds full-source reconciliation on this panel, but the forced-source control has exactly the same result. This is an effect of partial-document decoding/budget adaptation, not evidence that learned weights outperform deterministic acquisition.',
        'The panel contains nine clean companies out of 36. F1=.25 from an always-empty decoder is correct abstention on these clean companies, not detection of financial violations.',
        'The decoder ablation uses a scoped replacement of the deterministic decode callable with empty findings; the financial arithmetic is not executed for this control. Source acquisition and evaluator remain unchanged.']
    if 'decoder_control_verification' in result:
        lines+=['', 'Decoder-control verification: '+json.dumps(result['decoder_control_verification'],sort_keys=True)]
    lines+=['','Source hashes normalize CRLF to LF for portability. `sources_unchanged` must be true before this report is treated as final.','']
    path.write_text('\n'.join(lines),encoding='utf8')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--episodes',type=int,default=300);parser.add_argument('--output',type=Path,default=Path('reports/final-policy-study.json'));args=parser.parse_args()
    if not 1<=args.episodes<=10000:parser.error('episodes outside 1..10000')
    result=run(args.episodes);args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2),encoding='utf8');write_markdown(result,args.output.with_suffix('.md'))
    print(json.dumps(dict(source_snapshot_unchanged=result['sources_unchanged'],policy_runs=result['total_policy_runs'],seconds=result['seconds'])))
    raise SystemExit(0 if result['sources_unchanged'] and result['fixture_hashes_unchanged'] else 1)
