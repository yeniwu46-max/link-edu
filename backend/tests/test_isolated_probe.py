import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from classroom_probe_support import isolated_app, verify_room
from services.classroom_budget import reserve
from test_classroom_base import app


def test_isolated_probe_has_bounded_budget_and_own_database(tmp_path,monkeypatch):
    monkeypatch.setenv('AI_PRICING_CONFIRMED','true')
    probe=isolated_app(tmp_path)
    from sqlalchemy.engine import make_url
    database = make_url(probe.config['SQLALCHEMY_DATABASE_URI']).database
    assert Path(database).resolve().parent == tmp_path.resolve()
    with probe.app_context():
        reserve('test',9)
        with pytest.raises(ValueError,match='预算'):
            reserve('test',1)


def test_empty_synthetic_room_cannot_pass():
    assert not any(verify_room({}).values())


def test_probe_rejects_report_citing_a_different_unplayed_student():
    room={'events':[{'id':1,'type':'student','data':{'reply_id':'A'}},
                    {'id':2,'type':'student','data':{'reply_id':'B'}},
                    {'id':3,'type':'playback','data':{'reply_id':'A','status':'playback_completed'}}],
          'report':{'dimensions':[{'score':90,'event_ids':[2]}]}}
    result=verify_room(room)
    assert result['synthetic_playback_ack'] and not result['report_references']


def test_automatic_classroom_end_uses_server_duration_not_socket_start():
    from classroom_probe_support import automatic_end
    assert automatic_end({'type':'ended','at_ms':600010},600)
    assert not automatic_end({'type':'ended','at_ms':599999},600)
    assert not automatic_end({'type':'error','at_ms':600010},600)


def test_probe_reserves_real_budget_and_settles_only_isolated_cost(app,tmp_path,monkeypatch):
    import classroom_probe_support as support
    from services.classroom_budget import status
    monkeypatch.setattr(support,'main_app',app)
    reserve('earlier_calls',3)
    usage=support.open_reservation()
    assert status()['spent_and_reserved_cny']==13
    folder=tmp_path/'probe'; folder.mkdir()
    probe=isolated_app(folder)
    with probe.app_context(): reserve('synthetic_unknown_call',.5)
    assert support.close_reservation(probe,usage,folder)['spent_and_reserved_cny']==3.5


def test_probe_cannot_escape_existing_total_budget(app,monkeypatch):
    import classroom_probe_support as support
    monkeypatch.setattr(support,'main_app',app)
    reserve('earlier_calls',80)
    with pytest.raises(ValueError,match='预算'):
        support.open_reservation()
