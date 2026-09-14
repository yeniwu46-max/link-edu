"""Bounded PCM sender + per-segment receivers; classroom stays alive across segments."""
import base64
import json
import queue
import threading
import time
import uuid
from flask import current_app
import websocket
from services.classroom_providers import ProviderError, key
from services.xfyun_speech import book, charge, rate
from services.xfyun_segments import Segmenter
from services import xfyun_wire as wire

TAIL_WAIT_SECONDS = 15


def response_expired(started, ended, now):
    return now - started > 75 or (ended is not None and now - ended > TAIL_WAIT_SECONDS)


def next_deadline(previous, now, duration):
    # Fixed cadence avoids accumulating Windows timer overshoot / TLS send cost.
    # After a slow connect, catch up at most 200ms rather than bursting seconds of PCM.
    return max(previous, now - 0.2) + duration


class ASR:
    def __init__(self, session_id):
        for name in ('XFYUN_APP_ID', 'XFYUN_API_KEY', 'XFYUN_API_SECRET'):
            key(name)
        rate('asr')  # Fail before opening a socket if accounting is not configured.
        self.app, self.sid = current_app._get_current_object(), session_id
        self.prefix = uuid.uuid4().hex
        self.closed = threading.Event()
        self.commands, self.events = queue.Queue(maxsize=250), queue.Queue(maxsize=1000)
        self.lock = threading.RLock()
        self.sockets, self.completed = {}, {}
        self.next_final, self.total_segments = 1, None
        self.failed = self.finished = False
        self.finish_sent_at = None
        self.input_bytes = 0
        self.stats = {'sent_frames':0, 'sent_bytes':0, 'queue_peak':0, 'max_send_seconds':0}
        self.segmenter = Segmenter(self.enqueue, self.emit)
        self._thread(self._send)

    def _thread(self, fn, *args):
        def run():
            with self.app.app_context():
                try:
                    fn(*args)
                except Exception as exc:
                    self.fail(exc)
        threading.Thread(target=run, daemon=True).start()

    def emit(self, event):
        try:
            self.events.put_nowait(event)
        except queue.Full:
            self.fail(ProviderError('语音事件积压，请重新连接'))

    def fail(self, exc):
        with self.lock:
            if self.failed or self.closed.is_set():
                return
            self.failed = True
            # Diagnostic locations only: never log signed URLs, keys, audio or SQL values.
            import traceback
            frames = traceback.extract_tb(exc.__traceback__)
            self.app.logger.warning('ASR failure %s at %s', type(exc).__name__,
                ' > '.join(f'{f.name}:{f.lineno}' for f in frames[-4:]))
            safe = exc if isinstance(exc, ProviderError) else ProviderError('讯飞识别连接中断，请检查网络后重连；未确认文本不会入档')
            try:
                self.events.put_nowait(safe)
            except queue.Full:
                pass
            self.close()

    def enqueue(self, command):
        if self.closed.is_set():
            raise ProviderError('讯飞识别连接已关闭')
        try:
            self.commands.put_nowait(command)
            self.stats['queue_peak'] = max(self.stats['queue_peak'], self.commands.qsize())
        except queue.Full:
            self.fail(ProviderError('识别发送积压超过10秒，已停止以避免字幕错位'))
            raise ProviderError('识别发送积压，请重新连接') from None

    def audio(self, encoded):
        try:
            raw = base64.b64decode(encoded, validate=True)
        except Exception:
            raise ProviderError('音频Base64无效') from None
        if not 0 < len(raw) <= 32000 or len(raw) % 2:
            raise ProviderError('音频必须是16kHz单声道PCM16，每块最多一秒')
        self.input_bytes += len(raw)
        if self.input_bytes > 660 * 32000:
            raise ProviderError('识别会话超过11分钟')
        self.segmenter.feed(raw)

    def receive(self):
        try:
            event = self.events.get(timeout=0.5)
        except queue.Empty:
            if self.closed.is_set():
                raise ProviderError('讯飞识别连接已关闭') from None
            raise websocket.WebSocketTimeoutException() from None
        if isinstance(event, Exception):
            raise event
        return event

    def finish(self):
        self.segmenter.finish()

    def drain_expired(self, started_at, now):
        # PCM may still be queued when the user clicks finish. Start the response
        # allowance only after all tail/end frames were sent; still bound total wait.
        return now - started_at > 30 or (self.finish_sent_at is not None and now - self.finish_sent_at > TAIL_WAIT_SECONDS)

    def probe(self):
        # Explicit silent transport probe, not a claim of recognizing speech.
        self.enqueue(('start', 1))
        self.enqueue(('audio', 1, b'\0' * 1280))
        self.enqueue(('end', 1, 0.04))
        self.enqueue(('finish', 1))

    def settle(self):
        pass  # Each segment settles independently; unknown failures retain reserve.

    def close(self):
        self.closed.set()
        with self.lock:
            sockets = list(self.sockets.values())
        for segment in sockets:
            try:
                segment['socket'].close()
            except Exception:
                pass

    def _send(self):
        next_send = 0
        while not self.closed.is_set():
            try:
                command = self.commands.get(timeout=0.1)
            except queue.Empty:
                continue
            kind, number = command[:2]
            if kind == 'start':
                with self.lock:
                    if len(self.sockets) >= 3:
                        raise ProviderError('识别收尾积压，已停止；请检查网络')
                usage, amount = book('asr', self.sid)
                segment = {'socket': wire.connect(wire.ASR_URL), 'seq': 0, 'seconds': 0,
                           'usage': usage, 'amount': amount, 'ended': None}
                # websocket-client shares this timeout between send and receive.
                # 0.5 s spuriously aborted PCM writes on small-bandwidth servers.
                segment['socket'].settimeout(5)
                with self.lock:
                    if self.closed.is_set():
                        segment['socket'].close()
                        return
                    self.sockets[number] = segment
                self._thread(self._read, number, segment)
            elif kind in ('audio', 'end'):
                with self.lock:
                    segment = self.sockets.get(number)
                if not segment:
                    raise ProviderError('识别段提前关闭，未自动补造文本')
                raw = command[2] if kind == 'audio' else b''
                if self.closed.wait(max(0, next_send - time.monotonic())):
                    return
                status = 2 if kind == 'end' else (0 if segment['seq'] == 0 else 1)
                segment['seq'] += 1
                segment['seconds'] += len(raw)/32000
                if kind == 'end':
                    segment['ended'] = time.monotonic()
                send_started = time.monotonic()
                segment['socket'].send(json.dumps(wire.asr_frame(raw, status, segment['seq'])))
                self.stats['sent_frames'] += 1
                self.stats['sent_bytes'] += len(raw)
                self.stats['max_send_seconds'] = max(self.stats['max_send_seconds'], time.monotonic()-send_started)
                next_send = next_deadline(next_send, time.monotonic(), len(raw)/32000)
            elif kind == 'finish':
                with self.lock:
                    self.finish_sent_at = time.monotonic()
                    self.total_segments = number
                    self._flush()
                return

    def _read(self, number, segment):
        transcript, text = wire.Transcript(), ''
        started = time.monotonic()
        try:
            while not self.closed.is_set():
                if response_expired(started, segment['ended'], time.monotonic()):
                    raise ProviderError('讯飞识别结果等待超时（收尾15秒/单段75秒），未确认文本不会入档')
                try:
                    item = wire.receive(segment['socket'], '识别')
                except websocket.WebSocketTimeoutException:
                    continue
                result = (item.get('payload') or {}).get('result') or {}
                if result.get('text'):
                    data = json.loads(base64.b64decode(result['text'], validate=True))
                    if data.get('ret', 0):
                        code = data['ret'] if type(data['ret']) is int else 'unknown'
                        raise ProviderError(f'讯飞识别业务返回错误（{code}），未确认文本不会入档')
                    text = transcript.update(data)
                    with self.lock:
                        if number == self.next_final:
                            self.emit({'type': 'partial', 'text': text})
                if item.get('header', {}).get('status') == 2:
                    charge(segment['usage'], segment['amount'], 'asr', audio_seconds=segment['seconds'])
                    with self.lock:
                        self.completed[number] = {'type': 'final', 'item_id': f'{self.prefix}:{number}',
                            'transcript': text, 'speech_seconds': segment['seconds'], 'provider': 'xfyun'}
                        self._flush()
                    return
        finally:
            segment['socket'].close()
            with self.lock:
                self.sockets.pop(number, None)

    def _flush(self):
        while self.next_final in self.completed:
            self.emit(self.completed.pop(self.next_final))
            self.next_final += 1
        if self.total_segments is not None and self.next_final > self.total_segments and not self.finished:
            self.finished = True
            self.emit({'type': 'finished'})
