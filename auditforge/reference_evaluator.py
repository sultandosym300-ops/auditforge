"""Independent exponential reference judge for small trusted audit fixtures.

No production matcher or validation helper is used. All reachable assignments
are enumerated as sets of occupied truth indices, rather than using an augmenting
path matcher. At most sixteen truths are accepted: this is an audit tool, not a
replacement for the production evaluator or a policy-accessible endpoint.
"""
from fractions import Fraction


KINDS = frozenset(('duplicate_invoice', 'payment_allocation',
                   'fx_conversion', 'accounting_period'))


def _valid_submission(payload, episode_id):
    if not isinstance(payload, dict):
        return False
    if payload.get('episode_id') != episode_id:
        return False
    rows = payload.get('findings')
    if not isinstance(rows, list) or len(rows) > 30:
        return False
    for row in rows:
        if not isinstance(row, dict):
            return False
        # JSON values can include lists/dicts; do not hash unvalidated types.
        if not isinstance(row.get('type'), str) or row['type'] not in KINDS:
            return False
        amount = row.get('claimed_amount_minor')
        if type(amount) is not int or amount < 0:
            return False
        if not isinstance(row.get('currency'), str):
            return False
        prose = row.get('explanation')
        if not isinstance(prose, str) or len(prose) > 1000:
            return False
        for field, bound in (('affected_ids', 2000), ('evidence_ids', 10)):
            identifiers = row.get(field)
            if not isinstance(identifiers, list) or len(identifiers) > bound:
                return False
            if any(not isinstance(item, str) or len(item) > 128 for item in identifiers):
                return False
            if len(set(identifiers)) != len(identifiers):
                return False
    return True


def evaluate_reference(episode_id, truth, payload, inspection_steps):
    """Enumerate every admissible small-task assignment with official reward.

    Duplicate claims differing only in prose, ID ordering, or irrelevant evidence
    retain a single matching opportunity. Every submitted row still counts in
    the precision denominator. Extra irrelevant documents do not invalidate an
    otherwise complete proof, matching the declared production contract.
    """
    if len(truth) > 16:
        raise ValueError('Reference enumeration is limited to sixteen truths')
    if not _valid_submission(payload, episode_id):
        return dict(tp=0, fp=0, fn=len(truth), precision=0, recall=0,
                    f1=0, reward=-1, error='invalid_submission')
    assignments = {0}
    identities = set()
    submitted = payload['findings']
    for row in submitted:
        proofs = set()
        compatible = []
        for index, target in enumerate(truth):
            same_claim = (row['type'] == target['type']
                          and row['currency'] == target['currency']
                          and set(row['affected_ids']) == set(target['affected_ids'])
                          and abs(row['claimed_amount_minor']-target['expected_amount_minor'])
                          <= target.get('tolerance_minor', 0))
            if not same_claim:
                continue
            accepted = [tuple(sorted(proof)) for proof in target['evidence_sets']
                        if all(identifier in row['evidence_ids'] for identifier in proof)]
            if accepted:
                compatible.append(index)
                proofs.update(accepted)
        identity = (row['type'], tuple(sorted(row['affected_ids'])), row['currency'],
                    row['claimed_amount_minor'], tuple(sorted(proofs)))
        if identity in identities:
            continue
        identities.add(identity)
        # Keeping each prior state explicitly includes the unmatched alternative.
        next_assignments = set(assignments)
        for occupied in assignments:
            for index in compatible:
                bit = 1 << index
                if occupied & bit == 0:
                    next_assignments.add(occupied | bit)
        assignments = next_assignments
    tp = max(state.bit_count() for state in assignments)
    fp, fn = len(submitted)-tp, len(truth)-tp
    precision = float(Fraction(tp, tp+fp)) if tp+fp else 0
    recall = float(Fraction(tp, tp+fn)) if tp+fn else 0
    f1 = Fraction(2*tp, 2*tp+fp+fn) if 2*tp+fp+fn else Fraction(1)
    reward = max(Fraction(-1), min(Fraction(1), 2*f1-1-Fraction(inspection_steps, 500)))
    return dict(tp=tp, fp=fp, fn=fn, precision=precision, recall=recall,
                f1=float(f1), reward=float(reward))
