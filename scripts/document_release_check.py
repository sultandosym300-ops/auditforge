"""Verify frozen 2.2 artifacts and reproduce policy actions from saved checkpoints offline."""
import argparse
import hashlib
import json
from pathlib import Path

from auditforge.document_training import DocumentTrainer
from auditforge.document_policy import investigate
from auditforge.generator import generate
from auditforge.reference_evaluator import evaluate_reference
from scripts.final_policy_study import immutable_fixture

ROOT=Path(__file__).resolve().parents[1]


def check():
    folder=ROOT/'reports'
    summary=json.loads((folder/'document-2.2-summary.json').read_text(encoding='utf8'))
    protocol=(ROOT/'configs/document-study-2.2.json').read_bytes()
    assert hashlib.sha256(protocol).hexdigest()==summary['protocol_sha256']
    hashes=json.loads((folder/'document-2.2-source-sha256.json').read_text(encoding='utf8'))
    for name in ('document_world.py','independent_world.py','document_policy.py','document_training.py',
                 'documentary_decode.py','env.py','generator.py'):
        assert hashlib.sha256((ROOT/'auditforge'/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==hashes[name],name
    spec=json.loads(protocol);runs=0
    for trained in spec['families']:
        for evaluated in spec['families']:
            raw=json.loads((folder/f'document-2.2-{trained}-to-{evaluated}-raw.json').read_text(encoding='utf8'))
            assert len(raw['fixtures'])==spec['test_companies']
            for fixture in raw['fixtures'][:2]:
                episode=generate(fixture['seed'],fixture['config'])
                assert hashlib.sha256(json.dumps(episode,sort_keys=True).encode()).hexdigest()==fixture['sha256']
                for replicate in range(3):
                    model=DocumentTrainer.from_checkpoint(json.loads((folder/f'document-2.2-{trained}-selected-{replicate}.json').read_text(encoding='utf8')))
                    for budget in spec['budgets']:
                        for policy in ('learned','blind_statistical','heuristic_search','untrained'):
                            session,initial=immutable_fixture(episode)
                            result=investigate(session.step,initial,policy=policy,model=model.network,budget=budget,blind_statistics=model.blind_statistics)
                            expected=next(row for row in raw['rows'] if row['company']==fixture['company'] and row['checkpoint']==replicate and row['budget']==budget and row['policy']==policy)
                            assert all(session.report[key]==expected[key] for key in ('tp','fp','fn','f1','reward'))
                            assert session.steps==expected['steps']
                            reference=evaluate_reference(initial['manifest']['episode_id'],episode['truth'],
                                dict(episode_id=initial['manifest']['episode_id'],findings=result['findings']),session.steps-1)
                            assert all(reference[key]==session.report[key] for key in ('tp','fp','fn'))
                            assert all(abs(reference[key]-session.report[key])<1e-12 for key in ('precision','recall','f1','reward'))
                            runs+=1
    for name in ('FINAL_AUDIT','RL_STUDY','GENERATOR_BLIND_BENCHMARK','TRANSFER_REPORT','ADVERSARIAL_REPORT','JURY_DEMO','LIMITATIONS'):
        assert (ROOT/f'AUDITFORGE_2_2_{name}.md').is_file()
    return dict(passed=True,reproduced_runs=runs,independent_test_companies=96,
                protocol_sha256=summary['protocol_sha256'],official_score=None)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'work/document-release-check.json')
    args=parser.parse_args();result=check();args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps(result))


if __name__=='__main__':main()
