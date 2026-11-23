"""Executable 2.2 mutation checks; import/compile failures never count as detections."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
MUTATIONS=(
 ('actor_sign','auditforge/document_policy.py','advantage*(values[chosen][1][j]-expected[j])','advantage*(expected[j]-values[chosen][1][j])'),
 ('entropy_sign','auditforge/document_policy.py','-entropy_coefficient*sum','+entropy_coefficient*sum'),
 ('critic_credit','auditforge/document_training.py','[reward-v for v in values]','[0.-v for v in values]'),
 ('normalization_mean','auditforge/document_training.py','(v-mean)/math.sqrt(variance+1e-8)','v/math.sqrt(variance+1e-8)'),
 ('boolean_parameters','auditforge/document_policy.py','type(v) not in (int,float)','not isinstance(v,(int,float))'),
 ('source_corruption','auditforge/document_world.py','dict(invoices=[copy.deepcopy(inv)])','dict(invoices=[dict(copy.deepcopy(inv),total_minor=inv["total_minor"]+1)])'),
)
MODULES=('tests.test_document_training','tests.test_document_policy','tests.test_document_world',
         'tests.test_document_adversarial','tests.test_document_containment')


def execute(folder):
    result=subprocess.run([sys.executable,'-m','unittest',*MODULES,'-q'],cwd=folder,
       env=dict(os.environ,PYTHONPATH=str(folder),PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8'),
       capture_output=True,text=True,encoding='utf8',errors='replace',timeout=120)
    output=result.stdout+result.stderr
    count=re.search(r'Ran (\d+) tests?',output)
    status=('error' if not count or '_FailedTest' in output else
            'passed' if result.returncode==0 else 'failed' if 'FAILED (' in output else 'error')
    return dict(status=status,tests=int(count[1]) if count else 0,output=output)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'work/document-mutation.json')
    args=parser.parse_args();original={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'auditforge').glob('*.py')}
    report=dict(mutations=[])
    with tempfile.TemporaryDirectory(prefix='auditforge-document-mutation-') as temporary:
        base=Path(temporary)/'baseline';base.mkdir()
        for name in ('auditforge','tests','scripts','configs'):
            shutil.copytree(ROOT/name,base/name,ignore=shutil.ignore_patterns('__pycache__'))
        report['baseline']=execute(base)
        if report['baseline']['status']!='passed':raise RuntimeError(report['baseline'])
        for name,file,before,after in MUTATIONS:
            folder=Path(temporary)/name;shutil.copytree(base,folder)
            path=folder/file;source=path.read_text(encoding='utf8')
            if before not in source:raise RuntimeError('Stale mutation '+name)
            changed=source.replace(before,after);compile(changed,file,'exec');path.write_text(changed,encoding='utf8')
            result=execute(folder);result['status']={'failed':'killed','passed':'survived'}.get(result['status'],result['status'])
            report['mutations'].append(dict(id=name,file=file,**result))
            print(name,result['status'],flush=True)
    report['source_unchanged']=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in original.items())
    report['killed']=sum(r['status']=='killed' for r in report['mutations'])
    report['passed']=report['source_unchanged'] and report['killed']==len(MUTATIONS)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    if not report['passed']:raise SystemExit(1)


if __name__=='__main__':main()
