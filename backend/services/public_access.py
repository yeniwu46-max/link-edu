"""Small-instance admission and public API policy; no provider calls here."""
from collections import OrderedDict, deque
from datetime import datetime, timedelta
import threading
import time
from flask import current_app, request, jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from classroom_models import Classroom


def public_mode():
    return current_app.config.get('PUBLIC_DEPLOYMENT', False)


def capacity():
    from services.classroom_runtime import ACTIVE, active_lock
    with active_lock:
        limit = current_app.config.get('CLASSROOM_MAX_ACTIVE', 5)
        return {'limit': limit, 'active': len(ACTIVE), 'available': max(0, limit - len(ACTIVE))}


def daily_quota(uid):
    # Database timestamps are UTC; the public daily allowance resets at Shanghai midnight.
    now = datetime.utcnow()
    start = (now + timedelta(hours=8)).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=8)
    limit = current_app.config.get('CLASSROOM_DAILY_LIMIT', 2)
    used = Classroom.query.filter(Classroom.user_id == uid, Classroom.started_at >= start).count()
    return {'daily_limit': limit, 'used_today': used, 'remaining_today': max(0, limit - used),
            'reset_at': (start + timedelta(days=1)).isoformat() + 'Z'}


def public_budget(value):
    if not public_mode():
        return value
    return {key: bool(value.get(key)) for key in ('stopped', 'warning', 'pricing_confirmed')}


def install_policy(app):
    # Bounded process-local windows are sufficient because production has exactly one worker.
    windows, guard = OrderedDict(), threading.Lock()
    app.extensions['public_rate_windows'] = windows

    @app.before_request
    def enforce():
        if not app.config.get('PUBLIC_DEPLOYMENT') or not request.path.startswith('/api/'):
            return
        if request.method in ('POST', 'PATCH', 'PUT'):
            limit = app.config.get('MAX_CONTENT_LENGTH') or 2000000
            if request.endpoint == 'rag.upload_document':
                from rag.settings import load_settings
                try:
                    limit = load_settings().max_upload_bytes
                except ValueError:
                    pass
            if request.content_length and request.content_length > limit:
                return jsonify(message='请求内容过大'), 413
            body = request.get_json(silent=True)
            if body is not None and not isinstance(body, dict):
                return jsonify(message='请求必须是JSON对象'), 400
        if request.method == 'OPTIONS':
            return
        origin = request.headers.get('Origin')
        if origin and origin not in app.config.get('PUBLIC_ORIGINS', []):
            return jsonify(message='不允许的页面来源'), 403
        # Paid legacy review routes bypass the classroom ledger and are unavailable in public mode.
        if request.path == '/api/classroom/probe' or (request.method == 'POST' and
                ('/ai-review' in request.path or '/visual-evidence' in request.path or request.path.endswith('/ask'))):
            return jsonify(message='此入口仅供本机运维；请使用模拟课堂的证据评课'), 403
        if request.method != 'POST':
            return
        endpoint = request.endpoint or request.path
        if endpoint == 'auth.register':
            maximum, period = 5, 3600
        elif endpoint == 'auth.login':
            maximum, period = 20, 600
        else:
            maximum, period = 30, 60
        identity = request.remote_addr or 'unknown'
        if endpoint not in ('auth.register', 'auth.login'):
            verify_jwt_in_request(optional=True)
            identity = get_jwt_identity() or identity
        key = (endpoint, identity)
        now = time.monotonic()
        with guard:
            while windows and next(iter(windows.values()))['last'] < now - 3600:
                windows.popitem(last=False)
            if key not in windows and len(windows) >= 10000:
                return jsonify(message='请求繁忙，请稍后重试'), 429
            item = windows.setdefault(key, {'last': now, 'times': deque()})
            item['last'] = now
            windows.move_to_end(key)
            queue = item['times']
            while queue and queue[0] <= now - period:
                queue.popleft()
            if len(queue) >= maximum:
                return jsonify(message='操作过于频繁，请稍后重试'), 429, {'Retry-After': str(period)}
            queue.append(now)

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        if request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response
