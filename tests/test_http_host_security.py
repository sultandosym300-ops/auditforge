"""Actual HTTP host/origin rejection, independent of request parsing helpers."""
import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from auditforge.server import Handler


class HttpHostSecurityTests(unittest.TestCase):
    def test_same_origin_attacker_host_cannot_rebind_loopback_server(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def request(method,path,host,origin=None):
            connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
            headers={'Host':host,'Content-Type':'application/json'}
            if origin:headers['Origin']=origin
            connection.request(method,path,body='{}' if method=='POST' else None,headers=headers)
            response=connection.getresponse();result=response.status,json.loads(response.read());connection.close();return result
        try:
            port=server.server_port
            self.assertEqual(request('GET','/api/me',f'127.0.0.1:{port}')[0],200)
            self.assertEqual(request('GET','/api/me',f'attacker.example:{port}'),(403,{'error':'invalid_host'}))
            self.assertEqual(request('POST','/api/guest',f'attacker.example:{port}',f'http://attacker.example:{port}'),(403,{'error':'invalid_host'}))
            self.assertEqual(request('POST','/api/guest',f'127.0.0.1:{port}','https://attacker.example')[0],403)
        finally:
            server.shutdown();server.server_close();thread.join(timeout=5)


if __name__=='__main__':unittest.main()
