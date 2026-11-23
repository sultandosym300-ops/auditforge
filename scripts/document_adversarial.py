"""Evaluator-side document, causal, protocol and independent judge audit for 2.2.

Uses the existing exact-rational financial auditor, not the policy decoder, to
recover findings. It neither fits models nor selects experimental companies.
"""
import argparse
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import random
import time

from auditforge.env import Session
from auditforge.financial_audit import audit_episode, _inspect_books
from auditforge.generator import generate
from auditforge.matcher import evaluate
from auditforge.reference_evaluator import evaluate_reference
from auditforge.training import episode_seed
from auditforge.verify import transform

ROOT = Path(__file__).resolve().parents[1]
TABLES = ('ledger', 'invoices', 'payments', 'fx')
PRIVATE = {'truth', 'provenance', 'pristine', 'expected_amount_minor',
           'evidence_sets', 'seed', 'oracle_hint', 'issue_id'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def walk(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key, item
            yield from walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk(item)


def check_documents(episode):
    """Check actual public source contents against independent monetary audit.

    The book auditor checks rational FX/rounding, mirrored entries, pristine
    causality, amount reconstruction, evidence sufficiency and all four types.
    This extension additionally checks that those records can actually be read
    one source at a time, rather than trusting a hidden, unexposed public table.
    """
    result = audit_episode(episode)
    errors = list(result['errors'])
    try:
        public = episode['public']
        documents = public['business']['source_documents']
        index = public['manifest']['document_index']
        indexed = {item['document_id']: item for item in index}
        by_id = {item['doc_id']: item for item in documents}
        if len(indexed) != len(index) or len(by_id) != len(documents) or set(indexed) != set(by_id):
            errors.append('Document index does not uniquely cover source documents')
        if len(documents) + 1 > 100:
            errors.append('Full documentary acquisition exceeds official action budget')
        covered = {table: [] for table in TABLES}
        for document in documents:
            if set(key for key, _ in walk(document)) & PRIVATE:
                errors.append('Private evaluator fields in public document')
            records = document.get('records', {})
            if not isinstance(records, dict) or set(records) - set(TABLES):
                errors.append('Invalid source record table')
                continue
            nonempty = [table for table, rows in records.items() if rows]
            if len(nonempty) > 1:
                errors.append('A document releases a bundle of financial tables')
            for table, rows in records.items():
                if not isinstance(rows, list) or not 0 <= len(rows) <= (2 if table == 'ledger' else 1):
                    errors.append('A source releases more than one document/journal entry')
                    continue
                covered[table].extend(rows)
            for reference in document.get('references', []):
                if reference.get('document_id') not in indexed:
                    errors.append('Source references a permanently unavailable document')
        for table in TABLES:
            # Compare multisets including every value, not just ID coverage.
            if sorted(map(digest, covered[table])) != sorted(map(digest, public[table])):
                errors.append('Exposed '+table+' documents differ from audited financial books')
        if set(key for key, _ in walk(public['manifest'])) & PRIVATE:
            errors.append('Initial manifest contains evaluator-only information')
    except (KeyError, TypeError, ValueError) as error:
        errors.append('Malformed public document structure: '+str(error)[:160])
    return dict(valid=not errors, errors=errors, financial_audit=result,
                documents=len(episode.get('public', {}).get('business', {}).get('source_documents', [])))


def _fixture(episode):
    session = Session()
    session.episode = copy.deepcopy(episode)
    session.public = session.episode['public']
    session.mode = 'evaluation'
    session.steps, session.done = 0, False
    session.done_flags, session.report = (False, False), None
    session.started, session.seconds, session.final = time.monotonic(), 60, []
    return session, dict(manifest=copy.deepcopy(session.public['manifest']),
                         policy=copy.deepcopy(session.public['policy']), steps_remaining=100)


def _claims(issues):
    return [dict(type=item['type'], affected_ids=item['affected_ids'],
                 claimed_amount_minor=item['expected_amount_minor'], currency=item['currency'],
                 evidence_ids=item.get('evidence_ids', item.get('evidence_sets', [[]])[0]),
                 explanation='Independent exact-rational documentary reconstruction.') for item in issues]


def matcher_attacks(episode, foreign):
    """Differential test independent enumerated judge on real financial claims."""
    eid, truth = episode['public']['manifest']['episode_id'], episode['truth']
    payload = dict(episode_id=eid, findings=_claims(truth))
    variants = {'correct': copy.deepcopy(payload), 'empty': dict(episode_id=eid, findings=[]),
                'wrong_episode': dict(payload, episode_id=foreign['public']['manifest']['episode_id'])}
    if payload['findings']:
        changes = {'wrong_amount': ('claimed_amount_minor', payload['findings'][0]['claimed_amount_minor'] + 1),
                   'wrong_currency': ('currency', 'USD'), 'foreign_evidence': ('evidence_ids', ['foreign-document']),
                   'partial_evidence': ('evidence_ids', payload['findings'][0]['evidence_ids'][:-1]),
                   'forged_ids': ('affected_ids', ['unacquired-row']), 'boolean_money': ('claimed_amount_minor', True),
                   'nonstring_type': ('type', []), 'duplicate_evidence': ('evidence_ids', ['x', 'x'])}
        foreign_claims = _claims(foreign['truth'])
        if foreign_claims:
            changes['other_company_evidence'] = ('evidence_ids', foreign_claims[0]['evidence_ids'])
        for name, (field, replacement) in changes.items():
            changed = copy.deepcopy(payload)
            changed['findings'][0][field] = replacement
            variants[name] = changed
        repeated = copy.deepcopy(payload)
        repeated['findings'].append(copy.deepcopy(repeated['findings'][0]))
        variants['duplicate_claim'] = repeated
    else:
        # Clean companies still exercise the malformed-claim interface.
        finding = dict(type='fx_conversion', affected_ids=['forged-row'], claimed_amount_minor=1,
                       currency='KZT', evidence_ids=['foreign-document'], explanation='False accusation')
        for index, value in enumerate((None, True, [], {}, -1, 1.1, '1')):
            variants['invalid_'+str(index)] = dict(episode_id=eid, findings=[dict(finding, claimed_amount_minor=value)])
    rows, agreement, no_inflation = [], True, True
    for name, candidate in variants.items():
        actual = evaluate(eid, truth, candidate, 17)
        reference = evaluate_reference(eid, truth, candidate, 17)
        same = set(actual) == set(reference) and all(
            abs(actual[key]-value) < 1e-12 if isinstance(value, float) else actual[key] == value
            for key, value in reference.items())
        agreement &= same
        no_inflation &= actual['tp'] <= len(truth)
        if name not in ('correct', 'duplicate_claim', 'empty'):
            no_inflation &= actual['tp'] <= max(0, len(truth)-1)
        if name == 'duplicate_claim':
            no_inflation &= actual['tp'] == len(truth) and actual['fp'] == 1
        rows.append(dict(attack=name, same_as_independent_reference=same, **actual))
    return dict(differential_match=agreement, attacks_do_not_inflate=no_inflation, variants=rows)


def _full_acquisition(episode):
    """A reference reader receives only initial and tool-returned observations."""
    session, initial = _fixture(episode)
    public = dict(manifest=initial['manifest'], policy=initial['policy'], **{table: [] for table in TABLES})
    calls, observations = [], [copy.deepcopy(initial)]
    exposed = set()
    checks = dict(no_private_fields=True, single_source_actions=True, evaluation_reward_hidden=True,
                  acquired_evidence_only=True, budget_respected=True)
    for item in initial['manifest']['document_index']:
        action = dict(tool='get_document', doc_id=item['document_id'])
        response = session.step(action)
        calls.append(dict(action=copy.deepcopy(action), response=copy.deepcopy(response)))
        observations.append(response[0])
        if 'error' in response[0]:
            raise AssertionError('Indexed document unavailable')
        record = response[0]['result']
        for table, rows in record.get('records', {}).items():
            public[table].extend(rows)
            exposed.update(row.get('row_id', row.get('doc_id')) for row in rows)
        checks['single_source_actions'] &= sum(bool(rows) for rows in record.get('records', {}).values()) <= 1
        checks['evaluation_reward_hidden'] &= response[1] == 0 and response[4] == {}
    recovered, _ = _inspect_books(public)
    claims = _claims(recovered)
    checks['acquired_evidence_only'] &= all(set(f['evidence_ids']+f['affected_ids']) <= exposed for f in claims)
    action = dict(tool='submit', findings=dict(episode_id=initial['manifest']['episode_id'], findings=claims))
    response = session.step(action)
    calls.append(dict(action=action, response=copy.deepcopy(response)))
    observations.append(response[0])
    checks['no_private_fields'] &= not bool(set(key for key, _ in walk(observations)) & PRIVATE)
    checks['evaluation_reward_hidden'] &= response[1] == 0 and response[4] == {}
    checks['budget_respected'] &= session.steps <= 100 and response[2] and not response[3]
    replay, _ = _fixture(episode)
    checks['replay_exact'] = all(replay.step(item['action']) == tuple(item['response']) for item in calls)
    checks['replay_exact'] &= replay.report == session.report
    return dict(steps=session.steps, **session.report), checks


def _tool_attacks(episode):
    session, _ = _fixture(episode)
    valid = True
    for action in (None, [], True, 'get_document', {}, dict(tool='private_truth'),
                   dict(tool='get_document', doc_id=[]), dict(tool='get_document', doc_id='../truth.json'),
                   dict(tool='list_records', table='truth'), dict(tool='calculator', expression='__import__("os")')):
        response = session.step(action)
        valid &= response[0].get('error') == 'invalid_request' and response[1] == 0 and response[4] == {}
    # A bulk table endpoint cannot undermine one-source acquisition in v2.
    for table in TABLES:
        response = session.step(dict(tool='list_records', table=table, limit=50))
        rows = response[0].get('result', {}).get('records', [])
        valid &= len(rows) <= 1
    session, _ = _fixture(episode)
    for _ in range(100):
        last = session.step(dict(tool='calculator', expression='1+1'))
    valid &= session.steps == 100 and last[3] and not last[2]
    session.step(dict(tool='calculator', expression='1+1'))
    valid &= session.steps == 100
    session, initial = _fixture(episode)
    session.step(dict(tool='submit', findings=dict(episode_id=initial['manifest']['episode_id'], findings=[])))
    valid &= session.report['tp'] == 0
    valid &= session.report['fn'] == len(episode['truth'])
    return bool(valid)


def closing_risk_diagnostic(seed=837917, count=4):
    """Report the v1 shift explicitly; observational features are not labels.

    closing_transfer draws a separate recognition mechanism, so its former
    procurement risk prior is not calibrated by construction. No promise of
    invariant risk/label association is inferred from valid financial books.
    """
    rows = []
    for family in ('procurement', 'closing_transfer'):
        for i in range(count):
            episode = generate(episode_seed(seed, 'v1-risk-diagnostic', i),
                               dict(profile='investigation_v1', family=family, cases=4))
            public = episode['public']
            packets = {d['case_id']: d['records'] for d in public['business']['source_documents'] if 'records' in d}
            for item in public['manifest']['investigations']:
                recovered, _ = _inspect_books(packets[item['case_id']])
                rows.append(dict(family=family, company=i,
                    public_feature_sum=sum(item[k] for k in ('manual_entries', 'cutoff_pressure', 'cross_border', 'supplier_change')),
                    documentary_issues=len(recovered), positive=bool(recovered)))
    groups = []
    for family in ('procurement', 'closing_transfer'):
        for feature_sum in range(5):
            selected = [r for r in rows if r['family'] == family and r['public_feature_sum'] == feature_sum]
            groups.append(dict(family=family, feature_sum=feature_sum, departments=len(selected),
                               positives=sum(r['positive'] for r in selected)))
    return dict(independent_companies=count*2, rows=rows, groups=groups,
        conclusion='closing_transfer changes recognition assignment independently of the procurement operational-risk mechanism; this is declared covariate/mechanism shift, not calibrated risk or a deterministic label contract. Old generation and checkpoints are preserved.')


def _period_pair(seed, family):
    """Controlled financial intervention, never selected for a model's success.

    One period mismatch is applied to a fixed first obligation in a clean
    company. World B exchanges the locations of its two same-case invoices.
    The initial catalog is byte-identical. The queried journal's reference
    points to a different actual invoice, so the correct next source changes.
    This tests reference-following, not currency expertise or general banking.
    """
    episode = generate(seed, dict(profile='investigation_v2', family=family, cases=2, clean=True))
    public = episode['public']
    invoice = public['invoices'][0]
    other = next(inv for inv in public['invoices'][1:] if inv['entity_id'] == invoice['entity_id'])
    pair = [r for r in public['ledger'] if r['invoice_id'] == invoice['invoice_id'] and r['payment_id'] is None]
    before = copy.deepcopy(pair)
    start, end = (datetime.fromisoformat(public['manifest'][key]) for key in ('period_start', 'period_end'))
    issued = datetime.fromisoformat(invoice['issued_at'])
    wrong = end+timedelta(days=1) if start <= issued < end else start+timedelta(days=14)
    for row in pair:
        row['timestamp'] = wrong.isoformat()
    expense = next(row for row in pair if row['account'] == 'expense')
    changed_rows = {row['row_id']: row for row in pair}
    first_source = None
    for source in public['business']['source_documents']:
        for row in source.get('records', {}).get('ledger', []):
            if row['row_id'] in changed_rows:
                row.update(copy.deepcopy(changed_rows[row['row_id']]))
                first_source = source['doc_id']
    issue = dict(issue_id='controlled-period-intervention', type='accounting_period',
                 affected_ids=[expense['row_id']], expected_amount_minor=invoice['total_minor'],
                 currency=invoice['currency'], evidence_sets=[[invoice['doc_id'], expense['row_id']]], tolerance_minor=0)
    episode['truth'] = [issue]
    episode['provenance'] = [dict(issue_id=issue['issue_id'], operation='accounting_period', before=before, after=copy.deepcopy(pair))]
    mapping = {invoice['doc_id']: other['doc_id'], other['doc_id']: invoice['doc_id']}
    def replace(value):
        if isinstance(value, dict):
            return {key: replace(item) for key, item in value.items()}
        if isinstance(value, list):
            return [replace(item) for item in value]
        return mapping.get(value, value) if isinstance(value, str) else value
    alternative = replace(episode)
    alternative['public']['manifest']['document_index'] = copy.deepcopy(public['manifest']['document_index'])
    return episode, alternative, first_source


def _period_claims(public):
    """Small reference reader for the specifically declared period intervention."""
    start, end = (datetime.fromisoformat(public['manifest'][key]) for key in ('period_start', 'period_end'))
    invoices = {item['invoice_id']: item for item in public['invoices']}
    claims = []
    for row in public['ledger']:
        invoice = invoices.get(row['invoice_id'])
        if invoice and row['account'] == 'expense' and row['payment_id'] is None:
            issued, booked = datetime.fromisoformat(invoice['issued_at']), datetime.fromisoformat(row['timestamp'])
            if (start <= issued < end) != (start <= booked < end):
                claims.append(dict(type='accounting_period', affected_ids=[row['row_id']],
                    claimed_amount_minor=invoice['total_minor'], currency=invoice['currency'],
                    evidence_ids=[invoice['doc_id'], row['row_id']], explanation='Period boundaries independently compared.'))
    return claims


def adaptive_pairs(model, seed=202622071, count=4):
    """Measure a frozen policy on predeclared, actual two-world source probes.

    No weights are edited. Each pair has the same initial observation, same
    first action and different returned references. We assess the next choice
    with one inspection and submit left (three official actions in total).
    Unselected documents and evaluator truth are used only by the trusted
    auditor to establish the optimal next actions, never as scorer inputs.
    """
    from auditforge.document_policy import Network, distribution, feature_vector
    if type(seed) is not int or type(count) is not int or not 1 <= count <= 100:
        raise ValueError('Invalid counterfactual panel')
    rows = []
    for family in ('procurement', 'service_milestone'):
        for index in range(count):
            company_seed = episode_seed(seed, 'reference-counterfactual-'+family, index)
            left, right, first = _period_pair(company_seed, family)
            initial_digest = None
            pair_rows = []
            for world, episode in (('A', left), ('B', right)):
                integrity = check_documents(episode)
                if not integrity['valid']:
                    raise AssertionError(integrity['errors'])
                session, initial = _fixture(episode)
                encoded = digest(initial)
                if initial_digest is None:
                    initial_digest = encoded
                if initial_digest != encoded:
                    raise AssertionError('Counterfactual initial observations differ')
                result = session.step(dict(tool='get_document', doc_id=first))
                document = result[0]['result']
                acquired = {first: document}
                public = dict(manifest=initial['manifest'], policy=initial['policy'], **{table: [] for table in TABLES})
                for table, records in document.get('records', {}).items():
                    public[table].extend(records)
                candidates = [item for item in initial['manifest']['document_index'] if item['document_id'] != first]
                xs = [feature_vector(item, acquired, public, 2, 3) for item in candidates]
                xs.append(feature_vector(None, acquired, public, 2, 3, stop=True))
                scored = {}
                for name, active in (('learned', model), ('untrained', Network(model.architecture, seed=model.seed))):
                    probabilities = distribution(active, xs)
                    chosen = max(range(len(xs)), key=lambda item: probabilities[item])
                    scored[name] = candidates[chosen]['document_id'] if chosen < len(candidates) else 'STOP'
                scored['fixed'] = candidates[0]['document_id']
                options = []
                for candidate in candidates+[dict(document_id='STOP')]:
                    projected = copy.deepcopy(public)
                    if candidate['document_id'] != 'STOP':
                        source = next(item for item in episode['public']['business']['source_documents'] if item['doc_id'] == candidate['document_id'])
                        for table, records in source.get('records', {}).items():
                            projected[table].extend(records)
                    payload = dict(episode_id=initial['manifest']['episode_id'], findings=_period_claims(projected))
                    report = evaluate_reference(payload['episode_id'], episode['truth'], payload,
                                                1 if candidate['document_id'] == 'STOP' else 2)
                    options.append(dict(document_id=candidate['document_id'], **report))
                maximum = max(option['reward'] for option in options)
                optimal = [option['document_id'] for option in options if option['reward'] == maximum]
                outcomes = {}
                for name, choice in scored.items():
                    outcome = next(option for option in options if option['document_id'] == choice)
                    outcomes[name] = dict(document_id=choice, optimal=choice in optimal,
                                          f1=outcome['f1'], reward=outcome['reward'])
                pair_rows.append(dict(world=world, initial_sha256=encoded,
                    first_action=dict(tool='get_document', doc_id=first), first_observation_sha256=digest(result[0]),
                    optimal_next_documents=optimal, outcomes=outcomes))
            rows.append(dict(family=family, index=index, seed=company_seed, worlds=pair_rows,
                changed_optimal_actions=not bool(set(pair_rows[0]['optimal_next_documents']) & set(pair_rows[1]['optimal_next_documents'])),
                learned_switched=pair_rows[0]['outcomes']['learned']['document_id'] != pair_rows[1]['outcomes']['learned']['document_id']))
    denominator = 2*len(rows)
    summary = {name: dict(optimal_fraction=sum(world['outcomes'][name]['optimal'] for pair in rows for world in pair['worlds'])/denominator,
                          reward=sum(world['outcomes'][name]['reward'] for pair in rows for world in pair['worlds'])/denominator,
                          f1=sum(world['outcomes'][name]['f1'] for pair in rows for world in pair['worlds'])/denominator)
               for name in ('learned', 'untrained', 'fixed')}
    return dict(format='auditforge-adaptive-source-pairs-v1', root_seed=seed,
                independent_base_companies=len(rows), counterfactual_worlds=denominator, rows=rows, summary=summary,
                switched_pairs=sum(row['learned_switched'] for row in rows),
                different_optimal_pairs=sum(row['changed_optimal_actions'] for row in rows),
                scope='Controlled reference-following decision after one common actual source query, three-action horizon; not an end-to-end training benchmark or a currency-generalization proof.')


def audit(seed=2026112322, count=4):
    if type(seed) is not int or type(count) is not int or not 1 <= count <= 100:
        raise ValueError('Audit requires an integer seed and 1..100 independent companies per stratum')
    checks = dict(independent_financial_audit=True, document_coverage=True, full_resolvability=True,
                  zero_false_positives=True, reference_judge_agrees=True, attacks_do_not_inflate=True,
                  no_private_fields=True, single_source_actions=True, evaluation_reward_hidden=True,
                  acquired_evidence_only=True, budget_respected=True, replay_exact=True,
                  malformed_tool_requests_rejected=True, fixtures_unchanged=True)
    fixtures, attacks = [], []
    metamorphic = dict(comparisons=0, full_budget_f1_changes=0, false_positives=0)
    for family in ('procurement', 'service_milestone'):
        for clean in (False, True):
            for index in range(count):
                company_seed = episode_seed(seed, family+'-document-audit-'+str(clean), index)
                config = dict(profile='investigation_v2', family=family, cases=2, clean=clean)
                episode = generate(company_seed, config)
                frozen = digest(episode)
                inspected = check_documents(episode)
                checks['independent_financial_audit'] &= inspected['financial_audit']['valid']
                checks['document_coverage'] &= inspected['valid']
                score, boundary = _full_acquisition(episode)
                checks['full_resolvability'] &= score['f1'] == 1
                checks['zero_false_positives'] &= score['fp'] == 0
                for key, value in boundary.items():
                    checks[key] &= value
                foreign = generate(company_seed ^ 49271, config)
                attack = matcher_attacks(episode, foreign)
                checks['reference_judge_agrees'] &= attack['differential_match']
                checks['attacks_do_not_inflate'] &= attack['attacks_do_not_inflate']
                attacks.append(dict(family=family, index=index, clean=clean, **attack))
                changed = transform(episode, company_seed ^ 8197)
                random.Random(company_seed).shuffle(changed['public']['manifest']['document_index'])
                altered, bounds = _full_acquisition(changed)
                metamorphic['comparisons'] += 1
                metamorphic['full_budget_f1_changes'] += altered['f1'] != score['f1']
                metamorphic['false_positives'] += altered['fp']
                for key, value in bounds.items():
                    checks[key] &= value
                checks['malformed_tool_requests_rejected'] &= _tool_attacks(episode)
                checks['fixtures_unchanged'] &= digest(episode) == frozen
                fixtures.append(dict(seed=company_seed, config=config, sha256=frozen,
                                     documents=inspected['documents'], audit_errors=inspected['errors'], **score))
    checks['full_resolvability'] &= metamorphic['full_budget_f1_changes'] == 0
    checks['zero_false_positives'] &= metamorphic['false_positives'] == 0
    return dict(format='auditforge-document-adversarial-v1', seed=seed, independent_companies=len(fixtures),
                checks=checks, fixtures=fixtures, matcher_attacks=attacks, metamorphic=metamorphic,
                old_closing_transfer_diagnostic=closing_risk_diagnostic(seed, min(count, 4)),
                scope='Trusted-host protocol and independent rational audit; actual OS isolation is a separate Docker gate. No model training or test-panel selection.',
                limitations=['Only bounded declared attacks are covered; absence of all shortcuts is not proven.',
                             'Full-source audit is not a claim that low-budget learned policies solve every company.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=2026112322)
    parser.add_argument('--count', type=int, default=4)
    parser.add_argument('--output', type=Path, default=ROOT/'work/document-adversarial.json')
    args = parser.parse_args()
    result = audit(args.seed, args.count)
    result['created_at_utc'] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps(dict(independent_companies=result['independent_companies'], checks=result['checks'], output=str(args.output)), ensure_ascii=True))
    if not all(result['checks'].values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
