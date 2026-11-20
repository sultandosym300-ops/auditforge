"""Run AUDITFORGE_JURY_GAUNTLET on the submitted repository, entirely offline."""
import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import unittest

from auditforge.export import write_json
from auditforge.financial_audit import run_mass_audit
from auditforge.generator import GENERATOR_VERSION
from auditforge.metamorphic import run as metamorphic
from scripts import jury_blind, jury_delivery, jury_replay, jury_reward

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEED = 783061141199


def run_command(*args):
    subprocess.run([sys.executable, *map(str, args)], check=True, cwd=ROOT)


def fixed_checks(pattern):
    suite = unittest.defaultTestLoader.discover(str(ROOT/"tests"), pattern)
    class Results(unittest.TestResult):
        def __init__(self):
            super().__init__()
            self.rows = []
        def stopTest(self, test):
            super().stopTest(test)
            failed = any(case == test for case, _ in self.errors + self.failures + self.skipped)
            self.rows.append(dict(name=test.id(), passed=not failed,
                                  source="tests/"+pattern, inputs="fixture in named test",
                                  expected="all assertions hold", actual="failed" if failed else "passed"))
    result = Results()
    suite.run(result)
    return result.rows


def render(report):
    lines = ["# AUDITFORGE_JURY_GAUNTLET", "",
             f"Generator {report['version']}. Root seed `{report['seed']}`. Python {report['python']}.",
             "", "## Published rubric reproduced locally", "",
             "| Category | Score | Maximum |", "|---|---:|---:|"]
    for name, (points, maximum) in report['rubric'].items():
        lines.append(f"| {name} | {points:g} | {maximum} |")
    lines += ["", "## Extended checks", "", "| Test | Expected | Observed | Result |",
              "|---|---|---|---|"]
    for item in report["checks"]:
        lines.append(f"| {item['name']} | {item['expected']} | {item['actual']} | {'PASS' if item['passed'] else 'FAIL'} |")
    lines += ["", "## Mutation sensitivity", "", "| Mutation | Expected detection | Observed failing test (first) | Result |",
              "|---|---|---|---|"]
    for row in report["mutations"]["mutations"]:
        failed = row["failing_tests"] or ["none"]
        lines.append(f"| {row['id']} | {row.get('expected_detection', row['description'])} | {failed[0]} | {row['status']} |")
    lines += ["", "## Controlled reference configurations", "", "| Reference | Local rubric | With added data controls |",
              "|---|---:|---:|"]
    for row in report["references"]["references"].values():
        lines.append(f"| {row['description']} | {row['rubric_total']:g} | {row['stricter_total']:g} |")
    lines += ["", "Detailed inputs, episode IDs, measurements and individual outcomes are in "
              "[JURY_GAUNTLET_RESULTS.json](JURY_GAUNTLET_RESULTS.json). "
              "A fresh run with a new root seed changes the financial trials.",
              "", "The rubric is a local reconstruction. Container limits are checked separately by the release workflow."]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=DEFAULT_SEED)
    args = parser.parse_args()
    if not __debug__:
        parser.error("assertions must be enabled")
    root = args.seed
    work = ROOT/"work"
    work.mkdir(exist_ok=True)
    checks = []
    def record(name, expected, actual, passed, source, seed=root):
        checks.append(dict(name=name, seed=seed, expected=expected, actual=actual,
                           passed=bool(passed), source=source, severity="major"))

    with tempfile.TemporaryDirectory(dir=work, prefix="jury-") as folder:
        out = Path(folder)
        run_command("-m", "auditforge.verify", "--seed", root, "--output-dir", out)
        official = json.loads((out/"reports/verification.json").read_text(encoding="utf8"))
        delivery = jury_delivery.verify(ROOT, out)
        record("Submission inventory, exact regenerated files and trajectory privacy", len(delivery),
               sum(c["passed"] for c in delivery), all(c["passed"] for c in delivery), "scripts/jury_delivery.py")
        contracts = fixed_checks("test_contract.py")
        rewards = fixed_checks("test_reward.py")
        for label, rows, file in (("Contract", contracts, "test_contract.py"), ("Reward", rewards, "test_reward.py")):
            n = sum(r["passed"] for r in rows)
            record(label+" fixed checks", 20, n, len(rows) == n == 20, "tests/"+file)
        measure = official["benchmark"]
        max_steps = max(r["steps"] for r in measure)
        max_seconds = max(r["seconds"] for r in measure)
        record("80 complete baseline runs", "80, <=100 steps and <60s each",
               f"{len(measure)}, {max_steps} steps, {max_seconds:.3f}s maximum",
               len(measure) == 80 and max_steps <= 100 and max_seconds < 60, "auditforge/verify.py")
        finance = run_mass_audit(1000, root+1)
        finance.pop("episodes")
        record("Independent exact-rational financial and causal audit", 1000, finance["passed"],
               finance["failed"] == 0, "auditforge/financial_audit.py", root+1)
        blind = jury_blind.run(root+2, 50)
        record("Public evidence collected before submit", 50, blind["passed"],
               blind["passed"] == 50, "scripts/jury_blind.py", root+2)
        dense = blind["dense"]
        record("Sized batch-payment books at both published endpoints", 4,
               sum(r["passed"] for r in dense), len(dense) == 4 and all(r["passed"] for r in dense),
               "scripts/jury_batch.py", root+2)
        tournament = jury_reward.run(root+3)
        record("Independent reward and assignment tournament", 20, tournament["passed_checks"],
               tournament["passed"], "scripts/jury_reward.py", root+3)
        replay = jury_replay.run(root+4)
        record("Byte-identical public transcripts across interpreters", len(replay),
               sum(r["passed"] for r in replay), all(r["passed"] for r in replay), "scripts/jury_replay.py", root+4)
        pairs = metamorphic(root+5, 100)
        record("Renamed/reordered paired companies", 100, pairs["paired_checks"],
               pairs["paired_checks"] == 100, "auditforge/metamorphic.py", root+5)
        mutation_path = out/"mutations.json"
        run_command("-m", "scripts.mutation_audit", "--output", mutation_path)
        mutations = json.loads(mutation_path.read_text(encoding="utf8"))
        for row in mutations["mutations"]:
            row.pop("log", None)
        record("Disposable mutations detected", len(mutations["mutations"]), mutations["killed"],
               mutations["passed"], "scripts/mutation_audit.py")
        engineering = {
            "single command": bool(official["tests_passed"]),
            "versioned configurations": all(c["passed"] for c in delivery if "config" in c["name"]),
            "trajectories": all(c["passed"] for c in delivery if "trajectory" in c["name"]),
            "measured failures": mutations["passed"] and tournament["passed"],
            "documented limitations": all(s in (ROOT/"README.md").read_text(encoding="utf8")
                                          for s in ("tracemalloc", "Oracle", "--trusted-native")),
        }
        eng = 2 * sum(engineering.values())
        ref_path = out/"references.json"
        run_command("-m", "scripts.jury_references", "--seed", root+6, "--engineering", eng, "--output", ref_path)
        references = json.loads(ref_path.read_text(encoding="utf8"))
        record("Controlled reference discrimination", True, references["passed"], references["passed"],
               "scripts/jury_references.py", root+6)
    rubric = {"Contract & Isolation": [25*sum(r["passed"] for r in contracts)/20, 25],
              "Data & Truth": [25*sum(r["valid"] for r in official["data"])/20, 25],
              "Reward Robustness": [25*sum(r["passed"] for r in rewards)/20, 25],
              "Reproducibility & Generalization": [15*sum(r["repeat_exact"] and r["renamed_shuffled_equivalent"]
                  for r in official["metamorphic_pairs"])/20, 15], "Engineering & Explanation": [eng, 10]}
    report = dict(name="AUDITFORGE_JURY_GAUNTLET", version=GENERATOR_VERSION, python=platform.python_version(),
                  seed=root, rubric=rubric, official_score=None, engineering=engineering, checks=checks,
                  contract=contracts, reward=rewards, official_approximation=official, delivery=delivery,
                  finance=finance, blind=blind, tournament=tournament, replay=replay, pairs=pairs,
                  mutations=mutations, references=references)
    write_json(ROOT/"JURY_GAUNTLET_RESULTS.json", report)
    (ROOT/"JURY_GAUNTLET_REPORT.md").write_text(render(report), encoding="utf8")
    print(json.dumps(dict(rubric=rubric, checks=checks), indent=2))
    return int(not all(item["passed"] for item in checks))


if __name__ == "__main__":
    raise SystemExit(main())
