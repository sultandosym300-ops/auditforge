import http.client
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from auditforge import server


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.oldroot=server.ROOT;server.ROOT=Path(cls.temp.name)
        (server.ROOT/'runtime').mkdir()
        with sqlite3.connect(server.ROOT/'runtime'/'accounts.sqlite') as db: db.execute('CREATE TABLE accounts(name TEXT PRIMARY KEY,salt BLOB,digest BLOB)')
        cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close()
        for s in server.SESSIONS.values():
            if s['env']: s['env'].close()
        server.SESSIONS.clear();server.ATTEMPTS.clear();server.ROOT=cls.oldroot;cls.temp.cleanup()
    def request(self,path,payload,cookie='',origin=None):
        c=http.client.HTTPConnection('127.0.0.1',self.http.server_port)
        headers={'Content-Type':'application/json','Cookie':cookie}
        if origin:headers['Origin']=origin
        c.request('POST',path,json.dumps(payload),headers);r=c.getresponse();body=json.loads(r.read());status=r.status;token=r.getheader('Set-Cookie');c.close();return status,body,token
    def test_01_guard(self): self.assertEqual(self.request('/api/reset',{})[0],401)
    def test_02_origin(self): self.assertEqual(self.request('/api/guest',{},origin='https://unrelated.invalid')[0],403)
    def test_03_credentials(self):
        payload={'name':'unit-test-researcher','password':'synthetic-password-only'}
        status,body,cookie=self.request('/api/register',payload);self.assertEqual(status,200);self.assertIn('HttpOnly',cookie)
        self.assertEqual(self.request('/api/login',payload)[0],200)
        self.assertEqual(self.request('/api/login',dict(payload,password='wrong-password'))[0],401)
        self.assertEqual(self.request('/api/register',payload)[0],409)
    def test_04_invalid_credentials(self): self.assertEqual(self.request('/api/register',{'name':33,'password':[]})[0],400)
    def test_05_live_episode(self):
        _,_,cookie=self.request('/api/guest',{})
        status,result,_=self.request('/api/reset',{'seed':839},cookie);self.assertEqual(status,200);self.assertEqual(result['observation']['steps_remaining'],100)
        status,result,_=self.request('/api/run',{'policy':'reconciliation'},cookie);self.assertEqual(status,200);self.assertEqual(result['report']['f1'],1);self.assertEqual(len(result['trajectory']),11)
    def test_06_guest_logout(self):
        _,_,cookie=self.request('/api/guest',{})
        status,_,newcookie=self.request('/api/logout',{},cookie);self.assertEqual(status,200);self.assertIn('Max-Age=0',newcookie)
