"""One-command offline verification of the realistic and proof platform."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]

def verify(*,full_core=False,skip_unit_tests=False,output=Path('work/v4-verification/summary.json')):
    destination=output if output.is_absolute() else ROOT/output
    logs=ROOT/'work/v4-verification';logs.mkdir(parents=True,exist_ok=True)
    commands=[]
    if full_core:commands.append(('full_core',['-m','scripts.ultimate_verify','--seed','801973140685']))
    elif not skip_unit_tests:commands.append(('unit',['-m','unittest','discover','-s','tests','-q']))
    commands.extend([
        ('proof',['-m','scripts.v4_proof_check','--output',str(logs/'proof.json')]),
        ('world',['-m','scripts.v4_world_check','--output',str(logs/'world.json'),'--export-example',str(logs/'example')]),
        ('native_http',['-m','scripts.v4_native_demo_check','--output',str(logs/'native-http.json')]),
        ('training',['-m','scripts.v4_training_check','--output',str(logs/'training.json')]),
    ])
    checks=[];started=time.perf_counter()
    for name,args in commands:
        before=time.perf_counter();log=logs/(name+'.log')
        with log.open('w',encoding='utf8') as stream:
            result=subprocess.run([sys.executable,*args],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
        checks.append(dict(name=name,command=[sys.executable,*args],passed=result.returncode==0,returncode=result.returncode,seconds=time.perf_counter()-before,log=str(log.relative_to(ROOT))))
        print(json.dumps(checks[-1]),flush=True)
        if result.returncode:break
    source_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('auditforge','tests','scripts') for p in sorted((ROOT/folder).glob('*.py'))}
    summary=dict(format='auditforge-v4-offline-verification',python=platform.python_version(),platform=platform.platform(),full_core=full_core,unit_tests_skipped=skip_unit_tests,passed=all(c['passed'] for c in checks) and len(checks)==len(commands),checks=checks,source_sha256=source_hashes,seconds=time.perf_counter()-started,scope='Native Python and real loopback HTTP checks. This process does not claim that the browser ran Docker or that local tests are an official jury score.')
    destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(json.dumps(summary,indent=2),encoding='utf8')
    return summary

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);group=parser.add_mutually_exclusive_group();group.add_argument('--full-core',action='store_true');group.add_argument('--skip-unit-tests',action='store_true');parser.add_argument('--output',type=Path,default=Path('work/v4-verification/summary.json'));args=parser.parse_args()
    result=verify(full_core=args.full_core,skip_unit_tests=args.skip_unit_tests,output=args.output)
    raise SystemExit(0 if result['passed'] else 1)
