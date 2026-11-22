"""Create public release evidence only from a successful exact-commit CI run."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request
import os

ROOT=Path(__file__).resolve().parents[1]
REPO='sultandosym300-ops/geneziz'

def build(run_id,*,git_credential=False):
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():raise ValueError('Commit the release before recording CI evidence')
    token=os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if git_credential and not token:
        credentials=subprocess.run(['git','-c','credential.interactive=never','credential','fill'],input='protocol=https\nhost=github.com\nusername=sultandosym300-ops\n\n',cwd=ROOT,text=True,capture_output=True,check=True)
        token=dict(line.split('=',1) for line in credentials.stdout.splitlines() if '=' in line).get('password')
    def api(path):
        headers={'User-Agent':'AuditForge-release-proof','Accept':'application/vnd.github+json'}
        if token:headers['Authorization']='Bearer '+token
        with urllib.request.urlopen(urllib.request.Request('https://api.github.com/repos/'+REPO+'/'+path,headers=headers),timeout=30) as response:return json.load(response)
    run=api('actions/runs/'+str(run_id));jobs=api('actions/runs/'+str(run_id)+'/jobs')['jobs']
    if run['head_sha']!=sha or run['status']!='completed' or run['conclusion']!='success':raise ValueError('CI does not prove this exact commit')
    if not jobs or any(j['status']!='completed' or j['conclusion']!='success' for j in jobs):raise ValueError('Incomplete or failed CI jobs')
    source={}
    for folder in ('auditforge','web/src'):
        for file in sorted((ROOT/folder).rglob('*')):
            if file.is_file() and file.suffix in ('.py','.js','.jsx','.css'):source[file.relative_to(ROOT).as_posix()]=hashlib.sha256(file.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    for name in ('web/prepare.mjs','web/package.json','web/package-lock.json','scripts/prepare_release_evidence.mjs','scripts/build.mjs','web/public/python-worker.js','web/public/python-bridge.py'):
        source[name]=hashlib.sha256((ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    reports=[]
    for name,command in [('final-agent-only.json','python -m scripts.final_agent_only'),('final-policy-study.json','python -m scripts.final_policy_study')]:
        file=ROOT/'reports'/name
        if file.exists():
            data=json.loads(file.read_text(encoding='utf8'))
            reports.append(dict(path='reports/'+name,url='https://github.com/'+REPO+'/blob/'+sha+'/reports/'+name,sha256=hashlib.sha256(file.read_bytes().replace(b'\r\n',b'\n')).hexdigest(),command=command,metadata={k:v for k,v in data.items() if k not in ('rows','fixtures','checkpoints','trials','history','results','controls','summary','paired')}))
    return dict(reports=reports,format='auditforge-release-evidence',version=1,source_commit=sha,generator_version='2.0.1',financial_profile='realistic_v1',check_version='final-submission-v1',ci_run_id=run_id,ci_url=run['html_url'],ci_conclusion='success',ci_completed_at=run['updated_at'],recorded_at=datetime.now(timezone.utc).isoformat(),command='GitHub Actions .github/workflows/verify.yml',seed=801973140685,configuration=dict(python='3.11',cpus=2,memory_bytes=4294967296,network='none'),jobs=[dict(name=j['name'],conclusion=j['conclusion'],steps=[dict(name=s['name'],conclusion=s['conclusion']) for s in j['steps']]) for j in jobs],source_sha256=source,hash_encoding='UTF-8 source bytes with CRLF normalized to LF',scope='Confirmed external CI for the exact cited source commit. The browser validates the bundled source hashes; it does not execute Docker. No official jury score.')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--ci-run',type=int,required=True);parser.add_argument('--git-credential',action='store_true');parser.add_argument('--output',type=Path,default=ROOT/'web/public/release-evidence.json');args=parser.parse_args();result=build(args.ci_run,git_credential=args.git_credential);args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(dict(commit=result['source_commit'],ci=result['ci_url'],source_files=len(result['source_sha256']))))
