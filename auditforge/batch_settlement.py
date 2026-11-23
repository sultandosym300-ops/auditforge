"""Causal regrouping into positive multi-obligation bank settlements.

Refund documents stay separate, preserving signed credit-note semantics. Every
posting, source reference and causal before/after is remapped consistently;
no financial amount or error label is inferred from the hidden truth.
"""
import copy
import hashlib


def consolidate(episode):
    result=copy.deepcopy(episode)
    groups=[]
    for payment in result['pristine']['payments']:
        if payment['amount_minor']<=0:continue
        key=(payment['timestamp'][:10],payment['currency'])
        invoice_ids={ref['invoice_id'] for ref in payment['invoice_refs']}
        for group in groups:
            if group['key']==key and not invoice_ids.intersection(group['invoices']):
                group['payments'].append(payment);group['invoices'].update(invoice_ids);break
        else:groups.append(dict(key=key,invoices=invoice_ids,payments=[payment]))
    payment_map={};document_map={};stamps={};merged={}
    for group in groups:
        payments=group['payments']
        if len(payments)<2:continue
        token=hashlib.sha256('|'.join(sorted(p['payment_id'] for p in payments)).encode()).hexdigest()[:24]
        batch=copy.deepcopy(payments[0])
        batch.update(payment_id='pay-'+token,doc_id='doc-'+token,
                     timestamp=max(p['timestamp'] for p in payments),
                     amount_minor=sum(p['amount_minor'] for p in payments),
                     invoice_refs=[copy.deepcopy(ref) for p in payments for ref in p['invoice_refs']],
                     kind='batch_settlement')
        merged[batch['payment_id']]=batch
        for payment in payments:
            payment_map[payment['payment_id']]=batch['payment_id']
            document_map[payment['doc_id']]=batch['doc_id']
            stamps[payment['payment_id']]=batch['timestamp']
    def remap_row(row):
        old=row.get('payment_id')
        if old in payment_map:
            row['payment_id']=payment_map[old];row['timestamp']=stamps[old]
    for books in (result['public'],result['pristine']):
        kept=[p for p in books['payments'] if p['payment_id'] not in payment_map]
        books['payments']=kept+copy.deepcopy(list(merged.values()))
        for row in books['ledger']:remap_row(row)
        books['manifest']['documents']=len(books['invoices'])+len(books['payments'])
    for mutation in result['provenance']:
        for state in ('before','after'):
            for row in mutation[state]:remap_row(row)
    for issue in result['truth']:
        issue['evidence_sets']=[[document_map.get(item,item) for item in proof] for proof in issue['evidence_sets']]
    return result
