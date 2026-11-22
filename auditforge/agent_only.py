"""Public-actions-only documentary corroboration, separate from learned policies.

Additional sources corroborate an existing financial candidate. This does not make
those sources mandatory for the unchanged official matcher or the old baseline.
"""
from datetime import datetime
from .reconcile import reconcile
from fractions import Fraction


def converted_minor(amount, source, target, rate, exponents):
    return int(round(Fraction(amount)*Fraction(rate)*Fraction(10)**(exponents[target]-exponents[source])))


def run_agent_only(step, initial, *, inspect_context=True, log=None):
    public=dict(manifest=initial['manifest'],policy=initial['policy'])
    remaining=initial['steps_remaining'];ended=False;requested={};declined=[];context=[]
    def act(action):
        nonlocal remaining,ended
        result=step(action);remaining=result[0]['steps_remaining'];ended=result[2] or result[3]
        if log is not None:log.append(dict(episode_id=initial['manifest']['episode_id'],step=len(log)+1,action=action,observation=result[0],reward=result[1],terminated=result[2],truncated=result[3]))
        return result
    def get(doc_id):
        if doc_id in requested:return requested[doc_id]
        if ended or remaining<=1:return None
        result=act(dict(tool='get_document',doc_id=doc_id))
        record=result[0].get('result')
        requested[doc_id]=record if isinstance(record,dict) else None
        return requested[doc_id]
    for table in ('ledger','invoices','payments','fx'):
        public[table]=[];cursor=None
        while not ended and remaining>1:
            result=act(dict(tool='list_records',table=table,cursor=cursor,limit=50))
            page=result[0].get('result')
            if not isinstance(page,dict):break
            public[table].extend(page['records']);cursor=page['next_cursor']
            if cursor is None:break
    candidates=reconcile(public) if all(public.get(k) for k in ('ledger','invoices','payments','fx')) else []
    invoices={i['invoice_id']:i for i in public['invoices']};payments={p['payment_id']:p for p in public['payments']};rows={r['row_id']:r for r in public['ledger']}
    findings=[]
    for finding in candidates:
        row=rows[finding['affected_ids'][0]];support=[]
        if finding['type'] in ('duplicate_invoice','accounting_period'):
            invoice=invoices[row['invoice_id']]
            sources=[get(identity) for identity in invoice.get('related_document_ids',[])]
            contract=next((s for s in sources if s and s.get('type')=='supplier_contract'),None)
            acceptance=next((s for s in sources if s and s.get('type')=='service_acceptance'),None)
            if (contract and acceptance and contract.get('invoice_id')==acceptance.get('invoice_id')==invoice['invoice_id']
                and contract.get('contract_id')==acceptance.get('contract_id')==invoice['line_items'][0]['source_ref']
                and contract['amount_minor']==acceptance['amount_minor']==invoice['total_minor']
                and contract['currency']==acceptance['currency']==invoice['currency']
                and datetime.fromisoformat(contract['timestamp'])<=datetime.fromisoformat(acceptance['timestamp'])<=datetime.fromisoformat(invoice['issued_at'])):
                support=[contract['doc_id'],acceptance['doc_id']]
        else:
            payment=payments[row['payment_id']]
            source_amount=next(ref['allocated_minor'] for ref in payment['invoice_refs'] if ref['invoice_id']==row['invoice_id'])
            zone=datetime.fromisoformat(public['manifest']['period_start']).tzinfo
            date=datetime.fromisoformat(payment['timestamp']).astimezone(zone).date().isoformat()
            fx=next((f for f in public['fx'] if f['date']==date and f['source_currency']==payment['currency'] and f['target_currency']==public['manifest']['base_currency']),None)
            expected=converted_minor(source_amount,payment['currency'],public['manifest']['base_currency'],fx['rate'] if fx else '1',public['manifest']['currency_exponents'])
            for identity in payment.get('related_document_ids',[]):
                bank=get(identity)
                if (bank and bank.get('type')=='bank_statement' and bank.get('payment_id')==payment['payment_id']
                    and bank.get('invoice_id')==row['invoice_id'] and bank.get('cash_delta_minor')==-expected
                    and bank.get('amount_minor')==abs(expected) and bank.get('timestamp')==payment['timestamp']
                    and bank.get('currency')==public['manifest']['base_currency']):
                    support=[bank['doc_id']];break
        if support:
            finding=dict(finding,evidence_ids=sorted(set(finding['evidence_ids']+support)),explanation='Reconciled public records and corroborated the source obligation/payment against acceptance, contract or bank records.')
            if len(finding['evidence_ids'])<=10:findings.append(finding)
        else:declined.append(dict(type=finding['type'],affected_ids=finding['affected_ids'],reason='missing_or_inconsistent_public_corroboration'))
    if inspect_context:
        for identity in initial['manifest'].get('related_document_ids',[]):
            source=get(identity)
            if source:context.append(source['type'])
    terminal=None if ended else act(dict(tool='submit',findings=dict(episode_id=initial['manifest']['episode_id'],findings=findings)))
    return dict(terminal=terminal,findings=findings,declined=declined,requested_source_documents=len(requested),discovered_context_types=sorted(set(context)),scope='Official public actions only. Deterministic corroborating policy, not a trained model; additional documents do not replace the unchanged matcher evidence minimum.')
