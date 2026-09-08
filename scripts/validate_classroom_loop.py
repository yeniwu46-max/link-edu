"""Paid HTTP/WS synthetic classroom. No real microphone or acoustic playback acceptance."""
import argparse
import base64
import json
import logging
import os
import secrets
import subprocess
import sys
import threading
import time
import uuid
import wave
from pathlib import Path
from datetime import datetime
import httpx
import websocket
from werkzeug.serving import make_server
from classroom_probe_support import (ROOT, isolated_app, open_reservation,
    close_reservation, teacher_audio, verify_room, automatic_end)

LESSON = [
    '这是自编合成测试课堂。今天学习分数的初步认识。把一个圆看作同一个整体。只有每份一样大，才叫平均分。把同一个圆平均分成两份，其中一份就是这个圆的二分之一。小明，为什么必须平均分呢？',
    '小雨，请注意，不一样大的两块不是平均分，不能说每块都是二分之一。我刚才说随便分成两块都叫一半是错的，现在纠正，必须平均分。小雨，你能再解释一次吗？',
    '小林，请你回答。同一个整体平均分成四份，每份是四分之一。二分之一和四分之一比较时，要先确认是同样大的整体。你觉得哪一份更大呢？',
    '我们再看同一个圆。平均分成两份，每份比较大；平均分成四份，每份比较小。分母表示平均分成的份数，分子表示取了几份。你们还有什么疑问？',
]
CORRECTION = '请先停一下。我的意思是必须平均分，现在请继续解释。'


class ProbeFailure(ValueError):
    def __init__(self, message, details):
        super().__init__(message)
        self.details=details


def request(client, method, path, **kwargs):
    response=client.request(method,path,**kwargs)
    if response.status_code >= 400:
        raise ValueError(f'Local probe HTTP {response.status_code}: {path}')
    return response.json()


def stream_classroom(client, sid, raw_clips, seconds):
    ticket=request(client,'POST',f'/api/classroom/sessions/{sid}/ticket')['ticket']
    ws=websocket.create_connection(str(client.base_url).replace('http:','ws:').rstrip('/')+'/api/classroom/live',timeout=15)
    messages, errors, metrics=[],[],[]
    started=None; clip=None; offset=0; turn=0; next_turn=0; next_audio=0
    cancelled=set(); play_end={}; ended_audio=set(); reply_at={}; first_audio=set()
    interrupted=False; teacher_end=None; final_at=None; first_progress=30; active_reply=None; remote_ended=False
    def send(kind,**data):
        ws.send(json.dumps({'type':kind,'event_id':uuid.uuid4().hex,**data}))
    ws.send(json.dumps({'ticket':ticket}))
    try:
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            item=json.loads(ws.recv())
            if item['type']=='ready': break
            if item['type']=='error': raise ValueError(item['message'])
        else: raise ValueError('Classroom never became ready')
        ws.settimeout(.02); started=time.monotonic(); next_audio=started
        while time.monotonic()-started < seconds:
            now=time.monotonic(); elapsed=now-started
            if elapsed>=first_progress:
                print(json.dumps({'progress_seconds':round(elapsed),'messages':len(messages),'errors':len(errors)}),flush=True)
                first_progress+=30
            if clip is None and active_reply is None and elapsed>=next_turn:
                clip=raw_clips[turn % len(LESSON)]; offset=0; turn+=1; next_turn=elapsed+38; teacher_end=None
            if now>=next_audio:
                raw=clip[offset:offset+6400] if clip is not None else b''
                if clip is not None:
                    offset+=len(raw)
                    if offset>=len(clip):
                        clip=None; teacher_end=now; next_turn=max(next_turn,elapsed+25)
                send('audio',audio=base64.b64encode(raw.ljust(6400,b'\0')).decode())
                next_audio+=.2
            for rid in list(ended_audio):
                if now>=play_end.get(rid,now):
                    ended_audio.remove(rid)
                    if rid not in cancelled: send('playback_done',reply_id=rid)
            try:
                raw_message=ws.recv()
                if not raw_message: raise ValueError('Classroom socket closed before requested duration')
                item=json.loads(raw_message)
            except websocket.WebSocketTimeoutException: continue
            messages.append(item); kind=item['type']; rid=item.get('reply_id')
            if automatic_end(item,seconds):
                remote_ended=True
                break
            if kind=='error': errors.append(item.get('message','Classroom error'))
            if kind=='event' and item['event']['type']=='transcript':
                final_at=now
                if teacher_end is not None:
                    metrics.append({'stage':'last_teacher_chunk_to_final','seconds':round(now-teacher_end,3)})
            if kind=='reply':
                active_reply=rid
                reply_at[rid]=now
                if final_at is not None: metrics.append({'stage':'final_to_reply','seconds':round(now-final_at,3)})
            if kind=='cancel':
                if rid:
                    cancelled.add(rid); ended_audio.discard(rid)
                    if rid==active_reply: active_reply=None
            if kind=='listening':
                active_reply=None
                next_turn=min(next_turn,elapsed+3)
            if kind=='audio' and rid not in cancelled:
                rate=item['sample_rate']; audio=base64.b64decode(item['audio'],validate=True)
                if rate not in (16000,24000) or len(audio)%2: raise ValueError('Invalid student PCM')
                play_end[rid]=max(now,play_end.get(rid,now))+len(audio)/(2*rate)
                if rid not in first_audio:
                    first_audio.add(rid); send('playback_started',reply_id=rid,latency_ms=0)
                    metrics.append({'stage':'reply_to_first_pcm','seconds':round(now-reply_at.get(rid,now),3)})
                    if not interrupted and clip is None:
                        clip=raw_clips[-1]; offset=0; interrupted=True
            if kind=='audio_end' and rid not in cancelled:
                if item.get('ok') and rid in first_audio: ended_audio.add(rid)
                else: send('playback_failed',reply_id=rid)
        finished_at=time.monotonic()
        if not remote_ended: send('finish')
        request(client,'POST',f'/api/classroom/sessions/{sid}/finish')
        deadline=time.monotonic()+55
        while not remote_ended and time.monotonic()<deadline:
            try:
                raw=ws.recv()
                if not raw: break
                item=json.loads(raw); messages.append(item)
                if item['type']=='ended': break
            except websocket.WebSocketTimeoutException: continue
        return {'messages':messages,'errors':errors,'metrics':metrics,'audio_reply_count':len(first_audio),
                'stream_seconds':round(finished_at-started,3),'finish_monotonic':finished_at,
                'playback_kind':'PCM-duration acknowledgements; no speaker or browser playback'}
    except Exception as exc:
        raise ProbeFailure(str(exc) if isinstance(exc,ValueError) else 'Classroom transport failed',
            {'messages':messages,'errors':errors,'metrics':metrics,
             'stream_seconds':round(time.monotonic()-started,3) if started else 0}) from None
    finally:
        ws.close()


def wait_report(client, sid, timeout=100):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        room=request(client,'GET',f'/api/classroom/sessions/{sid}')
        if room['report_state'] in ('completed','failed'): return room
        time.sleep(.5)
    raise ValueError('Report did not reach a terminal state')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds',type=int,choices=(180,600),default=180)
    parser.add_argument('--paid',action='store_true',help='Explicitly permit budgeted real provider calls')
    parser.add_argument('--audio-cache',type=Path,help='Reuse previously generated private synthetic teacher WAVs')
    parser.add_argument('--direct-providers',action='store_true',help='Bypass environment proxy for provider domains in this test process only')
    args=parser.parse_args()
    if not args.paid: parser.error('--paid is required; this test consumes API usage')
    if args.direct_providers:
        bypass=os.getenv('NO_PROXY',os.getenv('no_proxy',''))
        bypass+=',127.0.0.1,localhost,api.deepseek.com,iat.xf-yun.com,tts-api.xfyun.cn'
        os.environ['NO_PROXY']=os.environ['no_proxy']=bypass.lstrip(',')
    output=ROOT/'artifacts/private'/('classroom-probe-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    output.mkdir(parents=True,exist_ok=False)
    probe=isolated_app(output); usage_id=open_reservation()
    result={'kind':'synthetic_cloud_classroom_not_human_acceptance','passed':False,'duration_requested':args.seconds}
    result['code_revision']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    result['working_tree_dirty']=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip())
    bypass=set(os.getenv('NO_PROXY',os.getenv('no_proxy','')).split(','))
    result['network']={'environment_proxy_present':bool(os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')),
        'explicit_provider_bypass':{host:host in bypass for host in ('api.deepseek.com','iat.xf-yun.com','tts-api.xfyun.cn')}}
    server=None
    try:
        logging.getLogger('werkzeug').setLevel(logging.ERROR)
        with probe.app_context():
            clips=[]
            for index,text in enumerate(LESSON+[CORRECTION]):
                if args.audio_cache:
                    cache=args.audio_cache.resolve()
                    if not cache.is_relative_to((ROOT/'artifacts/private').resolve()):
                        raise ValueError('Audio cache must be inside artifacts/private')
                    with wave.open(str(cache/f'teacher-{index}.wav'),'rb') as wav:
                        if (wav.getnchannels(),wav.getsampwidth(),wav.getframerate())!=(1,2,16000):
                            raise ValueError('Invalid synthetic cached audio format')
                        raw=wav.readframes(wav.getnframes())
                else:
                    raw=teacher_audio(text)
                clips.append(raw)
                with wave.open(str(output/f'teacher-{index}.wav'),'wb') as wav:
                    wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000); wav.writeframes(raw)
        server=make_server('127.0.0.1',0,probe,threaded=True)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        with httpx.Client(base_url=f'http://127.0.0.1:{server.server_port}',timeout=15,trust_env=False) as client:
            password=secrets.token_urlsafe(24)
            credentials={'account':'synthetic-probe','password':password,'name':'合成测试（非真人）'}
            request(client,'POST','/api/auth/register',json=credentials)
            token=request(client,'POST','/api/auth/login',json=credentials)['access_token']
            client.headers['Authorization']='Bearer '+token
            result['capabilities']=request(client,'GET','/api/classroom/capabilities')
            sid=request(client,'POST','/api/classroom/sessions',json={'mode':'full','audio_consent':True})['session_id']
            result['session_id']=sid
            print('Synthetic classroom started; no real microphone or playback.',flush=True)
            transport=stream_classroom(client,sid,clips,args.seconds)
            result.update(transport); finished_at=result.pop('finish_monotonic')
            room=wait_report(client,sid)
            result['finish_to_report_seconds']=round(time.monotonic()-finished_at,3)
            result['first_report']=room
            checks=verify_room(room)
            checks['received_real_pcm']=result['audio_reply_count']>0
            result['classroom_seconds']=room['elapsed']
            checks['stream_duration']=room['elapsed']>=args.seconds
            checks['no_cloud_errors']=not result['errors']
            checks['report_within_60_seconds']=result['finish_to_report_seconds']<=60
            first_version=room['report_version']
            request(client,'POST',f'/api/classroom/sessions/{sid}/finish')
            repeated=wait_report(client,sid)
            checks['duplicate_finish_same_version']=repeated['report_version']==first_version
            request(client,'POST',f'/api/classroom/sessions/{sid}/report',json={'objection':'请依据授课中必须平均分的纠错原文重新审查；不要固定加分。'})
            retried=wait_report(client,sid)
            checks['objection_report_completed']=retried['report_state']=='completed' and retried['report_version']==first_version+1
            checks['objection_saved']=any(e['type']=='correction' for e in retried['events'])
            result['retry_report']=retried; result['checks']=checks; result['passed']=all(checks.values())
    except Exception as exc:
        result.update(getattr(exc,'details',{}))
        result['error']=str(exc) if isinstance(exc,ValueError) else f'Probe failed ({type(exc).__name__}); no credentials logged'
    finally:
        if server: server.shutdown()
        from services.classroom_runtime import ACTIVE
        from services.classroom_reports import jobs
        deadline=time.monotonic()+60
        while (ACTIVE or jobs) and time.monotonic()<deadline: time.sleep(.2)
        if not ACTIVE and not jobs:
            result['budget']=close_reservation(probe,usage_id,output)
        else:
            result['budget_note']='Workers not confirmed stopped; full 10-yuan reservation retained'
        from classroom_models import ApiUsage
        with probe.app_context():
            result['usage']=[{'service':u.service,'reserved_cny':u.reserved_cny,'charged_cny':u.charged_cny,
                             'state':u.state,'units':u.units} for u in ApiUsage.query.filter(ApiUsage.service!='probe_fence').all()]
        (output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('messages','first_report','retry_report','capabilities','usage')},ensure_ascii=True),flush=True)
    print('Private artifact: '+str(output),flush=True)
    return 0 if result['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
