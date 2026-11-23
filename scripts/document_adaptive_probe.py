"""Reward-trained reference-following diagnostic, explicitly separate from the primary study."""
import json
import math
from pathlib import Path
import random
from auditforge.document_policy import Network, distribution, feature_vector, objective_gradient
from auditforge.documentary_decode import decode
from auditforge.training import episode_seed
from scripts.document_adversarial import _period_pair, _fixture, adaptive_pairs

ROOT=Path(__file__).resolve().parents[1]


def run():
    spec=json.loads((ROOT/'configs/document-adaptive-probe-2.2.json').read_text(encoding='utf8'))
    model=Network(seed=spec['policy_seed']);rng=random.Random(spec['policy_seed']);history=[];baseline=0.
    for i in range(spec['training_episodes']):
        pair=_period_pair(episode_seed(spec['training_root'],'reference-train',i),spec['training_family'])
        episode=pair[i%2];session,initial=_fixture(episode);session.mode='train'
        first=pair[2];doc=session.step(dict(tool='get_document',doc_id=first))[0]['result']
        public=dict(manifest=initial['manifest'],policy=initial['policy'],ledger=[],invoices=[],payments=[],fx=[])
        for table,records in doc['records'].items():public[table].extend(records)
        candidates=[d for d in initial['manifest']['document_index'] if d['document_id']!=first]
        xs=[feature_vector(c,{first:doc},public,2,3) for c in candidates]+[feature_vector(None,{first:doc},public,2,3,stop=True)]
        probabilities=distribution(model,xs);chosen=rng.choices(range(len(xs)),weights=probabilities)[0]
        if chosen<len(candidates):
            source=session.step(dict(tool='get_document',doc_id=candidates[chosen]['document_id']))[0]['result']
            for table,records in source['records'].items():public[table].extend(records)
        session.step(dict(tool='submit',findings=dict(episode_id=initial['manifest']['episode_id'],findings=decode(public))))
        reward=session.report['reward'];gradient=objective_gradient(model,xs,chosen,reward-baseline,spec['entropy'])
        norm=math.sqrt(sum(g*g for g in gradient));scale=min(1.,5/max(norm,1e-12))
        model.parameters=[max(-30,min(30,w+spec['learning_rate']*g*scale)) for w,g in zip(model.parameters,gradient)]
        baseline=.95*baseline+.05*reward;history.append(dict(episode=i+1,reward=reward,f1=session.report['f1']))
    result=adaptive_pairs(model,seed=spec['test_root'],count=spec['test_pairs_per_family'])
    return dict(protocol=spec,parameters=model.parameters,history=history,test=result,
                primary_study_unchanged=True,scope=spec['scope_limit'])


if __name__=='__main__':
    path=ROOT/'reports/document-2.2-adaptive-probe.json'
    if path.exists():raise ValueError('Preserve the completed diagnostic')
    result=run();path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result['test']['summary']))
