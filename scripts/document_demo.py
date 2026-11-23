"""A fixed-seed actual 2.2 demonstration; no search for a flattering company."""
import argparse
import json
from pathlib import Path
from auditforge.document_training import DocumentTrainer
from auditforge.document_policy import investigate
from auditforge.env import Session
from auditforge.reference_evaluator import evaluate_reference

ROOT=Path(__file__).resolve().parents[1]


def demo(checkpoint=None):
    checkpoint=checkpoint or ROOT/'reports/document-2.2-service_milestone-selected-0.json'
    model=DocumentTrainer.from_checkpoint(json.loads(Path(checkpoint).read_text(encoding='utf8')))
    runs=[]
    for policy in ('learned','untrained','blind_statistical','heuristic_search','random_valid'):
        session=Session();initial,_=session.reset(22022003,dict(profile='investigation_v2',family='service_milestone'),'evaluation')
        result=investigate(session.step,initial,policy=policy,budget=20,model=model.network,blind_statistics=model.blind_statistics)
        ref=evaluate_reference(initial['manifest']['episode_id'],session.episode['truth'],dict(episode_id=initial['manifest']['episode_id'],findings=result['findings']),session.steps-1)
        assert all(ref[k]==session.report[k] for k in ('tp','fp','fn'))
        assert all(abs(ref[k]-session.report[k])<1e-12 for k in ('f1','reward'))
        runs.append(dict(policy=policy,category=result['category'],report=session.report,reference=ref,steps=session.steps,
                         findings=result['findings'],trajectory=result['trajectory']))
    return dict(seed=22022003,family='service_milestone',budget=20,training_seed=model.seed,
                trained_episodes=model.episodes,runs=runs,official_score=None)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--checkpoint',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'work/document-demo.json');args=parser.parse_args()
    value=demo(args.checkpoint);args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in value.items() if k!='runs'}));print([(r['policy'],r['report']['reward']) for r in value['runs']])


if __name__=='__main__':main()
