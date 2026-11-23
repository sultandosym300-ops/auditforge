"""Create a curated, self-checking hackathon ZIP; never copy a working directory wholesale."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

from auditforge.generator import generate, GENERATOR_VERSION
from auditforge.export import export_episode
from scripts.run_baselines import POLICIES, evaluate_baseline
from scripts.submission_check import check_directory, forbidden

ROOT=Path(__file__).resolve().parents[1]
ROOT_FILES={'README.md','LICENSE','requirements.txt','pyproject.toml','Dockerfile','Dockerfile.policy',
            'Dockerfile.sequential-policy','AUDITFORGE_FINAL_INDEPENDENT_AUDIT.md',
            'AUDITFORGE_RL_BENCHMARK.md','AUDITFORGE_ADVERSARIAL_REPORT.md',
            'AUDITFORGE_GENESIS_COMPLIANCE.md','AUDITFORGE_JURY_DEMO.md','AUDITFORGE_LIMITATIONS.md',
            'package.json','vercel.json','.gitignore','.vercelignore','.dockerignore',
            'HACKATHON_COMPLIANCE.md','SUBMISSION_MANIFEST.md','FINAL_AUDIT_REPORT.md',
            'JURY_LIVE_DEMO_SCRIPT.md','AUDITFORGE_4_REALISM_AND_PROOF_REPORT.md','THIRD_PARTY_NOTICES.md'}
REPORT_PREFIXES=('v4-','final-','submission-')


def selected_sources(root):
    candidates=[]
    for base,directories,names in os.walk(root):
        parent=Path(base)
        directories[:]=[d for d in directories if not forbidden((parent/d).relative_to(root).as_posix()) and (parent/d).relative_to(root).as_posix() not in ('datasets','trajectories','dist','web/dist','web/public/python','reports/mutation-audit-logs','docs/history')]
        candidates.extend(parent/name for name in names)
    for file in sorted(candidates):
        if not file.is_file() or file.is_symlink():continue
        name=file.relative_to(root).as_posix()
        if forbidden(name) or name.startswith(('datasets/','trajectories/','dist/')):continue
        if name in ROOT_FILES or name.startswith(('.github/','auditforge/','scripts/','tests/','configs/','docs/')):
            yield file,name
        elif name.startswith('web/') and not name.startswith(('web/dist/','web/public/python/')) and name!='web/public/python-core.json':
            # Explicitly excluded user credentials remain excluded even when ignored by Git.
            yield file,name
        elif name.startswith('reports/') and file.suffix in ('.json','.md','.csv') and file.name.startswith(REPORT_PREFIXES):
            yield file,name


def source_commit(root):
    try:result=subprocess.run(['git','rev-parse','--show-toplevel'],cwd=root,capture_output=True,text=True,encoding='utf8')
    except FileNotFoundError:result=None
    if result is not None and result.returncode==0 and Path(result.stdout.strip()).resolve()==root.resolve():
        sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True,encoding='utf8').strip()
        dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True,encoding='utf8').strip())
        return dict(commit=sha,dirty=dirty)
    prior=root/'submission-manifest.json'
    if prior.exists():return json.loads(prior.read_text(encoding='utf8')).get('source',dict(commit=None,dirty=None))
    declared=os.environ.get('AUDITFORGE_SOURCE_COMMIT','')
    if len(declared)==40 and all(c in '0123456789abcdef' for c in declared):
        return dict(commit=declared,dirty=False,origin='explicit CI source identity')
    return dict(commit=None,dirty=None)


def prepare_tree(destination, *, source=ROOT):
    source=Path(source).resolve();destination=Path(destination).resolve()
    if destination==source or source.is_relative_to(destination):raise ValueError('Submission destination must not contain source')
    destination.mkdir(parents=True,exist_ok=True)
    if any(destination.iterdir()):raise ValueError('Prepare a submission only in an empty directory')
    for file,name in selected_sources(source):
        if file.resolve().is_relative_to(destination):continue
        target=destination/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,target)
    trajectory=[];evaluations=[]
    for split in ('train','dev'):
        specification=json.loads((source/'configs'/(split+'.json')).read_text(encoding='utf8'))
        for row in specification['episodes']:
            episode=generate(row['seed'],row['config'])
            if episode['public']['manifest']['episode_id']!=row['episode_id']:raise ValueError('Stale episode specification')
            export_episode(episode,destination/'datasets'/split)
            if split=='train':
                for policy in POLICIES:
                    result=evaluate_baseline(row['seed'],row['config'],policy,allow_evaluator_oracle=True,mode='train')
                    evaluations.append(dict(episode_id=row['episode_id'],policy=policy,evaluator_only=result['evaluator_only'],steps=result['steps'],**result['report']))
                    if policy!='oracle':trajectory.extend(dict(policy=policy,**step) for step in result['trajectory'])
    (destination/'trajectories').mkdir(exist_ok=True)
    (destination/'trajectories/trajectories.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in trajectory),encoding='utf8')
    (destination/'reports').mkdir(exist_ok=True)
    (destination/'reports/submission-baselines.json').write_text(json.dumps(dict(generator_version=GENERATOR_VERSION,scope='Four trusted-host baseline adapters on the ten published train episodes. Oracle is evaluator-only, not a policy RPC.',runs=evaluations),indent=2)+'\n',encoding='utf8')
    inventory=sorted(p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file())+['submission-manifest.json']
    template=(destination/'SUBMISSION_MANIFEST.md').read_text(encoding='utf8')
    (destination/'SUBMISSION_MANIFEST.md').write_text(template+'\n## Полный перечень файлов\n\n'+'\n'.join('- `'+name+'`' for name in sorted(inventory))+'\n',encoding='utf8')
    manifest=dict(format='auditforge-submission-manifest',version=1,generator_version=GENERATOR_VERSION,source=source_commit(source),
                  private_material='datasets/{train,dev}/evaluator_private is trusted-evaluator-only; never mount it into the policy container.',
                  files={p.relative_to(destination).as_posix():dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(destination.rglob('*')) if p.is_file()})
    (destination/'submission-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
    return check_directory(destination)


def package(output, *, source=ROOT):
    output=Path(output).resolve();output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='auditforge-package-') as temporary:
        staging=Path(temporary)/'AuditForge'
        result=prepare_tree(staging,source=source)
        with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
            for file in sorted(staging.rglob('*')):
                if file.is_file():archive.write(file,'AuditForge/'+file.relative_to(staging).as_posix())
        return dict(**result,archive=str(output),archive_bytes=output.stat().st_size,archive_sha256=hashlib.sha256(output.read_bytes()).hexdigest())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('work/submission/AuditForge-final.zip'))
    args=parser.parse_args();print(json.dumps(package(args.output)))


if __name__=='__main__':main()
