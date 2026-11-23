"""Real document-policy Docker boundary and trained linear/MLP replay checks."""
import json
import subprocess
import uuid

from auditforge.agent_runner import container_command, run


def main():
    boundary="""
import json,os
from pathlib import Path
assert os.getuid()==65534
assert set(os.listdir('/sys/class/net'))=={'lo'}
assert os.statvfs('/').f_flag & os.ST_RDONLY
assert set(os.listdir('/policy/auditforge'))=={'__init__.py','document_policy.py','documentary_decode.py'}
for directory in ('/app','/submission','/datasets','/workspace','/evaluator_private'):
    assert not Path(directory).exists()
status=dict(line.split(':',1) for line in Path('/proc/self/status').read_text().splitlines())
assert int(status['CapEff'],16)==0 and status['NoNewPrivs'].strip()=='1'
print(json.dumps({'uid':os.getuid(),'network':'none','private_modules_absent':True,'read_only':True}))
"""
    subprocess.run(container_command('auditforge-document-boundary-'+uuid.uuid4().hex,'document')+
                   ['python','-I','-c',boundary],check=True,timeout=45)
    from auditforge.document_training import DocumentTrainer
    from auditforge.document_policy import investigate
    from auditforge.env import Session
    for architecture in ('linear','mlp'):
        model=DocumentTrainer(seed=202611230022,budget=20,architecture=architecture)
        for _ in range(4):model.train_episode()
        for family in ('procurement','service_milestone'):
            config=dict(profile='investigation_v2',family=family)
            closed=run(202611230023,config=config,policy='document',weights=model.model.parameters,
                       budget=model.budget,architecture=architecture)
            session=Session();initial,_=session.reset(202611230023,config,'evaluation')
            native=investigate(session.step,initial,model=model.model,budget=model.budget)
            assert closed['containment']=='docker' and closed['report']==session.report
            assert [r['action'] for r in closed['trajectory']]==[r['action'] for r in native['trajectory']]
            assert len(closed['trajectory'])<=model.budget
            assert all(r['reward']==0 for r in closed['trajectory'])
            print(json.dumps(dict(architecture=architecture,family=family,trained_episodes=model.episodes,
                                  trained_checkpoint_parity=True,report=closed['report'])))


if __name__=='__main__':main()
