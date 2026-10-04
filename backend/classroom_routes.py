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
from classroom_models import Classroom, ClassroomEvent, ClassroomTicket, PracticePlan
from services import classroom_budget as budget
from services.classroom_speech import describe, probe_asr, speak
from services.classroom_runtime import ACTIVE, active_lock, LiveClassroom
from services.classroom_reports import jobs, request_report
from services.classroom_readiness import MIN_CLASS_SECONDS, report_readiness
from services.classroom_behaviors import analyze_behaviors
from services.classroom_scenarios import scenario_brief
from services.classroom_practice import ensure_plans
from services.classroom_clock import timing, transition, clock_lock

bp = Blueprint('classroom', __name__, url_prefix='/api/classroom')
from services.public_access import capacity, daily_quota, public_mode, public_budget
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
    clock = timing(room)
    data = {'session_id': room.session_id, 'topic': room.topic, 'mode': room.mode, 'state': room.state,
            'elapsed': (datetime.utcnow() - room.started_at).total_seconds() if not room.ended_at else (room.ended_at - room.started_at).total_seconds(),
            'cloud_vision': room.cloud_vision, 'report_state': room.report_state,
            'report': room.report, 'report_error': room.report_error, 'report_version': room.report_version,
            'created_at': room.started_at.isoformat(), 'students': room.students,
            'scenario': scenario_brief()}
    data.update(clock)
    data['elapsed'] = clock['active_elapsed']
    phase = ClassroomEvent.query.filter_by(session_id=room.session_id, kind='report_stage').order_by(ClassroomEvent.id.desc()).first()
    data['report_stage'] = room.report_state if room.report_state in ('completed','failed','insufficient') else phase.payload.get('stage') if phase else room.report_state
    if include_events:
        data['events'] = [e.to_dict() for e in ClassroomEvent.query.filter_by(session_id=room.session_id).order_by(ClassroomEvent.id).all()]
        data['behavior_analysis'] = analyze_behaviors(data['events'])
        data['practice_plans'] = [plan.to_dict() for plan in PracticePlan.query.filter_by(
            source_session_id=room.session_id, source_report_version=room.report_version)
            .order_by(PracticePlan.created_at.desc()).all()]
        active_plan = PracticePlan.query.filter_by(retest_session_id=room.session_id).first()
        data['active_practice_plan'] = active_plan.to_dict() if active_plan else None
        data['report_readiness'] = report_readiness(data['events'], clock['wall_elapsed'], room.cloud_vision,
                                                   active_elapsed=clock['active_elapsed'])
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
    return jsonify(services=services, budget=public_budget(budget.status()), scenario=scenario_brief(),
        capacity=capacity(), quota=daily_quota(int(get_jwt_identity())), can_probe=not public_mode(),
        motion_assets={name: (Path(current_app.root_path).parent / 'frontend/public/models' / filename).exists()
                       for name, filename in {'body': 'pose_landmarker_lite.task', 'hands': 'gesture_recognizer.task', 'face': 'face_landmarker.task'}.items()},
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
                                  {'test': 'synthetic two-color image'}, image=image, max_tokens=128, test=True)
                    if answer.get('left_color', '').lower() != 'blue' or answer.get('right_color', '').lower() != 'pink':
                        raise ValueError('视觉接口返回成功，但色块内容验证未通过')
                else:
                    answer = chat('返回JSON对象，包含ok=true。', {'test': 'API smoke test'}, max_tokens=128, test=True)
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
            if service in ('dialogue', 'vision') and (
                    describe(service)['provider'] == 'openai_next' or 'DEEPSEEK_TEST_API_KEY' in os.environ):
                probe_results[service]['message'] = '测试密钥模型验证通过；正式课堂使用该用途专属密钥'
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
    if data.get('camera_consent') is not True:
        return jsonify(message='请同意开启摄像头用于本地动作检测与 AI 教态评课'), 400
    mode_value = data.get('mode', 'full')
    if mode_value not in ('full', 'fragment'):
        return jsonify(message='训练模式无效'), 400
    practice_id = data.get('practice_plan_id')
    plan = None
    if practice_id is not None:
        if type(practice_id) is not int or practice_id <= 0:
            return jsonify(message='复练任务编号无效'), 400
        plan = PracticePlan.query.filter_by(id=practice_id, user_id=uid).first()
        if not plan:
            abort(404)
        source = db.session.get(Classroom, plan.source_session_id)
        if (plan.status != 'suggested' or not source or source.report_state != 'completed' or
                source.report_version != plan.source_report_version):
            return jsonify(message='这项复练任务已开始或来源报告已更新，请重新选择'), 409
    with active_lock:
        active = Classroom.query.filter_by(user_id=uid).filter(Classroom.state.in_(['active', 'paused'])).first()
        if active:
            if plan:
                return jsonify(message='请先完成当前课堂，再开始复练任务'), 409
            return jsonify(serialize(active)), 200
        if capacity()['available'] == 0:
            return jsonify(message='当前5个课堂名额已满，请稍后重试', code='classroom_capacity'), 503
        if public_mode() and daily_quota(uid)['remaining_today'] == 0:
            return jsonify(message='今日体验次数已用完，明天可继续训练', code='daily_quota'), 429
        if public_mode() and budget.status()['stopped']:
            return jsonify(message='体验额度已到停止线，已有报告仍可查看', code='budget_stopped'), 429
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
        if plan:
            plan.retest_session_id = session.id
            plan.status = 'active'
        db.session.commit()
        return jsonify(serialize(room)), 201


@bp.get('/sessions')
@jwt_required()
def history():
    return jsonify(items=[serialize(r) for r in Classroom.query.filter_by(user_id=int(get_jwt_identity()))
                         .order_by(Classroom.started_at.desc()).limit(50).all()])


@bp.get('/practice-plans')
@jwt_required()
def practice_plans():
    return jsonify(items=[plan.to_dict() for plan in PracticePlan.query.filter_by(
        user_id=int(get_jwt_identity())).order_by(PracticePlan.created_at.desc()).limit(100).all()])


@bp.get('/practice-plans/<int:plan_id>')
@jwt_required()
def practice_plan_detail(plan_id):
    plan = PracticePlan.query.filter_by(id=plan_id, user_id=int(get_jwt_identity())).first()
    if not plan:
        abort(404)
    return jsonify(plan.to_dict())


@bp.post('/sessions/<int:sid>/practice-plans')
@jwt_required()
def create_practice_plans(sid):
    room = owned(sid)
    if room.state != 'ended' or room.report_state != 'completed':
        return jsonify(message='请在课堂报告完成后生成复练任务'), 409
    plans = ensure_plans(room)
    db.session.commit()
    return jsonify(items=[plan.to_dict() for plan in plans])


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
    with active_lock:
        if sid not in ACTIVE and capacity()['available'] == 0:
            return jsonify(message='当前课堂名额已满，请稍后重试', code='classroom_capacity'), 503
    secret = secrets.token_urlsafe(32)
    # Expired tickets are rejected at consume time. Prune during maintenance;
    # concurrent range DELETEs here create MySQL gap-lock deadlocks on admission.
    row = ClassroomTicket(digest=hashlib.sha256(secret.encode()).hexdigest(), session_id=sid,
                          user_id=room.user_id, expires_at=datetime.utcnow() + timedelta(seconds=45))
    db.session.add(row)
    db.session.commit()
    return jsonify(ticket=secret, expires_in=45)


@bp.post('/sessions/<int:sid>/pause')
@jwt_required()
def pause(sid):
    with active_lock, clock_lock:
        room = owned(sid)
        runtime = ACTIVE.get(sid)
        if runtime and runtime.finish_requested:
            return jsonify(message='课堂正在结束，请等待'), 409
        transition(room, 'paused')
        if runtime and not runtime.finish_requested:
            runtime.closed.set()
        return jsonify(serialize(room))


@bp.post('/sessions/<int:sid>/resume')
@jwt_required()
def resume(sid):
    with active_lock, clock_lock:
        room = owned(sid)
        if room.state == 'ended':
            return jsonify(message='课堂已结束'), 409
        runtime = ACTIVE.get(sid)
        if runtime and runtime.closed.is_set():
            return jsonify(message='上一连接正在关闭，请稍后继续'), 409
        transition(room, 'active')
        return jsonify(serialize(room))


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
    elapsed = timing(room)['active_elapsed']
    if room.state in ('active', 'paused') and elapsed < MIN_CLASS_SECONDS:
        return jsonify(message='授课至少满 10 秒后才能结束并评课', minimum_seconds=MIN_CLASS_SECONDS,
                       remaining_seconds=max(0, MIN_CLASS_SECONDS - elapsed)), 409
    with active_lock:
        runtime = ACTIVE.get(sid)
        if runtime and not runtime.closed.is_set():
            runtime.finish_requested = True
            return jsonify(state='draining'), 202
    if room.state in ('active', 'paused'):
        room.state = 'ended'
        room.ended_at = datetime.utcnow()
        session = db.session.get(TrainingSession, sid)
        session.status = 'completed'
        session.duration_minutes = min(10, max(1, round(elapsed / 60)))
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
                if room.session_id in ACTIVE:
                    ws.close(reason='classroom already connected')
                    return
                if capacity()['available'] == 0:
                    ws.send(json.dumps({'type': 'error', 'message': '当前5个课堂名额已满，请稍后重试', 'code': 'classroom_capacity'}))
                    ws.close(reason='classroom capacity reached')
                    return
                runtime = LiveClassroom(app, ws, room)
                ACTIVE[room.session_id] = runtime
            try:
                runtime.run()
            finally:
                with active_lock:
                    if ACTIVE.get(room.session_id) is runtime:
                        ACTIVE.pop(room.session_id, None)
        except Exception:
            ws.close()
