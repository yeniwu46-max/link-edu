import hashlib
import os
import secrets
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from flask import Blueprint, abort, current_app, jsonify, request, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_sock import Sock
from sqlalchemy import update
from extensions import db
from models import Course, TrainingSession, User
from classroom_models import Classroom, ClassroomEvent, ClassroomTicket
from services import classroom_budget as budget
from services.classroom_speech import describe, probe_asr, speak
from services.classroom_runtime import ACTIVE, active_lock, LiveClassroom
from services.classroom_reports import jobs, request_report

bp = Blueprint('classroom', __name__, url_prefix='/api/classroom')
probe_results = {}
probe_lock = threading.Lock()
probe_times = {}


@bp.before_request
def validate_body():
    if request.method == 'POST':
        if request.content_length and request.content_length > 8192:
            return jsonify(message='请求内容过大'), 413
        data = request.get_json(silent=True)
        if data is not None and not isinstance(data, dict):
            return jsonify(message='请求必须是JSON对象'), 400


@bp.after_request
def private_headers(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    return response


def owned(sid):
    row = Classroom.query.filter_by(session_id=sid, user_id=int(get_jwt_identity())).first()
    if not row:
        abort(404)
    return row


def serialize(room, include_events=False):
    data = {'session_id': room.session_id, 'topic': room.topic, 'mode': room.mode, 'state': room.state,
            'elapsed': (datetime.utcnow() - room.started_at).total_seconds() if not room.ended_at else (room.ended_at - room.started_at).total_seconds(),
            'cloud_vision': room.cloud_vision, 'report_state': room.report_state,
            'report': room.report, 'report_error': room.report_error, 'report_version': room.report_version,
            'created_at': room.started_at.isoformat(), 'students': room.students}
    if include_events:
        data['events'] = [e.to_dict() for e in ClassroomEvent.query.filter_by(session_id=room.session_id).order_by(ClassroomEvent.id).all()]
    return data


@bp.get('/capabilities')
@jwt_required()
def capabilities():
    services = {}
    for service in ('dialogue', 'vision', 'asr', 'tts'):
        info = describe(service)
        services[service] = {**info,
            'status': probe_results.get(service, {}).get('status', 'unverified') if info['configured'] else 'unconfigured',
            'message': info.get('message') or probe_results.get(service, {}).get('message', '')}
    return jsonify(services=services, budget=budget.status(),
        pose_assets=(Path(current_app.root_path).parent / 'frontend/public/models/pose_landmarker_lite.task').exists())


@bp.post('/probe')
@jwt_required()
def probe():
    """Explicit, budgeted paid smoke tests; no silent cloud calls on page load."""
    from services.classroom_providers import chat
    if not probe_lock.acquire(blocking=False):
        return jsonify(message='能力验证正在进行'), 409
    try:
        service = (request.get_json(silent=True) or {}).get('service')
        if service not in ('dialogue', 'vision', 'asr', 'tts'):
            return jsonify(message='未知服务'), 400
        probe_key = (get_jwt_identity(), service)
        if time.monotonic() - probe_times.get(probe_key, -30) < 30:
            return jsonify(message='同一服务验证至少间隔30秒，避免重复付费'), 429
        probe_times[probe_key] = time.monotonic()
        try:
            if service in ('dialogue', 'vision'):
                image = None
                if service == 'vision':
                    from services.classroom_fixtures import probe_image
                    image = probe_image()
                    answer = chat('Read the image. Return JSON with left_color and right_color, each one common English color name.',
                                  {'test': 'synthetic two-color image'}, image=image, max_tokens=128)
                    if answer.get('left_color', '').lower() != 'blue' or answer.get('right_color', '').lower() != 'pink':
                        raise ValueError('视觉接口返回成功，但色块内容验证未通过')
                else:
                    answer = chat('返回JSON对象，包含ok=true。', {'test': 'API smoke test'}, max_tokens=128)
                    if answer.get('ok') is not True:
                        raise ValueError('对话接口返回成功，但JSON内容验证未通过')
            elif service == 'tts':
                chunks = []
                speak('老师好。', None, 'Cherry', lambda: False, lambda a, rate: chunks.append(a))
                if not chunks:
                    raise ValueError('没有收到合成音频')
            else:
                probe_asr()
            probe_results[service] = {'status': 'available', 'message': '接口验证通过' if service != 'asr' else '会话握手通过；真实识别需麦克风验收'}
        except Exception as exc:
            probe_results[service] = {'status': 'failed', 'message': str(exc)[:160] if isinstance(exc, ValueError) else '接口验证失败，请检查配置与网络'}
        return jsonify(probe_results[service])
    finally:
        probe_lock.release()


@bp.post('/sessions')
@jwt_required()
def create():
    uid = int(get_jwt_identity())
    if not db.session.get(User, uid):
        abort(401)
    data = request.get_json(silent=True) or {}
    if data.get('audio_consent') is not True:
        return jsonify(message='请确认语音上传识别用途'), 400
    mode_value = data.get('mode', 'full')
    if mode_value not in ('full', 'fragment'):
        return jsonify(message='训练模式无效'), 400
    with active_lock:
        active = Classroom.query.filter_by(user_id=uid, state='active').first()
        if active:
            return jsonify(serialize(active)), 200
        course = Course.query.filter_by(title='分数的初步认识（AI互动课堂）').first()
        if not course:
            course = Course(title='分数的初步认识（AI互动课堂）', category='小学数学', stage='综合12 · AI课堂',
                description='三年级：平均分、几分之一、同一整体', is_active=True)
            db.session.add(course)
            db.session.flush()
        session = TrainingSession(user_id=uid, course_id=course.id, status='in_progress',
            progress_percent=0, duration_minutes=0, started_at=datetime.utcnow(), last_trained_at=datetime.utcnow())
        db.session.add(session)
        db.session.flush()
        room = Classroom(session_id=session.id, user_id=uid, mode=mode_value, cloud_vision=data.get('cloud_vision') is True)
        db.session.add(room)
        db.session.commit()
        return jsonify(serialize(room)), 201


@bp.get('/sessions')
@jwt_required()
def history():
    return jsonify(items=[serialize(r) for r in Classroom.query.filter_by(user_id=int(get_jwt_identity()))
                         .order_by(Classroom.started_at.desc()).limit(50).all()])


@bp.get('/sessions/<int:sid>')
@jwt_required()
def detail(sid):
    room = owned(sid)
    if room.report_state == 'running' and sid not in jobs:
        room.report_state = 'failed'
        room.report_error = '服务重启中断了报告任务，请重试'
        db.session.commit()
    return jsonify(serialize(room, True))


@bp.post('/sessions/<int:sid>/ticket')
@jwt_required()
def ticket(sid):
    room = owned(sid)
    if room.state != 'active':
        return jsonify(message='课堂已结束'), 409
    secret = secrets.token_urlsafe(32)
    ClassroomTicket.query.filter(ClassroomTicket.expires_at < datetime.utcnow()).delete()
    row = ClassroomTicket(digest=hashlib.sha256(secret.encode()).hexdigest(), session_id=sid,
                          user_id=room.user_id, expires_at=datetime.utcnow() + timedelta(seconds=45))
    db.session.add(row)
    db.session.commit()
    return jsonify(ticket=secret, expires_in=45)


def consume_ticket(secret):
    digest = hashlib.sha256(secret.encode()).hexdigest()
    changed = db.session.execute(update(ClassroomTicket).where(ClassroomTicket.digest == digest,
        ClassroomTicket.used.is_(False), ClassroomTicket.expires_at > datetime.utcnow()).values(used=True))
    db.session.commit()
    return db.session.get(ClassroomTicket, digest) if changed.rowcount == 1 else None


@bp.post('/sessions/<int:sid>/finish')
@jwt_required()
def finish(sid):
    room = owned(sid)
    with active_lock:
        runtime = ACTIVE.get(sid)
        if runtime and not runtime.closed.is_set():
            runtime.finish_requested = True
            return jsonify(state='draining'), 202
    if room.state == 'active':
        room.state = 'ended'
        room.ended_at = datetime.utcnow()
        session = db.session.get(TrainingSession, sid)
        session.status = 'completed'
        session.duration_minutes = min(10, max(1, round((room.ended_at - room.started_at).total_seconds() / 60)))
        session.progress_percent = 100
        db.session.commit()
    request_report(current_app._get_current_object(), sid)
    return jsonify(serialize(room)), 202


@bp.post('/sessions/<int:sid>/report')
@jwt_required()
def report(sid):
    room = owned(sid)
    if room.state != 'ended':
        return jsonify(message='请先结束课堂'), 409
    data = request.get_json(silent=True) or {}
    with active_lock:
        if sid in jobs:
            return jsonify(serialize(room)), 202
        objection = str(data.get('objection', '')).strip()[:2000]
        if objection:
            room.correction = objection
            db.session.add(ClassroomEvent(session_id=sid, event_key=secrets.token_hex(16), kind='correction',
                at_ms=int((room.ended_at - room.started_at).total_seconds() * 1000), payload={'objection': objection}))
            db.session.commit()
        request_report(current_app._get_current_object(), sid, retry=True)
    return jsonify(serialize(room)), 202


@bp.get('/sessions/<int:sid>/evidence/<int:event_id>')
@jwt_required()
def evidence(sid, event_id):
    owned(sid)
    row = ClassroomEvent.query.filter_by(id=event_id, session_id=sid, kind='vision').first_or_404()
    filename = row.payload.get('image', '')
    if not filename or Path(filename).name != filename:
        abort(404)
    return send_file(Path(current_app.instance_path) / 'classroom_evidence' / str(sid) / filename,
                     mimetype='image/jpeg', max_age=0)


def register_classroom(app):
    app.register_blueprint(bp)
    app.config['SOCK_SERVER_OPTIONS'] = {'max_message_size': 450000, 'ping_interval': 20}
    sock = Sock(app)
    @sock.route('/api/classroom/live')
    def live(ws):
        # JWT and ticket travel in the first frame, never in access-log URLs.
        try:
            import json
            raw = ws.receive(timeout=5)
            auth = json.loads(raw or '{}')
            t = consume_ticket(str(auth.get('ticket', ''))[:128])
            if not t:
                ws.close(reason='invalid ticket')
                return
            room = Classroom.query.filter_by(session_id=t.session_id, user_id=t.user_id, state='active').first()
            if not room:
                ws.close(reason='classroom unavailable')
                return
            with active_lock:
                if ACTIVE:
                    ws.close(reason='another classroom connection is active')
                    return
                runtime = LiveClassroom(app, ws, room)
                ACTIVE[room.session_id] = runtime
            runtime.run()
        except Exception:
            ws.close()
