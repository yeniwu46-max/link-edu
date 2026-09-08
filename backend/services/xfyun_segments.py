"""PCM-only energy endpointing. Observable speech activity, not emotion inference."""
import math
import struct
from collections import deque

FRAME_BYTES = 1280  # 40 ms, PCM16 / 16 kHz / mono


class Segmenter:
    def __init__(self, command, event, threshold=0.012):
        self.command, self.event, self.threshold = command, event, threshold
        self.buffer = b''
        self.preroll = deque(maxlen=5)
        self.active = False
        self.voiced = self.silent = 0
        self.number = 0
        self.segment = None
        self.seconds = 0
        self.finished = False

    def feed(self, raw):
        if self.finished:
            return
        self.buffer += raw
        while len(self.buffer) >= FRAME_BYTES:
            frame, self.buffer = self.buffer[:FRAME_BYTES], self.buffer[FRAME_BYTES:]
            self._frame(frame)

    def _frame(self, frame):
        values = struct.unpack('<' + 'h' * (len(frame)//2), frame)
        rms = math.sqrt(sum(x*x for x in values)/len(values))/32768
        loud = rms >= self.threshold
        self.voiced = self.voiced + len(frame)/32000 if loud else 0
        self.silent = 0 if loud else self.silent + len(frame)/32000
        if self.segment is None:
            self.preroll.append(frame)
        if not self.active and self.voiced >= 0.075:
            self.active = True
            self.event({'type': 'speech_started'})
        if self.active:
            if self.segment is None:
                self.number += 1
                self.segment, self.seconds = self.number, 0
                self.command(('start', self.segment))
                for previous in self.preroll:
                    self._audio(previous)
                self.preroll.clear()
            else:
                self._audio(frame)
            if self.silent >= 0.6:
                self._end()
                self.active = False
                self.event({'type': 'speech_stopped'})
            elif self.seconds >= 54.999:
                # Roll the provider segment, not the classroom or teacher VAD state.
                self._end()

    def _audio(self, frame):
        self.command(('audio', self.segment, frame))
        self.seconds += len(frame)/32000

    def _end(self):
        if self.segment is not None:
            self.command(('end', self.segment, self.seconds))
            self.segment = None

    def finish(self):
        if self.finished:
            return
        if self.buffer:
            self._frame(self.buffer)
            self.buffer = b''
        self._end()
        if self.active:
            self.active = False
            self.event({'type': 'speech_stopped'})
        self.finished = True
        self.command(('finish', self.number))
