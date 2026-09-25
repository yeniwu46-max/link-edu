"""Lightweight graph metadata in kb_chunks.extra (GraphRAG entry point)."""


def build_graph_extra(document_title, heading_path, tags=()):
    path = list(heading_path or [])
    entities = [{'id': 'doc', 'label': document_title[:120], 'kind': 'document'}]
    relations = []
    prev = 'doc'
    for index, label in enumerate(path):
        node_id = f'sec:{index}'
        entities.append({'id': node_id, 'label': label[:120], 'kind': 'section'})
        relations.append({'from': prev, 'to': node_id, 'type': 'contains'})
        prev = node_id
    for tag in (tags or [])[:5]:
        tid = f'tag:{tag}'
        entities.append({'id': tid, 'label': str(tag)[:32], 'kind': 'tag'})
        relations.append({'from': 'doc', 'to': tid, 'type': 'tagged'})
    return {'graph': {'entities': entities, 'relations': relations}}


def related_section_keys(extra):
    """Return section node ids sharing the same document section prefix (for future graph walk)."""
    graph = (extra or {}).get('graph') or {}
    return [e['id'] for e in graph.get('entities', []) if e.get('kind') == 'section']
