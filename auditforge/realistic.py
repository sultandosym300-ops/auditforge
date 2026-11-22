"""Versioned event-backed business context around the four-error procurement audit.

The compact generator samples procurement economic terms. They are converted into
linked business events before this profile materializes its consolidated books.
The official audit projection and reward are unchanged. Other modules are real
accounting context, not additional discrepancy classes or legal/tax guidance.
"""
import copy
import hashlib
import json
import random
from collections import defaultdict
from datetime import datetime, timedelta
from .generator import converted

VERSION='realistic_v1'
BUSINESS_TYPES=('logistics','trade','manufacturing','it','services')
ASSET_ACCOUNTS=('cash','receivable','raw_inventory','work_in_progress','finished_inventory','inventory','equipment','accumulated_depreciation','prepaid_software','prepaid_insurance')
LIABILITY_ACCOUNTS=('payable','wages_payable','loan_payable','interest_payable','tax_payable')
EXPENSE_ACCOUNTS=('expense','wages_expense','depreciation_expense','cost_of_goods','interest_expense','tax_expense','software_expense','bank_fee_expense','disposal_loss','transport_expense','insurance_expense')
ACTIVITIES={'logistics':'freight_transport','trade':'wholesale_goods','manufacturing':'manufactured_goods','it':'software_services','services':'professional_services'}
PROCUREMENT={'logistics':('freight_subcontract','fuel_service','vehicle_lease'),'trade':('warehouse_service','distribution_service','goods_handling'),'manufacturing':('factory_energy','equipment_service','production_subcontract'),'it':('cloud_service','software_subscription','technical_consulting'),'services':('office_lease','professional_subcontract','communications')}


def _stamp(value):
    return datetime.fromisoformat(value)


def replay_business(events,journal,as_of,period_start=None):
    """Replay observed postings, not correct/private postings, into financial state."""
    cutoff=_stamp(as_of); start=_stamp(period_start) if period_start else None
    balances=defaultdict(int);period=defaultdict(lambda:[0,0]);opening=defaultdict(int)
    for row in journal:
        instant=_stamp(row['timestamp'])
        if instant>=cutoff:continue
        balances[row['account']]+=row['debit_minor']-row['credit_minor']
        if start and instant<start:opening[row['account']]+=row['debit_minor']-row['credit_minor']
        else:
            period[row['account']][0]+=row['debit_minor'];period[row['account']][1]+=row['credit_minor']
    accounts=dict(sorted(balances.items()))
    assets=sum(balances[a] for a in ASSET_ACCOUNTS)
    liabilities=0
    for account in LIABILITY_ACCOUNTS:
        value=balances[account]
        liabilities+=max(0,-value);assets+=max(0,value)
    cumulative_profit=-balances['revenue']-sum(balances[a] for a in EXPENSE_ACCOUNTS)
    capital=-balances['capital'];equity=capital+cumulative_profit
    revenue=period['revenue'][1]-period['revenue'][0]
    expenses=sum(period[a][0]-period[a][1] for a in EXPENSE_ACCOUNTS)
    trial=[dict(account=a,opening_minor=opening[a],debit_minor=period[a][0],credit_minor=period[a][1],closing_minor=balances[a]) for a in sorted(set(balances)|set(period))]
    cash_events=[e for e in events if e.get('cash_delta_minor') and (start is None or _stamp(e['timestamp'])>=start) and _stamp(e['timestamp'])<cutoff]
    flow={kind:sum(e['cash_delta_minor'] for e in cash_events if e.get('cash_flow_class','operating')==kind) for kind in ('operating','investing','financing')}
    cash_change=period['cash'][0]-period['cash'][1]
    # Source bank movement can differ from observed books when a controlled audit
    # error changes cash. Display that mismatch rather than correcting it silently.
    source_change=sum(flow.values())
    return dict(accounts=accounts,bank_balance_minor=balances['cash'],reports=dict(
        trial_balance=trial,balance_sheet=dict(assets_minor=assets,liabilities_minor=liabilities,equity_minor=equity,capital_minor=capital,retained_profit_minor=cumulative_profit,balanced=assets==liabilities+equity),
        income_statement=dict(revenue_minor=revenue,expenses_minor=expenses,profit_minor=revenue-expenses),
        cash_flow=dict(opening_cash_minor=opening['cash'],closing_cash_minor=balances['cash'],book_change_minor=cash_change,source_change_minor=source_change,reconciliation_difference_minor=cash_change-source_change,**{k+'_minor':v for k,v in flow.items()})))



def change_customer_receipt(world,event_id,amount_minor):
    """Apply one source-payment change and rebuild linked books/state/reports.

    This public financial counterfactual changes no official procurement labels.
    The original world is untouched. Amounts remain integer minor units.
    """
    result=copy.deepcopy(world)
    selected=next((e for e in result['events'] if e['event_id']==event_id),None)
    if selected is None or selected['type']!='customer_receipt':raise ValueError('Select a customer receipt event')
    sale=next(e for e in result['events'] if e['event_id']==selected['sale_event_id'])
    if type(amount_minor) is not int or not 1<=amount_minor<=sale['amount_minor']:raise ValueError('Receipt must be positive and no larger than its sale')
    old=selected['amount_minor'];selected['amount_minor']=amount_minor;selected['cash_delta_minor']=amount_minor
    selected.pop('payment_fraction_basis_points',None)
    selected['payment_ratio']=dict(numerator=amount_minor,denominator=sale['amount_minor'])
    for collection in ('documents','source_documents'):
        for doc in result[collection]:
            if doc['event_id']==event_id:
                doc['amount_minor']=amount_minor
                if doc['type']=='bank_statement':doc['cash_delta_minor']=amount_minor
    for row in result['journal']:
        if row.get('event_id')==event_id:
            row['debit_minor']=amount_minor if row['account']=='cash' else 0
            row['credit_minor']=amount_minor if row['account']=='receivable' else 0
    replay=replay_business(result['events'],result['journal'],result['as_of'],result['period_start'])
    result['reports']=replay['reports'];result['state']['accounts']=replay['accounts'];result['state']['bank_balance_minor']=replay['bank_balance_minor']
    for balance in result['state']['receivables']:
        if balance['customer_id']==selected['customer_id']:balance['balance_minor']+=old-amount_minor
    cutoff=_stamp(result['as_of'])
    bank=sum(d.get('cash_delta_minor',0) for d in result['source_documents'] if d['type']=='bank_statement' and _stamp(d['timestamp'])<cutoff)
    result['state']['bank_statement_balance_minor']=bank
    result['state']['bank_reconciliation_difference_minor']=result['state']['bank_balance_minor']-bank
    return result


def generate_realistic(seed,config=None):
    if type(seed) is not int:raise ValueError('seed must be an integer')
    if config is not None and not isinstance(config,dict):raise ValueError('config must be an object')
    config=dict(config or {})
    if config.pop('profile',VERSION)!=VERSION:raise ValueError('Unsupported financial world profile')
    business=config.pop('business_type','logistics')
    if business not in BUSINESS_TYPES:raise ValueError('Unsupported business_type')
    if 'recognition_world' in config:raise ValueError('recognition_world is a separate compact research profile')
    from .generator import generate
    sampled_seed=int.from_bytes(hashlib.sha256(f'{VERSION}:{business}:{seed}'.encode()).digest()[:8],'big')
    core=generate(sampled_seed,config)
    pristine=core['pristine'];public=core['public']
    # Supplier terms are sampled by the existing independently verified engine.
    # All subsequent business state is replayed from events and source documents.
    rng=random.Random('realistic-v1:'+str(seed)+':'+business)
    start=_stamp(public['manifest']['period_start']);end=_stamp(public['manifest']['period_end'])
    company={'logistics':'Aral Logistics','trade':'Turan Trading','manufacturing':'Nomad Manufacturing','it':'Saryarka Software','services':'Alatau Services'}[business]+' '+str(rng.randrange(100,999))
    for books in (public,pristine):
        books['manifest'].update(company=company,financial_profile=VERSION,business_type=business)
        for index,inv in enumerate(sorted(books['invoices'],key=lambda x:x['invoice_id'])):
            inv['line_items'][0]['description']=PROCUREMENT[business][index%3]
    ids=iter(range(1,100000))
    def ident(prefix):
        return prefix+'-'+hashlib.sha256(f'{seed}:{business}:{next(ids)}'.encode()).hexdigest()[:16]
    events=[];documents=[];contracts=[];context=[];chains=[];bank=[]
    def event(kind,stamp,amount=0,**facts):
        item=dict(event_id=ident('evt'),type=kind,timestamp=stamp,description_key=kind,amount_minor=amount,currency='KZT',document_ids=[],ledger_ids=[],related_event_ids=[]);item.update(facts)
        events.append(item);return item
    def document(item,kind,**facts):
        doc=dict(doc_id=ident('business-doc'),type=kind,event_id=item['event_id'],timestamp=item['timestamp'],amount_minor=item['amount_minor'],currency='KZT',**facts)
        documents.append(doc);item['document_ids'].append(doc['doc_id']);return doc
    def posting(item,debit,credit,amount=None,**facts):
        amount=item['amount_minor'] if amount is None else amount
        for account,is_debit in ((debit,True),(credit,False)):
            row=dict(row_id=ident('business-row'),timestamp=item['timestamp'],account=account,debit_minor=amount if is_debit else 0,credit_minor=0 if is_debit else amount,currency='KZT',entity_id=facts.get('entity_id','company'),invoice_id=None,payment_id=None,event_id=item['event_id'])
            context.append(row);item['ledger_ids'].append(row['row_id'])
        cash=(amount if debit=='cash' else -amount if credit=='cash' else 0)
        if cash:
            item['cash_delta_minor']=item.get('cash_delta_minor',0)+cash
            doc=document(item,'bank_statement',direction='incoming' if cash>0 else 'outgoing',cash_delta_minor=cash)
            bank.append(doc)
    # Event plan and real source links for the audited procurement stream.
    source_rows=pristine['ledger'];observed_rows=public['ledger'];invoices=sorted(public['invoices'],key=lambda x:x['invoice_id'])
    payables=[]
    for inv in invoices:
        iid=inv['invoice_id'];cid=inv['line_items'][0]['source_ref'];issued=_stamp(inv['issued_at'])
        contract=dict(contract_id=cid,supplier_id=inv['entity_id'],currency=inv['currency'],payment_terms_days=30,invoice_id=iid,purpose=inv['line_items'][0]['description'])
        contracts.append(contract)
        signed=event('supplier_contract',(issued-timedelta(days=3)).isoformat(),inv['total_minor'],contract_id=cid,invoice_id=iid)
        contract_doc=document(signed,'supplier_contract',contract_id=cid,invoice_id=iid,payment_terms_days=30)
        ordered=event('purchase_order',(issued-timedelta(days=2)).isoformat(),inv['total_minor'],contract_id=cid,invoice_id=iid,related_event_ids=[signed['event_id']])
        order_doc=document(ordered,'purchase_order',contract_id=cid,invoice_id=iid)
        accepted=event('service_acceptance',(issued-timedelta(hours=1)).isoformat(),inv['total_minor'],contract_id=cid,invoice_id=iid,related_event_ids=[ordered['event_id']])
        accept_doc=document(accepted,'service_acceptance',contract_id=cid,invoice_id=iid)
        booked=event('supplier_invoice',inv['issued_at'],inv['total_minor'],contract_id=cid,invoice_id=iid,related_event_ids=[accepted['event_id']])
        booked['document_ids'].append(inv['doc_id']);booked['ledger_ids']=[r['row_id'] for r in observed_rows if r['invoice_id']==iid and r['payment_id'] is None]
        linked=[signed,ordered,accepted,booked];docids=[contract_doc['doc_id'],order_doc['doc_id'],accept_doc['doc_id'],inv['doc_id']]
        for pay in sorted([p for p in public['payments'] if any(ref['invoice_id']==iid for ref in p['invoice_refs'])],key=lambda p:(p['timestamp'],p['payment_id'])):
            rows=[r for r in source_rows if r['payment_id']==pay['payment_id'] and r['invoice_id']==iid]
            cash=-sum(r['credit_minor']-r['debit_minor'] for r in rows if r['account']=='cash')
            paid=event('supplier_refund' if cash>0 else 'supplier_payment',pay['timestamp'],abs(cash),contract_id=cid,invoice_id=iid,payment_id=pay['payment_id'],related_event_ids=[booked['event_id']],cash_delta_minor=cash,cash_flow_class='operating')
            paid['document_ids'].append(pay['doc_id']);paid['ledger_ids']=[r['row_id'] for r in observed_rows if r['payment_id']==pay['payment_id']]
            bd=document(paid,'bank_statement',payment_id=pay['payment_id'],invoice_id=iid,cash_delta_minor=cash,direction='incoming' if cash>0 else 'outgoing')
            bank.append(bd);linked.append(paid);docids.extend((pay['doc_id'],bd['doc_id']))
        current=[r for r in observed_rows if r['invoice_id']==iid and _stamp(r['timestamp'])<end]
        balance=sum(r['credit_minor']-r['debit_minor'] for r in current if r['account']=='payable')
        paid=sum(r['debit_minor']-r['credit_minor'] for r in current if r['account']=='payable' and r['payment_id'] is not None)
        chain=dict(chain_id=ident('chain'),invoice_id=iid,contract_id=cid,event_ids=[e['event_id'] for e in linked],document_ids=docids,ledger_ids=[r['row_id'] for r in observed_rows if r['invoice_id']==iid],amount_minor=inv['total_minor'],paid_minor=paid,balance_minor=balance,currency='KZT',description_key=inv['line_items'][0]['description'])
        chains.append(chain);payables.append(dict(invoice_id=iid,balance_minor=balance,due_at=inv['due_at'],overdue=balance>0 and _stamp(inv['due_at'])<end))
    def at(day):return (start+timedelta(days=day,hours=12)).isoformat()
    def simple(kind,day,amount,debit,credit,flow='operating',**facts):
        e=event(kind,at(day),amount,cash_flow_class=flow,**facts);document(e,kind);posting(e,debit,credit);return e
    capital=sum(i['total_minor'] for i in invoices)*4+20_000_000
    simple('capital_contribution',-35,capital,'cash','capital','financing')
    principal=5_000_000
    simple('loan_received',1,principal,'cash','loan_payable','financing')
    simple('loan_repaid',24,500_000,'loan_payable','cash','financing')
    simple('interest_accrued',24,principal//100,'interest_expense','interest_payable',rate_basis_points=100)
    simple('interest_paid',25,principal//200,'interest_payable','cash')
    asset_cost={'logistics':12_000_000,'trade':2_000_000,'manufacturing':8_000_000,'it':3_000_000,'services':1_000_000}[business]
    asset=ident('asset');simple('equipment_acquired',2,asset_cost,'equipment','cash','investing',asset_id=asset,useful_life_months=60)
    depreciation=asset_cost//60
    simple('depreciation',25,depreciation,'depreciation_expense','accumulated_depreciation',asset_id=asset,useful_life_months=60)
    # A separate small fully documented equipment disposal has no invented gain.
    disposed=ident('asset');simple('equipment_acquired',3,120_000,'equipment','cash','investing',asset_id=disposed,useful_life_months=12)
    simple('equipment_disposed',22,120_000,'cash','equipment','investing',asset_id=disposed)
    employees={'logistics':4,'trade':3,'manufacturing':8,'it':6,'services':5}[business]
    wages=employees*240_000
    simple('payroll_accrued',20,wages,'wages_expense','wages_payable',employees=employees)
    simple('payroll_paid',25,wages*4//5,'wages_payable','cash')
    if business=='it':
        simple('software_prepaid',3,1_200_000,'prepaid_software','cash',months=12)
        simple('software_expensed',26,100_000,'software_expense','prepaid_software',months=12)
    inventory={};production_labor=0
    if business in ('trade','manufacturing'):
        received=rng.randrange(90,151);returned=rng.randrange(3,11);unit=rng.randrange(20_000,50_001,1000)
        account='inventory' if business=='trade' else 'raw_inventory'
        simple('goods_received' if business=='trade' else 'raw_material_received',4,received*unit,account,'cash',quantity=received,unit_cost_minor=unit,inventory_account=account)
        simple('goods_returned',5,returned*unit,'cash',account,quantity=returned,unit_cost_minor=unit,inventory_account=account)
        if business=='manufacturing':
            produced=(received-returned)*2//3;sold=produced*2//3;labor_unit=rng.randrange(5000,15001,1000)
            production_labor=produced*labor_unit;finished_unit=unit+labor_unit
            simple('production_material_issued',8,produced*unit,'work_in_progress','raw_inventory',quantity=produced,unit_cost_minor=unit)
            simple('production_labor_accrued',9,production_labor,'work_in_progress','wages_payable',quantity=produced,unit_cost_minor=labor_unit)
            simple('production_completed',10,produced*finished_unit,'finished_inventory','work_in_progress',quantity=produced,unit_cost_minor=finished_unit)
            simple('finished_goods_sold',15,sold*finished_unit,'cost_of_goods','finished_inventory',quantity=sold,unit_cost_minor=finished_unit)
            inventory=dict(raw_quantity=received-returned-produced,finished_quantity=produced-sold,raw_value_minor=(received-returned-produced)*unit,finished_value_minor=(produced-sold)*finished_unit)
        else:
            sold=(received-returned)*2//3
            simple('trading_goods_sold',15,sold*unit,'cost_of_goods','inventory',quantity=sold,unit_cost_minor=unit)
            inventory=dict(quantity=received-returned-sold,value_minor=(received-returned-sold)*unit)
    if business=='logistics':simple('freight_route_completed',12,80_000,'transport_expense','cash',route_count=3)
    if business=='services':simple('professional_insurance_prepaid',6,600_000,'prepaid_insurance','cash',months=12);simple('insurance_expensed',26,50_000,'insurance_expense','prepaid_insurance',months=12)
    customers=[]
    for index in range({'logistics':3,'trade':4,'manufacturing':2,'it':3,'services':5}[business]):
        customer=ident('customer');customers.append(customer)
        base_sale={'logistics':8_000_000,'trade':10_000_000,'manufacturing':20_000_000,'it':12_000_000,'services':8_000_000}[business]
        sale=(base_sale+rng.randrange(6_000_000))*len(invoices)//40
        order=simple('customer_order',11+index,sale,'receivable','revenue',customer_id=customer,service_kind=ACTIVITIES[business])
        # Recognition here is the completed service/delivery, not order signing.
        order['type']='sale_delivered';order['description_key']='sale_delivered';documents[-1]['type']='sale_delivered'
        receipt_percent=rng.randrange(55,91)
        simple('customer_receipt',17+index,sale*receipt_percent//100,'cash','receivable',customer_id=customer,sale_event_id=order['event_id'],payment_fraction_basis_points=receipt_percent*100)
    simple('bank_fee',26,2500,'bank_fee_expense','cash')
    before_tax=replay_business(events,source_rows+context,end.isoformat(),start.isoformat())
    taxable=max(0,before_tax['reports']['income_statement']['profit_minor'])
    tax=taxable//10
    simple('toy_tax_accrued',26,tax,'tax_expense','tax_payable',tax_base_minor=taxable,rate_basis_points=1000)
    simple('toy_tax_paid',27,tax//2,'tax_payable','cash')
    events.sort(key=lambda e:(e['timestamp'],e['event_id']))
    # Public source discovery uses the existing get_document tool. These links
    # are derived from business relations, never from injected issue labels.
    event_index={e['event_id']:e for e in events}
    for doc in documents:
        e=event_index[doc['event_id']]
        linked=set(e['document_ids'])
        for eid in e['related_event_ids']:
            linked.update(event_index[eid]['document_ids'])
        if e.get('sale_event_id'):
            linked.update(event_index[e['sale_event_id']]['document_ids'])
        for related in events:
            if e['event_id'] in related.get('related_event_ids',[]) or related.get('sale_event_id')==e['event_id']:
                linked.update(related['document_ids'])
            if e.get('asset_id') and related.get('asset_id')==e['asset_id']:
                linked.update(related['document_ids'])
        doc['related_document_ids']=sorted(linked-{doc['doc_id']})
    root_types=('capital_contribution','loan_received','equipment_acquired','payroll_accrued',
                'goods_received','raw_material_received','production_completed','software_prepaid',
                'professional_insurance_prepaid','sale_delivered','toy_tax_accrued')
    roots=[]
    for kind in root_types:
        found=next((d['doc_id'] for d in documents if d['type']==kind),None)
        if found:roots.append(found)
    for books in (public,pristine):
        books['manifest']['related_document_ids']=roots[:10]
        for inv in books['invoices']:
            inv['related_document_ids']=[d['doc_id'] for d in documents
                if d.get('invoice_id')==inv['invoice_id'] and d['type'] in ('supplier_contract','purchase_order','service_acceptance')]
        for pay in books['payments']:
            pay['related_document_ids']=[d['doc_id'] for d in documents if d.get('payment_id')==pay['payment_id']]
    for books,base_rows in ((public,observed_rows),(pristine,source_rows)):
        journal=copy.deepcopy(base_rows+context)
        book_events=copy.deepcopy(events)
        for e in book_events:
            if e['type']=='supplier_invoice':e['ledger_ids']=[r['row_id'] for r in base_rows if r['invoice_id']==e['invoice_id'] and r['payment_id'] is None]
            elif e['type'] in ('supplier_payment','supplier_refund'):e['ledger_ids']=[r['row_id'] for r in base_rows if r['payment_id']==e['payment_id']]
        book_chains=copy.deepcopy(chains)
        for chain in book_chains:
            rows=[r for r in base_rows if r['invoice_id']==chain['invoice_id'] and _stamp(r['timestamp'])<end]
            chain['ledger_ids']=[r['row_id'] for r in base_rows if r['invoice_id']==chain['invoice_id']]
            chain['paid_minor']=sum(r['debit_minor']-r['credit_minor'] for r in rows if r['account']=='payable' and r['payment_id'] is not None)
            chain['balance_minor']=sum(r['credit_minor']-r['debit_minor'] for r in rows if r['account']=='payable')
        due={i['invoice_id']:i['due_at'] for i in books['invoices']}
        book_payables=[dict(invoice_id=c['invoice_id'],balance_minor=c['balance_minor'],due_at=due[c['invoice_id']],overdue=c['balance_minor']>0 and _stamp(due[c['invoice_id']])<end) for c in book_chains]
        replay=replay_business(events,journal,end.isoformat(),start.isoformat())
        state=dict(accounts=replay['accounts'],bank_balance_minor=replay['bank_balance_minor'],payables=book_payables,receivables=[dict(customer_id=c,balance_minor=sum(e['amount_minor']*(1 if e['type']=='sale_delivered' else -1) for e in events if e.get('customer_id')==c and e['type'] in ('sale_delivered','customer_receipt') and _stamp(e['timestamp'])<end)) for c in customers],inventory=copy.deepcopy(inventory),assets=[dict(asset_id=asset,cost_minor=asset_cost,accumulated_depreciation_minor=depreciation,carrying_minor=asset_cost-depreciation,disposed=False),dict(asset_id=disposed,cost_minor=120_000,carrying_minor=0,disposed=True)],payroll=dict(employees=employees,accrued_minor=wages+production_labor,paid_minor=wages*4//5,outstanding_minor=-(replay['accounts'].get('wages_payable',0))),loan=dict(principal_received_minor=principal,principal_repaid_minor=500_000,principal_outstanding_minor=4_500_000,interest_accrued_minor=principal//100,interest_paid_minor=principal//200),tax=dict(model='toy_profit_tax_v1',rate_basis_points=1000,tax_base_minor=taxable,accrued_minor=tax,paid_minor=tax//2,outstanding_minor=tax-tax//2))
        bank_balance=sum(d.get('cash_delta_minor',0) for d in bank if _stamp(d['timestamp'])<end)
        state['bank_statement_balance_minor']=bank_balance
        state['bank_reconciliation_difference_minor']=state['bank_balance_minor']-bank_balance
        books['business']=dict(version=VERSION,profile=business,company=dict(name=company,activity_key=ACTIVITIES[business],customers=len(customers),suppliers=len(invoices)),scope=dict(audited='procurement_four_official_error_types',limitation_key='other_modules_are_balanced_context_not_new_error_classes',report_basis='closing_before_period_end; source events can include adjacent dates'),as_of=end.isoformat(),period_start=start.isoformat(),events=book_events,contracts=copy.deepcopy(contracts),documents=copy.deepcopy(documents),source_documents=copy.deepcopy(documents),chains=book_chains,state=state,reports=replay['reports'],journal=journal)
    return core
