"""Run golden retrieval queries against the loaded knowledge base (no LLM cost).

Usage:
  python scripts/rag_eval_retrieval.py
  python scripts/rag_eval_retrieval.py --json evals/rag_retrieval_golden.json
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'backend'
DEFAULT = ROOT / 'evals' / 'rag_retrieval_golden.json'


def match_hit(hit, expect):
    title = hit['document']['title']
    if expect.get('title_contains') and expect['title_contains'] not in title:
        return False
    if expect.get('category') and hit['document']['category'] != expect['category']:
        return False
    if expect.get('section_contains'):
        section = hit.get('section') or ''
        if expect['section_contains'] not in section:
            return False
    return True


def evaluate_cases(kb, cases, *, graph=False):
    """Keep the golden set's relevance gate and ranking cutoff identical for both modes."""
    rows = []
    for case in cases:
        started = time.perf_counter()
        result = kb.retrieve(case['query'], top_k=case.get('top_k', 5),
                             categories=case.get('categories'), document_ids=case.get('document_ids'),
                             graph=graph)
        elapsed_ms = (time.perf_counter() - started) * 1000
        ranks = [rank for rank, hit in enumerate(result['hits'][:5], 1)
                 if hit.get('relevant', True) and match_hit(hit, case.get('expect', {}))]
        rank = ranks[0] if ranks else None
        passed = (result['retrieval']['relevant_count'] == 0 if case.get('expect_irrelevant')
                  else rank is not None and rank <= case.get('check_top', 3))
        rows.append({'query': case['query'], 'expect_irrelevant': bool(case.get('expect_irrelevant')),
                     'passed': passed, 'rank_at_5': None if case.get('expect_irrelevant') else rank,
                     'elapsed_ms': round(elapsed_ms, 3), 'result': result})
    return rows


def summarize(rows):
    positive = [row for row in rows if not row['expect_irrelevant']]
    times = sorted(row['elapsed_ms'] for row in rows)
    return {
        'passed': sum(row['passed'] for row in rows), 'total': len(rows),
        'pass_rate': sum(row['passed'] for row in rows) / len(rows) if rows else 0.0,
        'recall_at_5': sum(row['rank_at_5'] is not None for row in positive) / len(positive) if positive else 0.0,
        'mrr_at_5': sum(1 / row['rank_at_5'] for row in positive if row['rank_at_5']) / len(positive) if positive else 0.0,
        'latency_ms': {'mean': sum(times) / len(times) if times else 0.0,
                       'p95': times[max(0, (95 * len(times) + 99) // 100 - 1)] if times else 0.0,
                       'first_query': rows[0]['elapsed_ms'] if rows else None},
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--json', type=Path, default=DEFAULT)
    parser.add_argument('--min-pass-rate', type=float, default=0.8)
    parser.add_argument('--report', type=Path, help='Write scores and retrieved chunk IDs as JSON')
    args = parser.parse_args(argv)
    cases = json.loads(args.json.read_text(encoding='utf-8'))
    sys.path.insert(0, str(BACKEND))
    from app import app, init_db  # noqa: E402
    from rag.service import get_kb  # noqa: E402

    init_db()
    with app.app_context():
        kb = get_kb()
        if kb.settings.query_rewrite == 'hyde':
            parser.error('HyDE calls an LLM; use RAG_QUERY_REWRITE=expand or off for offline evaluation')
        rows = evaluate_cases(kb, cases, graph=False)
        stats = kb.stats()
    metrics = summarize(rows)
    for row in rows:
        print(f"{'PASS' if row['passed'] else 'FAIL'}  {row['query'][:48]}")
        hits = row['result']['hits']
        if not row['passed'] and hits:
            print('   top:', hits[0]['document']['title'], hits[0].get('similarity'))
    passed = bool(rows) and metrics['pass_rate'] >= args.min_pass_rate
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps({'passed': passed, 'graph': False,
                                          'threshold': args.min_pass_rate, 'metrics': metrics,
                                          'knowledge_base': stats, 'cases': rows},
                                         ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Summary: {metrics['passed']}/{metrics['total']} ({metrics['pass_rate']:.1%})")
    print(f"Recall@5: {metrics['recall_at_5']:.1%}; MRR@5: {metrics['mrr_at_5']:.3f}")
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
