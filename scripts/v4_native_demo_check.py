"""Real loopback HTTP demonstration and session revocation regression check."""
import argparse
import http.cookiejar
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[1]

def run():
    with socket.socket() as reserve:
        reserve.bind(('127.0.0.1',0));port=reserve.getsockname()[1]
    process=subprocess.Popen([sys.executable,'-m','auditforge.server','--port',str(port)],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    url='http://127.0.0.1:'+str(port)
    cookies=http.cookiejar.CookieJar();client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
    def request(path,payload=None,old_cookie=None):
        data=None if payload is None else json.dumps(payload).encode()
        headers={'Content-Type':'application/json','Origin':url}
        if old_cookie is not None:headers['Cookie']=old_cookie
        opener=urllib.request.build_opener() if old_cookie is not None else client
        req=urllib.request.Request(url+'/api/'+path,data=data,headers=headers)
        try:
            with opener.open(req,timeout=30) as response:return response.status,json.load(response)
        except urllib.error.HTTPError as error:return error.code,json.load(error)
    try:
        for _ in range(100):
            try:
                if request('me')[0]==200:break
            except (urllib.error.URLError,TimeoutError):time.sleep(.1)
        else:raise RuntimeError('Native server did not become ready')
        assert request('guest',{})[0]==200
        login_cookie='; '.join(c.name+'='+c.value for c in cookies)
        assert request('guest',{})[0]==200
        login_rotated=request('me',old_cookie=login_cookie)[1]['user'] is None
        assert request('reset',dict(seed=772103,config=dict(profile='realistic_v1',business_type='manufacturing',invoices=40)))[0]==200
        status,story=request('world_story',{});assert status==200 and story['business']['version']=='realistic_v1'
        event=next(e for e in story['business']['events'] if e['type']=='customer_receipt')
        status,scenario=request('world_counterfactual',dict(event_id=event['event_id'],amount_minor=event['amount_minor']-100));assert status==200
        assert scenario['after']['cash_minor']-scenario['before']['cash_minor']==-100
        assert scenario['after']['receivable_minor']-scenario['before']['receivable_minor']==100
        assert request('world_story',{})[1]==story
        assert request('demo_explain',dict(demo=True))[0]==400
        status,result=request('run',dict(policy='reconciliation'));assert status==200 and result['report']['f1']==1
        status,explanation=request('demo_explain',dict(demo=True));assert status==200 and len(explanation['issues'])==4
        status,proof=request('proof_suite',dict(seed=772103));assert status==200 and all(c['passed'] for c in proof['matcher_cases'])
        logout_cookie='; '.join(c.name+'='+c.value for c in cookies)
        assert request('logout',{})[0]==200
        logout_revoked=request('me',old_cookie=logout_cookie)[1]['user'] is None
        protected_revoked=request('world_story',{},old_cookie=logout_cookie)[0]==401
        assert login_rotated,'Repeated sign-in did not revoke previous session'
        assert logout_revoked and protected_revoked,'Logout did not revoke the server-side session'
        return dict(passed=True,transport='real loopback HTTP',business_type='manufacturing',causal_payment_delta_minor=-100,
                    active_episode_unchanged=True,preterminal_explanation_denied=True,postterminal_issues=4,
                    matcher_cases=len(proof['matcher_cases']),f1=result['report']['f1'],
                    repeated_login_revoked=True,logout_revoked=True,protected_requests_after_logout_denied=True)
    finally:
        process.terminate()
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.kill();process.wait()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=Path('reports/v4-native-demo-check.json'));args=parser.parse_args()
    result=run();args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result))
