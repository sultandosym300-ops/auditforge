"""Independent integer reconciliation of the realistic business event world.

This verifier imports no report, replay or posting function from the generator.
The compact exact-rational auditor separately validates the four-error projection.
"""
from collections import Counter, defaultdict
from datetime import datetime
from .financial_audit import audit_episode, converted_minor

ACCOUNTS={
 'capital_contribution':('cash','capital'), 'loan_received':('cash','loan_payable'),
 'loan_repaid':('loan_payable','cash'), 'interest_accrued':('interest_expense','interest_payable'),
 'interest_paid':('interest_payable','cash'), 'equipment_acquired':('equipment','cash'),
 'equipment_disposed':('cash','equipment'), 'depreciation':('depreciation_expense','accumulated_depreciation'),
 'payroll_accrued':('wages_expense','wages_payable'), 'payroll_paid':('wages_payable','cash'),
 'software_prepaid':('prepaid_software','cash'), 'software_expensed':('software_expense','prepaid_software'),
 'professional_insurance_prepaid':('prepaid_insurance','cash'), 'insurance_expensed':('insurance_expense','prepaid_insurance'),
 'goods_received':('inventory','cash'), 'raw_material_received':('raw_inventory','cash'),
 'production_material_issued':('work_in_progress','raw_inventory'), 'production_labor_accrued':('work_in_progress','wages_payable'),
 'production_completed':('finished_inventory','work_in_progress'), 'finished_goods_sold':('cost_of_goods','finished_inventory'),
 'trading_goods_sold':('cost_of_goods','inventory'), 'freight_route_completed':('transport_expense','cash'),
 'sale_delivered':('receivable','revenue'), 'customer_receipt':('cash','receivable'),
 'bank_fee':('bank_fee_expense','cash'), 'toy_tax_accrued':('tax_expense','tax_payable'),
 'toy_tax_paid':('tax_payable','cash')}
EXPENSES={'expense','wages_expense','depreciation_expense','cost_of_goods','interest_expense','tax_expense','software_expense','bank_fee_expense','disposal_loss','transport_expense','insurance_expense'}
ASSETS={'cash','receivable','raw_inventory','work_in_progress','finished_inventory','inventory','equipment','accumulated_depreciation','prepaid_software','prepaid_insurance'}
LIABILITIES={'payable','wages_payable','loan_payable','interest_payable','tax_payable'}


def _audit_public_world(episode):
    errors=[];checks=[]
    def require(test,message):
        if not test:raise ValueError(message)
    try:
        base=audit_episode(episode);require(base['valid'],'Procurement projection: '+repr(base['errors']))
        checks.append('four_type_projection_and_causal_errors')
        public=episode['public'];world=public['business']
        require(world['version']=='realistic_v1','Unsupported world version')
        require(world['documents']==world['source_documents'],'Document collections disagree')
        events={e['event_id']:e for e in world['events']};journal={r['row_id']:r for r in world['journal']};docs={d['doc_id']:d for d in world['source_documents']}
        require(len(events)==len(world['events']) and len(journal)==len(world['journal']) and len(docs)==len(world['source_documents']),'Duplicate world identity')
        all_docs={**{d['doc_id']:d for d in public['invoices']+public['payments']},**docs}
        source_journal={r['row_id']:r for r in public['ledger']}
        require(all(journal.get(k)==row for k,row in source_journal.items()),'Consolidated journal differs from observed procurement projection')
        for e in events.values():
            require(set(e['related_event_ids'])<=set(events),'Missing event link')
            require(set(e['document_ids'])<=set(all_docs),'Missing document link')
            require(set(e['ledger_ids'])<=set(journal),'Missing journal link')
            kind=e['type'];rows=[journal[k] for k in e['ledger_ids']]
            if kind in ACCOUNTS or kind=='goods_returned':
                expected=ACCOUNTS.get(kind,('cash',e.get('inventory_account')))
                require(len(rows)==2 and {r['account'] for r in rows}==set(expected),'Incorrect event accounting accounts: '+kind)
                require(Counter((r['account'],r['debit_minor'],r['credit_minor']) for r in rows)==Counter(((expected[0],e['amount_minor'],0),(expected[1],0,e['amount_minor']))),'Event/journal amount disagrees: '+kind)
                require(e['amount_minor']>=0 and all(r.get('event_id')==e['event_id'] for r in rows),'Event identity/amount invalid')
                if 'unit_cost_minor' in e:require(e['quantity']*e['unit_cost_minor']==e['amount_minor'],'Quantity valuation mismatch')
                if kind=='customer_receipt':
                    sale=events.get(e['sale_event_id']);require(sale is not None and sale['type']=='sale_delivered' and sale['customer_id']==e['customer_id'],'Customer receipt is not linked to delivered sale')
            elif kind in ('supplier_invoice','supplier_payment','supplier_refund'):
                require(all(r['row_id'] in source_journal for r in rows),'Procurement event links unrelated context posting')
            elif kind in ('supplier_contract','purchase_order','service_acceptance'):
                require(not rows,'Nonrecognition procurement event has journal entries')
            else:raise ValueError('Unknown financial event: '+kind)
        for d in docs.values():
            e=events[d['event_id']]
            require(d['doc_id'] in e['document_ids'] and d['amount_minor']==e['amount_minor'] and d['timestamp']==e['timestamp'],'Source document disagrees with event')
        roots=public['manifest'].get('related_document_ids',[])
        require(isinstance(roots,list) and len(roots)<=10 and set(roots)<=set(docs),'Invalid public source-document roots')
        for d in all_docs.values():
            links=d.get('related_document_ids',[])
            require(isinstance(links,list) and len(links)<=50 and len(links)==len(set(links)) and set(links)<=set(all_docs),'Broken public source-document discovery link')
        checks.append('events_documents_journal_references')
        require(set(journal)==set(source_journal)|{k for e in events.values() if e['type'] in ACCOUNTS or e['type']=='goods_returned' for k in e['ledger_ids']},'Orphan consolidated posting')
        cutoff=datetime.fromisoformat(world['as_of']);start=datetime.fromisoformat(world['period_start'])
        balances=Counter();opening=Counter();debits=Counter();credits=Counter()
        for r in journal.values():
            require(type(r['debit_minor']) is int and type(r['credit_minor']) is int and r['currency']=='KZT','Invalid journal value')
            t=datetime.fromisoformat(r['timestamp'])
            if t>=cutoff:continue
            balances[r['account']]+=r['debit_minor']-r['credit_minor']
            if t<start:opening[r['account']]+=r['debit_minor']-r['credit_minor']
            else:debits[r['account']]+=r['debit_minor'];credits[r['account']]+=r['credit_minor']
        require(sum(balances.values())==0,'Consolidated closing trial balance does not balance')
        require(all(world['state']['accounts'].get(a,0)==v for a,v in balances.items()),'Cached account state differs from journal replay')
        trial={r['account']:r for r in world['reports']['trial_balance']}
        for account in set(balances)|set(trial):
            r=trial[account]
            require((r['opening_minor'],r['debit_minor'],r['credit_minor'],r['closing_minor'])==(opening[account],debits[account],credits[account],balances[account]),'Trial balance detail does not replay')
        rev=credits['revenue']-debits['revenue'];expense=sum(debits[a]-credits[a] for a in EXPENSES)
        require(world['reports']['income_statement']==dict(revenue_minor=rev,expenses_minor=expense,profit_minor=rev-expense),'Income statement differs from period postings')
        assets=sum(balances[a] for a in ASSETS)+sum(max(0,balances[a]) for a in LIABILITIES)
        liabilities=sum(max(0,-balances[a]) for a in LIABILITIES)
        equity=-balances['capital']-balances['revenue']-sum(balances[a] for a in EXPENSES)
        b=world['reports']['balance_sheet']
        require((b['assets_minor'],b['liabilities_minor'],b['equity_minor'])==(assets,liabilities,equity) and assets==liabilities+equity and b['balanced'],'Balance sheet equation/report disagrees')
        checks.append('independent_trial_balance_balance_sheet_income_statement')
        by_invoice=defaultdict(list)
        for r in source_journal.values():
            if datetime.fromisoformat(r['timestamp'])<cutoff:by_invoice[r['invoice_id']].append(r)
        for chain in world['chains']:
            inv=next(i for i in public['invoices'] if i['invoice_id']==chain['invoice_id'])
            rows=by_invoice[inv['invoice_id']]
            payable=sum(r['credit_minor']-r['debit_minor'] for r in rows if r['account']=='payable')
            paid=sum(r['debit_minor']-r['credit_minor'] for r in rows if r['account']=='payable' and r['payment_id'] is not None)
            require((chain['amount_minor'],chain['paid_minor'],chain['balance_minor'])==(inv['total_minor'],paid,payable),'Financial story debt does not match actual books')
            require(set(chain['event_ids'])<=set(events) and set(chain['document_ids'])<=set(all_docs) and set(chain['ledger_ids'])<=set(journal),'Broken financial story reference')
        require(sum(p['balance_minor'] for p in world['state']['payables'])==-balances['payable'],'Payables subledger differs from control account')
        require(sum(r['balance_minor'] for r in world['state']['receivables'])==balances['receivable'],'Receivables subledger differs from control account')
        checks.append('receivables_payables_and_story_replay')
        bank=[d for d in docs.values() if d['type']=='bank_statement' and datetime.fromisoformat(d['timestamp'])<cutoff]
        bank_balance=sum(d['cash_delta_minor'] for d in bank)
        require(bank_balance==world['state']['bank_statement_balance_minor'],'Bank statement balance differs from independent line sum')
        require(balances['cash']-bank_balance==world['state']['bank_reconciliation_difference_minor'],'Bank reconciliation difference concealed')
        rates={(f['date'],f['source_currency']):f['rate'] for f in public['fx']}
        zone=datetime.fromisoformat(public['manifest']['period_start']).tzinfo
        for d in docs.values():
            if d['type']=='bank_statement' and d.get('payment_id'):
                pay=next(p for p in public['payments'] if p['payment_id']==d['payment_id'])
                date=datetime.fromisoformat(pay['timestamp']).astimezone(zone).date().isoformat();rate='1' if pay['currency']=='KZT' else rates[date,pay['currency']]
                amount=converted_minor(pay['amount_minor'],pay['currency'],'KZT',rate,public['manifest']['currency_exponents'])
                require(d['cash_delta_minor']==-amount,'Source bank line does not match independent FX conversion')
        flow=world['reports']['cash_flow'];source_change=sum(d['cash_delta_minor'] for d in bank if datetime.fromisoformat(d['timestamp'])>=start)
        require(flow['closing_cash_minor']-flow['opening_cash_minor']==flow['book_change_minor'] and flow['source_change_minor']==source_change and flow['reconciliation_difference_minor']==flow['book_change_minor']-source_change,'Cash flow does not reconcile')
        checks.append('bank_sources_fx_and_cash_flow')
        inv=world['state']['inventory'];profile=world['profile']
        if profile in ('trade','manufacturing'):
            quantities=Counter();values=Counter()
            for e in sorted(events.values(),key=lambda e:(datetime.fromisoformat(e['timestamp']),e['event_id'])):
                kind=e['type'];qty=e.get('quantity',0);amount=e['amount_minor']
                if kind in ('goods_received','raw_material_received'):
                    account=e['inventory_account'];quantities[account]+=qty;values[account]+=amount
                elif kind=='goods_returned':
                    account=e['inventory_account'];quantities[account]-=qty;values[account]-=amount
                elif kind=='production_material_issued':quantities['raw_inventory']-=qty;values['raw_inventory']-=amount
                elif kind=='production_completed':quantities['finished_inventory']+=qty;values['finished_inventory']+=amount
                elif kind=='finished_goods_sold':quantities['finished_inventory']-=qty;values['finished_inventory']-=amount
                elif kind=='trading_goods_sold':quantities['inventory']-=qty;values['inventory']-=amount
                require(all(q>=0 for q in quantities.values()) and all(v>=0 for v in values.values()),'Inventory issued before available stock')
            require(all(q>=0 for q in quantities.values()),'Inventory went negative')
            if profile=='trade':require(inv['quantity']==quantities['inventory'] and inv['value_minor']==values['inventory']==balances['inventory'],'Trading source quantity/cost rollforward failed')
            else:
                require(inv['raw_quantity']==quantities['raw_inventory'] and inv['finished_quantity']==quantities['finished_inventory'],'Manufacturing source quantity rollforward failed')
                require(inv['raw_value_minor']==values['raw_inventory']==balances['raw_inventory'] and inv['finished_value_minor']==values['finished_inventory']==balances['finished_inventory'] and balances['work_in_progress']==0,'Manufacturing source cost rollforward failed')
        for asset in world['state']['assets']:
            related=[e for e in events.values() if e.get('asset_id')==asset['asset_id']]
            acquired=sum(e['amount_minor'] for e in related if e['type']=='equipment_acquired');disposed=sum(e['amount_minor'] for e in related if e['type']=='equipment_disposed');depreciated=sum(e['amount_minor'] for e in related if e['type']=='depreciation')
            require(asset['cost_minor']==acquired and asset['carrying_minor']==acquired-disposed-depreciated,'Asset rollforward failed')
            require(asset.get('accumulated_depreciation_minor',0)==depreciated,'Cached accumulated depreciation differs from source events')
            require(type(asset['disposed']) is bool and asset['disposed']==bool(disposed),'Asset disposal status differs from source events')
            for e in related:
                if e['type']=='depreciation':require(e['amount_minor']==acquired//e['useful_life_months'],'Straight-line depreciation policy violated')
        payroll=world['state']['payroll'];require(payroll['accrued_minor']-payroll['paid_minor']==payroll['outstanding_minor']==-balances['wages_payable'],'Payroll control account does not reconcile')
        source_payroll=[e for e in events.values() if e['type']=='payroll_accrued']
        require(len(source_payroll)==1 and type(payroll['employees']) is int and payroll['employees']>0 and payroll['employees']==source_payroll[0]['employees'],'Payroll employee count differs from source event')
        loan=world['state']['loan'];require(loan['principal_received_minor']-loan['principal_repaid_minor']==loan['principal_outstanding_minor']==-balances['loan_payable'],'Loan principal does not reconcile')
        interest_paid=sum(e['amount_minor'] for e in events.values() if e['type']=='interest_paid')
        require(loan['interest_paid_minor']==interest_paid and loan['interest_accrued_minor']-interest_paid==-balances['interest_payable'],'Paid interest does not reconcile to source events and control account')
        tax=world['state']['tax'];require(tax['model']=='toy_profit_tax_v1' and tax['tax_base_minor']//10==tax['accrued_minor'] and tax['accrued_minor']-tax['paid_minor']==tax['outstanding_minor']==-balances['tax_payable'],'Toy tax model does not reconcile')
        source_tax=[e for e in events.values() if e['type']=='toy_tax_accrued']
        require(tax['rate_basis_points']==1000 and len(source_tax)==1 and source_tax[0]['rate_basis_points']==1000 and source_tax[0]['tax_base_minor']==tax['tax_base_minor'],'Toy tax rate or source tax base differs from declared model')
        source_profit=0
        for r in episode['pristine']['ledger']+[r for r in journal.values() if r['row_id'] not in source_journal]:
            if start<=datetime.fromisoformat(r['timestamp'])<cutoff:
                if r['account']=='revenue':source_profit+=r['credit_minor']-r['debit_minor']
                elif r['account'] in EXPENSES-{'tax_expense'}:source_profit-=r['debit_minor']-r['credit_minor']
        require(tax['tax_base_minor']==max(0,source_profit),'Toy tax base differs from source economic profit')
        require(loan['interest_accrued_minor']==loan['principal_received_minor']//100,'Loan interest convention violated')
        checks.append('inventory_assets_payroll_financing_toy_tax')
        return dict(valid=True,errors=[],checks=checks,profile=profile,event_count=len(events),journal_count=len(journal),source_document_count=len(docs),projection=base)
    except (KeyError,ValueError,TypeError,StopIteration,IndexError,ZeroDivisionError) as error:
        errors.append(str(error)[:400])
        return dict(valid=False,errors=errors,checks=checks)


def audit_realistic(episode):
    """Validate observed AND pristine business worlds, never expose to a policy."""
    observed=_audit_public_world(episode)
    if not observed['valid']:return observed
    pristine=episode['pristine']
    clean=dict(public=pristine,pristine=pristine,truth=[],provenance=[])
    original=_audit_public_world(clean)
    if not original['valid']:
        return dict(valid=False,errors=['Pristine business state: '+e for e in original['errors']],checks=observed['checks'])
    observed['pristine_valid']=True
    observed['pristine_checks']=original['checks']
    return observed
