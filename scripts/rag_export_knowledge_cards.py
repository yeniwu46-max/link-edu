"""Export backend/data/classroom_knowledge.json into Markdown files for RAG ingest."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / 'backend' / 'data' / 'classroom_knowledge.json'
OUT_DIR = ROOT / 'sources' / 'rag' / 'corpus' / 'classroom_knowledge'


def category(item):
    title = item.get('title', '')
    kind = item.get('type', '')
    if '评价' in title or 'rubric' in kind.lower():
        return 'rubric'
    if '大纲' in title or '课标' in kind or '官方' in kind:
        return 'curriculum_standard'
    if '场景' in kind or '误解' in title:
        return 'case'
    return 'theory'


def slug(value):
    value = re.sub(r'[^\w\u3400-\u9fff-]+', '-', value.strip())[:48]
    return value.strip('-') or 'card'


def main():
    cards = json.loads(JSON_PATH.read_text(encoding='utf-8'))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_rows = []
    for item in cards:
        cid = item['id']
        title = item['title']
        path = OUT_DIR / f'{slug(cid)}.md'
        lines = [
            f'# {title}',
            '',
            f'**类型**：{item.get("type", "")}',
            f'**出处**：{item.get("source", "")}',
        ]
        if item.get('url'):
            lines.append(f'**链接**：{item["url"]}')
        if item.get('location'):
            lines.append(f'**位置**：{item["location"]}')
        if item.get('accessed'):
            lines.append(f'**访问日期**：{item["accessed"]}')
        if item.get('training_permission'):
            lines.append(f'**使用说明**：{item["training_permission"]}')
        lines.extend(['', item.get('text', '').strip(), ''])
        path.write_text('\n'.join(lines), encoding='utf-8')
        manifest_rows.append({
            'path': str(path.relative_to(ROOT)).replace('\\', '/'),
            'title': title,
            'category': category(item),
            'source': item.get('source', ''),
            'tags': ['分数', '微格', 'P0'],
            'priority': 'P0',
        })
        print(path.relative_to(ROOT))
    manifest_path = ROOT / 'sources' / 'rag' / 'manifest.json'
    existing = []
    if manifest_path.exists():
        existing = [row for row in json.loads(manifest_path.read_text(encoding='utf-8'))
                    if not str(row.get('path', '')).startswith('sources/rag/corpus/classroom_knowledge/')]
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(existing + manifest_rows, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Updated {manifest_path.relative_to(ROOT)} (+{len(manifest_rows)} rows)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
