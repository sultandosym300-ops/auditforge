"""Verify submitted public examples and trajectory files against a fresh export."""
import hashlib
import json
from pathlib import Path


def normalized_digest(path):
    # A Windows checkout may use CRLF while a Linux checkout uses LF.
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def verify(root, generated):
    checks = []
    def check(name, actual, expected, source):
        checks.append(dict(name=name, actual=actual, expected=expected, source=source,
                           passed=actual == expected, severity="major"))

    for split in ("train", "dev"):
        relative = Path("datasets") / split / "public"
        wanted = {p.relative_to(generated) for p in (generated / relative).rglob("*") if p.is_file()}
        actual = {p.relative_to(root) for p in (root / relative).rglob("*") if p.is_file()}
        check(split + " public files", sorted(map(str, actual ^ wanted)), [], relative.as_posix())
        mismatches = sorted(p.as_posix() for p in wanted & actual
                            if normalized_digest(root / p) != normalized_digest(generated / p))
        check(split + " public content", mismatches, [], relative.as_posix())
        config = Path("configs") / (split + ".json")
        check(split + " versioned config", normalized_digest(root/config),
              normalized_digest(generated/config), config.as_posix())
        check(split + " episode count", len({p.parent for p in actual}), 10, relative.as_posix())

    trajectory = Path("trajectories/trajectories.jsonl")
    check("trajectory replay", normalized_digest(root/trajectory),
          normalized_digest(generated/trajectory), trajectory.as_posix())
    private_keys = {"seed", "truth", "provenance", "issue_id", "evidence_sets", "expected_amount_minor"}
    def private_fields(value):
        if isinstance(value, dict):
            yield from private_keys.intersection(value)
            for item in value.values():
                yield from private_fields(item)
        elif isinstance(value, list):
            for item in value:
                yield from private_fields(item)
    seen = set()
    with (root/trajectory).open(encoding="utf-8") as stream:
        for line in stream:
            seen.update(private_fields(json.loads(line)["observation"]))
    check("public trajectory fields", sorted(seen), [], trajectory.as_posix())
    required = ("README.md", "LICENSE", "requirements.txt", "pyproject.toml", "Dockerfile",
                "Dockerfile.policy", "docs/findings.schema.json", "auditforge/agent_runner.py",
                "auditforge/policy_agent.py", "auditforge/policies.py", "auditforge/matcher.py")
    check("submission inventory", [file for file in required if not (root/file).is_file()], [],
          "README.md")
    return checks
