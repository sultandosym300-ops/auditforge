"""JSON input matrix and equivalent timestamp representations through the public proxy."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path

from auditforge.env import AuditEnv
from auditforge.generator import generate
from auditforge.financial_audit import audit_episode
from auditforge.verify import check_transitions, transform

ROOT = Path(__file__).resolve().parents[1]


def run():
    rows = []
    contract_checks = []
    private = {"truth", "provenance", "seed", "pristine", "evidence_sets", "issue_id", "expected_amount_minor"}
    def keys(value):
        if isinstance(value, dict):
            yield from value
            for item in value.values():
                yield from keys(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                yield from keys(item)
    actions = [None, [], True, 17, "submit", {},
               {"tool": ["submit"]}, {"tool":"list_records", "table":{}},
               {"tool":"list_records", "table":"ledger", "cursor":"-1"},
               {"tool":"list_records", "table":"ledger", "limit":True},
               {"tool":"list_records", "table":"ledger", "cursor":"9"*5000},
               {"tool":"get_record", "table":"payments", "id":[]},
               {"tool":"get_document", "doc_id":{}},
               {"tool":"calculator", "expression":"1/0"},
               {"tool":"calculator", "expression":"2**3"},
               {"tool":"calculator", "expression":"open('truth.json')"}]
    for mode in ("train", "evaluation"):
        with AuditEnv(mode) as env:
            initial, info = env.reset(927314143902, {"interaction":1})
            baseline = copy.deepcopy(initial)
            assert not private.intersection(keys([initial,info]))
            if mode == "evaluation":
                contract_checks.append(dict(name="reset public fields",passed=True))
            for index, action in enumerate(actions):
                observed = env.step(action)
                assert observed[0] == {"error":"invalid_request", "steps_remaining":99-index}, (action,observed)
                assert observed[1:] == (0,False,False,{})
                if mode == "evaluation":
                    contract_checks.append(dict(name="bounded JSON input "+str(index), action=action,passed=True))
            initial, info = env.reset(927314143902, {"interaction":1})
            assert initial == baseline
            if mode == "evaluation":
                contract_checks.append(dict(name="exact reset following invalid requests",passed=True))
            terminal = env.step({"tool":"submit", "findings":None})
            assert terminal[1:] == ((-1 if mode == "train" else 0),True,False,{})
            if mode == "evaluation":
                contract_checks.append(dict(name="invalid submit terminates with hidden reward",passed=True))
            report = env.evaluator_report()
            for action in actions + [{"tool":"submit","findings":None}]:
                after = env.step(action)
                assert after[1:] == (0,True,False,{})
                assert env.evaluator_report() == report
            if mode == "evaluation":
                contract_checks.append(dict(name="terminal report frozen under further actions",passed=True))
            rows.append(dict(mode=mode, malformed_actions=len(actions), frozen_terminal=True,
                             exact_reset_after_invalid=True, passed=True))
    for i in range(12):
        seed = 730191726103+i
        config = ({"recognition_world":i%4} if i%3 == 0 else
                  {"interaction":i%3,"boundary_payments":True,"timezone":("-00:30","+14:00")[i%2]})
        episode = generate(seed,config)
        equivalent = transform(episode,seed+1)
        def convert(value):
            if isinstance(value,dict):
                for key,item in value.items():
                    if key in ("timestamp","issued_at","due_at") and isinstance(item,str):
                        value[key] = datetime.fromisoformat(item).astimezone(timezone.utc).isoformat()
                    else:
                        convert(item)
            elif isinstance(value,list):
                for item in value:
                    convert(item)
        convert(equivalent)
        financial = audit_episode(equivalent)
        assert financial["valid"], financial
        check_transitions(episode,equivalent)
        rows.append(dict(seed=seed,config=config,utc_equivalent_dates=True,passed=True))
    assert len(contract_checks) == 20
    return dict(passed=True, contract_checks=contract_checks, checks=rows, scope="Public proxy JSON inputs, frozen terminal state and same instants with UTC offsets")


if __name__ == "__main__":
    result=run()
    (ROOT/"reports/ultimate-contract.json").write_text(json.dumps(result,indent=2),encoding="utf8")
    print(json.dumps(result))
