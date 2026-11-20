"""Confirm public evidence delivery through a separately confined policy process."""
from auditforge.agent_runner import run
from auditforge.generator import TYPES


def main():
    for i in range(3):
        result = run(6087193912+i, config=dict(invoices=200, clean=i==0,
                     interaction=i, counts=dict.fromkeys(TYPES, 3), boundary_payments=True))
        seen = set()
        for row in result["trajectory"]:
            assert row["reward"] == 0
            if row["action"]["tool"] == "list_records":
                for item in row["observation"]["result"]["records"]:
                    seen.add(item.get("row_id") or item["doc_id"])
            if row["action"]["tool"] == "submit":
                for claim in row["action"]["findings"]["findings"]:
                    assert seen.issuperset(claim["affected_ids"] + claim["evidence_ids"])
        assert result["containment"] == "docker" and result["report"]["f1"] == 1
        assert len(result["trajectory"]) <= 100 and result["trajectory"][-1]["terminated"]
        print("Isolated policy", i, len(result["trajectory"]), result["report"])


if __name__ == "__main__":
    main()
