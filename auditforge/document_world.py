"""Versioned individual-source investigation with bounded, causal financial books.

Every source query returns one source: an invoice, payment, exchange quote, or
one balanced journal entry. Contracts, bank confirmations, allocations and
acceptance certificates corroborate the graph without providing hidden labels.
The procurement and service families create independent economic events; shared
serialization enforces the same public bookkeeping and official reward contract.
"""
import copy
import hashlib
import json
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_EVEN

FAMILIES = ('procurement', 'service_milestone')
VERSION = 'investigation_v2'


def identity(*parts):
    return hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()[:24]


def procurement_events(seed, count):
    rng = random.Random(identity(seed, 'purchase-orders-v2'))
    events = []
    for case in range(count):
        quantity = rng.randint(4, 31)
        unit = rng.randint(80, 650) * 100
        first = quantity * unit
        second = rng.randint(2, 11) * rng.randint(100, 900) * 100
        advance = rng.randint(700, 2300)
        events.append(dict(case=case, obligations=[first, second],
                           issued_days=[rng.choice((2, 9, 20, 30)), rng.choice((0, 27, 30, 31))],
                           payments=[dict(currency='USD', amounts=[advance, advance // 2], day=29),
                                     dict(currency='KZT', amounts=[first // 4, second // 8 if rng.randrange(2) else 0], day=30),
                                     dict(currency='USD', amounts=[0, -(advance // 5)], day=29)],
                           source_model='purchase_order_partial_delivery',
                           contract=dict(quantity=quantity, unit_price_minor=unit,
                                         obligation_totals_minor=[first, second],
                                         delivery_lots=2, acceptance_required=True)))
    return events


def generate_document_world(seed, config):
    if set(config) - {'profile', 'cases', 'clean', 'family'}:
        raise ValueError('Unsupported document-world configuration')
    count, clean, family = config.get('cases', 4), config.get('clean', False), config.get('family', 'procurement')
    if type(count) is not int or not 2 <= count <= 4 or type(clean) is not bool or family not in FAMILIES:
        raise ValueError('Invalid document-world configuration')
    if family == 'service_milestone':
        from .independent_world import service_events
        events = service_events(seed, count)
    else:
        events = procurement_events(seed, count)
    names = random.Random(identity(seed, VERSION, family, 'ids'))
    labels = random.Random(identity(seed, VERSION, family, 'causes'))
    start = datetime(2026, 10, 1, tzinfo=timezone(timedelta(hours=5)))
    end = datetime(2026, 11, 1, tzinfo=start.tzinfo)
    def ident(prefix):
        return prefix + '-' + identity(seed, family, names.getrandbits(128))
    manifest = dict(schema_version='1.0', generator_version='2.0.1', config_version='2.2',
                    profile=VERSION, family=family, episode_id='ep-'+identity(seed, config),
                    company=('Steppe Supply ' if family == 'procurement' else 'Orda Services ')+str(names.randrange(100, 999)),
                    base_currency='KZT', period_start=start.isoformat(), period_end=end.isoformat(),
                    timezone='+05:00', currency_exponents={'KZT':2, 'USD':2, 'EUR':2, 'JPY':0},
                    rounding='ROUND_HALF_EVEN', records=0, documents=0)
    policy = dict(fx_date='payment local date in manifest timezone', period='[period_start, period_end)',
                  invoice_recognition='issued_at', rounding='ROUND_HALF_EVEN', amount_tolerance_minor=0,
                  allocation='invoice_refs amounts in payment currency; refunds signed')
    public = dict(manifest=manifest, policy=policy, ledger=[], invoices=[], payments=[], fx=[])
    case_rows, contracts, journal_pairs, row_cases = [], [], [], {}
    def convert(amount, rate):
        return int((Decimal(amount)*Decimal(rate)).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))
    def journal(case_id, invoice, stamp, amount, payment=None, **extra):
        rows = []
        for account, debit in (('payable', True), ('cash', False)) if payment else (('expense', True), ('payable', False)):
            row = dict(row_id=ident('row'), timestamp=stamp, account=account,
                       debit_minor=amount if debit else 0, credit_minor=0 if debit else amount,
                       currency='KZT', entity_id=invoice['entity_id'], invoice_id=invoice['invoice_id'],
                       payment_id=payment, **extra)
            rows.append(row); row_cases[row['row_id']] = case_id
        public['ledger'].extend(rows); journal_pairs.append((case_id, rows))
        return rows
    if family == 'service_milestone':
        from .independent_world import service_books
        case_rows, contracts, journal_pairs, row_cases = service_books(events, public, ident)
    for event in events if family == 'procurement' else []:
        case_id, entity = ident('case'), ident('entity')
        contract_id = ident('contract')
        contracts.append(dict(doc_id=contract_id, case_id=case_id, kind='contract',
                              terms=event['contract'], economic_model=event['source_model']))
        invoices, payments, entries = [], [], []
        for n, amount in enumerate(event['obligations']):
            stamp = (start+timedelta(days=event['issued_days'][n])).isoformat()
            invoice = dict(doc_id=ident('invoice-doc'), invoice_id=ident('invoice'), entity_id=entity,
                           issued_at=stamp, due_at=(datetime.fromisoformat(stamp)+timedelta(days=30)).isoformat(),
                           currency='KZT', total_minor=amount,
                           line_items=[dict(quantity=1, unit_minor=amount, amount_minor=amount)],
                           contract_doc_id=contract_id)
            public['invoices'].append(invoice); invoices.append(invoice)
            entries.append(journal(case_id, invoice, stamp, amount))
        for event_pay in event['payments']:
            stamp = (start+timedelta(days=event_pay['day'], hours=11)).isoformat()
            currency = event_pay['currency']; date = stamp[:10]
            if currency != 'KZT':
                fx = next((f for f in public['fx'] if f['date']==date and f['source_currency']==currency), None)
                if fx is None:
                    quote_rng=random.Random(identity(seed, family, 'declared-quotes', date, currency))
                    rate=str(Decimal(quote_rng.randrange(4600000, 5900000))/10000)
                    fx=dict(row_id=ident('fx'), date=date, source_currency=currency, target_currency='KZT', rate=rate)
                    public['fx'].append(fx)
                rate=fx['rate']
            else:
                rate='1'
            refs=[dict(invoice_id=invoices[i]['invoice_id'], allocated_minor=value, currency=currency)
                  for i,value in enumerate(event_pay['amounts']) if value]
            pay=dict(doc_id=ident('payment-doc'), payment_id=ident('payment'), timestamp=stamp, currency=currency,
                     amount_minor=sum(event_pay['amounts']), invoice_refs=refs,
                     kind='refund' if sum(event_pay['amounts'])<0 else 'settlement')
            public['payments'].append(pay); payments.append(pay)
            for i,value in enumerate(event_pay['amounts']):
                if value:
                    entries.append(journal(case_id, invoices[i], stamp, convert(value,rate), pay['payment_id'],
                                           allocation_source_minor=value, fx_rate=rate, fx_date=date))
                    if value<0: invoices[i]['related_credit_doc_id']=pay['doc_id']
        case_rows.append(dict(case_id=case_id, invoices=invoices, payments=payments, entries=entries))
    pristine=copy.deepcopy(public); truth, provenance=[],[]
    def record(kind, affected, before, after, amount, evidence):
        issue_id=ident('issue')
        truth.append(dict(issue_id=issue_id,type=kind,affected_ids=sorted(r['row_id'] for r in affected),
                          expected_amount_minor=abs(amount),currency='KZT',evidence_sets=[sorted(evidence)],tolerance_minor=0))
        provenance.append(dict(issue_id=issue_id,operation=kind,before=before,after=copy.deepcopy(after)))
    # Declared distribution for generator-aware competitors, never specific labels:
    # each mechanism fires independently with P=.65 (procurement), .50 (services).
    # Targets are uniform among cases. Allocation swaps preserve aggregate totals.
    probability=.65 if family=='procurement' else .50
    if family == 'service_milestone' and not clean:
        from .independent_world import inject_service_faults
        truth,provenance=inject_service_faults(public,case_rows,seed,ident,journal_pairs,row_cases)
    for kind in ('duplicate_invoice','payment_allocation','fx_conversion','accounting_period') if family == 'procurement' else []:
        if clean or labels.random()>=probability: continue
        case=labels.choice(case_rows); invoices=case['invoices']
        if kind=='duplicate_invoice':
            pair=case['entries'][0]; before=copy.deepcopy(pair); clones=copy.deepcopy(pair)
            for row in clones:
                row['row_id']=ident('row');row_cases[row['row_id']]=case['case_id']
            public['ledger'].extend(clones);journal_pairs.append((case['case_id'],clones))
            record(kind,[pair[0],clones[0]],before,pair+clones,invoices[0]['total_minor'],
                   [invoices[0]['doc_id'],pair[0]['row_id'],clones[0]['row_id']])
        elif kind=='payment_allocation':
            pay=case['payments'][0]
            selected=[pair for pair in case['entries'] if pair[0]['payment_id']==pay['payment_id']]
            delta=max(1,min(abs(pair[0]['allocation_source_minor']) for pair in selected)//4)
            for sign,pair in zip((1,-1),selected):
                before=copy.deepcopy(pair);value=pair[0]['allocation_source_minor']+sign*delta
                for row in pair:
                    row['allocation_source_minor']=value
                    row['debit_minor' if row['account']=='payable' else 'credit_minor']=convert(value,row['fx_rate'])
                fx=next(f for f in public['fx'] if f['date']==pair[0]['fx_date'] and f['source_currency']==pay['currency'])
                record(kind,[pair[0]],before,pair,abs(before[0]['debit_minor']-pair[0]['debit_minor']),
                       [pay['doc_id'],pair[0]['row_id'],fx['row_id']])
        elif kind=='fx_conversion':
            pay=case['payments'][-1]  # Refund conversion; separate from allocation mutations.
            pair=next(p for p in case['entries'] if p[0]['payment_id']==pay['payment_id'])
            before=copy.deepcopy(pair);wrong=str(Decimal(pair[0]['fx_rate'])+Decimal('7.25'))
            for row in pair:
                row['fx_rate']=wrong
                row['debit_minor' if row['account']=='payable' else 'credit_minor']=convert(row['allocation_source_minor'],wrong)
            fx=next(f for f in public['fx'] if f['date']==pair[0]['fx_date'] and f['source_currency']==pay['currency'])
            record(kind,[pair[0]],before,pair,before[0]['debit_minor']-pair[0]['debit_minor'],
                   [pay['doc_id'],pair[0]['row_id'],fx['row_id']])
        else:
            pair=case['entries'][1];before=copy.deepcopy(pair)
            stamp=(end+timedelta(days=1) if start<=datetime.fromisoformat(invoices[1]['issued_at'])<end else start+timedelta(days=15)).isoformat()
            for row in pair:row['timestamp']=stamp
            record(kind,[pair[0]],before,pair,invoices[1]['total_minor'],[invoices[1]['doc_id'],pair[0]['row_id']])
    documents=[]
    def document(doc_id,case_id,kind,records=None,**metadata):
        row=dict(doc_id=doc_id,case_id=case_id,kind=kind,records=records or {},references=[],**metadata)
        documents.append(row);return row
    invoice_docs={}; payment_docs={}; journal_docs={}; quote_docs={}
    for case in case_rows:
        cid=case['case_id']
        for inv in case['invoices']:
            invoice_docs[inv['invoice_id']]=document(inv['doc_id'],cid,'invoice',dict(invoices=[copy.deepcopy(inv)]))
        for pay in case['payments']:
            payment_docs[pay['payment_id']]=document(pay['doc_id'],cid,'refund' if pay['kind']=='refund' else 'payment',dict(payments=[copy.deepcopy(pay)]))
    for cid,pair in journal_pairs:
        doc=document(ident('journal-doc'),cid,'journal_entry',dict(ledger=copy.deepcopy(pair)))
        for row in pair:journal_docs[row['row_id']]=doc
    for quote in public['fx']:
        quote_docs[quote['row_id']]=document(quote['row_id'],'shared','exchange_quote',dict(fx=[copy.deepcopy(quote)]))
    for contract in contracts:
        document(**contract)
    for case in case_rows:
        cid=case['case_id']
        for inv in case['invoices']:
            document(ident('acceptance'),cid,'fulfillment_confirmation',invoice_id=inv['invoice_id'],accepted_at=inv['issued_at'],accepted_amount_minor=inv['total_minor'])
        for pay in case['payments']:
            document(ident('bank'),cid,'bank_confirmation',payment_id=pay['payment_id'],settled_at=pay['timestamp'],currency=pay['currency'],amount_minor=pay['amount_minor'])
            if len(pay['invoice_refs'])>1:
                document(ident('allocation'),cid,'allocation_document',payment_id=pay['payment_id'],invoice_refs=copy.deepcopy(pay['invoice_refs']))
    # References are source provenance, not error labels; each group lists all its
    # ordinary evidence so an investigator can identify incomplete recognition.
    for doc in documents:
        related=set()
        for inv in doc['records'].get('invoices',[]):
            related.add(inv['contract_doc_id'])
            related.update(journal_docs[r['row_id']]['doc_id'] for r in public['ledger'] if r['invoice_id']==inv['invoice_id'])
            related.update(p['doc_id'] for p in public['payments'] if any(x['invoice_id']==inv['invoice_id'] for x in p['invoice_refs']))
        for row in doc['records'].get('ledger',[]):
            related.add(invoice_docs[row['invoice_id']]['doc_id'])
            if row['payment_id']:
                pay=payment_docs[row['payment_id']]['records']['payments'][0];related.add(pay['doc_id'])
                related.update(q['row_id'] for q in public['fx'] if q['date']==row['fx_date'] and q['source_currency']==pay['currency'])
        for pay in doc['records'].get('payments',[]):
            related.update(invoice_docs[r['invoice_id']]['doc_id'] for r in pay['invoice_refs'])
            related.update(journal_docs[r['row_id']]['doc_id'] for r in public['ledger'] if r['payment_id']==pay['payment_id'])
            related.update(q['row_id'] for q in public['fx'] if q['date']==pay['timestamp'][:10] and q['source_currency']==pay['currency'])
        if not doc['records']:
            related.update(d['doc_id'] for d in documents if d['case_id']==doc['case_id'] and d['records'])
        doc['references']=[dict(document_id=d['doc_id'],kind=d['kind'],case_id=d['case_id']) for d in documents if d['doc_id'] in related and d is not doc]
    names.shuffle(documents)
    manifest['document_index']=[dict(document_id=d['doc_id'],kind=d['kind'],case_id=d['case_id'],query_cost=1) for d in documents]
    manifest['records']=len(public['ledger']);manifest['documents']=len(public['invoices'])+len(public['payments'])
    pristine['manifest']['records']=len(pristine['ledger']);pristine['manifest']['documents']=manifest['documents']
    public['business']=dict(version=VERSION,source_documents=documents)
    return dict(public=public,pristine=pristine,truth=truth,provenance=provenance)
