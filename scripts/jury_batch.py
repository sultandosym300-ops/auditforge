"""Independent exact-size financial fixtures for the jury, including batch payments."""
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import random

from auditforge.generator import generate


def batch_company(seed, n, cutoff_error):
    """n invoices and n batch payments; each invoice is settled in nine instalments."""
    rng = random.Random(seed)
    # Reuse published schema, synthetic IDs and period metadata, replace every
    # financial transaction independently of the production mutation routines.
    public = generate(seed, {'clean': True, 'invoices': max(40, n)})['public']
    manifest = public['manifest']
    start = datetime.fromisoformat(manifest['period_start'])
    end = datetime.fromisoformat(manifest['period_end'])
    manifest['episode_id'] = 'batch-' + hashlib.sha256(str((seed, n, cutoff_error)).encode()).hexdigest()[:16]
    public['invoices'] = public['invoices'][:n]
    public['payments'] = public['payments'][:n]
    public['ledger'] = []
    portions = defaultdict(list)
    entity = public['invoices'][0]['entity_id']

    def entry(invoice, when, account, debit, credit, payment=None, allocation=None):
        row = dict(row_id=f'row-{rng.getrandbits(96):024x}', timestamp=when,
                   account=account, debit_minor=debit, credit_minor=credit,
                   currency='KZT', entity_id=entity, invoice_id=invoice['invoice_id'],
                   payment_id=None if payment is None else payment['payment_id'])
        if payment is not None:
            row.update(allocation_source_minor=allocation, fx_rate='1', fx_date=when[:10])
        public['ledger'].append(row)
        return row

    for p, payment in enumerate(public['payments']):
        refs = []
        when = (start + timedelta(days=10+rng.randrange(15))).isoformat()
        for offset in range(9):
            i = (p + offset) % n
            invoice = public['invoices'][i]
            amount = rng.randrange(23, 67591)
            portions[i].append(amount)
            refs.append(dict(invoice_id=invoice['invoice_id'], allocated_minor=amount,
                             currency='KZT'))
            entry(invoice, when, 'payable', amount, 0, payment, amount)
            entry(invoice, when, 'cash', 0, amount, payment, amount)
        payment.update(currency='KZT', amount_minor=sum(r['allocated_minor'] for r in refs),
                       invoice_refs=refs, kind='settlement', timestamp=when)

    recognition = []
    for i, invoice in enumerate(public['invoices']):
        total = sum(portions[i])
        when = start + timedelta(hours=rng.randrange(120))
        invoice.update(entity_id=entity, total_minor=total, issued_at=when.isoformat(),
                       due_at=(when+timedelta(days=30)).isoformat())
        invoice.pop('related_credit_doc_id', None)
        invoice['line_items'][0].update(quantity=1, unit_minor=total, amount_minor=total)
        recognition.append((entry(invoice, when.isoformat(), 'expense', total, 0),
                            entry(invoice, when.isoformat(), 'payable', 0, total)))
    manifest.update(records=len(public['ledger']), documents=2*n)
    rng.shuffle(public['ledger'])
    pristine = deepcopy(public)
    truth, provenance = [], []
    if cutoff_error:
        i = rng.randrange(n)
        debit, credit = recognition[i]
        before = deepcopy([debit, credit])
        debit['timestamp'] = credit['timestamp'] = end.isoformat()
        issue_id = 'issue-cutoff'
        truth.append(dict(issue_id=issue_id, type='accounting_period',
                          affected_ids=[debit['row_id']], expected_amount_minor=debit['debit_minor'],
                          currency='KZT', tolerance_minor=0,
                          evidence_sets=[[debit['row_id'], public['invoices'][i]['doc_id']]]))
        provenance.append(dict(issue_id=issue_id, operation='accounting_period',
                               before=before, after=deepcopy([debit, credit])))
    return dict(public=public, pristine=pristine, provenance=provenance, truth=truth)

