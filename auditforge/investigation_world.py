"""Optional sequential acquisition world; original financial books stay auditable.

Risk attributes describe operating controls, not injected issue labels. A latent
company control regime creates correlated uncertainty across departments. Each
department contains a complete compact financial history; document routing adds
different, explicit API query costs. Bulk-table access remains available to every
baseline, so this is a budgeted research extension, not a harder official case.
"""
import copy
import hashlib
import json
import math
import random

from .generator import TYPES, generate

VERSION = 'investigation_v1'
FAMILIES = ('procurement', 'closing_transfer', 'batch_transfer')


def identity(*values):
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()[:24]


def generate_investigation(seed, config):
    allowed = {'profile', 'cases', 'clean', 'family'}
    if set(config) - allowed:
        raise ValueError('Unsupported investigation configuration')
    count, clean, family = config.get('cases', 6), config.get('clean', False), config.get('family', 'procurement')
    if type(count) is not int or not 4 <= count <= 6 or type(clean) is not bool or family not in FAMILIES:
        raise ValueError('Invalid investigation configuration')
    # All randomness is keyed by purpose; document IDs/order/name do not select labels.
    rng = random.Random(identity(seed, VERSION, 'economics'))
    labels = random.Random(identity(seed, VERSION, 'controls'))
    names = random.Random(identity(seed, VERSION, 'identifiers'))
    regime = labels.choice((-.9, .9))
    company_clean = clean
    cases, packets, index = [], [], []
    for number in range(count):
        attributes = [rng.randrange(2) for _ in range(4)]
        manual, cutoff, cross_border, supplier_change = attributes
        probability = 1 / (1 + math.exp(-(-2.1 + 1.1*manual + .8*cutoff + .6*cross_border + .7*supplier_change + regime)))
        active = not company_clean and labels.random() < probability
        kinds = [kind for kind in TYPES if labels.random() < .6] if active else []
        if active and not kinds:
            kinds = [labels.choice(TYPES)]
        base = dict(invoices=40, timezone='+05:00', boundary_payments=True,
                    interaction=number % 3, clean=not active, counts={kind:1 for kind in kinds})
        if family == 'closing_transfer' and not company_clean:
            # Different *period injection* mechanism (crossed source/book dates),
            # still sharing the original economic-book generator, not real-bank transfer.
            base = dict(invoices=40, timezone='+05:00', recognition_world=labels.randrange(4))
        case = generate(int(identity(seed, number, 'case'), 16), base, _quote_seed=identity(seed, 'quotes'))
        if family=='batch_transfer':
            from .batch_settlement import consolidate
            case=consolidate(case)
        canonical = {row['row_id']:'fx-'+identity(seed, row['date'], row['source_currency'], row['target_currency']) for row in case['public']['fx']}
        for books in (case['public'], case['pristine']):
            for row in books['fx']:
                row['row_id'] = canonical[row['row_id']]
        for issue in case['truth']:
            issue['evidence_sets'] = [[canonical.get(item, item) for item in evidence] for evidence in issue['evidence_sets']]
        cases.append(case)
        case_id = 'case-'+identity(seed, names.getrandbits(128))
        cost = rng.randint(1, 3)
        routes = ['doc-'+identity(seed, names.getrandbits(128)) for _ in range(cost)]
        index.append(dict(case_id=case_id, document_id=routes[0], query_cost=cost,
                          manual_entries=manual, cutoff_pressure=cutoff,
                          cross_border=cross_border, supplier_change=supplier_change))
        for depth, document_id in enumerate(routes):
            document = dict(doc_id=document_id, case_id=case_id, kind='routing_receipt')
            if depth + 1 < cost:
                document['next_document_id'] = routes[depth+1]
            else:
                document.update(kind='department_source_packet', records=copy.deepcopy(case['public']))
            packets.append(document)
    public = copy.deepcopy(cases[0]['public'])
    pristine = copy.deepcopy(cases[0]['pristine'])
    for books, key in ((public, 'public'), (pristine, 'pristine')):
        for table in ('ledger', 'invoices', 'payments'):
            books[table] = [copy.deepcopy(row) for case in cases for row in case[key][table]]
        books['fx'] = copy.deepcopy(cases[0][key]['fx'])
        books['manifest'].update(episode_id='ep-'+identity(seed, config), profile=VERSION,
                                 company='Consolidated departments '+str(names.randrange(100, 999)),
                                 records=len(books['ledger']), documents=len(books['invoices'])+len(books['payments']),
                                 investigations=copy.deepcopy(index))
        books['business'] = dict(version=VERSION, source_documents=copy.deepcopy(packets))
    return dict(public=public, pristine=pristine,
                truth=[copy.deepcopy(t) for case in cases for t in case['truth']],
                provenance=[copy.deepcopy(p) for case in cases for p in case['provenance']])
