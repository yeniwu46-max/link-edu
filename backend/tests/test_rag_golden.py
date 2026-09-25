"""Golden retrieval set for seeded classroom_knowledge corpus (local embedding, no LLM)."""
import json
import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from app import create_app  # noqa: E402
from config import Config  # noqa: E402
from extensions import db  # noqa: E402
from rag.embeddings import HashEmbedder  # noqa: E402
from rag.service import DuplicateDocument, get_kb  # noqa: E402
from services.classroom_reports import gather_report_references  # noqa: E402


class RagGoldenConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    JWT_SECRET_KEY = 'test-secret-for-rag-golden-retrieval-0000'
    SEED_ON_STARTUP = False
    RAG_ENABLED = True
    RAG_STORAGE_DIR = str(ROOT / 'tmp' / 'rag-golden-test')
    RAG_EMBEDDING_PROVIDER = 'local'
    RAG_MIN_SCORE = 0.08


def _ingest_p0():
    manifest = json.loads((ROOT / 'sources' / 'rag' / 'manifest.json').read_text(encoding='utf-8'))
    kb = get_kb()
    for row in manifest:
        if row.get('priority') != 'P0':
            continue
        path = ROOT / row['path']
        tags = row.get('tags') or []
        try:
            kb.ingest(path.read_bytes(), path.name, title=row.get('title'), category=row.get('category'),
                      tags=tags, source=row.get('source'))
        except DuplicateDocument:
            pass


class RagGoldenRetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(RagGoldenConfig)
        with cls.app.app_context():
            db.create_all()
            _ingest_p0()

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    def test_golden_retrieval_pass_rate(self):
        cases = json.loads((ROOT / 'evals' / 'rag_retrieval_golden.json').read_text(encoding='utf-8'))
        kb = get_kb()
        passed = 0
        for case in cases:
            result = kb.retrieve(case['query'], top_k=case.get('top_k', 5), categories=case.get('categories'))
            if case.get('expect_irrelevant'):
                ok = result['retrieval']['relevant_count'] == 0
            else:
                expect = case['expect']
                top = result['hits'][: case.get('check_top', 3)]
                ok = False
                for hit in top:
                    if not hit.get('relevant', True):
                        continue
                    title = hit['document']['title']
                    if expect.get('title_contains') and expect['title_contains'] not in title:
                        continue
                    if expect.get('category') and hit['document']['category'] != expect['category']:
                        continue
                    ok = True
                    break
            passed += int(ok)
        rate = passed / len(cases)
        self.assertGreaterEqual(rate, 0.65, f'golden pass rate {rate:.0%} below 65%')

    def test_reindex_clears_stale_signature(self):
        from rag.settings import load_settings
        from rag.vector_store import build_store
        kb = get_kb()
        kb.embedder = HashEmbedder(dim=512)
        kb.store = build_store(load_settings(), kb.embedder.signature, kb.embedder.dim)
        stale = kb.stale_documents()
        self.assertGreaterEqual(len(stale), 1)
        for document in stale:
            kb.reindex(document)
        self.assertEqual(kb.stale_documents(), [])
        self.assertGreater(kb.store.size(), 0)

    def test_classroom_report_merges_kb_sources(self):
        refs = gather_report_references('平均分 分数')
        legacy = [r for r in refs if not str(r['id']).startswith('kb:')]
        kb_refs = [r for r in refs if str(r['id']).startswith('kb:')]
        self.assertTrue(legacy, 'BM25 legacy cards should remain')
        self.assertTrue(kb_refs, 'RAG chunks should appear when KB is seeded')
        self.assertTrue(all('location' in r for r in kb_refs))


if __name__ == '__main__':
    unittest.main()
