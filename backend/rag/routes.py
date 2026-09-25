"""/api/rag endpoints. Management needs RAG_ADMIN_ACCOUNTS in public deployments because the
login form lets users pick their own role."""
from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.formparser import parse_form_data

from extensions import db
from models import User
from rag.embeddings import EmbeddingError
from rag.evaluation import evaluate_lesson
from rag.models import KnowledgeChunk, KnowledgeDocument
from rag.parsing import ParseError
from rag.governance import KnowledgeAuditLog, log_audit
from rag.jobs import schedule_ingest
from rag.service import DuplicateDocument, get_kb
from rag.settings import CATEGORIES, FILE_TYPES

bp = Blueprint('rag', __name__, url_prefix='/api/rag')


@bp.before_request
def guard():
    try:
        kb = get_kb()
    except (ValueError, RuntimeError) as error:
        return jsonify(message=f'知识库配置错误：{error}'), 503
    if not kb.settings.enabled:
        return jsonify(message='知识库功能未启用'), 404
    if request.method in ('POST', 'PATCH') and request.endpoint != 'rag.upload_document':
        body = request.get_json(silent=True)
        if body is not None and not isinstance(body, dict):
            return jsonify(message='请求必须是JSON对象'), 400


@bp.after_request
def private_headers(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


def _user():
    return db.session.get(User, int(get_jwt_identity()))


def _can_manage(user):
    settings = get_kb().settings
    if settings.admin_accounts:
        return user is not None and user.account in settings.admin_accounts
    return user is not None and user.role == 'teacher' and not current_app.config.get('PUBLIC_DEPLOYMENT')


def _forbidden():
    return jsonify(message='仅知识库管理员可以维护资料'), 403


def _document(document_id):
    document = db.session.get(KnowledgeDocument, document_id)
    if document is None:
        return None, (jsonify(message='资料不存在'), 404)
    return document, None


def _body():
    return request.get_json(silent=True) or {}


def _categories(value):
    if value in (None, '', []):
        return None
    values = value.split(',') if isinstance(value, str) else value
    if not isinstance(values, list) or any(not isinstance(v, str) or v.strip() not in CATEGORIES for v in values):
        raise ValueError('categories 包含无效分类')
    return [v.strip() for v in values]


def _ids(value):
    if value in (None, []):
        return None
    if not isinstance(value, list) or any(type(v) is not int for v in value):
        raise ValueError('document_ids 必须是整数数组')
    return value


def _tags(value):
    if isinstance(value, str):
        value = value.replace('，', ',').split(',')
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()]


def _filters(data):
    return {
        'top_k': data.get('top_k'),
        'categories': _categories(data.get('categories')),
        'document_ids': _ids(data.get('document_ids')),
        'min_score': data.get('min_score'),
        'hybrid': data.get('hybrid'),
        'rerank': data.get('rerank'),
        'rewrite': data.get('rewrite'),
    }


def _truthy(value):
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    return str(value).lower() in ('1', 'true', 'yes', 'on')


def _governance_fields(form):
    fields = {}
    if form.get('content_version'):
        fields['content_version'] = str(form.get('content_version')).strip()[:32]
    if form.get('license_note'):
        fields['license_note'] = str(form.get('license_note')).strip()[:255]
    if form.get('valid_until'):
        fields['valid_until'] = str(form.get('valid_until')).strip()[:10]
    return fields


def _question(data):
    value = data.get('query', data.get('question'))
    if not isinstance(value, str) or not value.strip():
        raise ValueError('请提供检索问题 query')
    return value


def _service_error(error):
    return jsonify(message=str(error)), 502


@bp.get('/status')
@jwt_required()
def status():
    kb = get_kb()
    return jsonify(**kb.stats(), can_manage=_can_manage(_user()),
                   categories=CATEGORIES, file_types=FILE_TYPES,
                   max_upload_mb=kb.settings.max_upload_bytes // 1024 // 1024)


@bp.get('/categories')
@jwt_required()
def categories():
    return jsonify(items=[{'key': k, 'label': v} for k, v in CATEGORIES.items()])


@bp.post('/documents')
@jwt_required()
def upload_document():
    if not _can_manage(_user()):
        return _forbidden()
    limit = get_kb().settings.max_upload_bytes
    try:
        # Parsed directly so uploads get their own limit instead of the app-wide MAX_CONTENT_LENGTH.
        _, form, files = parse_form_data(request.environ, max_content_length=limit, silent=False)
    except RequestEntityTooLarge:
        return jsonify(message=f'文件超过 {limit // 1024 // 1024} MB 上限'), 413
    except ValueError:
        return jsonify(message='上传表单无效'), 400
    upload = files.get('file')
    if upload is None or not upload.filename:
        return jsonify(message='请选择要上传的文件（表单字段 file）'), 400
    raw = upload.read()
    user_id = int(get_jwt_identity())
    fields = {
        'title': (form.get('title') or '').strip() or None,
        'category': (form.get('category') or 'other').strip(),
        'tags': _tags(form.get('tags')),
        'source': (form.get('source') or '').strip() or None,
        'description': (form.get('description') or '').strip() or None,
        **_governance_fields(form),
    }
    kb = get_kb()
    use_async = _truthy(form.get('async')) or (
        kb.settings.async_ingest_default and not _truthy(form.get('sync')))
    if use_async:
        try:
            brief = schedule_ingest(
                current_app._get_current_object(), kb,
                data=raw, filename=upload.filename, user_id=user_id, fields=fields)
        except DuplicateDocument as error:
            return jsonify(message=str(error), document=error.document.to_dict()), 409
        except ParseError as error:
            return jsonify(message=str(error)), 422
        return jsonify(message='资料已排队入库', document=brief, async_job=True), 202
    try:
        document = kb.ingest(raw, upload.filename, user_id=user_id, **fields)
    except DuplicateDocument as error:
        return jsonify(message=str(error), document=error.document.to_dict()), 409
    except (ParseError, EmbeddingError) as error:
        failed = getattr(error, 'document', None)
        return jsonify(message=str(error), document=failed.to_dict() if failed else None), \
            422 if isinstance(error, ParseError) else 502
    return jsonify(message='资料已入库', document=document.to_dict()), 201


@bp.get('/documents')
@jwt_required()
def list_documents():
    query = KnowledgeDocument.query
    category = request.args.get('category')
    if category:
        query = query.filter_by(category=category)
    status_value = request.args.get('status')
    if status_value:
        query = query.filter_by(status=status_value)
    keyword = (request.args.get('q') or '').strip()
    if keyword:
        query = query.filter(KnowledgeDocument.title.contains(keyword))
    page = max(1, request.args.get('page', 1, type=int))
    size = max(1, min(request.args.get('page_size', 20, type=int), 100))
    total = query.count()
    rows = query.order_by(KnowledgeDocument.created_at.desc(), KnowledgeDocument.id.desc()) \
        .offset((page - 1) * size).limit(size).all()
    return jsonify(items=[row.to_dict() for row in rows], total=total, page=page, page_size=size)


@bp.get('/documents/<int:document_id>')
@jwt_required()
def get_document(document_id):
    document, error = _document(document_id)
    return error or jsonify(document=document.to_dict())


@bp.patch('/documents/<int:document_id>')
@jwt_required()
def update_document(document_id):
    if not _can_manage(_user()):
        return _forbidden()
    document, error = _document(document_id)
    if error:
        return error
    data = _body()
    if 'category' in data:
        if data['category'] not in CATEGORIES:
            return jsonify(message='知识分类无效'), 400
        document.category = data['category']
    for field, limit in (('title', 200), ('source', 255)):
        if field in data:
            if not isinstance(data[field], str) or (field == 'title' and not data[field].strip()):
                return jsonify(message=f'{field} 无效'), 400
            setattr(document, field, data[field].strip()[:limit] or None)
    if 'description' in data:
        document.description = str(data['description'] or '').strip() or None
    if 'tags' in data:
        document.tags = _tags(data['tags'])[:20]
    if 'is_active' in data:
        if not isinstance(data['is_active'], bool):
            return jsonify(message='is_active 必须是布尔值'), 400
        document.is_active = data['is_active']
    for field, limit in (('content_version', 32), ('license_note', 255), ('valid_until', 10)):
        if field in data:
            value = str(data[field] or '').strip()
            setattr(document, field, value[:limit] or None)
    if data.get('record_audit'):
        from datetime import datetime
        document.last_audited_at = datetime.utcnow()
        log_audit(document.id, 'governance_review', actor_id=int(get_jwt_identity()),
                  content_version=document.content_version)
    db.session.commit()
    get_kb()._invalidate_indexes()
    return jsonify(document=document.to_dict())


@bp.delete('/documents/<int:document_id>')
@jwt_required()
def delete_document(document_id):
    if not _can_manage(_user()):
        return _forbidden()
    document, error = _document(document_id)
    if error:
        return error
    get_kb().delete(document)
    return jsonify(message='资料已删除')


@bp.post('/documents/<int:document_id>/reindex')
@jwt_required()
def reindex_document(document_id):
    if not _can_manage(_user()):
        return _forbidden()
    document, error = _document(document_id)
    if error:
        return error
    try:
        get_kb().reindex(document)
    except ParseError as error:
        return jsonify(message=str(error), document=document.to_dict()), 422
    except EmbeddingError as error:
        return _service_error(error)
    return jsonify(message='已重新切片并向量化', document=document.to_dict())


@bp.get('/documents/<int:document_id>/chunks')
@jwt_required()
def list_chunks(document_id):
    document, error = _document(document_id)
    if error:
        return error
    offset = max(0, request.args.get('offset', 0, type=int))
    limit = max(1, min(request.args.get('limit', 50, type=int), 200))
    rows = KnowledgeChunk.query.filter_by(document_id=document.id).order_by(KnowledgeChunk.ordinal) \
        .offset(offset).limit(limit).all()
    return jsonify(document=document.to_dict(), items=[row.to_dict(include_extra=True) for row in rows],
                   total=document.chunk_count, offset=offset, limit=limit)


@bp.get('/chunks/<int:chunk_id>')
@jwt_required()
def get_chunk(chunk_id):
    chunk = db.session.get(KnowledgeChunk, chunk_id)
    if chunk is None or not chunk.document.is_active:
        return jsonify(message='切片不存在'), 404
    return jsonify(chunk=chunk.to_dict(include_extra=True), document=chunk.document.to_dict())


@bp.get('/audit')
@jwt_required()
def list_audit():
    if not _can_manage(_user()):
        return _forbidden()
    document_id = request.args.get('document_id', type=int)
    query = KnowledgeAuditLog.query
    if document_id:
        query = query.filter_by(document_id=document_id)
    page = max(1, request.args.get('page', 1, type=int))
    size = max(1, min(request.args.get('page_size', 30, type=int), 100))
    total = query.count()
    rows = query.order_by(KnowledgeAuditLog.created_at.desc(), KnowledgeAuditLog.id.desc()) \
        .offset((page - 1) * size).limit(size).all()
    return jsonify(items=[row.to_dict() for row in rows], total=total, page=page, page_size=size)


@bp.post('/retrieve')
@jwt_required()
def retrieve():
    """Retrieval only (no LLM call, no model cost) - for tuning chunking, thresholds and filters."""
    data = _body()
    try:
        return jsonify(get_kb().retrieve(_question(data), **_filters(data)))
    except (ValueError, TypeError) as error:
        return jsonify(message=str(error)), 400
    except EmbeddingError as error:
        return _service_error(error)


@bp.post('/query')
@jwt_required()
def query():
    data = _body()
    try:
        question = _question(data)
        filters = _filters(data)
    except (ValueError, TypeError) as error:
        return jsonify(message=str(error)), 400
    try:
        return jsonify(get_kb().query(question, generate=data.get('generate', True) is not False, **filters))
    except (ValueError, TypeError) as error:
        return jsonify(message=str(error)), 400
    except EmbeddingError as error:
        return _service_error(error)


@bp.post('/evaluate')
@jwt_required()
def evaluate():
    data = _body()
    try:
        data['categories'] = _categories(data.get('categories'))
        return jsonify(evaluate_lesson(get_kb(), data))
    except (ValueError, TypeError) as error:
        return jsonify(message=str(error)), 400
    except EmbeddingError as error:
        return _service_error(error)

