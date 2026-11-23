"""Actual closed-boundary checks; must run where Docker is available."""
import json
import subprocess
import uuid
from pathlib import Path

from auditforge.agent_runner import container_command,run
from auditforge.sequential_policy import INITIAL_WEIGHTS


def main():
    code="""
import importlib.util,json,os
from pathlib import Path
assert os.getuid()==65534
assert set(os.listdir('/sys/class/net'))=={'lo'}
assert os.statvfs('/').f_flag & os.ST_RDONLY
assert set(os.listdir('/policy/auditforge'))=={'__init__.py','sequential_policy.py','documentary_decode.py'}
for name in ('generator','env','matcher','sequential_training'):
    assert not Path('/policy/auditforge/'+name+'.py').exists()
for directory in ('/app','/submission','/datasets','/workspace','/evaluator_private'):
    assert not Path(directory).exists()
status=dict(line.split(':',1) for line in Path('/proc/self/status').read_text().splitlines())
assert int(status['CapEff'],16)==0 and status['NoNewPrivs'].strip()=='1'
print(json.dumps({'uid':os.getuid(),'network':'none','private_modules_absent':True,'read_only':True}))
"""
    subprocess.run(container_command('auditforge-sequential-boundary-'+uuid.uuid4().hex,'sequential')+['python','-I','-c',code],check=True,timeout=45)
    for family in ('procurement','closing_transfer'):
        result=run(202611230017,config=dict(profile='investigation_v1',family=family),
                   policy='sequential',weights=INITIAL_WEIGHTS,budget=100)
        assert result['containment']=='docker' and result['report']['f1']==1
        assert len(result['trajectory'])<=100 and all(row['reward']==0 for row in result['trajectory'])
        print(json.dumps(dict(family=family,steps=len(result['trajectory']),report=result['report'])))
    # Test the actual validation-selected trained weights as well, not only the
    # zero-initialized inference package. Private evaluation stays in the host.
    from auditforge.efficient_training import load_trainer
    from auditforge.env import Session
    from auditforge.sequential_policy import investigate
    checkpoint=Path(__file__).resolve().parents[1]/'reports/final-sequential-selected-0.json'
    model=load_trainer(json.loads(checkpoint.read_text(encoding='utf8')))
    config=dict(profile='investigation_v1')
    closed=run(202611230017,config=config,policy='sequential',weights=model.weights,budget=model.budget)
    session=Session();initial,_=session.reset(202611230017,config,'evaluation')
    native=investigate(session.step,initial,weights=model.weights,budget=model.budget)
    assert closed['report']==session.report
    assert [row['action'] for row in closed['trajectory']]==[row['action'] for row in native['trajectory']]
    print(json.dumps(dict(trained_checkpoint_parity=True,report=closed['report'])))


if __name__=='__main__':main()
