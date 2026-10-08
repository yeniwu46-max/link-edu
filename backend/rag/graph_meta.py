"""Versioned, source-grounded graph metadata stored alongside each knowledge chunk."""
import json
import hashlib
from functools import lru_cache
from pathlib import Path

GRAPH_SCHEMA_VERSION = 1
_VOCABULARY_PATH = Path(__file__).with_name('graph_vocabulary.json')


@lru_cache(maxsize=4)
def _load_vocabulary(_mtime_ns):
    try:
        return json.loads(_VOCABULARY_PATH.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {'schema_version': GRAPH_SCHEMA_VERSION, 'entities': [], 'relation_rules': []}


def _vocabulary():
    try:
        stamp = _VOCABULARY_PATH.stat().st_mtime_ns
    except OSError:
        stamp = 0
    return _load_vocabulary(stamp)


def _contains(text, alias):
    return bool(alias) and str(alias).casefold() in text.casefold()


def build_graph_extra(document_title, heading_path, tags=(), text='', document_id=None):
    """Build stable entity IDs and materialize reviewed vocabulary rules with source cues."""
    vocabulary = _vocabulary()
    path = list(heading_path or [])
    body = str(text or '')
    search_text = ' '.join([body, *path, *(str(tag) for tag in (tags or []))])
    title = str(document_title)
    doc_key = str(document_id) if document_id is not None else hashlib.sha256(title.encode('utf-8')).hexdigest()[:16]
    doc_node = f'doc:{doc_key}'
    entities = [{'id': doc_node, 'label': title[:120], 'kind': 'document', 'aliases': []}]
    relations = []
    previous = doc_node
    for index, label in enumerate(path):
        node_id = f'sec:{index}:{str(label)[:80]}'
        entities.append({'id': node_id, 'label': str(label)[:120], 'kind': 'section', 'aliases': []})
        relations.append({'from': previous, 'to': node_id, 'type': 'contains', 'cue': str(label)[:120]})
        previous = node_id
    for tag in (tags or [])[:20]:
        label = str(tag)[:32]
        node_id = f'tag:{label}'
        entities.append({'id': node_id, 'label': label, 'kind': 'tag', 'aliases': []})
        relations.append({'from': doc_node, 'to': node_id, 'type': 'tagged', 'cue': label})

    entries = vocabulary.get('entities', [])
    found = {}
    for entry in entries:
        aliases = [entry.get('label', ''), *entry.get('aliases', [])]
        matched = [str(alias) for alias in aliases if _contains(search_text, alias)]
        if not matched or not entry.get('id') or not entry.get('label'):
            continue
        found[entry['id']] = {
            'id': str(entry['id'])[:120], 'label': str(entry['label'])[:120],
            'kind': str(entry.get('kind') or 'concept')[:40], 'aliases': matched[:20],
        }

    for rule in vocabulary.get('relation_rules', []):
        source, target = rule.get('from'), rule.get('to')
        if source not in found or target not in found:
            continue
        cue = next((str(cue) for cue in rule.get('cues', []) if _contains(body, cue)), None)
        if cue:
            relations.append({'from': source, 'to': target, 'type': str(rule.get('type') or 'related')[:40],
                              'cue': cue})

    entities.extend(found[key] for key in sorted(found))
    # Legacy consumers used kind/section nodes only. Keep the helper API stable.
    return {'graph': {'schema_version': GRAPH_SCHEMA_VERSION, 'entities': entities,
                      'relations': relations}}


def related_section_keys(extra):
    graph = (extra or {}).get('graph') or {}
    return [entity['id'] for entity in graph.get('entities', []) if entity.get('kind') == 'section']
