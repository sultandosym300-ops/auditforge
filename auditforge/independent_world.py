"""Independent service-event generator: milestones, retainers and credit refunds.

This module does not import the procurement generator, its sampling streams,
invoices, postings or causal operations. A common journal serializer is applied
only after this independent economic event history has been constructed.
"""
import hashlib
import random
import copy
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_EVEN


def service_events(seed, count):
    rng = random.Random(hashlib.sha256(('service-events-v1:' + str(seed)).encode()).digest())
    events = []
    for case in range(count):
        # Two contract milestones have correlated fees and a retainer split.
        hours = rng.randint(17, 94)
        hourly_fee = rng.choice((3400, 5900, 8700, 12400))
        first = hours * hourly_fee + rng.randint(0, 9900)
        second = first * rng.choice((2, 3, 5)) // 4 + rng.randint(1000, 9000)
        retainer = rng.randint(37, 83) * 100
        refund = -(retainer // rng.randint(4, 9))
        events.append(dict(case=case, obligations=[first, second],
                           issued_days=[rng.choice((0, 1, 29, 30)), rng.choice((1, 28, 30, 31))],
                           payments=[dict(currency='EUR', amounts=[retainer * 3 // 5, retainer - retainer * 3 // 5], day=28),
                                     dict(currency='KZT', amounts=[first // 7 if rng.randrange(2) else 0, second // 3], day=30),
                                     dict(currency='EUR', amounts=[refund, 0], day=28)],
                           source_model='time_based_milestone_contract',
                           contract=dict(hours=hours, hourly_fee_minor=hourly_fee,
                                         mobilization_fee_minor=first-hours*hourly_fee,
                                         milestone_fees_minor=[first, second], acceptance_required=True)))
    return events


def service_books(events, public, ident):
    """Build service journals directly from accepted milestones and retainers.

    No procurement book constructor or monetary conversion helper is called.
    Shared output schemas permit the same external independent financial auditor.
    """
    start=datetime.fromisoformat(public['manifest']['period_start'])
    cases, contracts, pairs, owners=[],[],[],{}
    def amount(value, rate):
        return int((Decimal(value)*Decimal(rate)).quantize(Decimal('1'),rounding=ROUND_HALF_EVEN))
    def post(cid, inv, stamp, value, pid=None, source=None, rate='1'):
        debit=dict(row_id=ident('row'),timestamp=stamp,account='payable' if pid else 'expense',
                   debit_minor=value,credit_minor=0,currency='KZT',entity_id=inv['entity_id'],
                   invoice_id=inv['invoice_id'],payment_id=pid)
        credit=dict(debit,row_id=ident('row'),account='cash' if pid else 'payable',debit_minor=0,credit_minor=value)
        if pid:
            for row in (debit,credit):
                row.update(allocation_source_minor=source,fx_rate=rate,fx_date=stamp[:10])
        pair=[debit,credit];public['ledger'].extend(pair);pairs.append((cid,pair))
        for row in pair:owners[row['row_id']]=cid
        return pair
    for event in events:
        cid,entity,contract_id=ident('case'),ident('entity'),ident('contract')
        contracts.append(dict(doc_id=contract_id,case_id=cid,kind='contract',terms=event['contract'],economic_model=event['source_model']))
        invoices,payments,entries=[],[],[]
        for index,fee in enumerate(event['obligations']):
            issued=(start+timedelta(days=event['issued_days'][index])).isoformat()
            inv=dict(doc_id=ident('invoice-doc'),invoice_id=ident('invoice'),entity_id=entity,
                     issued_at=issued,due_at=(datetime.fromisoformat(issued)+timedelta(days=30)).isoformat(),
                     currency='KZT',total_minor=fee,line_items=[dict(quantity=1,unit_minor=fee,amount_minor=fee)],contract_doc_id=contract_id)
            invoices.append(inv);public['invoices'].append(inv)
            entries.append(post(cid,inv,issued,fee))
        for transfer in event['payments']:
            stamp=(start+timedelta(days=transfer['day'],hours=11)).isoformat();currency=transfer['currency']
            rate='1'
            if currency!='KZT':
                quote=next((r for r in public['fx'] if r['date']==stamp[:10] and r['source_currency']==currency),None)
                if quote is None:
                    # A separate deterministic quote construction for services.
                    number=int(hashlib.sha256(('service-quote:'+stamp[:10]).encode()).hexdigest()[:8],16)
                    quote=dict(row_id=ident('fx'),date=stamp[:10],source_currency=currency,target_currency='KZT',rate=str(Decimal(5100000+number%600000)/10000))
                    public['fx'].append(quote)
                rate=quote['rate']
            refs=[dict(invoice_id=invoices[i]['invoice_id'],allocated_minor=value,currency=currency) for i,value in enumerate(transfer['amounts']) if value]
            pay=dict(doc_id=ident('payment-doc'),payment_id=ident('payment'),timestamp=stamp,currency=currency,
                     amount_minor=sum(transfer['amounts']),invoice_refs=refs,kind='refund' if sum(transfer['amounts'])<0 else 'settlement')
            payments.append(pay);public['payments'].append(pay)
            for index,value in enumerate(transfer['amounts']):
                if not value:continue
                entries.append(post(cid,invoices[index],stamp,amount(value,rate),pay['payment_id'],value,rate))
                if value<0:invoices[index]['related_credit_doc_id']=pay['doc_id']
        cases.append(dict(case_id=cid,invoices=invoices,payments=payments,entries=entries))
    return cases,contracts,pairs,owners


def inject_service_faults(public, cases, seed, ident, pairs, owners):
    """Service-specific causal transformations, independent of procurement faults.

    Each mechanism has probability .5; cases are selected uniformly. Sources
    remain immutable. Errors affect accepted milestone journals, retainer FX,
    and one partial KZT payment, rather than procurement batch/refund operations.
    """
    rng=random.Random(hashlib.sha256(('service-causes-v1:'+str(seed)).encode()).digest())
    truth,provenance=[],[]
    start=datetime.fromisoformat(public['manifest']['period_start']);end=datetime.fromisoformat(public['manifest']['period_end'])
    def emit(kind,before,after,affected,value,evidence):
        iid=ident('issue')
        truth.append(dict(issue_id=iid,type=kind,affected_ids=sorted(r['row_id'] for r in affected),expected_amount_minor=abs(value),currency='KZT',evidence_sets=[sorted(evidence)],tolerance_minor=0))
        provenance.append(dict(issue_id=iid,operation=kind,before=before,after=copy.deepcopy(after)))
    for kind in ('accounting_period','duplicate_invoice','fx_conversion','payment_allocation'):
        if rng.random()>=.5:continue
        case=rng.choice(cases)
        if kind=='accounting_period':
            inv=case['invoices'][0];pair=case['entries'][0];before=copy.deepcopy(pair)
            recorded=(end+timedelta(hours=2) if start<=datetime.fromisoformat(inv['issued_at'])<end else start+timedelta(days=12)).isoformat()
            for row in pair:row['timestamp']=recorded
            emit(kind,before,pair,[pair[0]],inv['total_minor'],[inv['doc_id'],pair[0]['row_id']])
        elif kind=='duplicate_invoice':
            inv=case['invoices'][1];original=case['entries'][1];before=copy.deepcopy(original);clones=copy.deepcopy(original)
            for row in clones:row['row_id']=ident('row');owners[row['row_id']]=case['case_id']
            public['ledger'].extend(clones);pairs.append((case['case_id'],clones))
            emit(kind,before,original+clones,[original[0],clones[0]],inv['total_minor'],[inv['doc_id'],original[0]['row_id'],clones[0]['row_id']])
        else:
            payment=case['payments'][0 if kind=='fx_conversion' else 1]
            pair=next(p for p in case['entries'] if p[0]['payment_id']==payment['payment_id'])
            before=copy.deepcopy(pair)
            rate=str(Decimal(pair[0]['fx_rate'])*Decimal('1.025')) if kind=='fx_conversion' else pair[0]['fx_rate']
            source=pair[0]['allocation_source_minor'] if kind=='fx_conversion' else pair[0]['allocation_source_minor']//2
            booked=int((Decimal(source)*Decimal(rate)).quantize(Decimal('1'),rounding=ROUND_HALF_EVEN))
            for row in pair:
                row.update(fx_rate=rate,allocation_source_minor=source)
                row['debit_minor' if row['account']=='payable' else 'credit_minor']=booked
            evidence=[payment['doc_id'],pair[0]['row_id']]
            if payment['currency']!='KZT':
                evidence.extend(r['row_id'] for r in public['fx'] if r['date']==payment['timestamp'][:10] and r['source_currency']==payment['currency'])
            emit(kind,before,pair,[pair[0]],before[0]['debit_minor']-booked,evidence)
    return truth,provenance
