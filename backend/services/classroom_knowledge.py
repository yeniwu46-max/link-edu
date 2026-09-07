import json
from pathlib import Path
import jieba
from rank_bm25 import BM25Okapi

ROOT = Path(__file__).resolve().parents[1]


def documents():
    result = []
    for path in [ROOT / 'data/classroom_knowledge.json', ROOT / 'private/knowledge.json']:
        if path.exists():
            result.extend(json.loads(path.read_text(encoding='utf-8')))
    return result


def search(query, limit=5):
    docs = [d for d in documents() if d.get('text')]
    if not docs:
        return []
    tokens = [list(jieba.cut(d['title'] + ' ' + d['text'])) for d in docs]
    scores = BM25Okapi(tokens).get_scores(list(jieba.cut(query)))
    ranked = sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)
    return [dict(d, relevance=round(float(score), 3)) for score, d in ranked[:min(5, limit)] if score > 0]
