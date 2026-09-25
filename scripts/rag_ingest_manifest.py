"""Ingest sources/rag/manifest.json via backend RAG CLI logic.

Usage (from repo root):
  python scripts/rag_export_knowledge_cards.py
  python scripts/rag_ingest_manifest.py
  python scripts/rag_ingest_manifest.py --priority P0
  python scripts/rag_ingest_manifest.py --dry-run
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'backend'
MANIFEST = ROOT / 'sources' / 'rag' / 'manifest.json'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, default=MANIFEST)
    parser.add_argument('--priority', help='Only ingest rows with this priority (e.g. P0)')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if not args.manifest.is_file():
        print(f'Manifest not found: {args.manifest}', file=sys.stderr)
        return 1
    rows = json.loads(args.manifest.read_text(encoding='utf-8'))
    if args.priority:
        rows = [row for row in rows if row.get('priority') == args.priority]
    if args.dry_run:
        for row in rows:
            print(row.get('path'), row.get('category'), row.get('title'))
        return 0

    sys.path.insert(0, str(BACKEND))
    from app import app, init_db  # noqa: E402
    from rag.embeddings import EmbeddingError  # noqa: E402
    from rag.parsing import ParseError  # noqa: E402
    from rag.service import DuplicateDocument, get_kb  # noqa: E402

    init_db()
    failures = 0
    with app.app_context():
        kb = get_kb()
        print(f'Embedding: {kb.embedder.signature} semantic={kb.embedder.semantic}')
        for row in rows:
            rel = row['path']
            path = ROOT / rel
            if not path.is_file():
                print(f'[skip] missing file: {rel}', file=sys.stderr)
                failures += 1
                continue
            tags = row.get('tags') or []
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.replace('，', ',').split(',') if t.strip()]
            try:
                document = kb.ingest(
                    path.read_bytes(),
                    path.name,
                    title=row.get('title'),
                    category=row.get('category', 'other'),
                    tags=tags,
                    source=row.get('source'),
                    description=row.get('description'),
                )
                print(f'[ok] #{document.id} {path.name}: {document.chunk_count} chunks')
            except DuplicateDocument as error:
                print(f'[dup] {path.name} -> #{error.document.id}')
            except (ParseError, EmbeddingError) as error:
                failures += 1
                print(f'[fail] {path.name}: {error}', file=sys.stderr)
        stats = kb.stats()
        print(json.dumps({
            'indexed_chunks': stats['indexed_chunks'],
            'stale_documents': stats['stale_documents'],
            'embedding': stats['embedding'],
        }, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
