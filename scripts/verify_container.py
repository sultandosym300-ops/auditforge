"""Validate the effective settings of the broker's policy container."""
import subprocess
import uuid

from auditforge.agent_runner import container_command


def main():
    name = 'auditforge-boundary-' + uuid.uuid4().hex
    code = """
import json
import os
from pathlib import Path

assert os.getuid() == os.getgid() == 65534
assert set(os.listdir('/sys/class/net')) == {'lo'}
assert os.statvfs('/').f_flag & os.ST_RDONLY
assert set(os.listdir('/policy')) == {'agent.py', 'reconcile.py'}
for directory in ('/app', '/workspace', '/datasets'):
    assert not Path(directory).exists(), directory
status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines())
assert int(status['CapEff'].strip(), 16) == 0
assert status['NoNewPrivs'].strip() == '1'
cgroup = Path('/sys/fs/cgroup')
assert (cgroup/'memory.max').read_text().strip() == str(512*1024*1024)
assert (cgroup/'pids.max').read_text().strip() == '64'
quota, period = map(int, (cgroup/'cpu.max').read_text().split())
assert quota == period
print(json.dumps({'network_interfaces':['lo'], 'read_only':True, 'policy_files':2,
                  'uid':os.getuid(), 'cpu_cores':1, 'ram_bytes':512*1024*1024,
                  'pids':64, 'capabilities':0}))
"""
    subprocess.run(container_command(name) + ['python', '-I', '-c', code],
                   check=True, timeout=45)


if __name__ == '__main__':
    main()
