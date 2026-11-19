"""Trusted broker: an untrusted policy only sees initial observations and step results."""
import argparse
import json
import queue
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from .env import AuditEnv


def send_line(process, value, deadline):
    """Bound backpressure too: a policy may stop consuming its stdin."""
    outcome = queue.Queue(maxsize=1)
    def writer():
        try:
            process.stdin.write(json.dumps(value)+'\n')
            process.stdin.flush()
            outcome.put(None)
        except (BrokenPipeError, OSError) as error:
            outcome.put(error)
    threading.Thread(target=writer, daemon=True).start()
    try:
        error = outcome.get(timeout=max(.001, deadline-time.monotonic()))
    except queue.Empty:
        raise TimeoutError('Policy stopped reading observations') from None
    if error is not None:
        raise error


def run(seed, isolated=True, config=None):
    container_name = 'auditforge-policy-' + uuid.uuid4().hex
    if isolated:
        command=['docker','run','--rm','--name',container_name,'-i','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','512m','--cpus','1','--pids-limit','64','--user','65534:65534','auditforge-policy:1.0']
    else:
        command=[sys.executable,str(Path(__file__).with_name('policy_agent.py'))]
    with AuditEnv(mode='evaluation') as env, tempfile.TemporaryDirectory() as cwd:
        started=time.monotonic()
        initial,_=env.reset(seed,config)
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
        trajectory=[]
        try:
            send_line(process, initial, started+60)
            for step in range(1,101):
                try:
                    line=inbox.get(timeout=max(.01,60-(time.monotonic()-started)))
                    if not line or len(line)>131072: raise ValueError()
                    action=json.loads(line)
                    json.dumps(action, allow_nan=False)
                except Exception:
                    action=dict(tool='invalid_policy_output') if time.monotonic()-started>=60 else dict(tool='submit',findings=None)
                observation,reward,terminated,truncated,info=env.step(action)
                trajectory.append(dict(episode_id=initial['manifest']['episode_id'],step=step,action=action,observation=observation,reward=reward,terminated=terminated,truncated=truncated))
                if terminated or truncated: break
                try:
                    send_line(process, dict(observation=observation,reward=reward,terminated=terminated,truncated=truncated,info=info), started+60)
                except (BrokenPipeError,OSError): pass
                except TimeoutError:
                    # The next iteration reaches Session's authoritative clock.
                    continue
            return dict(report=env.evaluator_report(),trajectory=trajectory,containment='docker' if isolated else 'trusted-native-only')
        finally:
            process.kill();process.wait(timeout=5)
            process.stdin.close()
            thread.join(timeout=1)
            process.stdout.close()
            if isolated:
                subprocess.run(['docker','rm','-f',container_name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5,check=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, default=829193)
    parser.add_argument('--config', type=Path, help='Evaluator-only episode config JSON')
    parser.add_argument('--trusted-native', action='store_true')
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8')) if args.config else None
    print(json.dumps(run(args.seed, not args.trusted_native, config)))

if __name__=='__main__':main()
