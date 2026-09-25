import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from config import Config  # noqa: E402
from extensions import db  # noqa: E402
from flask_jwt_extended import create_access_token  # noqa: E402
from models import User  # noqa: E402
from rag.hybrid import rrf_merge  # noqa: E402
from rag.query_rewrite import expand_query  # noqa: E402
from rag.service import get_kb  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

RUBRIC = '''# 提问量表
教师提问后应留出三到五秒的候答时间，避免自问自答。
'''


@pytest.fixture
def app(tmp_path):
    class TestConfig(Config):
        TESTING = True
        SQLALCHEMY_DATABASE_URI = 'sqlite://'
        JWT_SECRET_KEY = 'test-rag-hybrid-secret-key-00000000'
        SEED_ON_STARTUP = False
        PUBLIC_DEPLOYMENT = False
        RAG_ENABLED = True
        RAG_STORAGE_DIR = str(tmp_path / 'rag')
        RAG_EMBEDDING_PROVIDER = 'local'
        RAG_HYBRID_ENABLED = True
        RAG_RERANK_ENABLED = False
        RAG_ASYNC_INGEST = False

    application = create_app(TestConfig)
    with application.app_context():
        db.create_all()
        db.session.add(User(account='teacher', password_hash=generate_password_hash('x'), name='t', role='teacher'))
        db.session.commit()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def auth():
    user = User.query.filter_by(account='teacher').one()
    return {'Authorization': f'Bearer {create_access_token(identity=str(user.id))}'}


def test_expand_query_adds_rubric_terms():
    out = expand_query('量表里候答怎么评', mode='expand')
    assert '候答' in out
    assert '评价' in out or '评分' in out


def test_rrf_merge_prefers_both_lists():
    fused = rrf_merge([(1, 0.9), (2, 0.8)], [(2, 5.0), (3, 4.0)], k=60)
    ids = [cid for cid, _ in fused]
    assert ids[0] == 2
    assert set(ids[:3]) == {1, 2, 3}


def test_retrieve_reports_hybrid(client):
    data = {'file': (io.BytesIO(RUBRIC.encode()), 'rubric.md')}
    resp = client.post('/api/rag/documents', data=data, headers=auth(), content_type='multipart/form-data')
    assert resp.status_code == 201
    body = client.post('/api/rag/retrieve', json={'query': '候答时间', 'hybrid': True}, headers=auth()).get_json()
    assert body['retrieval']['hybrid'] is True
    assert body['hits']
    assert body['hits'][0].get('bm25_score') is not None or body['hits'][0].get('vector_score') is not None


def test_async_upload_returns_202(client, monkeypatch):
    finished = []

    def fake_finish(_app, kb, *, data, filename, user_id, fields, on_done=None):
        doc = kb.create_processing_document(data, filename, user_id=user_id, **fields)
        db.session.commit()
        kb.finish_ingest(doc.id, data)
        finished.append(doc.id)
        return doc.to_dict()

    monkeypatch.setattr('rag.routes.schedule_ingest', fake_finish)
    resp = client.post(
        '/api/rag/documents',
        data={'file': (io.BytesIO(RUBRIC.encode()), 'a.md'), 'async': '1'},
        headers=auth(),
        content_type='multipart/form-data',
    )
    assert resp.status_code == 202
    assert finished
    assert get_kb().stats()['indexed_chunks'] >= 1
