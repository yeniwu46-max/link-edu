import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from config import Config  # noqa: E402
from extensions import db  # noqa: E402
from flask_jwt_extended import create_access_token  # noqa: E402
from models import User  # noqa: E402
from rag.graph_index import KnowledgeGraphIndex  # noqa: E402
from rag.graph_meta import build_graph_extra  # noqa: E402
from rag.models import KnowledgeChunk  # noqa: E402
from rag.service import get_kb  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402


MISCONCEPTION = ('小雨可能认为分母4比2大，所以四分之一更大。教师可以用同样大小纸片分别二等分和四等分，'
                '引导比较一份。小明可以追问：不同大小蛋糕的一半一样多吗？')
RELATED = '用同样大小纸片观察平均分，比较单位分数的大小。'


def make_app(tmp_path):
    class TestConfig(Config):
        TESTING = True
        SQLALCHEMY_DATABASE_URI = 'sqlite://'
        JWT_SECRET_KEY = 'test-rag-graph-secret-key-0000000000'
        SEED_ON_STARTUP = False
        PUBLIC_DEPLOYMENT = False
        RAG_ENABLED = True
        RAG_STORAGE_DIR = str(tmp_path / 'rag')
        RAG_EMBEDDING_PROVIDER = 'local'
        RAG_HYBRID_ENABLED = True
        RAG_RERANK_ENABLED = False
        RAG_GRAPH_ENABLED = False
        RAG_ASYNC_INGEST = False

    return create_app(TestConfig)


def test_graph_metadata_has_stable_entities_and_only_source_cued_relations():
    first = build_graph_extra('学生误解与追问', [], ['微格'], MISCONCEPTION)['graph']
    second = build_graph_extra('学生误解与追问', [], ['微格'], MISCONCEPTION)['graph']
    assert first == second
    assert first['schema_version'] == 1
    assert 'misconception:denominator_order' in {item['id'] for item in first['entities']}
    assert any(edge['type'] == 'addresses' and edge['cue'] in MISCONCEPTION for edge in first['relations'])
    unsupported = build_graph_extra('无关系', [], [], '分母越大分数越大。')['graph']
    assert not any(edge['type'] == 'addresses' for edge in unsupported['relations'])


def test_graph_index_expands_evidence_paths_and_obeys_document_filters(tmp_path):
    app = make_app(tmp_path)
    with app.app_context():
        db.create_all()
        user = User(account='teacher', password_hash=generate_password_hash('x'), name='t', role='teacher')
        db.session.add(user)
        db.session.commit()
        kb = get_kb()
        source = kb.ingest(MISCONCEPTION.encode(), 'misconception.md', title='学生误解与追问',
                           category='case', tags=['分数', '微格'])
        related = kb.ingest(RELATED.encode(), 'equal-partition.md', title='平均分练习',
                            category='theory', tags=['分数'])
        source_chunk = KnowledgeChunk.query.filter_by(document_id=source.id).first()
        index = KnowledgeGraphIndex(kb.embedder.signature)
        result = index.search('分母4比2大，如何用纸片纠正？', top_k=20)
        related_ids = {chunk.id for chunk in KnowledgeChunk.query.filter_by(document_id=related.id)}
        assert related_ids.intersection(dict(result['ranked']))
        path = result['paths'][next(iter(related_ids.intersection(result['paths'])) )][0]
        assert source_chunk.id in path['source_chunk_ids']
        assert path['relations'][0]['cue'] in source_chunk.text

        filtered = index.search('分母4比2大，如何用纸片纠正？', top_k=20, categories=['case'])
        filtered_ids = set(dict(filtered['ranked']))
        assert not filtered_ids.intersection(related_ids)
        scoped = index.search('分母4比2大，如何用纸片纠正？', top_k=20, document_ids=[source.id])
        assert not set(dict(scoped['ranked'])).intersection(related_ids)
        assert index.stats()['relation_count'] > 0
        db.session.remove()
        db.drop_all()


def test_retrieve_graph_flag_defaults_off_and_returns_traceable_paths(tmp_path):
    app = make_app(tmp_path)
    with app.app_context():
        db.create_all()
        db.session.add(User(account='teacher', password_hash=generate_password_hash('x'), name='t', role='teacher'))
        db.session.commit()
        kb = get_kb()
        kb.ingest(MISCONCEPTION.encode(), 'misconception.md', title='学生误解与追问',
                  category='case', tags=['分数', '微格'])
        query = '分母4比2大，怎么用同样大小纸片纠正并追问？'
        off = kb.retrieve(query)
        on = kb.retrieve(query, graph=True)
        assert off['retrieval']['graph']['enabled'] is False
        assert on['retrieval']['graph']['enabled'] is True
        assert any(hit.get('graph_paths') for hit in on['hits'])
        for hit in on['hits']:
            for path in hit.get('graph_paths', []):
                for chunk_id in path['source_chunk_ids']:
                    source = db.session.get(KnowledgeChunk, chunk_id)
                    assert source is not None
                    assert any(relation['cue'] in source.text for relation in path['relations'])
        db.session.remove()
        db.drop_all()


def test_graph_rebuild_refreshes_metadata_without_reembedding(tmp_path, monkeypatch):
    app = make_app(tmp_path)
    with app.app_context():
        db.create_all()
        db.session.add(User(account='teacher', password_hash=generate_password_hash('x'), name='t', role='teacher'))
        db.session.commit()
        kb = get_kb()
        doc = kb.ingest(MISCONCEPTION.encode(), 'misconception.md', title='学生误解与追问')
        chunk = KnowledgeChunk.query.filter_by(document_id=doc.id).first()
        old = dict(chunk.extra)
        monkeypatch.setattr(kb.embedder, 'embed_documents', lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError()))
        result = kb.rebuild_graph_metadata()
        db.session.refresh(chunk)
        assert result == {'documents': 1, 'chunks': 1}
        assert chunk.extra['graph']['schema_version'] == 1
        assert chunk.extra['parent_summary'] == old.get('parent_summary')
        db.session.remove()
        db.drop_all()


def test_graph_index_refreshes_for_inactive_and_expired_documents(tmp_path):
    app = make_app(tmp_path)
    with app.app_context():
        db.create_all()
        db.session.add(User(account='teacher', password_hash=generate_password_hash('x'), name='t', role='teacher'))
        db.session.commit()
        kb = get_kb()
        doc = kb.ingest(MISCONCEPTION.encode(), 'misconception.md', title='学生误解与追问')
        index = KnowledgeGraphIndex(kb.embedder.signature)
        first = index.search('分母4比2大如何纠正', top_k=10)
        assert first['ranked']

        doc.is_active = False
        db.session.commit()
        inactive = index.search('分母4比2大如何纠正', top_k=10)
        assert not inactive['ranked']

        doc.is_active = True
        doc.valid_until = (date.today() - timedelta(days=1)).isoformat()
        db.session.commit()
        expired = index.search('分母4比2大如何纠正', top_k=10)
        assert not expired['ranked']
        db.session.remove()
        db.drop_all()


def test_retrieve_route_rejects_non_boolean_graph_value(tmp_path):
    app = make_app(tmp_path)
    with app.app_context():
        db.create_all()
        user = User(account='teacher', password_hash=generate_password_hash('x'), name='t', role='teacher')
        db.session.add(user)
        db.session.commit()
        token = create_access_token(identity=str(user.id))
        response = app.test_client().post('/api/rag/retrieve', json={'query': '分数', 'graph': 'yes'},
                                          headers={'Authorization': f'Bearer {token}'})
        assert response.status_code == 400
        db.session.remove()
        db.drop_all()


def test_retrieve_route_accepts_request_level_graph_toggle(tmp_path):
    app = make_app(tmp_path)
    with app.app_context():
        db.create_all()
        user = User(account='teacher', password_hash=generate_password_hash('x'), name='t', role='teacher')
        db.session.add(user)
        db.session.commit()
        get_kb().ingest(MISCONCEPTION.encode(), 'misconception.md', title='学生误解与追问',
                        category='case', tags=['分数'])
        token = create_access_token(identity=str(user.id))
        response = app.test_client().post(
            '/api/rag/retrieve', json={'query': '分母4比2大，如何用纸片纠正？', 'graph': True},
            headers={'Authorization': f'Bearer {token}'})
        assert response.status_code == 200
        payload = response.get_json()
        assert payload['retrieval']['graph']['enabled'] is True
        assert any(hit.get('graph_paths') for hit in payload['hits'])
        db.session.remove()
        db.drop_all()


def test_graph_cache_detects_metadata_change_without_timestamp_change(tmp_path):
    app = make_app(tmp_path)
    with app.app_context():
        db.create_all()
        kb = get_kb()
        doc = kb.ingest(MISCONCEPTION.encode(), 'cache.md', title='学生误解与追问')
        chunk = KnowledgeChunk.query.filter_by(document_id=doc.id).first()
        extra = dict(chunk.extra)
        timestamp = doc.updated_at
        index = KnowledgeGraphIndex(kb.embedder.signature)
        assert index.search('分母4比2大')['ranked']
        chunk.extra = {key: value for key, value in extra.items() if key != 'graph'}
        db.session.commit()
        assert doc.updated_at == timestamp
        assert not index.search('分母4比2大')['ranked']
        chunk.extra = extra
        db.session.commit()
        assert index.search('分母4比2大')['ranked']
        db.session.remove()
        db.drop_all()


def test_expired_source_cannot_be_opened_from_a_stale_graph_path(tmp_path):
    app = make_app(tmp_path)
    with app.app_context():
        db.create_all()
        doc = get_kb().ingest(MISCONCEPTION.encode(), 'expired.md', title='学生误解与追问')
        chunk = KnowledgeChunk.query.filter_by(document_id=doc.id).first()
        source_id = chunk.id
        token = create_access_token(identity='1')
        headers = {'Authorization': f'Bearer {token}'}
        client = app.test_client()
        assert client.get(f'/api/rag/chunks/{source_id}', headers=headers).status_code == 200
        doc.valid_until = (date.today() - timedelta(days=1)).isoformat()
        db.session.commit()
        assert client.get(f'/api/rag/chunks/{source_id}', headers=headers).status_code == 404
        db.session.remove()
        db.drop_all()


def test_graph_failure_reports_fallback_and_preserves_results(tmp_path, monkeypatch):
    app = make_app(tmp_path)
    with app.app_context():
        db.create_all()
        kb = get_kb()
        kb.ingest(MISCONCEPTION.encode(), 'fallback.md', title='学生误解与追问')
        off = kb.retrieve('分母4比2大怎么纠正', graph=False)
        def fail(*args, **kwargs):
            raise RuntimeError('injected graph failure')
        monkeypatch.setattr(kb._graph, 'search', fail)
        result = kb.retrieve('分母4比2大怎么纠正', graph=True)
        assert result['hits'] == off['hits']
        assert result['retrieval']['graph']['fallback'] is True
        assert result['retrieval']['graph']['error'] == 'graph_retrieval_failed'
        db.session.remove()
        db.drop_all()
