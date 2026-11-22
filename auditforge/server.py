"""Loopback-only workbench with local accounts and evaluator-backed sessions."""
import argparse
import hashlib
import hmac
import json
import mimetypes
import secrets
import sqlite3
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from .env import AuditEnv
from .policies import run_policy

ROOT=Path(__file__).resolve().parents[1]
SESSIONS={}
LOCK=threading.Lock()
ATTEMPTS={}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def json(self, data, status=200, cookie=None):
        body=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        if cookie: self.send_header('Set-Cookie',cookie)
        self.send_header('Content-Length',str(len(body)))
        self.end_headers(); self.wfile.write(body)
    def session(self):
        cookie=SimpleCookie(self.headers.get('Cookie',''))
        token=cookie.get('auditforge_session')
        s=SESSIONS.get(token.value if token else '')
        if not s or time.monotonic()-s['created']>86400: return None
        return s
    def do_GET(self):
        path=urlparse(self.path).path
        if path=='/api/me':
            s=self.session()
            return self.json(dict(user=s['user'] if s else None,backend='python',version='1.0.0'))
        if path=='/api/trajectory':
            s=self.session()
            return self.json(s['log'] if s else [],200 if s else 401)
        if path.startswith('/api/'): return self.json({'error':'not_found'},404)
        base=(ROOT/'web'/'dist').resolve()
        file=(base/path.lstrip('/')).resolve()
        if not file.is_relative_to(base): return self.json({'error':'not_found'},404)
        if not file.is_file(): file=base/'index.html'
        if not file.is_file(): return self.json({'error':'Build web frontend first'},503)
        body=file.read_bytes()
        self.send_response(200); self.send_header('Content-Type',mimetypes.guess_type(str(file))[0] or 'application/octet-stream'); self.send_header('Content-Length',str(len(body))); self.send_header('X-Content-Type-Options','nosniff'); self.end_headers(); self.wfile.write(body)
    def do_POST(self):
        origin=self.headers.get('Origin')
        if origin and urlparse(origin).netloc!=self.headers.get('Host'): return self.json({'error':'invalid_origin'},403)
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=131072: raise ValueError()
            payload=json.loads(self.rfile.read(size))
            if not isinstance(payload,dict): raise ValueError()
        except Exception: return self.json({'error':'invalid_request'},400)
        path=urlparse(self.path).path
        if path in ('/api/register','/api/login','/api/guest'):
            user={'name':'Guest','guest':True}
            if path!='/api/guest':
                name=payload.get('name',''); password=payload.get('password','')
                if not isinstance(name,str) or not isinstance(password,str): return self.json({'error':'invalid_credentials_format'},400)
                name=name.strip()
                if not isinstance(name,str) or not 3<=len(name)<=40 or not isinstance(password,str) or not 8<=len(password)<=128: return self.json({'error':'invalid_credentials_format'},400)
                ip=self.client_address[0]; now=time.monotonic()
                ATTEMPTS[ip]=[x for x in ATTEMPTS.get(ip,[]) if now-x<60]
                if len(ATTEMPTS[ip])>=10: return self.json({'error':'try_later'},429)
                ATTEMPTS[ip].append(now)
                with sqlite3.connect(ROOT/'runtime'/'accounts.sqlite') as db:
                    if path=='/api/register':
                        salt=secrets.token_bytes(16); digest=hashlib.scrypt(password.encode(),salt=salt,n=16384,r=8,p=1)
                        try: db.execute('INSERT INTO accounts(name,salt,digest) VALUES(?,?,?)',(name.casefold(),salt,digest))
                        except sqlite3.IntegrityError: return self.json({'error':'name_taken'},409)
                    else:
                        row=db.execute('SELECT salt,digest FROM accounts WHERE name=?',(name.casefold(),)).fetchone()
                        if not row or not hmac.compare_digest(hashlib.scrypt(password.encode(),salt=row[0],n=16384,r=8,p=1),row[1]): return self.json({'error':'wrong_password'},401)
                user={'name':name,'guest':False}
            old=self.session()
            if old and old.get('env'): old['env'].close()
            token=secrets.token_urlsafe(32)
            SESSIONS[token]=dict(user=user,created=time.monotonic(),env=None,log=[],initial=None)
            return self.json(dict(user=user,backend='python'),cookie='auditforge_session='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=86400')
        s=self.session()
        if not s: return self.json({'error':'sign_in_required'},401)
        try:
            if path=='/api/logout':
                if s['env']: s['env'].close()
                return self.json({'ok':True},cookie='auditforge_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
            if path=='/api/reset':
                if s['env']: s['env'].close()
                s['env']=AuditEnv(mode='train'); s['log']=[]
                initial,_=s['env'].reset(payload.get('seed',secrets.randbelow(2**32)),payload.get('config',{}))
                s['initial']=initial
                return self.json(dict(observation=initial))
            if path=='/api/proof_suite':
                from .proof import proof_suite
                return self.json(proof_suite(payload.get('seed',2026112204)))
            if not s['env']: return self.json({'error':'create_episode_first'},409)
            if path=='/api/world_story':
                return self.json(s['env'].evaluator_story())
            if path=='/api/demo_explain':
                return self.json(s['env'].evaluator_demo(demo=payload.get('demo') is True))
            if path=='/api/step':
                action=payload.get('action'); result=s['env'].step(action)
                s['log'].append(dict(episode_id=s['initial']['manifest']['episode_id'],step=len(s['log'])+1,action=action,observation=result[0],reward=result[1],terminated=result[2],truncated=result[3]))
                return self.json(dict(observation=result[0],reward=result[1],terminated=result[2],truncated=result[3],report=s['env'].evaluator_report() if result[2] or result[3] else None))
            if path=='/api/run':
                policy=payload.get('policy','reconciliation')
                if policy not in ('random','reconciliation','mark_all'): return self.json({'error':'unknown_policy'},400)
                result=run_policy(s['env'],s['initial'],policy,s['log'])
                return self.json(dict(result=result,report=s['env'].evaluator_report(),trajectory=s['log']))
            return self.json({'error':'not_found'},404)
        except Exception:
            return self.json({'error':'invalid_request'},400)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--port',type=int,default=8765); args=parser.parse_args()
    (ROOT/'runtime').mkdir(exist_ok=True)
    with sqlite3.connect(ROOT/'runtime'/'accounts.sqlite') as db:
        db.execute('CREATE TABLE IF NOT EXISTS accounts(name TEXT PRIMARY KEY,salt BLOB NOT NULL,digest BLOB NOT NULL)')
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print('AuditForge http://127.0.0.1:'+str(args.port),flush=True)
    try: server.serve_forever()
    finally:
        for s in SESSIONS.values():
            if s['env']: s['env'].close()

if __name__=='__main__': main()
