"""Operator CLI (run from backend/):

    python -m rag.cli ingest 资料目录或文件... --category rubric [--source 出处] [--tags 提问,量表]
    python -m rag.cli reindex [--all | 文档ID...]      # after switching embedding model/dimension
    python -m rag.cli query "如何评价课堂提问的有效性" [--top-k 5] [--answer]
    python -m rag.cli stats
"""
import argparse
import json
import sys
from pathlib import Path


def _print(value):
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def _files(paths):
    suffixes = {'.pdf', '.docx', '.txt', '.md', '.markdown'}
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            yield from sorted(p for p in path.rglob('*') if p.suffix.lower() in suffixes)
        elif path.is_file():
            yield path


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m rag.cli')
    sub = parser.add_subparsers(dest='command', required=True)
    ingest = sub.add_parser('ingest')
    ingest.add_argument('paths', nargs='+')
    ingest.add_argument('--category', default='other')
    ingest.add_argument('--source')
    ingest.add_argument('--tags', default='')
    reindex = sub.add_parser('reindex')
    reindex.add_argument('ids', nargs='*', type=int)
    reindex.add_argument('--all', action='store_true', help='重建全部；默认只重建模型签名过期的文档')
    sub.add_parser('graph-rebuild', help='仅重建图谱元数据，不调用 Embedding')
    query = sub.add_parser('query')
    query.add_argument('text')
    query.add_argument('--top-k', type=int)
    query.add_argument('--answer', action='store_true', help='调用 LLM 生成回答（会产生费用）')
    sub.add_parser('stats')
    args = parser.parse_args(argv)

    from app import app, init_db
    from rag.embeddings import EmbeddingError
    from rag.models import KnowledgeDocument
    from rag.parsing import ParseError
    from rag.service import DuplicateDocument, get_kb

    init_db()
    with app.app_context():
        kb = get_kb()
        if args.command == 'ingest':
            tags = [t for t in args.tags.split(',') if t.strip()]
            failures = 0
            for path in _files(args.paths):
                try:
                    document = kb.ingest(path.read_bytes(), path.name, category=args.category,
                                         source=args.source, tags=tags)
                    print(f'[入库] {path.name}: {document.chunk_count} 个切片')
                except DuplicateDocument as error:
                    print(f'[跳过] {path.name}: 已存在 (#{error.document.id})')
                except (ParseError, EmbeddingError) as error:
                    failures += 1
                    print(f'[失败] {path.name}: {error}', file=sys.stderr)
            return 1 if failures else 0
        if args.command == 'reindex':
            if args.ids:
                documents = KnowledgeDocument.query.filter(KnowledgeDocument.id.in_(args.ids)).all()
            elif args.all:
                documents = KnowledgeDocument.query.filter(KnowledgeDocument.status != 'processing').all()
            else:
                documents = kb.stale_documents()
            for document in documents:
                try:
                    kb.reindex(document)
                    print(f'[重建] #{document.id} {document.title}: {document.chunk_count} 个切片')
                except (ParseError, EmbeddingError) as error:
                    print(f'[失败] #{document.id} {document.title}: {error}', file=sys.stderr)
            return 0
        if args.command == 'graph-rebuild':
            _print(kb.rebuild_graph_metadata())
            return 0
        if args.command == 'query':
            _print(kb.query(args.text, generate=args.answer, top_k=args.top_k))
            return 0
        _print(kb.stats())
        return 0


if __name__ == '__main__':
    sys.exit(main())
