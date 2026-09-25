"""Structure-aware chunking: sections follow the heading tree, paragraphs are packed whole,
long paragraphs split on sentence boundaries, tables split by rows with the header repeated."""
import re
from dataclasses import dataclass, field

from rag.parsing import Block

_SENTENCE = re.compile(r'.+?(?:[。！？!?；;…]+[”’」』）)》]*|\.(?=\s)|\n|$)', re.S)
_CLAUSE = re.compile(r'.+?(?:[，,、：:]|$)', re.S)


@dataclass
class Chunk:
    text: str
    heading_path: list
    kind: str = 'text'
    page_start: int | None = None
    page_end: int | None = None
    overlap: str = field(default='', repr=False)

    @property
    def section(self):
        return ' > '.join(self.heading_path)


def split_sentences(text):
    return [s.strip() for s in _SENTENCE.findall(text) if s.strip()]


def _hard_split(text, limit):
    pieces = []
    for clause in (c for c in _CLAUSE.findall(text) if c):
        while len(clause) > limit:
            pieces.append(clause[:limit])
            clause = clause[limit:]
        if pieces and len(pieces[-1]) + len(clause) <= limit:
            pieces[-1] += clause
        elif clause:
            pieces.append(clause)
    return pieces


def _pack(units, limit, sep=''):
    packed = []
    for unit in units:
        if packed and len(packed[-1]) + len(sep) + len(unit) <= limit:
            packed[-1] += sep + unit
        else:
            packed.append(unit)
    return packed


class Chunker:
    def __init__(self, target_chars=500, max_chars=900, overlap_chars=80, min_chars=60):
        self.target = target_chars
        self.max = max(max_chars, target_chars)
        self.overlap_chars = overlap_chars
        self.min = min_chars

    def split(self, blocks):
        self._chunks, self._stack = [], []
        self._buf, self._buf_path, self._pages = [], None, []
        self._overlap = self._buf_overlap = ''
        for block in blocks:
            if block.kind == 'heading':
                self._open_heading(block)
            elif block.kind == 'table':
                self._mark_body()
                self._flush()
                self._emit_table(block)
            else:
                self._mark_body()
                for unit in self._units(block.text):
                    self._add(unit, block)
        self._close_empty_headings(0)
        self._flush()
        return self._merge_small(self._chunks)

    def _path(self):
        return [item['title'] for item in self._stack]

    def _mark_body(self):
        for item in self._stack:
            item['has_body'] = True

    def _open_heading(self, block):
        self._close_empty_headings(block.level)
        while self._stack and self._stack[-1]['level'] >= block.level:
            self._stack.pop()
        self._stack.append({'level': block.level, 'title': block.text, 'has_body': False, 'page': block.page})

    def _close_empty_headings(self, level):
        # A "heading" followed directly by a sibling was a short list item (e.g. rubric lines like "1. 目标明确").
        while self._stack and not self._stack[-1]['has_body'] and self._stack[-1]['level'] >= level:
            item = self._stack.pop()
            self._mark_body()
            self._add(item['title'], Block(item['title'], page=item['page'], page_end=item['page']))

    def _units(self, text):
        if len(text) <= self.max:
            return [text]
        sentences = []
        for sentence in split_sentences(text):
            sentences.extend(_hard_split(sentence, self.target) if len(sentence) > self.target else [sentence])
        return _pack(sentences, self.target)

    def _add(self, unit, block):
        path = self._path()
        if self._buf and (path != self._buf_path or self._length() + len(unit) > self.target):
            self._flush(keep_overlap=path == self._buf_path)
        if not self._buf:
            self._buf_path = path
            if self._overlap and len(self._overlap) + len(unit) <= self.max:
                self._buf.append(self._overlap)
                self._buf_overlap = self._overlap
            else:
                self._buf_overlap = ''
            self._overlap = ''
        self._buf.append(unit)
        self._pages.extend(p for p in (block.page, block.page_end) if p is not None)

    def _length(self):
        return sum(len(u) for u in self._buf) + max(0, len(self._buf) - 1)

    def _flush(self, keep_overlap=False):
        self._overlap = ''
        if not self._buf:
            return
        text = '\n'.join(self._buf)
        self._chunks.append(Chunk(text, list(self._buf_path or []), 'text',
                                  min(self._pages) if self._pages else None,
                                  max(self._pages) if self._pages else None,
                                  self._buf_overlap))
        if keep_overlap and self.overlap_chars:
            self._overlap = self._tail(self._buf[-1])
        self._buf, self._pages = [], []

    def _tail(self, text):
        tail = ''
        for sentence in reversed(split_sentences(text)):
            if len(tail) + len(sentence) > self.overlap_chars:
                break
            tail = sentence + tail
        return tail if tail != text else ''

    def _emit_table(self, block):
        rows = block.rows or block.text.split('\n')
        header, body = rows[0], rows[1:] or []
        path, page = self._path(), block.page
        if not body:
            groups = [[header]]
        else:
            groups, current = [], []
            for row in body:
                size = len(header) + sum(len(r) + 1 for r in current) + len(row) + 1
                if current and size > self.max:
                    groups.append(current)
                    current = []
                current.append(row)
            groups.append(current)
            groups = [[header] + group for group in groups]
        for group in groups:
            text = '\n'.join(group)
            for piece in ([text] if len(text) <= self.max else _hard_split(text, self.max)):
                self._chunks.append(Chunk(piece, list(path), 'table', page, block.page_end or page))

    def _merge_small(self, chunks):
        merged = []
        for chunk in chunks:
            prev = merged[-1] if merged else None
            if (prev and prev.kind == chunk.kind == 'text' and prev.heading_path == chunk.heading_path
                    and (len(prev.text) < self.min or len(chunk.text) < self.min)):
                body = chunk.text[len(chunk.overlap) + 1:] if chunk.overlap else chunk.text
                if len(prev.text) + 1 + len(body) <= self.max:
                    prev.text = f'{prev.text}\n{body}'
                    pages = [p for p in (prev.page_start, prev.page_end, chunk.page_start, chunk.page_end)
                             if p is not None]
                    prev.page_start, prev.page_end = (min(pages), max(pages)) if pages else (None, None)
                    continue
            merged.append(chunk)
        return merged


def chunk_blocks(blocks, **options):
    return Chunker(**options).split(blocks)
