"""Incremental student JSON and cancellable SSE transport (no draft persistence)."""
import json
import threading


class StreamCancelled(Exception):
    pass


class StreamControl:
    def __init__(self):
        self.event = threading.Event()
        self.response = None
        self.lock = threading.Lock()

    def bind(self, response):
        with self.lock:
            self.response = response
            if self.event.is_set():
                response.close()
                raise StreamCancelled()

    def check(self):
        if self.event.is_set():
            raise StreamCancelled()

    def cancel(self):
        self.event.set()
        with self.lock:
            if self.response:
                try:
                    self.response.close()
                except Exception:
                    pass


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate field')
        result[key] = value
    return result


def partial_string(source):
    """Decode only complete JSON string escapes, including surrogate pairs."""
    if not source.startswith('"'):
        return ''
    end = 1
    while end < len(source):
        char = source[end]
        if char == '"':
            return json.loads(source[:end + 1])
        if char == '\\':
            size = 6 if source[end:end + 2] == '\\u' else 2
            if end + size > len(source):
                break
            if size == 6:
                code = int(source[end + 2:end + 6], 16)
                if 0xD800 <= code <= 0xDBFF:
                    if end + 12 > len(source):
                        break
                    if source[end + 6:end + 8] != '\\u' or not 0xDC00 <= int(source[end + 8:end + 12], 16) <= 0xDFFF:
                        raise ValueError('invalid surrogate')
                    size = 12
            end += size
        else:
            end += 1
    return json.loads(source[:end] + '"')


class StudentDraft:
    """Only the ordered action/student_id/text prefix is eligible for preview."""
    def __init__(self):
        self.buffer = ''
        self.decoder = json.JSONDecoder()

    def feed(self, delta):
        self.buffer += delta
        if len(self.buffer) > 32000:
            raise ValueError('student response too large')
        source = self.buffer.lstrip()
        if not source.startswith('{'):
            return None
        source = source[1:].lstrip()
        values = {}
        for expected in ('action', 'student_id', 'text'):
            try:
                key, offset = self.decoder.raw_decode(source)
            except ValueError:
                return None
            if key != expected:
                return None  # Unordered output waits for full validation.
            source = source[offset:].lstrip()
            if not source.startswith(':'):
                return None
            source = source[1:].lstrip()
            if expected == 'text':
                return {**values, 'text': partial_string(source)[:100]}
            try:
                value, offset = self.decoder.raw_decode(source)
            except ValueError:
                return None
            values[expected] = value
            source = source[offset:].lstrip()
            if not source.startswith(','):
                return None
            source = source[1:].lstrip()
        return None


def validate_student(output):
    if not isinstance(output, dict) or output.get('action') not in ('wait', 'raise', 'answer', 'followup'):
        raise ValueError('invalid action')
    if output['action'] == 'wait':
        return output
    if output.get('student_id') not in ('ming', 'yu', 'lin'):
        raise ValueError('invalid student')
    if not all(isinstance(output.get(k), str) for k in ('text', 'understanding', 'open_question')):
        raise ValueError('invalid student text')
    if not output['text'].strip() or type(output.get('resolved')) is not bool:
        raise ValueError('invalid student reply')
    return output


def sse_events(lines):
    parts = []
    for line in lines:
        if not line:
            if parts:
                yield '\n'.join(parts)
                parts = []
        elif line.startswith('data:'):
            parts.append(line[5:].lstrip(' '))
    if parts:
        yield '\n'.join(parts)
