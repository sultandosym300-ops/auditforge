"""Trusted broker: an untrusted policy only sees initial observations and step results."""
import argparse
import json
import queue
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from .env import AuditEnv


def run(seed, isolated=True):
    if isolated:
        command=['docker','run','--rm','-i','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','512m','--cpus','1','--pids-limit','64','--user','65534:65534','auditforge-policy:1.0']
    else:
        command=[sys.executable,str(Path(__file__).with_name('policy_agent.py'))]
    with AuditEnv(mode='evaluation') as env, tempfile.TemporaryDirectory() as cwd:
        initial,_=env.reset(seed,{})
        process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf-8',cwd=cwd,bufsize=1)
        inbox=queue.Queue(maxsize=2)
        def reader():
            try:
                for _ in range(101):
                    line=process.stdout.readline(131073)
                    inbox.put(line,timeout=1)
                    if not line: break
            except Exception: pass
        thread=threading.Thread(target=reader,daemon=True); thread.start()
        started=time.monotonic(); trajectory=[]
        try:
            process.stdin.write(json.dumps(initial)+'\n');process.stdin.flush()
            for step in range(1,101):
                try:
                    line=inbox.get(timeout=max(.01,60-(time.monotonic()-started)))
                    if not line or len(line)>131072: raise ValueError()
                    action=json.loads(line)
                except Exception:
                    action=dict(tool='invalid_policy_output') if time.monotonic()-started>=60 else dict(tool='submit',findings=None)
                observation,reward,terminated,truncated,info=env.step(action)
                trajectory.append(dict(episode_id=initial['manifest']['episode_id'],step=step,action=action,observation=observation,reward=reward,terminated=terminated,truncated=truncated))
                try:
                    process.stdin.write(json.dumps(dict(observation=observation,reward=reward,terminated=terminated,truncated=truncated,info=info))+'\n');process.stdin.flush()
                except (BrokenPipeError,OSError): pass
                if terminated or truncated: break
            return dict(report=env.evaluator_report(),trajectory=trajectory,containment='docker' if isolated else 'trusted-native-only')
        finally:
            process.kill();process.wait(timeout=5)


def main():
    p=argparse.ArgumentParser();p.add_argument('--seed',type=int,default=829193);p.add_argument('--trusted-native',action='store_true');args=p.parse_args()
    print(json.dumps(run(args.seed,not args.trusted_native)))

if __name__=='__main__':main()
