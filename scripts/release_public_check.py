"""External trusted-HTTPS acceptance, real providers and synthetic cached speech.
Operator provisions labelled synthetic accounts; no production data is deleted.
"""
import argparse, concurrent.futures, json, secrets, sys, time, wave
from pathlib import Path
import httpx, paramiko

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from validate_classroom_loop import stream_classroom, wait_report
from classroom_probe_support import verify_room

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--paid',action='store_true')
    parser.add_argument('--url',default='https://106.15.77.40:8443')
    parser.add_argument('--five-only',action='store_true')
    parser.add_argument('--speech-offset',type=float,default=0,help='Seconds between synthetic teacher starts; classroom clocks remain concurrent')
    args=parser.parse_args()
    if not args.paid: parser.error('--paid required; public release ledger enforces 30 CNY ceiling')
    output=ROOT/'artifacts/private/public-acceptance'; output.mkdir(parents=True,exist_ok=True)
    clips=[]
    for i in range(4):
        with wave.open(str(ROOT/f'artifacts/private/competition-cloud/teacher-{i}.wav'),'rb') as w: clips.append(w.readframes(w.getnframes()))
    accounts=[{'account':'qa_load_'+secrets.token_hex(5),'password':secrets.token_urlsafe(20),'name':f'合成并发验收{i+1}'} for i in range(10)]
    (output/'accounts.private.json').write_text(json.dumps(accounts,ensure_ascii=False),encoding='utf-8')
    ssh=paramiko.SSHClient(); ssh.load_system_host_keys(); ssh.connect('106.15.77.40',username='root',key_filename=str(Path.home()/'.ssh/plex_ecs'))
    script='from app import app\nfrom extensions import db\nfrom models import User\nfrom werkzeug.security import generate_password_hash\nimport json\nrows=json.loads('+repr(json.dumps(accounts))+')\nwith app.app_context():\n for r in rows: db.session.add(User(account=r["account"],name=r["name"],password_hash=generate_password_hash(r["password"]),role="student"))\n db.session.commit()\nprint("Synthetic accounts ready")\n'
    stdin,stdout,stderr=ssh.exec_command('podman exec -i link-demo-api python'); stdin.write(script); stdin.channel.shutdown_write()
    assert stdout.channel.recv_exit_status()==0,stderr.read().decode()
    records=[]; index=0
    for count,seconds in ([(5,600)] if args.five_only else [(1,60),(3,90),(5,600)]):
        clients=[]; rooms=[]; phase={'concurrency':count,'requested_seconds':seconds,'speech_offset_seconds':args.speech_offset,'results':[],'samples':[]}
        for account in accounts[index:index+count+(1 if count==5 else 0)]:
            client=httpx.Client(base_url=args.url,timeout=60,trust_env=False)
            login=client.post('/api/auth/login',json=account); login.raise_for_status()
            client.headers['Authorization']='Bearer '+login.json()['access_token']
            create=client.post('/api/classroom/sessions',json={'audio_consent':True,'camera_consent':True}); create.raise_for_status()
            clients.append(client); rooms.append(create.json()['session_id'])
        index+=count
        def run(n):
            try:
                stream=stream_classroom(clients[n],rooms[n],clips,seconds,allow_interrupt=False,start_delay=n*args.speech_offset)
                room=wait_report(clients[n],rooms[n],timeout=130)
                return {'session_id':rooms[n],'stream':stream,'room':room,'checks':verify_room(room)}
            except Exception as e:
                return {'session_id':rooms[n],'error':str(e)[:160] if isinstance(e,ValueError) else type(e).__name__,'details':getattr(e,'details',None)}
        with concurrent.futures.ThreadPoolExecutor(max_workers=count) as pool:
            futures=[pool.submit(run,n) for n in range(count)]
            checked=False
            while not all(f.done() for f in futures):
                _,stdout,_=ssh.exec_command('podman stats --no-stream --format json')
                phase['samples'].append({'at':time.time(),'containers':json.loads(stdout.read().decode() or '[]')})
                if count==5 and not checked:
                    caps=clients[0].get('/api/classroom/capabilities').json()
                    if caps['capacity']['active']==5:
                        sixth=clients[5].post(f'/api/classroom/sessions/{rooms[5]}/ticket')
                        phase['sixth_rejected']={'status':sixth.status_code,'body':sixth.json()}
                        checked=True
                time.sleep(10)
            phase['results']=[f.result() for f in futures]
        for client in clients: client.close()
        records.append(phase)
        (output/'result.json').write_text(json.dumps({'provenance':'real cloud providers; synthetic teacher audio and playback acknowledgements; no human/device claim','phases':records},ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'concurrency':count,'checks':[r.get('checks',r.get('error')) for r in phase['results']],'sixth':phase.get('sixth_rejected')},ensure_ascii=True),flush=True)
        if any('error' in r for r in phase['results']): break
    ssh.close()

if __name__=='__main__': main()
