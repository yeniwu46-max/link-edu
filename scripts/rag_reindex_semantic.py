"""Switch to DashScope semantic embeddings and rebuild all document vectors.

Requires in backend/.env or environment:
  RAG_EMBEDDING_PROVIDER=openai_compatible
  RAG_EMBEDDING_MODEL=text-embedding-v4
  RAG_EMBEDDING_DIM=1024
  DASHSCOPE_API_KEY or RAG_EMBEDDING_API_KEY
  AI_PRICING_CONFIRMED=true
  RAG_EMBEDDING_CNY_PER_MILLION=<verified rate>

Usage (from backend/):
  python ../scripts/rag_reindex_semantic.py
  python ../scripts/rag_reindex_semantic.py --dry-run
"""
import argparse
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / 'backend'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    required = (
        'RAG_EMBEDDING_PROVIDER',
        'RAG_EMBEDDING_MODEL',
        'RAG_EMBEDDING_DIM',
        'AI_PRICING_CONFIRMED',
        'RAG_EMBEDDING_CNY_PER_MILLION',
    )
    missing = [name for name in required if not os.getenv(name, '').strip()]
    if os.getenv('RAG_EMBEDDING_PROVIDER', '').lower() != 'openai_compatible':
        missing.append('RAG_EMBEDDING_PROVIDER=openai_compatible')
    if not os.getenv('RAG_EMBEDDING_API_KEY', '').strip() and not os.getenv('DASHSCOPE_API_KEY', '').strip():
        missing.append('DASHSCOPE_API_KEY or RAG_EMBEDDING_API_KEY')
    if missing:
        print('缺少或未正确配置：', ', '.join(missing), file=sys.stderr)
        print('请对照 backend/.env.example 与 deploy/runtime.env.example', file=sys.stderr)
        return 1
    if args.dry_run:
        stale = os.getenv('RAG_EMBEDDING_MODEL')
        print(f'将使用 {stale} 执行 python -m rag.cli reindex --all')
        return 0
    sys.path.insert(0, str(BACKEND))
    from app import app, init_db  # noqa: E402
    from rag.cli import main as cli_main  # noqa: E402

    init_db()
    with app.app_context():
        from rag.service import get_kb  # noqa: E402
        kb = get_kb()
        if not kb.embedder.semantic:
            print('当前 Embedding 不是语义模型，请检查 RAG_EMBEDDING_PROVIDER', file=sys.stderr)
            return 1
        print(f'目标签名: {kb.embedder.signature}')
        print(f'待重建文档: {len(kb.stale_documents())} stale + ready 全量')
    return cli_main(['reindex', '--all'])


if __name__ == '__main__':
    sys.exit(main())
