"""Replay the same public actions in two fresh Python interpreters per case."""
import hashlib
import json
import os
import random
import subprocess
import sys

from auditforge.env import Session
from auditforge.metamorphic import canonical
from auditforge.policies import run_policy


def capture(seed, noise):
    # Deliberately vary unrelated state before resetting the evaluator.
    random.seed(noise)
    session = Session()
    session.reset(noise, {"clean": True}, "train")
    session.step({"tool": "calculator", "expression": "7/2"})
    initial, info = session.reset(seed, {"interaction": seed % 3}, "train")
    log = []
    run_policy(session, initial, "reconciliation", log)
    return canonical([initial, info, log, session.report])


def run(seed, count=6):
    rng = random.Random(seed)
    rows = []
    for _ in range(count):
        episode_seed = rng.getrandbits(128)
        streams = [
            subprocess.run(
                [sys.executable, "-m", "scripts.jury_replay", str(episode_seed), str(noise)],
                capture_output=True, check=True, timeout=60,
                env=dict(os.environ, PYTHONHASHSEED=str(noise)),
            ).stdout for noise in (17, 7901)
        ]
        initial, _, log, report = json.loads(streams[0])
        passed = streams[0] == streams[1] and report["f1"] == 1 and log[-1]["terminated"]
        rows.append(dict(seed=episode_seed, episode=initial["manifest"]["episode_id"],
                         bytes=len(streams[0]), sha256=hashlib.sha256(streams[0]).hexdigest(),
                         steps=len(log), passed=passed))
    return rows


if __name__ == "__main__":
    sys.stdout.buffer.write(capture(int(sys.argv[1]), int(sys.argv[2])))
