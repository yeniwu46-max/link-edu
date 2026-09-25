"""Run golden retrieval queries against the loaded knowledge base (no LLM cost).

Usage:
  python scripts/rag_eval_retrieval.py
  python scripts/rag_eval_retrieval.py --json evals/rag_retrieval_golden.json
"""
import argparse
import json
import sys
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--json', type=Path, default=DEFAULT)
    parser.add_argument('--min-pass-rate', type=float, default=0.8)
    args = parser.parse_args()
    cases = json.loads(args.json.read_text(encoding='utf-8'))
    sys.path.insert(0, str(BACKEND))
    from app import app, init_db  # noqa: E402
    from rag.service import get_kb  # noqa: E402

    init_db()
    passed = 0
    with app.app_context():
        kb = get_kb()
        for case in cases:
            query = case['query']
            result = kb.retrieve(query, top_k=case.get('top_k', 5), categories=case.get('categories'))
            hits = result['hits']
            if case.get('expect_irrelevant'):
                ok = result['retrieval']['relevant_count'] == 0
            else:
                expect = case.get('expect', {})
                top = hits[: case.get('check_top', 3)]
                ok = any(match_hit(hit, expect) for hit in top if hit.get('relevant', True))
            status = 'PASS' if ok else 'FAIL'
            print(f'{status}  {query[:48]}')
            if not ok and hits:
                print('   top:', hits[0]['document']['title'], hits[0].get('similarity'))
            passed += int(ok)
    rate = passed / len(cases) if cases else 1
    print(f'Summary: {passed}/{len(cases)} ({rate:.0%})')
    return 0 if rate >= args.min_pass_rate else 1


if __name__ == '__main__':
    sys.exit(main())
