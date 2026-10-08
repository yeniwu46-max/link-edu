"""Compare graph retrieval with a fixed no-graph baseline; never call a generation LLM."""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'backend'
DEFAULT = ROOT / 'evals' / 'rag_graph_golden.json'
sys.path.insert(0, str(ROOT))
from scripts.rag_eval_retrieval import evaluate_cases, summarize  # noqa: E402


def matches(hit, expected):
    document = hit.get('document') or {}
    return (hit.get('relevant', True)
            and (not expected.get('title_contains') or expected['title_contains'] in document.get('title', ''))
            and (not expected.get('text_contains') or expected['text_contains'] in hit.get('text', ''))
            and (not expected.get('category') or expected['category'] == document.get('category')))


def path_is_valid(hit, path, sources, *, categories=None, document_ids=None):
    """Check every edge, direction, endpoint, source and filter, not just cue presence."""
    def allowed(source):
        return (source and source['eligible']
                and (not categories or source['category'] in categories)
                and (not document_ids or source['document_id'] in document_ids))

    target = sources.get(hit['chunk_id'])
    entities = [entity.get('id') for entity in path.get('entities', [])]
    relations = path.get('relations') or []
    if (not allowed(target) or not relations or len(entities) != len(relations) + 1
            or path.get('depth') != len(relations) or len(set(entities)) != len(entities)
            or path.get('target_chunk_id') != hit['chunk_id']):
        return False
    if entities[-1] not in {entry.get('id') for entry in target['graph'].get('entities', [])}:
        return False
    ids = {edge.get('source_chunk_id') for edge in relations}
    if set(path.get('source_chunk_ids') or []) != ids:
        return False
    for index, relation in enumerate(relations):
        source = sources.get(relation.get('source_chunk_id'))
        cue = relation.get('cue')
        if not allowed(source) or not cue or cue not in source['text']:
            return False
        start, end = entities[index:index + 2]
        if relation.get('reverse'):
            start, end = end, start
        if not any(edge.get('from') == start and edge.get('to') == end
                   and edge.get('type') == relation.get('type') and edge.get('cue') == cue
                   for edge in source['graph'].get('relations', [])):
            return False
    return True


def acceptance_checks(graph_metrics, baseline_direct, graph_direct, *, min_recall, max_regression,
                      min_pass_rate, path_count, valid_path_count, no_answer_ok, data_errors, errors):
    return {
        'golden_pass_rate': graph_direct['pass_rate'] >= min_pass_rate,
        'graph_recall_at_5': graph_metrics['pass_rate'] >= min_recall,
        'direct_regression': baseline_direct['direct_pass_rate'] - graph_direct['direct_pass_rate'] <= max_regression,
        'path_evidence': path_count > 0 and valid_path_count == path_count,
        'no_answer': no_answer_ok,
        'expected_sources_exist': not data_errors,
        'no_graph_errors': not errors,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--json', type=Path, default=DEFAULT)
    parser.add_argument('--retrieval-json', type=Path, default=ROOT / 'evals/rag_retrieval_golden.json')
    parser.add_argument('--min-graph-recall', type=float, default=0.8)
    parser.add_argument('--max-direct-regression', type=float, default=0.02)
    parser.add_argument('--min-pass-rate', type=float, default=0.8)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args(argv)
    cases = json.loads(args.json.read_text(encoding='utf-8'))
    direct_cases = json.loads(args.retrieval_json.read_text(encoding='utf-8'))
    if not cases or not direct_cases or not any(case.get('kind') == 'multi_hop' for case in cases):
        parser.error('Both evaluation sets must be nonempty and include multi-hop questions')
    sys.path.insert(0, str(BACKEND))
    from app import app, init_db  # noqa: E402
    from rag.governance import document_is_expired  # noqa: E402
    from rag.models import KnowledgeChunk  # noqa: E402
    from rag.service import get_kb  # noqa: E402

    init_db()
    rows, data_errors, errors = [], [], []
    path_count = valid_paths = relation_count = 0
    path_depth_counts = {}
    with app.app_context():
        kb = get_kb()
        if kb.settings.query_rewrite == 'hyde':
            parser.error('HyDE calls an LLM; use RAG_QUERY_REWRITE=expand or off for offline evaluation')
        sources = {
            chunk.id: {
                'document_id': chunk.document_id, 'category': chunk.document.category,
                'title': chunk.document.title, 'text': chunk.text, 'graph': (chunk.extra or {}).get('graph') or {},
                'eligible': (chunk.document.status == 'ready' and chunk.document.is_active
                             and not document_is_expired(chunk.document)
                             and chunk.embedding_model == kb.embedder.signature),
            } for chunk in KnowledgeChunk.query.all()
        }
        baseline_rows = evaluate_cases(kb, direct_cases, graph=False)
        graph_rows = evaluate_cases(kb, direct_cases, graph=True)
        for case in cases:
            expected = case.get('expect', {})
            options = {'top_k': 5, 'categories': case.get('categories'), 'document_ids': case.get('document_ids')}
            if not case.get('expect_irrelevant') and not any(
                source['eligible'] and matches({'text': source['text'], 'document': source}, expected)
                and (not options['categories'] or source['category'] in options['categories'])
                and (not options['document_ids'] or source['document_id'] in options['document_ids'])
                for source in sources.values()
            ):
                data_errors.append({'query': case['query'], 'expect': expected,
                                    'reason': 'No eligible source chunk matches the expected title/text/category'})
            modes = {}
            for enabled in (False, True):
                started = time.perf_counter()
                result = kb.retrieve(case['query'], graph=enabled, **options)
                rank = next((rank for rank, hit in enumerate(result['hits'][:5], 1) if matches(hit, expected)), None)
                passed = (result['retrieval']['relevant_count'] == 0 if case.get('expect_irrelevant')
                          else rank is not None and rank <= case.get('check_top', 5))
                if enabled and case.get('kind') == 'multi_hop':
                    passed = passed and any(matches(hit, expected) and hit.get('graph_paths')
                                            for hit in result['hits'][:5])
                modes['graph' if enabled else 'baseline'] = {
                    'query': case['query'], 'expect_irrelevant': bool(case.get('expect_irrelevant')),
                    'passed': passed, 'rank_at_5': None if case.get('expect_irrelevant') else rank,
                    'elapsed_ms': round((time.perf_counter() - started) * 1000, 3), 'result': result,
                }
            rows.append({'kind': case.get('kind'), 'expect': expected, **modes})

        evaluated_cases = [*zip(graph_rows, direct_cases), *[(row['graph'], case) for row, case in zip(rows, cases)]]
        for row, case in evaluated_cases:
            if row['result']['retrieval'].get('graph', {}).get('error'):
                errors.append(row['query'])
            for hit in row['result']['hits']:
                for path in hit.get('graph_paths') or []:
                    path_count += 1
                    depth = str(path.get('depth'))
                    path_depth_counts[depth] = path_depth_counts.get(depth, 0) + 1
                    relation_count += len(path.get('relations') or [])
                    valid_paths += int(path_is_valid(hit, path, sources, categories=case.get('categories'),
                                                     document_ids=case.get('document_ids')))
        stats = kb.stats()

    baseline_direct, graph_direct = summarize(baseline_rows), summarize(graph_rows)
    for metrics, evaluated in [(baseline_direct, baseline_rows), (graph_direct, graph_rows)]:
        positive = [row for row in evaluated if not row['expect_irrelevant']]
        metrics['direct_pass_rate'] = sum(row['passed'] for row in positive) / len(positive) if positive else 0.0
    baseline_multi = summarize([row['baseline'] for row in rows if row['kind'] == 'multi_hop'])
    graph_multi = summarize([row['graph'] for row in rows if row['kind'] == 'multi_hop'])
    no_answers = [row for row in [*baseline_rows, *graph_rows,
                                 *[row[mode] for row in rows for mode in ('baseline', 'graph')]]
                  if row['expect_irrelevant']]
    checks = acceptance_checks(
        graph_multi, baseline_direct, graph_direct, min_recall=args.min_graph_recall,
        max_regression=args.max_direct_regression, min_pass_rate=args.min_pass_rate,
        path_count=path_count, valid_path_count=valid_paths,
        no_answer_ok=bool(no_answers) and all(row['passed'] for row in no_answers),
        data_errors=data_errors, errors=errors)
    for row in rows:
        print(f"{'PASS' if row['graph']['passed'] else 'FAIL'} graph=1 baseline={int(row['baseline']['passed'])}  {row['graph']['query'][:48]}")
    print(f"Graph Recall@5 (with path): {graph_multi['pass_rate']:.1%}; MRR@5: {graph_multi['mrr_at_5']:.3f}")
    print(f"Multi-hop baseline Recall@5: {baseline_multi['recall_at_5']:.1%}; MRR@5: {baseline_multi['mrr_at_5']:.3f}")
    print(f"Golden pass rate: baseline={baseline_direct['pass_rate']:.1%}, graph={graph_direct['pass_rate']:.1%}")
    print(f"Direct pass rate: baseline={baseline_direct['direct_pass_rate']:.1%}, graph={graph_direct['direct_pass_rate']:.1%}")
    print(f'Graph source evidence: {valid_paths}/{path_count} paths, {relation_count} edge instances')
    for error in data_errors:
        print('DATA ERROR:', error['query'], error['expect'])
    print('Acceptance:', json.dumps(checks, ensure_ascii=False))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps({
            'passed': all(checks.values()), 'checks': checks, 'knowledge_base': stats,
            'thresholds': {'graph_recall_at_5': args.min_graph_recall,
                           'direct_regression': args.max_direct_regression, 'golden_pass_rate': args.min_pass_rate},
            'baseline_direct': baseline_direct, 'graph_direct': graph_direct,
            'baseline_multi': baseline_multi, 'graph_multi': graph_multi,
            'path_evidence': {'paths': path_count, 'valid_paths': valid_paths, 'edge_instances': relation_count,
                              'rate': valid_paths / path_count if path_count else None,
                              'depth_counts': path_depth_counts},
            'data_errors': data_errors, 'graph_errors': errors,
            'direct_cases': {'baseline': baseline_rows, 'graph': graph_rows}, 'graph_cases': rows,
        }, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    sys.exit(main())
