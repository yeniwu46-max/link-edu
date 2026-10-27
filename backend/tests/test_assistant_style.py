import pytest
from test_classroom_base import app
from test_assistant import session
from assistant_routes import AssistantRegistry, SYSTEM, STYLES
from services.classroom_stream import StreamControl
from extensions import db
from models import User
from flask_jwt_extended import create_access_token

def test_registry_default_and_selected_style():
    r=AssistantRegistry()
    assert r.consume(r.issue(1,'text'))==(1,'text','warm')
    assert r.consume(r.issue(1,'text','calm'))==(1,'text','calm')
    assert '阿贝贝老师' in SYSTEM

@pytest.mark.parametrize('bad',['unknown',None,[],{}])
def test_ticket_rejects_invalid_style(app,monkeypatch,bad):
    import assistant_routes as routes
    user=User(account='style',password_hash='synthetic',name='Test');db.session.add(user);db.session.commit()
    headers={'Authorization':'Bearer '+create_access_token(identity=str(user.id))}
    monkeypatch.setattr(routes,'capabilities_for',lambda uid:dict(text_available=True,message=''))
    response=app.test_client().post('/api/assistant/ticket',headers=headers,json={'mode':'text','style':bad})
    assert response.status_code==400

def test_style_change_does_not_cancel_current_answer_and_next_answer_uses_it(app,monkeypatch):
    import services.assistant_dialogue as dialogue
    import rag.service
    monkeypatch.setattr(rag.service,'report_reference_sources',lambda *a,**k:[])
    s,w=session(app);systems=[]
    def stream(system,*args):
        systems.append(system)
        s.update_style('calm')
        assert not s.control.event.is_set()
        return {'text':'进入模拟课堂','source_ids':['system:start']}
    monkeypatch.setattr(dialogue,'chat_stream',stream)
    s.generations.acquire();s.answer('one','开始',s.control,'warm')
    assert STYLES['warm'] in systems[0]
    s.turn='two';s.control=StreamControl()
    s.generations.acquire();s.answer('two','再说',s.control,s.style)
    assert STYLES['calm'] in systems[1]
    assert s.mode=='text' and len(s.history)==4
