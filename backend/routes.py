from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from models import User
from services.dashboard import build_dashboard_overview, list_courses, list_resources
from services.growth import build_growth, get_feedback, list_feedbacks
from services.studio import CORRECTION_OPTIONS, add_journal, build_profile, list_journals, update_profile
from services.training import (
    ask_ai_review_question,
    complete_session,
    generate_ai_review,
    regenerate_feedback,
    start_session,
    update_session,
)

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')
dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api/dashboard')
content_bp = Blueprint('content', __name__, url_prefix='/api')


def current_user():
    identity = get_jwt_identity()
    if identity is None:
        return None
    return db.session.get(User, int(identity))


@auth_bp.post('/register')
def register():
    data = request.get_json(silent=True) or {}
    account = (data.get('account') or '').strip()
    password = data.get('password') or ''
    name = (data.get('name') or '').strip()
    role = data.get('role') or 'student'

    if not account or not password or not name:
        return jsonify(message='请完整填写姓名、账号和密码'), 400
    if len(password) < 6:
        return jsonify(message='密码至少需要 6 位'), 400
    if role not in {'student', 'teacher'}:
        return jsonify(message='角色无效'), 400
    if User.query.filter_by(account=account).first():
        return jsonify(message='该账号已经注册，请直接登录'), 409

    user = User(
        account=account,
        password_hash=generate_password_hash(password),
        name=name,
        role=role,
    )
    db.session.add(user)
    db.session.commit()
    return jsonify(message='注册成功', user=user.to_dict()), 201


@auth_bp.post('/login')
def login():
    data = request.get_json(silent=True) or {}
    account = (data.get('account') or '').strip()
    password = data.get('password') or ''
    role = data.get('role') or 'student'

    user = User.query.filter_by(account=account).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify(message='账号或密码错误'), 401

    if role in {'student', 'teacher'} and user.role != role:
        user.role = role
        db.session.commit()

    token = create_access_token(identity=str(user.id))
    return jsonify(access_token=token, user=user.to_dict())


@auth_bp.get('/me')
@jwt_required()
def me():
    user = current_user()
    if not user:
        return jsonify(message='用户不存在'), 404
    return jsonify(user.to_dict())


@dashboard_bp.get('/overview')
@jwt_required()
def overview():
    user = current_user()
    if not user:
        return jsonify(message='用户不存在'), 404
    return jsonify(build_dashboard_overview(user))


@content_bp.get('/courses')
@jwt_required()
def courses():
    user = current_user()
    if not user:
        return jsonify(message='用户不存在'), 404
    return jsonify(items=list_courses(user))


@content_bp.get('/resources')
@jwt_required()
def resources():
    return jsonify(items=list_resources())


@content_bp.post('/training/sessions')
@jwt_required()
def create_training_session():
    user = current_user()
    if not user:
        return jsonify(message='用户不存在'), 404
    data = request.get_json(silent=True) or {}
    course_id = data.get('course_id')
    if not course_id:
        return jsonify(message='请选择课程'), 400
    session, error = start_session(user, int(course_id))
    if error:
        return jsonify(message=error), 404
    return jsonify(session=session.to_dict()), 201


@content_bp.patch('/training/sessions/<int:session_id>')
@jwt_required()
def patch_training_session(session_id):
    user = current_user()
    if not user:
        return jsonify(message='用户不存在'), 404
    data = request.get_json(silent=True) or {}
    session, error = update_session(
        user,
        session_id,
        progress_percent=data.get('progress_percent'),
        duration_minutes=data.get('duration_minutes'),
    )
    if error:
        return jsonify(message=error), 404
    return jsonify(session=session.to_dict())


@content_bp.post('/training/sessions/<int:session_id>/complete')
@jwt_required()
def finish_training_session(session_id):
    user = current_user()
    if not user:
        return jsonify(message='用户不存在'), 404
    data = request.get_json(silent=True) or {}
    session, feedback, error = complete_session(
        user,
        session_id,
        duration_minutes=data.get('duration_minutes') or 1,
        scene=data.get('scene') or '导入',
        mode=data.get('mode') or 'fragment',
    )
    if error:
        return jsonify(message=error), 404
    return jsonify(session=session.to_dict(), feedback=feedback.to_dict())


@content_bp.post('/training/sessions/<int:session_id>/ai-review')
@jwt_required()
def create_ai_review(session_id):
    user = current_user()
    if not user:
        return jsonify(message='用户不存在'), 404
    data = request.get_json(silent=True)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        return jsonify(message='请求内容必须是 JSON 对象'), 400
    transcript_value = data.get('transcript_text')
    notes_value = data.get('teacher_notes')
    regenerate_value = data.get('regenerate', False)
    if transcript_value is not None and not isinstance(transcript_value, str):
        return jsonify(message='课堂转写必须是文本'), 400
    if notes_value is not None and not isinstance(notes_value, str):
        return jsonify(message='教师备注必须是文本'), 400
    if not isinstance(regenerate_value, bool):
        return jsonify(message='regenerate 必须是布尔值'), 400
    transcript_text = (transcript_value or '').strip()
    teacher_notes = (notes_value or '').strip()
    feedback, error = generate_ai_review(
        user,
        session_id,
        transcript_text,
        teacher_notes,
        force_regenerate=regenerate_value,
    )
    if error:
        if error == '训练不存在':
            status = 404
        elif error.startswith('AI 评课请求过于频繁'):
            status = 429
        elif error.startswith('请先') or error.startswith('AI 评课正在生成'):
            status = 409
        else:
            status = 502
        return jsonify(message=error), status
    return jsonify(feedback=feedback.to_dict())


@content_bp.get('/feedbacks')
@jwt_required()
def feedbacks():
    user = current_user()
    if not user:
        return jsonify(message='用户不存在'), 404
    return jsonify(items=list_feedbacks(user))


@content_bp.get('/feedbacks/<int:feedback_id>')
@jwt_required()
def feedback_detail(feedback_id):
    user = current_user()
    if not user:
        return jsonify(message='用户不存在'), 404
    item = get_feedback(user, feedback_id)
    if not item:
        return jsonify(message='评课不存在'), 404
    return jsonify(item)


@content_bp.post('/feedbacks/<int:feedback_id>/ask')
@jwt_required()
def ask_feedback_question(feedback_id):
    user = current_user()
    if not user:
        return jsonify(message='用户不存在'), 404
    data = request.get_json(silent=True)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        return jsonify(message='请求内容必须是 JSON 对象'), 400
    question = data.get('question')
    if not isinstance(question, str):
        return jsonify(message='问题必须是文本'), 400
    if not question.strip():
        return jsonify(message='问题不能为空'), 400

    result, error = ask_ai_review_question(user, feedback_id, question)
    if error:
        if error == '评课不存在':
            status = 404
        elif error.startswith('请先'):
            status = 409
        else:
            status = 502
        return jsonify(message=error), status
    return jsonify(result)


@content_bp.get('/growth')
@jwt_required()
def growth():
    user = current_user()
    if not user:
        return jsonify(message='用户不存在'), 404
    range_key = (request.args.get('range') or 'all').strip()
    if range_key not in {'7d', '30d', 'all'}:
        range_key = 'all'
    return jsonify(build_growth(user, range_key))


@content_bp.post('/feedbacks/<int:feedback_id>/regenerate')
@jwt_required()
def regenerate_review(feedback_id):
    user = current_user()
    if not user:
        return jsonify(message='用户不存在'), 404
    data = request.get_json(silent=True) or {}
    row, error = regenerate_feedback(user, feedback_id, note_ids=data.get('notes') or [])
    if error:
        return jsonify(message=error), 404
    return jsonify(feedback=row.to_dict(), options=CORRECTION_OPTIONS)


@content_bp.get('/studio/corrections')
@jwt_required()
def correction_options():
    return jsonify(items=CORRECTION_OPTIONS)


@content_bp.get('/journals')
@jwt_required()
def journals():
    user = current_user()
    if not user:
        return jsonify(message='用户不存在'), 404
    return jsonify(items=list_journals(user))


@content_bp.post('/journals')
@jwt_required()
def create_journal():
    user = current_user()
    if not user:
        return jsonify(message='用户不存在'), 404
    data = request.get_json(silent=True) or {}
    row, error = add_journal(user, data.get('entry_date'), data.get('body'))
    if error:
        return jsonify(message=error), 400
    return jsonify(item=row), 201


@content_bp.get('/profile')
@jwt_required()
def profile():
    user = current_user()
    if not user:
        return jsonify(message='用户不存在'), 404
    return jsonify(build_profile(user))


@content_bp.patch('/profile')
@jwt_required()
def save_profile():
    user = current_user()
    if not user:
        return jsonify(message='用户不存在'), 404
    data = request.get_json(silent=True) or {}
    return jsonify(update_profile(user, data))


@content_bp.get('/health')
def health():
    return jsonify(status='ok', database=db.engine.url.drivername)
