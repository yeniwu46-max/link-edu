"""Paid synthetic pedagogy probes. No classroom is created and no real ASR/TTS is claimed."""
import json
import sys
import time
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app import app,init_db
from services.classroom_runtime import STUDENT_SYSTEM, STUDENTS
from services.classroom_providers import chat
from services.classroom_knowledge import search
from services.classroom_reports import validate_report, REPORT_SYSTEM
from services.classroom_budget import status

def event(n,kind,text):
    return {'id':n,'type':kind,'at_ms':n*20000,'data':{'text':text}}

cases=[
    {'id':'named-quiet','named_student':'lin','allow_proactive':False,
     'history':[event(1,'transcript','把同一张纸平均分成四份，每一份就是四分之一。小林，四分之一下面的4表示什么？')]},
    {'id':'unequal-partition','named_student':'ming','allow_proactive':False,
     'history':[event(1,'transcript','同学们，只有平均分，每份才能称为几分之一。'),event(2,'transcript','小明，如果我现在把一张纸切成一大一小两块，也能把每块叫这张纸的二分之一，对吗？')]},
    {'id':'followup-context','named_student':'ming','allow_proactive':False,
     'history':[event(1,'transcript','蛋糕平均分成两份，每一份是它的二分之一。'),event(2,'student','老师，大蛋糕的一半和小蛋糕的一半一样多吗？'),event(3,'transcript','小明，不一定一样多。它们都表示各自蛋糕的二分之一，但是整体大小不同。你能换个例子说说吗？')]},
    {'id':'proactive','named_student':None,'allow_proactive':True,
     'history':[event(1,'transcript','我们已经把这张纸平均分成两份，一份是二分之一。现在再把同样大的另一张纸平均分成四份，一份是四分之一。')]},
]

init_db()
out={'provenance':'合成文本/报告探针，不是麦克风授课，不计入三次10分钟验收或语音P95',
     'at':datetime.now(timezone.utc).isoformat(),'results':[]}
with app.app_context():
    for case in ([] if '--report-only' in sys.argv else cases):
        t=time.monotonic()
        try:
            answer=chat(STUDENT_SYSTEM,{**case,'students':STUDENTS,'states':{},'reference_only':search('分数 平均分')})
            result={'id':case['id'],'seconds':round(time.monotonic()-t,3),'result':answer,'status':'returned_for_human_review'}
        except ValueError as e:
            result={'id':case['id'],'status':'failed','message':str(e)}
        out['results'].append(result)
        print(json.dumps(result,ensure_ascii=True),flush=True)
    events=[event(1,'transcript','我把纸分成一大一小两份，每份都是二分之一。'),
            event(2,'student','老师，刚才不是说每份要一样大吗？'),
            event(3,'transcript','谢谢提醒，我刚才说错了。必须平均分成两份，每份才是这个整体的二分之一。'),
            event(4,'transcript','换一张同样大的纸，平均分成四份，每份是四分之一。分母4表示总共平均分成四份。')]
    sources=search('分数 平均分 教学评价');t=time.monotonic()
    try:
        raw=chat(REPORT_SYSTEM,
                 {'synthetic_only':True,'events':events,'references':sources},max_tokens=2500)
        report=validate_report(raw,events,sources)
        out['report']={'seconds':round(time.monotonic()-t,3),'result':report,'raw':raw}
        print(json.dumps({'report_seconds':out['report']['seconds'],'coverage':report['coverage'],
                          'posture_score':next(d['score'] for d in report['dimensions'] if d['key']=='posture'),
                          'dimensions':report['dimensions'],'raw':raw},ensure_ascii=True),flush=True)
    except ValueError as e:
        out['report']={'status':'failed','message':str(e)}
    out['budget']=status()
folder=ROOT/'artifacts/private';folder.mkdir(parents=True,exist_ok=True)
(folder/('report-probe.json' if '--report-only' in sys.argv else 'pedagogy-probes.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
