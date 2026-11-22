"""Fail-closed validation of a submission directory or ZIP, without Git or network."""
import argparse
import copy
import csv
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import tempfile
import zipfile

from auditforge.env import Session
from auditforge.generator import generate, GENERATOR_VERSION, TYPES
from auditforge.financial_audit import audit_episode
from scripts.run_baselines import POLICIES, evaluate_baseline

MAX_BYTES = 1_000_000_000
REQUIRED = ('README.md','LICENSE','requirements.txt','pyproject.toml','Dockerfile','Dockerfile.policy',
            'docs/public.schema.json','docs/findings.schema.json','docs/DESIGN_NOTE.md',
            'HACKATHON_COMPLIANCE.md','SUBMISSION_MANIFEST.md','JURY_LIVE_DEMO_SCRIPT.md',
            'FINAL_AUDIT_REPORT.md','THIRD_PARTY_NOTICES.md',
            'auditforge/generator.py','auditforge/env.py','auditforge/matcher.py',
            'scripts/run_baselines.py','scripts/submission_check.py','scripts/package_submission.py',
            'configs/train.json','configs/dev.json','trajectories/trajectories.jsonl','reports/submission-baselines.json')
PRIVATE_KEYS = {'truth','provenance','expected_amount_minor','evidence_sets','pristine'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def inspect_public(value):
    if isinstance(value,dict):
        require(not PRIVATE_KEYS.intersection(value), 'Private evaluator key in public data')
        for child in value.values():inspect_public(child)
    elif isinstance(value,list):
        for child in value:inspect_public(child)


def forbidden(name):
    parts = PurePosixPath(name).parts
    if any(p in ('.git','.openai','.impeccable','.vercel','node_modules','__pycache__','.pytest_cache','work','runtime','.venv','venv') for p in parts):return True
    return any(p.startswith('.env') and p!='.env.example' for p in parts) or name.endswith(('.pyc','.zip','.pem','.key'))


def exported_public(folder):
    public = {key:json.loads((folder/(key+'.json')).read_text(encoding='utf8')) for key in ('manifest','policy')}
    for table in ('invoices','payments'):
        public[table]=[json.loads(line) for line in (folder/(table+'.jsonl')).read_text(encoding='utf8').splitlines() if line.strip()]
    for table in ('ledger','fx'):
        rows=[]
        for row in csv.DictReader(io.StringIO((folder/(table+'.csv')).read_text(encoding='utf8'))):
            for key,value in list(row.items()):
                require(value!='','Ambiguous empty CSV cell')
                if value=='null':row[key]=None
                elif key.endswith('_minor'):row[key]=int(value)
            rows.append(row)
        public[table]=rows
    if (folder/'business.json').exists():public['business']=json.loads((folder/'business.json').read_text(encoding='utf8'))
    return public


def check_directory(root, *, verify_manifest=True):
    root=Path(root).resolve()
    for name in REQUIRED:require((root/name).is_file(),'Missing required file: '+name)
    require(bool(list((root/'tests').glob('test_*.py'))),'Regression tests missing')
    # Executing the checker itself can create Python bytecode in an extracted
    # source tree. Such runtime caches are not payload files. ZIP inputs reject
    # them before extraction; arbitrary extra source/data files still fail.
    files={str(p.relative_to(root)).replace('\\','/'):p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.relative_to(root).parts}
    require(sum(p.stat().st_size for p in files.values())<MAX_BYTES,'Submission exceeds one decimal GB')
    for name,path in files.items():
        require(not path.is_symlink(),'Symlink in submission: '+name)
        require(not forbidden(name),'Forbidden artifact: '+name)
        if path.suffix in ('.py','.js','.jsx','.json','.md','.yml','.txt'):
            text=path.read_text(encoding='utf-8-sig',errors='replace')
            require(not re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|sb_secret_[A-Za-z0-9]{20,}',text),'Credential material: '+name)
    if verify_manifest:
        manifest=json.loads((root/'submission-manifest.json').read_text(encoding='utf8'))
        expected=manifest.get('files',{})
        require(set(expected)==set(files)-{'submission-manifest.json'},'Manifest file set differs')
        for name,item in expected.items():
            data=files[name].read_bytes()
            require(item==dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest()),'Manifest digest differs: '+name)
    schema=json.loads((root/'docs/public.schema.json').read_text(encoding='utf8'))
    require(schema.get('$schema')=='https://json-schema.org/draft/2020-12/schema','Public schema draft missing')
    require(set(schema['$defs']['action']['properties']['tool']['enum'])=={'list_records','get_record','get_document','calculator','submit'},'Official tool schema differs')
    require(set(json.loads((root/'docs/findings.schema.json').read_text(encoding='utf8'))['properties']['findings']['items']['properties']['type']['enum'])==set(TYPES),'Finding classes differ')
    specifications={};seen_seeds=set();counts={}
    for split in ('train','dev'):
        config=json.loads((root/'configs'/(split+'.json')).read_text(encoding='utf8'))
        require(config.get('generator_version')==GENERATOR_VERSION,'Generator version differs')
        episodes=config.get('episodes',[])
        require(len(episodes)==10,split+' must contain exactly ten episodes')
        actual_folders={p.name for p in (root/'datasets'/split/'public').iterdir() if p.is_dir()}
        require(actual_folders=={r['episode_id'] for r in episodes},split+' public directory set differs')
        for row in episodes:
            seed=row['seed'];require(type(seed) is int and seed not in seen_seeds,'Repeated or invalid split seed');seen_seeds.add(seed)
            episode=generate(seed,row['config']);eid=episode['public']['manifest']['episode_id']
            require(row['episode_id']==eid,'Episode ID mismatch')
            public=exported_public(root/'datasets'/split/'public'/eid)
            inspect_public(public)
            # CSV has a fixed union of columns. The exporter encodes both absent
            # optional fields and JSON null as explicit `null` cells.
            expected_public=copy.deepcopy(episode['public'])
            for table in ('ledger','fx'):
                columns=set().union(*(r.keys() for r in expected_public[table]))
                expected_public[table]=[{k:r.get(k) for k in columns} for r in expected_public[table]]
            require(public==expected_public,'Export does not reproduce seed/config: '+eid)
            for field in ('truth','provenance'):
                actual=json.loads((root/'datasets'/split/'evaluator_private'/eid/(field+'.json')).read_text(encoding='utf8'))
                require(actual==episode[field],'Evaluator material differs: '+eid+'/'+field)
            require(audit_episode(episode)['valid'],'Independent financial audit failed: '+eid)
            specifications[eid]=(seed,row['config'])
        counts[split]=len(episodes)
    trajectories=[json.loads(line) for line in (root/'trajectories/trajectories.jsonl').read_text(encoding='utf8').splitlines() if line.strip()]
    require(trajectories,'Trajectories missing')
    sessions={};coverage=set()
    for row in trajectories:
        required={'episode_id','step','action','observation','reward','terminated','truncated','policy'}
        require(required<=set(row),'Trajectory schema incomplete')
        eid,policy=row['episode_id'],row['policy'];require(eid in specifications and policy in POLICIES[:3],'Unknown public trajectory episode/policy')
        key=(eid,policy)
        if key not in sessions:
            session=Session();session.reset(*specifications[eid],'train');sessions[key]=session
        session=sessions[key]
        require(not session.done and row['step']==session.steps+1,'Repeated, missing or post-terminal trajectory step')
        require(row['step']<=100,'Action budget exceeded')
        inspect_public(row['observation'])
        result=session.step(row['action'])
        require([row['observation'],row['reward'],row['terminated'],row['truncated']]==list(result[:4]),'Trajectory replay differs')
        require(type(row['terminated']) is bool and type(row['truncated']) is bool,'Termination flags are not booleans')
        if row['action'].get('tool')=='list_records':require(len(row['observation'].get('result',{}).get('records',[]))<=50,'Page size exceeds 50')
        coverage.add(key)
    train=json.loads((root/'configs/train.json').read_text(encoding='utf8'))['episodes']
    require(coverage=={(r['episode_id'],p) for r in train for p in POLICIES[:3]},'Incomplete train trajectory coverage')
    require(all(s.done for s in sessions.values()),'Unfinished trajectory')
    baseline_results=[]
    packaged=json.loads((root/'reports/submission-baselines.json').read_text(encoding='utf8'))
    packaged_rows=packaged.get('runs',[])
    require(len(packaged_rows)==40,'Expected forty train baseline runs')
    packaged_map={(r['episode_id'],r['policy']):r for r in packaged_rows}
    require(set(packaged_map)=={(r['episode_id'],p) for r in train for p in POLICIES},'Packaged baseline coverage differs')
    for row in train:
        for policy in POLICIES:
            actual=evaluate_baseline(row['seed'],row['config'],policy,allow_evaluator_oracle=True,mode='train')
            expected=dict(episode_id=row['episode_id'],policy=policy,evaluator_only=actual['evaluator_only'],steps=actual['steps'],**actual['report'])
            require(packaged_map[(row['episode_id'],policy)]==expected,'Packaged baseline report does not replay')
    for policy in POLICIES:
        result=evaluate_baseline(8471209,{},policy,allow_evaluator_oracle=True)
        require(policy not in ('reconciliation','oracle') or result['report']['f1']==1,'Exact baseline failed')
        baseline_results.append(dict(policy=policy,steps=result['steps'],**result['report']))
    try:evaluate_baseline(8471209,{},'oracle')
    except ValueError:pass
    else:raise ValueError('Oracle authorization guard missing')
    return dict(passed=True,train=counts['train'],dev=counts['dev'],trajectory_runs=len(sessions),trajectory_steps=len(trajectories),files=len(files),total_bytes=sum(p.stat().st_size for p in files.values()),baseline_results=baseline_results,official_score=None)


def check_archive(archive):
    with tempfile.TemporaryDirectory(prefix='auditforge-submission-') as folder:
        with zipfile.ZipFile(archive) as source:
            names=source.namelist();require(len(names)==len(set(names)),'Duplicate ZIP entry')
            require(sum(i.file_size for i in source.infolist())<MAX_BYTES,'Expanded ZIP exceeds limit')
            for info in source.infolist():
                path=PurePosixPath(info.filename)
                require(not path.is_absolute() and '..' not in path.parts and '\\' not in info.filename and ':' not in info.filename,'Unsafe ZIP path')
                require((info.external_attr>>16)&0o170000!=0o120000,'ZIP symlink')
                require(not forbidden(info.filename),'Forbidden ZIP artifact: '+info.filename)
            source.extractall(folder)
        root=Path(folder)
        if not (root/'README.md').exists():
            children=list(root.iterdir());require(len(children)==1 and children[0].is_dir(),'ZIP root ambiguous');root=children[0]
        return check_directory(root)


def main():
    parser=argparse.ArgumentParser(description=__doc__);group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--root',type=Path);group.add_argument('--archive',type=Path)
    args=parser.parse_args()
    try:result=check_archive(args.archive) if args.archive else check_directory(args.root)
    except (OSError,ValueError,KeyError,TypeError,StopIteration,zipfile.BadZipFile) as error:
        print(json.dumps(dict(passed=False,error=str(error))));return 1
    print(json.dumps(result));return 0


if __name__=='__main__':raise SystemExit(main())
