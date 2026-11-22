"""Only the evaluator process holds truth. Agent-facing proxy exchanges JSON messages."""
import ast
import copy
import json
import multiprocessing
import time
from decimal import Decimal, localcontext
from .generator import generate
from .matcher import evaluate


def calculator(expression):
    if not isinstance(expression, str) or len(expression) > 256:
        raise ValueError('Invalid arithmetic expression')
    tree = ast.parse(expression, mode='eval')
    if len(list(ast.walk(tree))) > 64:
        raise ValueError('Expression too complex')
    def walk(n):
        if isinstance(n, ast.Constant) and type(n.value) in (int, float):
            return Decimal(ast.get_source_segment(expression, n))
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
            return walk(n.operand) * (-1 if isinstance(n.op, ast.USub) else 1)
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            a, b = walk(n.left), walk(n.right)
            if isinstance(n.op, ast.Add): return a+b
            if isinstance(n.op, ast.Sub): return a-b
            if isinstance(n.op, ast.Mult): return a*b
            return a/b
        raise ValueError('Only decimal arithmetic is allowed')
    with localcontext() as c:
        c.prec = 40
        result = walk(tree.body)
    if not result.is_finite() or result.adjusted() > 100:
        raise ValueError('Result outside arithmetic bounds')
    return str(result)


class Session:
    """Evaluator-side state. Never passed to agent policy processes."""
    def reset(self, seed, config, mode):
        self.episode = generate(seed, config)
        self.public = self.episode['public']
        self.mode = mode
        self.steps = 0
        self.done = False
        self.done_flags = (False, False)
        self.report = None
        self.started = time.monotonic()
        self.seconds = 60
        self.final = []
        return dict(
            task='Audit the company for four documented financial issue types; submit evidence-backed findings.',
            manifest=copy.deepcopy(self.public['manifest']),
            policy=copy.deepcopy(self.public['policy']),
            steps_remaining=100,
        ), {}

    def step(self, action):
        if self.done:
            return dict(error='episode_finished', steps_remaining=max(0, 100-self.steps)), 0, *self.done_flags, {}
        self.steps += 1
        observation = dict(steps_remaining=100-self.steps)
        if time.monotonic()-self.started >= self.seconds:
            self.done = True
            self.done_flags = (False, True)
            self.final = []
            observation.update(error='time_limit', findings=[])
            self.report = evaluate(self.public['manifest']['episode_id'], self.episode['truth'], dict(episode_id=self.public['manifest']['episode_id'], findings=[]), self.steps)
            return observation, self.report['reward'] if self.mode == 'train' else 0, False, True, {}
        tool = action.get('tool') if isinstance(action, dict) else None
        if tool == 'submit':
            self.done = True
            self.done_flags = (True, False)
            payload = action.get('findings')
            self.report = evaluate(self.public['manifest']['episode_id'], self.episode['truth'], payload, self.steps-1)
            self.final = payload if 'error' not in self.report else []
            observation['result'] = dict(submitted=True)
            reward = self.report['reward'] if self.mode == 'train' else 0
            return observation, reward, True, False, {}
        try:
            if tool == 'calculator':
                result = calculator(action.get('expression'))
            elif tool in ('list_records', 'get_record'):
                table = action.get('table')
                if table not in ('ledger', 'invoices', 'payments', 'fx'):
                    raise ValueError('Unknown public table')
                records = self.public[table]
                if tool == 'list_records':
                    limit = action.get('limit', 50)
                    cursor = action.get('cursor')
                    if type(limit) is not int or not 1 <= limit <= 50 or (cursor is not None and (not isinstance(cursor, str) or not cursor.isdecimal())):
                        raise ValueError('Invalid page request')
                    offset = int(cursor or '0')
                    if offset > len(records):
                        raise ValueError('Invalid cursor')
                    result = dict(records=records[offset:offset+limit], next_cursor=str(offset+limit) if offset+limit < len(records) else None)
                else:
                    record_id = action.get('id')
                    if not isinstance(record_id, str) or not record_id:
                        raise ValueError('Invalid record ID')
                    keys = {
                        'ledger': ('row_id',),
                        'fx': ('row_id',),
                        'invoices': ('doc_id', 'invoice_id'),
                        'payments': ('doc_id', 'payment_id'),
                    }[table]
                    result = next((r for r in records if any(record_id == r[key] for key in keys)), None)
                    if result is None: raise ValueError('Record not found')
            elif tool == 'get_document':
                documents = [d for table in ('invoices', 'payments') for d in self.public[table]]
                documents += self.public.get('business', {}).get('source_documents', [])
                result = next((d for d in documents if d['doc_id'] == action.get('doc_id')), None)
                if result is None: raise ValueError('Document not found')
            else:
                raise ValueError('Unknown action')
            observation['result'] = copy.deepcopy(result)
        except Exception:
            observation['error'] = 'invalid_request'
        if self.steps >= 100:
            self.done = True
            self.done_flags = (False, True)
            self.final = []
            observation['findings'] = []
            self.report = evaluate(self.public['manifest']['episode_id'], self.episode['truth'], dict(episode_id=self.public['manifest']['episode_id'], findings=[]), self.steps)
            return observation, self.report['reward'] if self.mode == 'train' else 0, False, True, {}
        return observation, 0, False, False, {}


def _worker(connection):
    session = Session()
    while True:
        try:
            message = json.loads(connection.recv_bytes())
            command = message['command']
            if command == 'close': break
            if command == 'reset':
                response = session.reset(message['seed'], message['config'], message['mode'])
            elif command == 'step':
                response = session.step(message['action'])
            elif command == 'report':
                response = session.report if session.done else None
            elif command == 'host_story':
                from .proof import public_story
                response = dict(public_story(session.public), business=session.public.get('business'))
            elif command == 'host_demo':
                from .proof import explain_completed
                response = explain_completed(session, demo=message.get('demo') is True)
            elif command == 'host_counterfactual':
                from .proof import receipt_scenario
                response = receipt_scenario(session.public, message.get('event_id'), message.get('amount_minor'))
            else:
                response = None
            connection.send_bytes(json.dumps(dict(ok=True, value=response), allow_nan=False).encode())
        except (EOFError, BrokenPipeError):
            break
        except Exception:
            connection.send_bytes(b'{"ok":false,"error":"invalid_request"}')
    connection.close()


class AuditEnv:
    def __init__(self, mode='train'):
        if mode not in ('train', 'evaluation'): raise ValueError('Unknown mode')
        self.mode = mode
        context = multiprocessing.get_context('spawn')
        self._connection, child = context.Pipe()
        self._process = context.Process(target=_worker, args=(child,), daemon=True)
        self._process.start()
        child.close()

    def _call(self, message):
        self._connection.send_bytes(json.dumps(message, allow_nan=False).encode())
        if not self._connection.poll(65):
            self.close()
            raise TimeoutError('Evaluator did not respond')
        response = json.loads(self._connection.recv_bytes())
        if not response['ok']: raise ValueError('Invalid environment request')
        return response['value']

    def reset(self, seed, config=None):
        return tuple(self._call(dict(command='reset', seed=seed, config=config, mode=self.mode)))

    def step(self, action):
        return tuple(self._call(dict(command='step', action=action)))

    def evaluator_report(self):
        """Trusted host only. Never expose this method in the agent RPC broker."""
        return self._call(dict(command='report'))

    def evaluator_story(self):
        """Trusted website host: source facts only; not an agent RPC command."""
        return self._call(dict(command='host_story'))

    def evaluator_demo(self, *, demo=False):
        """Trusted explicit demonstration, rejected until terminal submission."""
        return self._call(dict(command='host_demo', demo=demo))

    def evaluator_receipt_scenario(self, event_id, amount_minor):
        """Trusted companion UI: change a copy of public facts, never the episode."""
        return self._call(dict(command='host_counterfactual', event_id=event_id, amount_minor=amount_minor))

    def close(self):
        if self._process.is_alive():
            try: self._connection.send_bytes(b'{"command":"close"}')
            except (BrokenPipeError, OSError): pass
            self._process.join(2)
            if self._process.is_alive(): self._process.kill()
        self._connection.close()

    def __enter__(self): return self
    def __exit__(self, *args): self.close()
